#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - bot.py
# 4/4/22 22:06
#

__author__ = "Benny <benny.think@gmail.com>"

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Dict, Tuple

from pyrogram import Client, enums, filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import SearchEngine
from .access_control import require_access, require_owner, access_controller
from .config_loader import BOT_MODE, DATABASE_ENABLED, DATABASE_PATH, TOKEN, get_config
from .db_manager import get_db_manager
from .init_client import get_client
from .privacy import privacy_manager
from .sync_http_client import SyncHTTPClient
from .time_utils import parse_time_window, format_time_window
from .utils import setup_logger

tgdb = SearchEngine()

setup_logger()
app = get_client(TOKEN)

# Get configuration
config = get_config()

# Initialize sync HTTP client (uses userbot service)
userbot_url = config.get("services.userbot.base_url", "http://127.0.0.1:8082")
sync_client = SyncHTTPClient(base_url=userbot_url)

# Custom filter to exclude all command messages (starting with /)
def not_command_filter(_, __, message: types.Message):
    """Filter out messages that start with / (commands)."""
    if not message.text:
        return True
    return not message.text.startswith("/")

not_command = filters.create(not_command_filter)

# Initialize database manager for query logging
db_manager = get_db_manager(DATABASE_PATH) if DATABASE_ENABLED else None
chat_types = [i for i in dir(enums.ChatType) if not i.startswith("_")]
parser = argparse.ArgumentParser()
parser.add_argument("keyword", help="the keyword to be searched")
parser.add_argument("-t", "--type", help="the type of message", default=None)
parser.add_argument("-u", "--user", help="the user who sent the message", default=None)
parser.add_argument("-m", "--mode", help="match mode, e: exact match, other value is fuzzy search", default=None)

# Pagination limits
MAX_PAGE = 100  # Maximum allowed page number to prevent abuse

# Auto-delete mechanism: Track deletion tasks for messages with inline keyboards
# Key: (chat_id, message_id), Value: asyncio.Task
deletion_tasks: Dict[Tuple[int, int], asyncio.Task] = {}


async def schedule_message_deletion(client: Client, chat_id: int, message_id: int, delay: int = 120):
    """
    Schedule a message for auto-deletion after a delay if no interaction occurs.

    Args:
        client: Pyrogram Client instance
        chat_id: Chat ID where the message was sent
        message_id: Message ID to delete
        delay: Delay in seconds before deletion (default: 120)
    """
    key = (chat_id, message_id)

    async def delete_message():
        try:
            await asyncio.sleep(delay)
            await client.delete_messages(chat_id, message_id)
            logging.info(f"Auto-deleted message {message_id} in chat {chat_id} after {delay}s of no interaction")
        except asyncio.CancelledError:
            logging.debug(f"Deletion cancelled for message {message_id} in chat {chat_id} (user interacted)")
        except Exception as e:
            logging.error(f"Failed to auto-delete message {message_id}: {e}")
        finally:
            # Clean up task from dict
            if key in deletion_tasks:
                del deletion_tasks[key]

    # Cancel any existing task for this message
    if key in deletion_tasks:
        deletion_tasks[key].cancel()

    # Schedule new deletion task
    task = asyncio.create_task(delete_message())
    deletion_tasks[key] = task


def cancel_message_deletion(chat_id: int, message_id: int):
    """
    Cancel a scheduled message deletion (called when user interacts).

    Args:
        chat_id: Chat ID where the message was sent
        message_id: Message ID to cancel deletion for
    """
    key = (chat_id, message_id)
    if key in deletion_tasks:
        deletion_tasks[key].cancel()
        del deletion_tasks[key]
        logging.debug(f"Cancelled auto-deletion for message {message_id} in chat {chat_id}")


async def auto_delete_in_groups(client: Client, message: types.Message, sent_msg: types.Message, has_markup: bool = False):
    """
    Schedule auto-deletion for bot messages in group/supergroup chats.

    Args:
        client: Pyrogram Client instance
        message: Original message that triggered the bot
        sent_msg: Bot's response message to be deleted
        has_markup: Whether the message has inline keyboard (for pagination)
    """
    # Only auto-delete in groups and supergroups
    if sent_msg.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await schedule_message_deletion(client, sent_msg.chat.id, sent_msg.id)
        logging.debug(f"Scheduled auto-deletion for message {sent_msg.id} in group {sent_msg.chat.id}")


@app.on_message(filters.command(["start"]))
async def search_handler(client: "Client", message: "types.Message"):
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    sent_msg = await message.reply_text("Hello, I'm search bot.", quote=True)
    await auto_delete_in_groups(client, message, sent_msg)


