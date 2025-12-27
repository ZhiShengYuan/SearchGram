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
from .config_loader import BOT_MODE, TOKEN
from .init_client import get_client
from .privacy import privacy_manager
from .utils import setup_logger

tgdb = SearchEngine()

setup_logger()
app = get_client(TOKEN)
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


@app.on_message(filters.command(["start"]))
def search_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    message.reply_text("Hello, I'm search bot.", quote=True)


@app.on_message(filters.command(["help"]))
def help_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

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

{f'''**🛠️ Admin Commands (Owner Only):**
- `/ping` - Check bot health and database stats
- `/dedup` - Remove duplicate messages from database
- `/delete` - Delete messages from specific chat
''' if access_controller.is_owner(user.id if user else 0) else ''}
**⚙️ Bot Mode:** {BOT_MODE}
{f"**Blocked Users:** {privacy_manager.get_blocked_count()}" if access_controller.is_owner(user.id if user else 0) else ""}

**📖 Privacy Notice:**
This bot indexes messages for search. Use `/block_me` anytime to remove yourself from search results. Your privacy matters! 🛡️
    """
    message.reply_text(help_text, quote=True, parse_mode=enums.ParseMode.MARKDOWN)


@app.on_message(filters.command(["ping"]))
@require_owner
def ping_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text = tgdb.ping()
    text += f"\n🔐 Privacy: {privacy_manager.get_blocked_count()} users opted out"
    client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)


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
def clean_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text = tgdb.ping()
    client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)


@app.on_message(filters.command(["block_me", "optout", "privacy_block"]))
def block_me_handler(client: "Client", message: "types.Message"):
    """Allow users to opt-out of search results."""
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    user = message.from_user
    if not user:
        message.reply_text("❌ Could not identify your user ID.", quote=True)
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

    message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)


@app.on_message(filters.command(["unblock_me", "optin", "privacy_unblock"]))
def unblock_me_handler(client: "Client", message: "types.Message"):
    """Allow users to opt back into search results."""
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    user = message.from_user
    if not user:
        message.reply_text("❌ Could not identify your user ID.", quote=True)
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

    message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)


@app.on_message(filters.command(["privacy_status", "privacy", "mystatus"]))
def privacy_status_handler(client: "Client", message: "types.Message"):
    """Check user's current privacy status."""
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    user = message.from_user
    if not user:
        message.reply_text("❌ Could not identify your user ID.", quote=True)
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

    message.reply_text(response, quote=True, parse_mode=enums.ParseMode.MARKDOWN)


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


def parse_and_search(text, page=1, requester_info=None, chat_id=None, apply_privacy_filter=True) -> Tuple[str, InlineKeyboardMarkup | None]:
    """
    Parse search query and perform search.

    Args:
        text: Search query text
        page: Page number
        requester_info: Requester information for display
        chat_id: Optional chat ID to filter results (for group-specific searches)
        apply_privacy_filter: Whether to filter out blocked users (False for admin in private chat)

    Returns:
        Tuple of (result_text, inline_keyboard_markup)
    """
    # Validate page number
    if page < 1:
        return "Invalid page number. Page must be greater than 0.", None
    if page > MAX_PAGE:
        return f"Page number too high. Maximum allowed page is {MAX_PAGE}.", None

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
    text, markup = parse_and_search(search_query, requester_info=requester_info, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter)

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
    text, markup = parse_and_search(refined_text, requester_info=requester_info, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter)
    sent_msg = await message.reply_text(
        text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup, disable_web_page_preview=True
    )

    # Schedule auto-deletion if message has inline keyboard (pagination) and in a group
    if markup and sent_msg.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        asyncio.create_task(schedule_message_deletion(client, sent_msg.chat.id, sent_msg.id))


@app.on_message(filters.text & filters.incoming)
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
    text, markup = parse_and_search(message.text, requester_info=requester_info, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter)

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
    new_text, new_markup = parse_and_search(refined_text, new_page, chat_id=group_chat_id, apply_privacy_filter=apply_privacy_filter)
    await message.edit_text(new_text, reply_markup=new_markup, disable_web_page_preview=True)

    # Reschedule auto-deletion for the updated message (reset 120s timer) in groups only
    if new_markup and message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        asyncio.create_task(schedule_message_deletion(client, message.chat.id, message.id))


if __name__ == "__main__":
    app.run()