@app.on_message(filters.command(["help"]))
async def help_handler(client: "Client", message: "types.Message"):
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Get requester info for personalization
    user = message.from_user
    user_name = user.first_name if user else "User"

    help_text = f"""
**SearchGram Help** 👋 {user_name}

**🔍 Search Commands:**
- **In groups**: `/search <query>` - Search messages in this group
- **In private**: Send any text or use `/search <query>`
- **Type shortcuts**: `/private [username] keyword`

**🔍 Search Syntax:**
1. **Global search**: `keyword` or `/search keyword`
2. **Chat type search**: `-t=GROUP keyword`
   - Supported types: {', '.join(chat_types)}
3. **User search**: `-u=user_id|username keyword`
4. **Exact match**: `-m=e keyword` or `"keyword"`
5. **Combined**: `-t=GROUP -u=username keyword`

**🔐 Privacy Commands:**
- `/block_me` - Opt-out: Your messages won't appear in anyone's search
- `/unblock_me` - Opt-in: Allow your messages in search results
- `/privacy_status` - Check your current privacy status

**📊 Activity Stats (Group Only):**
- `/mystats` - Your activity in the last year
- `/mystats 30d` - Your activity in the last 30 days
- `/mystats 90d at` - Last 90 days with mention counts
- `/mystats 2025-01-01..2025-12-31` - Custom date range

{f'''**🛠️ Admin Commands (Owner Only):**
- `/ping` - Comprehensive health check (engine, messages, privacy, logs, config)
- `/dedup` - Remove duplicate messages from database
- `/clean_commands` - Remove all command messages (starting with /) from database
- `/delete` - Delete messages from specific chat
- `/logs [limit]` - View recent query logs
- `/logstats` - View query statistics
- `/settings [key] [value]` - View/update database settings
- `/cleanup_logs` - Clean up old query logs

**📥 Sync Commands (Owner Only):**
- `/sync <chat_id>` - Add a chat to sync queue
- `/sync_status` - Check all sync tasks progress
- `/sync_pause <chat_id>` - Pause an ongoing sync
- `/sync_resume <chat_id>` - Resume a paused sync
- `/sync_list` - List all sync tasks (same as /sync_status)
''' if access_controller.is_owner(user.id if user else 0) else ''}
**⚙️ Bot Mode:** {BOT_MODE}
{f"**Blocked Users:** {privacy_manager.get_blocked_count()}" if access_controller.is_owner(user.id if user else 0) else ""}

**📖 Privacy Notice:**
This bot indexes messages for search. Use `/block_me` anytime to remove yourself from search results. Your privacy matters! 🛡️
    """
    sent_msg = await message.reply_text(help_text, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
    await auto_delete_in_groups(client, message, sent_msg)


@app.on_message(filters.command(["ping"]))
@require_owner
async def ping_handler(client: "Client", message: "types.Message"):
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Get search engine stats
    ping_result = tgdb.ping()

    # Handle both dict (http_engine) and string (other engines) responses
    if isinstance(ping_result, dict):
        # HTTP engine returns dict with structured data
        status = ping_result.get("status", "unknown")
        engine = ping_result.get("engine", "unknown")
        total_docs = ping_result.get("total_documents", 0)

        text = f"🏓 **Pong!**\n\n"
        text += f"**Search Engine:** {engine}\n"
        text += f"**Status:** {status}\n"
        text += f"**📊 Total Messages:** {total_docs:,}\n"
    else:
        # Other engines return formatted string
        text = ping_result

    # Add privacy stats
    blocked_count = privacy_manager.get_blocked_count()
    text += f"\n🔐 **Privacy:** {blocked_count} user(s) opted out"

    # Add database query log stats if enabled
    if db_manager:
        try:
            stats = db_manager.get_statistics()
            text += f"\n\n**📝 Query Logs:**"
            text += f"\n  • Total Queries: {stats['total_queries']:,}"
            text += f"\n  • Last 24h: {stats['queries_24h']:,}"
            text += f"\n  • Avg Time: {stats['avg_processing_time_ms']:.0f}ms"
        except Exception as e:
            logging.error(f"Error getting database stats: {e}")

    # Add bot mode and permissions info
    text += f"\n\n**⚙️ Bot Configuration:**"
    text += f"\n  • Mode: {BOT_MODE}"
    text += f"\n  • Allowed Groups: {len(access_controller.allowed_groups)}"
    text += f"\n  • Allowed Users: {len(access_controller.allowed_users)}"
    text += f"\n  • Admins: {len(access_controller.admins)}"

    sent_msg = await client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)
    await auto_delete_in_groups(client, message, sent_msg)


@app.on_message(filters.command(["clean_commands"]))
@require_owner
def clean_commands_handler(client: "Client", message: "types.Message"):
    """Remove all indexed command messages (starting with /) from database (owner only)."""
    import time
    import threading

    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Send initial message
    status_msg = client.send_message(
        message.chat.id,
        "🧹 **Starting command cleanup...**\n\n"
        "Removing all messages starting with `/` from the database.\n\n"
        "_Please wait..._",
        parse_mode=enums.ParseMode.MARKDOWN
    )

    try:
        # Check if the engine supports clean_commands
        if not hasattr(tgdb, 'clean_commands'):
            status_msg.edit_text(
                "❌ **Command Cleanup Not Supported**\n\n"
                "Your current search engine doesn't support command cleanup.\n"
                "Please use `ENGINE=http` (Go search service) for this feature.",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        # Track operation start time
        start_time = time.time()
        cleanup_done = threading.Event()
        cleanup_result = {}
        cleanup_error = None

        # Run cleanup in background thread
        def run_cleanup():
            nonlocal cleanup_result, cleanup_error
            try:
                cleanup_result = tgdb.clean_commands()
            except Exception as e:
                cleanup_error = e
            finally:
                cleanup_done.set()

        # Start cleanup in background
        cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
        cleanup_thread.start()

        # Wait for completion
        cleanup_done.wait()

        # Check for errors
        if cleanup_error:
            raise cleanup_error

        # Format final response
        deleted_count = cleanup_result.get('deleted_count', 0)
        elapsed = int(time.time() - start_time)

        if deleted_count == 0:
            response_text = f"✅ **Command Cleanup Complete**\n\n" \
                          f"⏱️ Completed in {elapsed}s\n\n" \
                          f"No command messages found. Your database is clean! 🎉"
        else:
            response_text = f"✅ **Command Cleanup Complete**\n\n" \
                          f"⏱️ Completed in {elapsed}s\n" \
                          f"🗑️ Removed: {deleted_count:,} command messages\n\n" \
                          f"All messages starting with `/` have been removed! 🎉"

        status_msg.edit_text(response_text, parse_mode=enums.ParseMode.MARKDOWN)

    except Exception as e:
        error_text = f"❌ **Command Cleanup Failed**\n\n" \
                   f"Error: {str(e)}\n\n" \
                   f"💡 Tip: Check your server logs for more details.\n" \
                   f"Make sure your Go search service and Elasticsearch are running."
        status_msg.edit_text(error_text, parse_mode=enums.ParseMode.MARKDOWN)
        logging.exception("Command cleanup failed")


@app.on_message(filters.command(["dedup"]))
@require_owner
def dedup_handler(client: "Client", message: "types.Message"):
    """Remove duplicate messages from the search index (owner only)."""
    import time
    import threading

    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Send initial message
    status_msg = client.send_message(
        message.chat.id,
        "🔄 **Starting deduplication process...**\n\n"
        "⏱️ This can take up to 10 minutes for large databases.\n"
        "📊 Check your server logs for detailed progress.\n\n"
        "_Please wait, processing..._",
        parse_mode=enums.ParseMode.MARKDOWN
    )

    try:
        # Check if the engine supports dedup
        if not hasattr(tgdb, 'dedup'):
            status_msg.edit_text(
                "❌ **Deduplication Not Supported**\n\n"
                "Your current search engine doesn't support deduplication.\n"
                "Please use `ENGINE=http` (Go search service) for this feature.",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        # Track operation start time
        start_time = time.time()
        dedup_done = threading.Event()
        dedup_result = {}
        dedup_error = None

        # Run deduplication in background thread
        def run_dedup():
            nonlocal dedup_result, dedup_error
            try:
                dedup_result = tgdb.dedup()
            except Exception as e:
                dedup_error = e
            finally:
                dedup_done.set()

        # Start dedup in background
        dedup_thread = threading.Thread(target=run_dedup, daemon=True)
        dedup_thread.start()

        # Update status every 15 seconds while running
        update_interval = 15
        last_update = 0
        while not dedup_done.is_set():
            dedup_done.wait(timeout=update_interval)
            elapsed = int(time.time() - start_time)

            # Only update message if enough time has passed (avoid rate limits)
            if elapsed - last_update >= update_interval and not dedup_done.is_set():
                try:
                    status_msg.edit_text(
                        f"🔄 **Deduplication in progress...**\n\n"
                        f"⏱️ Elapsed time: {elapsed // 60}m {elapsed % 60}s\n"
                        f"📊 Check server logs for detailed progress.\n\n"
                        f"_Please wait, this may take up to 10 minutes..._",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                    last_update = elapsed
                except Exception:
                    pass  # Ignore edit errors (rate limits, etc.)

        # Check for errors
        if dedup_error:
            raise dedup_error

        # Format final response
        duplicates_found = dedup_result.get('duplicates_found', 0)
        duplicates_removed = dedup_result.get('duplicates_removed', 0)
        elapsed = int(time.time() - start_time)

        if duplicates_found == 0:
            response_text = f"✅ **Deduplication Complete**\n\n" \
                          f"⏱️ Completed in {elapsed // 60}m {elapsed % 60}s\n\n" \
                          f"No duplicates found. Your database is clean! 🎉"
        else:
            response_text = f"✅ **Deduplication Complete**\n\n" \
                          f"⏱️ Completed in {elapsed // 60}m {elapsed % 60}s\n" \
                          f"📊 Duplicates found: {duplicates_found:,}\n" \
                          f"🗑️ Duplicates removed: {duplicates_removed:,}\n\n" \
                          f"Your database has been optimized! 🎉"

        status_msg.edit_text(response_text, parse_mode=enums.ParseMode.MARKDOWN)

    except Exception as e:
        error_text = f"❌ **Deduplication Failed**\n\n" \
                   f"Error: {str(e)}\n\n" \
                   f"💡 Tip: Check your server logs for more details.\n" \
                   f"Make sure your Go search service and Elasticsearch are running."
        status_msg.edit_text(error_text, parse_mode=enums.ParseMode.MARKDOWN)
        logging.exception("Deduplication failed")


@app.on_message(filters.command(["delete"]))
@require_owner
async def clean_handler(client: "Client", message: "types.Message"):
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text = tgdb.ping()
    sent_msg = await client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)
    await auto_delete_in_groups(client, message, sent_msg)


@app.on_message(filters.command(["block_me", "optout", "privacy_block"]))
async def block_me_handler(client: "Client", message: "types.Message"):
    """Allow users to opt-out of search results."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    user = message.from_user
    if not user:
        sent_msg = await message.reply_text("❌ Could not identify your user ID.", quote=True)
        await auto_delete_in_groups(client, message, sent_msg)
        return

    user_id = user.id
    was_new = privacy_manager.block_user(user_id)

    if was_new:
        response = f"""
✅ **Privacy Protection Enabled**

Your messages have been removed from search results.

**What this means:**
- Your existing messages won't appear in search
- Future messages won't be searchable
- This applies to all chats where this bot is active

**To reverse this:** Use `/unblock_me` anytime

Your privacy is important! 🛡️
        """
    else:
        response = "✅ You were already blocked from search results. You're all set! 🛡️"

    sent_msg = await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
    await auto_delete_in_groups(client, message, sent_msg)


@app.on_message(filters.command(["unblock_me", "optin", "privacy_unblock"]))
async def unblock_me_handler(client: "Client", message: "types.Message"):
    """Allow users to opt back into search results."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    user = message.from_user
    if not user:
        sent_msg = await message.reply_text("❌ Could not identify your user ID.", quote=True)
        await auto_delete_in_groups(client, message, sent_msg)
        return

    user_id = user.id
    was_blocked = privacy_manager.unblock_user(user_id)

    if was_blocked:
        response = f"""
✅ **Privacy Protection Disabled**

Your messages will now appear in search results again.

**What this means:**
- Your messages are now searchable
- This applies to all indexed chats

**To block again:** Use `/block_me` anytime
        """
    else:
        response = "✅ You weren't blocked. Your messages are already searchable."

    sent_msg = await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
    await auto_delete_in_groups(client, message, sent_msg)


@app.on_message(filters.command(["privacy_status", "privacy", "mystatus"]))
async def privacy_status_handler(client: "Client", message: "types.Message"):
    """Check user's current privacy status."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    user = message.from_user
    if not user:
        sent_msg = await message.reply_text("❌ Could not identify your user ID.", quote=True)
        await auto_delete_in_groups(client, message, sent_msg)
        return

    user_id = user.id
    is_blocked = privacy_manager.is_blocked(user_id)

    status_emoji = "🔒" if is_blocked else "🔓"
    status_text = "**BLOCKED**" if is_blocked else "**SEARCHABLE**"

    response = f"""
{status_emoji} **Your Privacy Status**

**Status:** {status_text}
**User ID:** `{user_id}`

{f"✅ Your messages are hidden from search results." if is_blocked else "⚠️ Your messages can appear in search results."}

**Available commands:**
- {"/unblock_me - Allow search" if is_blocked else "/block_me - Block from search"}
    """

    sent_msg = await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
    await auto_delete_in_groups(client, message, sent_msg)


def get_display_name(chat: dict):
    if chat.get("title"):
        return chat["title"]
    # get first_name last_name, if not exist, return username
    first_name = chat.get("first_name", "")
    last_name = chat.get("last_name", "")
    username = chat.get("username", "")
    if first_name or last_name:
        return f"{first_name} {last_name}".strip()
    else:
        return username


def unix_to_rfc3339_utc8(timestamp: int) -> str:
    """
    Convert Unix timestamp to RFC3339 format in UTC+8 timezone.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        RFC3339 formatted datetime string in UTC+8

    Example:
        1766764050 -> "2025-12-26T16:14:10+08:00"
    """
    # Define UTC+8 timezone
    utc8 = timezone(timedelta(hours=8))

    # Convert Unix timestamp to datetime in UTC+8
    dt = datetime.fromtimestamp(timestamp, tz=utc8)

    # Format as RFC3339
    return dt.isoformat()


def parse_search_results(data: "dict"):
    result = ""
    hits = data.get("hits") or []

    for hit in hits:
        text = hit.get("text") or hit.get("caption")
        if not text:
            # maybe sticker of media without caption
            continue
        logging.info("Hit: %s", hit)
        chat_username = get_display_name(hit["chat"])
        from_username = get_display_name(hit.get("from_user") or hit.get("sender_chat", {}))
        unix_timestamp = hit["date"]
        date = unix_to_rfc3339_utc8(unix_timestamp)
        outgoing = hit.get("outgoing", False)  # Default to False if not present
        username = hit["chat"].get("username")
        from_ = hit.get("from_user", {})
        from_id = from_.get("id")
        message_id = hit.get("message_id")  # Get actual message ID, not composite ID
        raw_chat_id = hit["chat"]["id"]
        # For supergroups/channels, chat_id is like -1001026262135
        # For private links, we need to remove the -100 prefix to get 1026262135
        if raw_chat_id < 0:
            # Remove -100 prefix for supergroups/channels: -1001234567890 -> 1234567890
            chat_id = abs(raw_chat_id) - 1000000000000 if abs(raw_chat_id) > 1000000000000 else abs(raw_chat_id)
        else:
            chat_id = raw_chat_id
        # https://corefork.telegram.org/api/links
        # Use chat username if available, otherwise fall back to from_id (if available), or chat_id
        if username:
            deep_link = f"tg://resolve?domain={username}"
        elif from_id:
            deep_link = f"tg://user?id={from_id}"
        else:
            # For channels/groups without username and no from_user, use chat link
            deep_link = f"tg://privatepost?channel={chat_id}&post={message_id}"
        text_link = f"https://t.me/{username}/{message_id}" if username else f"https://t.me/c/{chat_id}/{message_id}"

        if outgoing:
            result += f"{from_username} -> [{chat_username}]({deep_link}) on {date}: \n`{text}` [👀]({text_link})\n\n"
        else:
            # For incoming messages, show: sender -> chat (or "-> me" for private chats)
            if from_username and from_username != chat_username:
                # Group/channel message: show sender -> chat
                result += f"{from_username} -> [{chat_username}]({deep_link}) on {date}: \n`{text}` [👀]({text_link})\n\n"
            else:
                # Private message: show sender -> me
                result += f"[{chat_username}]({deep_link}) -> me on {date}: \n`{text}` [👀]({text_link})\n\n"
    return result


def generate_navigation(page, total_pages):
    if total_pages != 1:
        # Check if we're at the max page limit
        at_max_page = page >= MAX_PAGE
        # Check if next page would exceed max
        next_page_available = page < total_pages and not at_max_page

        if page == 1:
            # first page, only show next button if available
            if next_page_available:
                next_button = InlineKeyboardButton("Next Page", callback_data=f"n|{page}")
                markup_content = [next_button]
            else:
                # No navigation needed if only one accessible page
                return None
        elif page == total_pages or at_max_page:
            # last page or max page reached, only show previous button
            previous_button = InlineKeyboardButton("Previous Page", callback_data=f"p|{page}")
            markup_content = [previous_button]
        else:
            # middle page, show both previous and next button (if next is available)
            previous_button = InlineKeyboardButton("Previous Page", callback_data=f"p|{page}")
            if next_page_available:
                next_button = InlineKeyboardButton("Next Page", callback_data=f"n|{page}")
                markup_content = [previous_button, next_button]
            else:
                # Only show previous if at limit
                markup_content = [previous_button]
        markup = InlineKeyboardMarkup([markup_content])
    else:
        markup = None
    return markup


def parse_and_search(text, page=1, requester_info=None, chat_id=None, apply_privacy_filter=True, user_id=None, user_obj=None) -> Tuple[str, InlineKeyboardMarkup | None]:
    """
    Parse search query and perform search.

    Args:
        text: Search query text
        page: Page number
        requester_info: Requester information for display
        chat_id: Optional chat ID to filter results (for group-specific searches)
        apply_privacy_filter: Whether to filter out blocked users (False for admin in private chat)
        user_id: User ID for permission-based group filtering
        user_obj: Pyrogram User object for logging

    Returns:
        Tuple of (result_text, inline_keyboard_markup)
    """
    # Validate page number
    if page < 1:
        return "Invalid page number. Page must be greater than 0.", None
    if page > MAX_PAGE:
        return f"Page number too high. Maximum allowed page is {MAX_PAGE}.", None

    # Start timing for query logging
    import time
    start_time = time.time()

    args = parser.parse_args(text.split())
    _type = args.type
    user = args.user
    keyword = args.keyword
    mode = args.mode
    logging.info("Search keyword: %s, type: %s, user: %s, page: %s, mode: %s, chat_id: %s, privacy_filter: %s",
                 keyword, _type, user, page, mode, chat_id, apply_privacy_filter)

    # Perform search with optional chat_id filter
    results = tgdb.search(keyword, _type, user, page, mode, chat_id=chat_id)

    # Filter results to exclude blocked users (privacy control)
    # Skip filtering for admin in private chat to allow full search access
    if apply_privacy_filter:
        results = privacy_manager.filter_search_results(results)

    # Filter results based on user group permissions
    # Owner and admins see all groups, regular users see only their allowed groups
    if user_id and not chat_id:  # Only apply if not already filtered to a specific chat
        # Skip filtering for owner and admins - they can see all groups
        if not access_controller.is_owner(user_id) and not access_controller.is_admin(user_id):
            allowed_groups = access_controller.get_allowed_groups_for_user(user_id)
            if allowed_groups:  # If user has specific group restrictions
                # Filter hits to only include messages from allowed groups
                original_hits = results.get("hits", [])
                filtered_hits = [hit for hit in original_hits if hit.get("chat", {}).get("id") in allowed_groups]
                results["hits"] = filtered_hits
                # Update count to reflect filtered results
                results["totalHits"] = len(filtered_hits)
                # Recalculate pages based on filtered results
                hits_per_page = results.get("hitsPerPage", 10)
                results["totalPages"] = (len(filtered_hits) + hits_per_page - 1) // hits_per_page if hits_per_page > 0 else 1
                logging.info(f"Filtered search results for user {user_id}: {len(original_hits)} -> {len(filtered_hits)} hits")

    text = parse_search_results(results)
    if not text:
        return "No results found. Try different keywords or check privacy settings.", None

    total_hits = results["totalHits"]
    total_pages = results["totalPages"]
    page = results["page"]
    processing_time = results.get("processingTimeMs", 0)

    # Add header with stats
    header = f"🔍 **Search Results**\n"
    # Cap displayed total_pages to MAX_PAGE
    displayed_total = min(total_pages, MAX_PAGE)
    header += f"**Hits:** {total_hits} | **Page:** {page}/{displayed_total}"
    if total_pages > MAX_PAGE:
        header += f" (capped at {MAX_PAGE})"
    header += f" | **Time:** {processing_time}ms\n"

    if requester_info:
        header += f"**Requested by:** {requester_info}\n"

    header += "\n"

    markup = generate_navigation(page, total_pages)

    # Log query to database
    if db_manager and user_id and user_obj:
        processing_time_ms = int((time.time() - start_time) * 1000)
        try:
            db_manager.log_query(
                user_id=user_id,
                username=user_obj.username if user_obj else None,
                first_name=user_obj.first_name if user_obj else None,
                chat_id=chat_id if chat_id else 0,  # 0 for private/global search
                chat_type="PRIVATE" if not chat_id else "GROUP",
                query=keyword,
                search_type=_type,
                search_user=user,
                search_mode=mode,
                results_count=total_hits,
                page_number=page,
                processing_time_ms=processing_time_ms
            )
        except Exception as e:
            logging.error(f"Failed to log query: {e}")

    return f"{header}{text}", markup


def get_requester_info(message: types.Message) -> str:
    """Get formatted requester information for group searches."""
    if message.chat.type == enums.ChatType.PRIVATE:
        return None

    user = message.from_user
    if not user:
        return "Unknown"

    name = user.first_name or user.username or "User"
    username = f"@{user.username}" if user.username else f"ID:{user.id}"
    return f"{name} ({username})"


@app.on_message(filters.command(["search"]) & filters.text & filters.incoming)
@require_access
async def search_command_handler(client: "Client", message: "types.Message"):
    """Handle /search command in groups and private chats."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Extract search query after /search command
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "Usage: `/search <query>`\n\nExamples:\n"
            "- `/search keyword`\n"
            "- `/search -t=GROUP keyword`\n"
            "- `/search -u=username keyword`\n"
            "- `/search \"exact phrase\"`",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return

    search_query = parts[1]
    requester_info = get_requester_info(message)

    # Determine privacy filtering: skip for owner in private chat, apply for everyone else
    user = message.from_user
    is_private = message.chat.type == enums.ChatType.PRIVATE
    is_owner = user and access_controller.is_owner(user.id)
    apply_privacy_filter = not (is_private and is_owner)

    # In groups, filter search results to only this group
    group_chat_id = message.chat.id if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else None
    user_id = user.id if user else None
    text, markup = parse_and_search(search_query, requester_info=requester_info, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter, user_id=user_id, user_obj=user)

    if len(text) > 4096:
        logging.warning("Message too long, sending as file instead")
        file = BytesIO(text.encode())
        file.name = "search_result.txt"
        await message.reply_text("Your search result is too long, sending as file instead", quote=True)
        sent_msg = await message.reply_document(file, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup)
    else:
        sent_msg = await message.reply_text(
            text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup, disable_web_page_preview=True
        )

    # Schedule auto-deletion if message has inline keyboard (pagination) and in a group
    if markup and sent_msg.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        asyncio.create_task(schedule_message_deletion(client, sent_msg.chat.id, sent_msg.id))


@app.on_message(filters.command(chat_types) & filters.text & filters.incoming)
@require_access
async def type_search_handler(client: "Client", message: "types.Message"):
    parts = message.text.split(maxsplit=2)
    chat_type = parts[0][1:].upper()
    if len(parts) == 1:
        await message.reply_text(f"/{chat_type} [username] keyword", quote=True, parse_mode=enums.ParseMode.MARKDOWN)
        return
    if len(parts) > 2:
        user_filter = f"-u={parts[1]}"
        keyword = parts[2]
    else:
        user_filter = ""
        keyword = parts[1]

    refined_text = f"-t={chat_type} {user_filter} {keyword}"
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    requester_info = get_requester_info(message)

    # Determine privacy filtering: skip for owner in private chat, apply for everyone else
    user = message.from_user
    is_private = message.chat.type == enums.ChatType.PRIVATE
    is_owner = user and access_controller.is_owner(user.id)
    apply_privacy_filter = not (is_private and is_owner)

    # In groups, filter search results to only this group
    group_chat_id = message.chat.id if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else None
    user_id = user.id if user else None
    text, markup = parse_and_search(refined_text, requester_info=requester_info, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter, user_id=user_id, user_obj=user)
    sent_msg = await message.reply_text(
        text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup, disable_web_page_preview=True
    )

    # Schedule auto-deletion if message has inline keyboard (pagination) and in a group
    if markup and sent_msg.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        asyncio.create_task(schedule_message_deletion(client, sent_msg.chat.id, sent_msg.id))


@app.on_message(filters.text & filters.incoming & not_command)
@require_access
async def search_handler(client: "Client", message: "types.Message"):
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    requester_info = get_requester_info(message)

    # Determine privacy filtering: skip for owner in private chat, apply for everyone else
    user = message.from_user
    is_private = message.chat.type == enums.ChatType.PRIVATE
    is_owner = user and access_controller.is_owner(user.id)
    apply_privacy_filter = not (is_private and is_owner)

    # In groups, filter search results to only this group
    group_chat_id = message.chat.id if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else None
    user_id = user.id if user else None
    text, markup = parse_and_search(message.text, requester_info=requester_info, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter, user_id=user_id, user_obj=user)

    if len(text) > 4096:
        logging.warning("Message too long, sending as file instead")
        file = BytesIO(text.encode())
        file.name = "search_result.txt"
        await message.reply_text("Your search result is too long, sending as file instead", quote=True)
        sent_msg = await message.reply_document(file, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup)
        file.close()
    else:
        sent_msg = await message.reply_text(
            text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup, disable_web_page_preview=True
        )

    # Schedule auto-deletion if message has inline keyboard (pagination) and in a group
    if markup and sent_msg.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        asyncio.create_task(schedule_message_deletion(client, sent_msg.chat.id, sent_msg.id))


@app.on_callback_query(filters.regex(r"n|p"))
async def send_method_callback(client: "Client", callback_query: types.CallbackQuery):
    # Cancel auto-deletion when user interacts with the message (groups only)
    message = callback_query.message
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        cancel_message_deletion(message.chat.id, message.id)

    call_data = callback_query.data.split("|")
    direction, page = call_data[0], int(call_data[1])
    if direction == "n":
        new_page = page + 1
    elif direction == "p":
        new_page = page - 1
    else:
        raise ValueError("Invalid direction")

    # find original user query
    # /search hello           -> hello
    # /private hello          -> -t=PRIVATE hello
    # /private username hello -> -t=PRIVATE -u=username hello
    # -t=private -u=123 hello -> -t=private -u=123 hello
    # hello                   -> hello
    user_query = message.reply_to_message.text

    parts = user_query.split(maxsplit=2)
    if user_query.startswith("/search "):
        # Handle /search command: extract query after "/search "
        refined_text = user_query[8:]  # Remove "/search " prefix
    elif user_query.startswith("/") and parts[0][1:].lower() in [ct.lower() for ct in chat_types]:
        # Handle chat type shortcuts like /private, /group, etc.
        user_filter = f"-u={parts[1]}" if len(parts) > 2 else ""
        keyword = parts[2] if len(parts) > 2 else parts[1]
        refined_text = f"-t={parts[0][1:].upper()} {user_filter} {keyword}"
    elif len(parts) == 1:
        refined_text = parts[0]
    else:
        refined_text = user_query
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Determine privacy filtering: skip for owner in private chat, apply for everyone else
    user = callback_query.from_user
    is_private = message.chat.type == enums.ChatType.PRIVATE
    is_owner = user and access_controller.is_owner(user.id)
    apply_privacy_filter = not (is_private and is_owner)

    # In groups, filter search results to only this group
    group_chat_id = message.chat.id if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else None
    user_id = user.id if user else None
    new_text, new_markup = parse_and_search(refined_text, new_page, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter, user_id=user_id, user_obj=user)
    await message.edit_text(new_text, reply_markup=new_markup, disable_web_page_preview=True)

    # Reschedule auto-deletion for the updated message (reset 120s timer) in groups only
    if new_markup and message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        asyncio.create_task(schedule_message_deletion(client, message.chat.id, message.id))


@app.on_message(filters.command(["mystats"]))
@require_access
async def mystats_handler(client: "Client", message: "types.Message"):
    """Show user's activity stats in the current group."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Check if message is from a user or a channel
    user = message.from_user
    sender_chat = message.sender_chat

    # For now, only support regular users (not channels)
    if not user and sender_chat:
        sent_msg = await message.reply_text(
            "❌ **Channel Stats Not Yet Supported**\n\n"
            "The `/mystats` command currently only works for individual users.\n\n"
            "💡 **Tip**: Send this command as yourself (not as the channel) to see your personal stats.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        await auto_delete_in_groups(client, message, sent_msg)
        return

    if not user:
        sent_msg = await message.reply_text("❌ Could not identify sender.", quote=True)
        await auto_delete_in_groups(client, message, sent_msg)
        return

    # Only work in group chats
    if message.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        sent_msg = await message.reply_text(
            "❌ This command only works in group chats.\n\n"
            "Use it in a group to see your activity stats!",
            quote=True
        )
        await auto_delete_in_groups(client, message, sent_msg)
        return

    # Parse command arguments
    parts = message.text.split(maxsplit=2)
    time_window = "365d"  # Default: 1 year
    include_mentions = False

    # Parse arguments: /mystats [time_window] [at]
    if len(parts) >= 2:
        # Check if second arg is "at" flag
        if parts[1].lower() == "at":
            include_mentions = True
        else:
            time_window = parts[1]
            # Check for "at" flag in third position
            if len(parts) >= 3 and parts[2].lower() == "at":
                include_mentions = True

    # Parse time window
    try:
        from_ts, to_ts = parse_time_window(time_window)
    except ValueError as e:
        sent_msg = await message.reply_text(
            f"❌ Invalid time window: {e}\n\n"
            "**Supported formats:**\n"
            "- `7d`, `30d`, `90d`, `365d`, `1y`\n"
            "- `2025-01-01..2025-12-31`\n\n"
            "**Examples:**\n"
            "- `/mystats` - Last 1 year\n"
            "- `/mystats 30d` - Last 30 days\n"
            "- `/mystats 90d at` - Last 90 days with mentions\n"
            "- `/mystats 2025-01-01..2025-12-31 at` - Date range with mentions",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        await auto_delete_in_groups(client, message, sent_msg)
        return

    # Get stats from backend (user only, channels not supported yet)
    try:
        stats = tgdb.get_user_stats(
            group_id=message.chat.id,
            user_id=user.id,
            from_timestamp=from_ts,
            to_timestamp=to_ts,
            include_mentions=include_mentions,
            include_deleted=False  # Regular users never see deleted
        )

        # Format response
        user_count = stats["user_message_count"]
        group_total = stats["group_message_total"]
        ratio = stats["user_ratio"]
        time_desc = format_time_window(from_ts, to_ts)

        response = f"📊 **Your Activity Stats**\n\n"
        response += f"**Group:** {message.chat.title or 'This Group'}\n"
        response += f"**Period:** {time_desc}\n\n"

        if group_total == 0:
            response += "No messages found in this time period."
        else:
            response += f"**Your Messages:** {user_count:,}\n"
            response += f"**Group Total:** {group_total:,}\n"
            response += f"**Your Share:** {ratio:.1%}\n"

            if include_mentions:
                mentions_out = stats.get("mentions_out", 0)
                mentions_in = stats.get("mentions_in", 0)
                response += f"\n**Mentions:**\n"
                response += f"  • You mentioned others: {mentions_out:,} times\n"
                response += f"  • Others mentioned you: {mentions_in:,} times\n"

        sent_msg = await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
        await auto_delete_in_groups(client, message, sent_msg)

    except Exception as e:
        logging.exception("Error getting user stats")
        sent_msg = await message.reply_text(
            f"❌ Error retrieving stats: {str(e)}\n\n"
            "Please try again or contact the bot owner.",
            quote=True
        )
        await auto_delete_in_groups(client, message, sent_msg)


@app.on_message(filters.command(["logs", "query_logs"]))
@require_owner
async def logs_handler(client: "Client", message: "types.Message"):
    """View recent query logs (owner only)."""
    if not db_manager:
        await message.reply_text("❌ Database logging is disabled.", quote=True)
        return

    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        # Parse command arguments
        parts = message.text.split(maxsplit=2)
        limit = 20  # Default limit
        user_filter = None

        # Check for user filter: /logs @username or /logs 123456
        if len(parts) >= 2:
            try:
                # Try parsing as user ID
                user_filter = int(parts[1])
            except ValueError:
                # Try parsing as limit
                try:
                    limit = int(parts[1])
                    limit = min(limit, 100)  # Cap at 100
                except ValueError:
                    pass

        logs = db_manager.get_recent_logs(limit=limit, user_id=user_filter)

        if not logs:
            await message.reply_text("📊 No query logs found.", quote=True)
            return

        # Format logs
        response = f"📊 **Query Logs** (showing {len(logs)} most recent)\n\n"

        for log in logs:
            timestamp = datetime.fromtimestamp(log['timestamp'])
            username = log['username'] or log['first_name'] or f"ID:{log['user_id']}"
            query = log['query'][:50] + "..." if len(log['query']) > 50 else log['query']
            results = log['results_count']
            time_ms = log['processing_time_ms']

            response += f"**{timestamp.strftime('%Y-%m-%d %H:%M')}** - {username}\n"
            response += f"  Query: `{query}`\n"
            if log['search_type']:
                response += f"  Type: {log['search_type']}"
            if log['search_user']:
                response += f", User: {log['search_user']}"
            if log['search_mode']:
                response += f", Mode: {log['search_mode']}"
            response += f"\n  Results: {results}, Time: {time_ms}ms\n\n"

        if len(response) > 4096:
            # Send as file if too long
            file = BytesIO(response.encode())
            file.name = "query_logs.txt"
            await message.reply_document(file, quote=True, caption="Query logs (too long for message)")
            file.close()
        else:
            await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)

    except Exception as e:
        logging.exception("Error retrieving logs")
        await message.reply_text(f"❌ Error retrieving logs: {str(e)}", quote=True)


@app.on_message(filters.command(["logstats", "log_stats"]))
@require_owner
async def logstats_handler(client: "Client", message: "types.Message"):
    """View query log statistics (owner only)."""
    if not db_manager:
        await message.reply_text("❌ Database logging is disabled.", quote=True)
        return

    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        stats = db_manager.get_statistics()

        response = "📈 **Query Log Statistics**\n\n"
        response += f"**Total Queries:** {stats['total_queries']:,}\n"
        response += f"**Queries (24h):** {stats['queries_24h']:,}\n"
        response += f"**Avg Results:** {stats['avg_results_per_query']:.1f}\n"
        response += f"**Avg Time:** {stats['avg_processing_time_ms']:.0f}ms\n\n"

        if stats['top_users']:
            response += "**Top Users:**\n"
            for user in stats['top_users'][:5]:
                username = user['username'] or user['first_name'] or f"ID:{user['user_id']}"
                response += f"  • {username}: {user['count']:,} queries\n"
            response += "\n"

        if stats['by_chat_type']:
            response += "**By Chat Type:**\n"
            for chat_type in stats['by_chat_type']:
                response += f"  • {chat_type['chat_type']}: {chat_type['count']:,}\n"

        await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)

    except Exception as e:
        logging.exception("Error retrieving statistics")
        await message.reply_text(f"❌ Error retrieving statistics: {str(e)}", quote=True)


@app.on_message(filters.command(["settings", "db_settings"]))
@require_owner
async def settings_handler(client: "Client", message: "types.Message"):
    """View or update database settings (owner only)."""
    if not db_manager:
        await message.reply_text("❌ Database logging is disabled.", quote=True)
        return

    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        parts = message.text.split(maxsplit=2)

        # View all settings
        if len(parts) == 1:
            settings = db_manager.get_all_settings()
            response = "⚙️ **Database Settings**\n\n"

            for key, info in settings.items():
                value = info['value']
                desc = info['description']
                updated = datetime.fromtimestamp(info['updated_at']).strftime('%Y-%m-%d %H:%M')
                response += f"**{key}:** `{value}`\n"
                if desc:
                    response += f"  _{desc}_\n"
                response += f"  Last updated: {updated}\n\n"

            response += "\n💡 **Usage:**\n"
            response += "`/settings <key> <value>` - Update a setting\n"
            response += "`/settings enable_query_logging true` - Example\n"

            await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)

        # Update setting
        elif len(parts) == 3:
            key = parts[1]
            value_str = parts[2]

            # Parse value based on type
            if value_str.lower() in ('true', 'false'):
                value = value_str.lower() == 'true'
            else:
                try:
                    value = int(value_str)
                except ValueError:
                    try:
                        value = float(value_str)
                    except ValueError:
                        value = value_str

            user_id = message.from_user.id
            db_manager.set_setting(key, value, updated_by=user_id)

            await message.reply_text(
                f"✅ Setting updated:\n**{key}** = `{value}`",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )

        else:
            await message.reply_text(
                "Usage:\n"
                "`/settings` - View all settings\n"
                "`/settings <key> <value>` - Update setting",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )

    except Exception as e:
        logging.exception("Error managing settings")
        await message.reply_text(f"❌ Error: {str(e)}", quote=True)


@app.on_message(filters.command(["cleanup_logs"]))
@require_owner
async def cleanup_logs_handler(client: "Client", message: "types.Message"):
    """Cleanup old query logs (owner only)."""
    if not db_manager:
        await message.reply_text("❌ Database logging is disabled.", quote=True)
        return

    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        # Cleanup old logs based on retention setting
        deleted_old = db_manager.cleanup_old_logs()
        # Cleanup excess logs based on max entries setting
        deleted_excess = db_manager.cleanup_excess_logs()

        total_deleted = deleted_old + deleted_excess

        response = "🧹 **Log Cleanup Complete**\n\n"
        response += f"Deleted old logs: {deleted_old}\n"
        response += f"Deleted excess logs: {deleted_excess}\n"
        response += f"**Total removed:** {total_deleted}\n\n"

        stats = db_manager.get_statistics()
        response += f"Remaining logs: {stats['total_queries']:,}"

        await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)

    except Exception as e:
        logging.exception("Error cleaning up logs")
        await message.reply_text(f"❌ Error: {str(e)}", quote=True)


@app.on_message(filters.command(["sync"]))
@require_owner
async def sync_handler(client: "Client", message: "types.Message"):
    """Add a chat to the sync queue (owner only)."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        # Parse command arguments
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply_text(
                "❌ **Usage:** `/sync <chat_id>`\n\n"
                "Examples:\n"
                "• `/sync -1001234567890` - Sync a specific group\n"
                "• `/sync 123456789` - Sync a user/channel by ID\n\n"
                "**Tip:** Use `/sync_status` to check ongoing syncs",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        # Extract chat ID
        try:
            chat_id = int(args[1].strip())
        except ValueError:
            await message.reply_text(
                "❌ Invalid chat ID. Must be a numeric ID (e.g., -1001234567890)",
                quote=True
            )
            return

        # Send command to client via HTTP API
        user_id = message.from_user.id if message.from_user else 0
        result = sync_client.add_sync(chat_id, requested_by=user_id)

        if result.get("success"):
            await message.reply_text(
                f"✅ **Sync task started!**\n\n"
                f"Chat ID: `{chat_id}`\n\n"
                f"{result.get('message', 'Syncing in progress...')}\n"
                f"Use `/sync_status` to monitor progress.",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await message.reply_text(
                f"⚠️ **Sync task status:**\n\n"
                f"Chat ID: `{chat_id}`\n"
                f"Status: {result.get('status', 'unknown')}\n\n"
                f"{result.get('message', 'Chat may already be in queue.')}",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )

    except Exception as e:
        logging.exception("Error submitting sync task")
        await message.reply_text(
            f"❌ **Error connecting to sync API:**\n\n"
            f"`{str(e)}`\n\n"
            f"Make sure the client process is running.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )


@app.on_message(filters.command(["sync_status"]))
@require_owner
async def sync_status_handler(client: "Client", message: "types.Message"):
    """Check sync status for all tasks (owner only)."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        # Get status from HTTP API
        status = sync_client.get_sync_status()

        if not status or not status.get("chats"):
            await message.reply_text(
                "ℹ️ **No active sync tasks**\n\n"
                "Use `/sync <chat_id>` to start syncing a chat.",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        # Format status message
        response = "📊 **Sync Status**\n\n"
        response += f"Last Updated: `{status.get('timestamp', 'Unknown')}`\n\n"

        chats = status.get("chats", [])
        for chat_data in chats:
            chat_id = chat_data.get("chat_id", "Unknown")
            status_str = chat_data.get("status", "unknown")
            progress_percent = chat_data.get("progress_percent", 0)
            synced = chat_data.get("synced_count", 0)
            total = chat_data.get("total_count", 0)
            error_count = chat_data.get("error_count", 0)
            last_error = chat_data.get("last_error")

            # Status emoji
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "paused": "⏸️"
            }.get(status_str, "❓")

            response += f"**Chat {chat_id}**\n"
            response += f"  Status: {status_emoji} {status_str}\n"
            response += f"  Progress: {progress_percent}% ({synced:,}/{total:,})\n"

            if error_count > 0:
                response += f"  Errors: {error_count}\n"
            if last_error and status_str == "failed":
                response += f"  Last Error: `{last_error[:100]}`\n"

            response += "\n"

        # Add summary
        pending = sum(1 for c in chats if c.get("status") == "pending")
        in_progress = sum(1 for c in chats if c.get("status") == "in_progress")
        completed = sum(1 for c in chats if c.get("status") == "completed")
        failed = sum(1 for c in chats if c.get("status") == "failed")
        paused = sum(1 for c in chats if c.get("status") == "paused")

        response += f"**Summary:**\n"
        response += f"• Pending: {pending}\n"
        response += f"• In Progress: {in_progress}\n"
        response += f"• Completed: {completed}\n"
        if paused > 0:
            response += f"• Paused: {paused}\n"
        if failed > 0:
            response += f"• Failed: {failed}\n"

        await message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)

    except Exception as e:
        logging.exception("Error getting sync status")
        await message.reply_text(
            f"❌ **Error connecting to sync API:**\n\n"
            f"`{str(e)}`\n\n"
            f"Make sure the client process is running.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )


@app.on_message(filters.command(["sync_pause"]))
@require_owner
async def sync_pause_handler(client: "Client", message: "types.Message"):
    """Pause an ongoing sync task (owner only)."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        # Parse command arguments
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply_text(
                "❌ **Usage:** `/sync_pause <chat_id>`\n\n"
                "Example: `/sync_pause -1001234567890`",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        # Extract chat ID
        try:
            chat_id = int(args[1].strip())
        except ValueError:
            await message.reply_text(
                "❌ Invalid chat ID. Must be a numeric ID",
                quote=True
            )
            return

        # Send pause command via HTTP API
        result = sync_client.pause_sync(chat_id)

        if result.get("success"):
            await message.reply_text(
                f"⏸️ **Sync paused!**\n\n"
                f"Chat ID: `{chat_id}`\n\n"
                f"{result.get('message', 'Sync paused at next checkpoint.')}\n"
                f"Use `/sync_resume {chat_id}` to continue.",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await message.reply_text(
                f"❌ **Failed to pause sync:**\n\n"
                f"Chat ID: `{chat_id}`\n\n"
                f"{result.get('message', 'Unknown error')}",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )

    except Exception as e:
        logging.exception("Error pausing sync")
        await message.reply_text(
            f"❌ **Error connecting to sync API:**\n\n"
            f"`{str(e)}`\n\n"
            f"Make sure the client process is running.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )


@app.on_message(filters.command(["sync_resume"]))
@require_owner
async def sync_resume_handler(client: "Client", message: "types.Message"):
    """Resume a paused sync task (owner only)."""
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    try:
        # Parse command arguments
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply_text(
                "❌ **Usage:** `/sync_resume <chat_id>`\n\n"
                "Example: `/sync_resume -1001234567890`",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        # Extract chat ID
        try:
            chat_id = int(args[1].strip())
        except ValueError:
            await message.reply_text(
                "❌ Invalid chat ID. Must be a numeric ID",
                quote=True
            )
            return

        # Send resume command via HTTP API
        result = sync_client.resume_sync(chat_id)

        if result.get("success"):
            await message.reply_text(
                f"▶️ **Sync resumed!**\n\n"
                f"Chat ID: `{chat_id}`\n\n"
                f"{result.get('message', 'Sync resumed from last checkpoint.')}\n"
                f"Use `/sync_status` to monitor progress.",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await message.reply_text(
                f"❌ **Failed to resume sync:**\n\n"
                f"Chat ID: `{chat_id}`\n\n"
                f"{result.get('message', 'Unknown error')}",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )

    except Exception as e:
        logging.exception("Error resuming sync")
        await message.reply_text(
            f"❌ **Error connecting to sync API:**\n\n"
            f"`{str(e)}`\n\n"
            f"Make sure the client process is running.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )


@app.on_message(filters.command(["sync_list"]))
@require_owner
async def sync_list_handler(client: "Client", message: "types.Message"):
    """List all sync tasks with their status (owner only). Alias for /sync_status."""
    await sync_status_handler(client, message)


if __name__ == "__main__":
    import threading
    from .bot_api import init_bot_api, run_bot_api

    # Initialize bot API with bot client
    init_bot_api(app)

    # Get bot HTTP API configuration
    bot_host = config.get("http.listen", "127.0.0.1")
    bot_port = config.get_int("http.bot_port", 8081)

    # Start bot HTTP API server in background thread
    logging.info(f"Starting bot HTTP API server on {bot_host}:{bot_port}")
    threading.Thread(
        target=run_bot_api,
        args=(bot_host, bot_port),
        daemon=True
    ).start()

    # Run the bot
    app.run()
