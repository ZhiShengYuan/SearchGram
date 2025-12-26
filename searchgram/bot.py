#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - bot.py
# 4/4/22 22:06
#

__author__ = "Benny <benny.think@gmail.com>"

import argparse
import logging
from io import BytesIO
from typing import Tuple

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

**🔍 Search Syntax:**
1. **Global search**: Send any message to search all chats
2. **Chat type search**: `-t=GROUP keyword`
   - Supported types: {', '.join(chat_types)}
3. **User search**: `-u=user_id|username keyword`
4. **Exact match**: `-m=e keyword` or `"keyword"`
5. **Combined**: `-t=GROUP -u=username keyword`
6. **Type shortcuts**: `/private [username] keyword`

**🔐 Privacy Commands:**
- `/block_me` - Opt-out: Your messages won't appear in anyone's search
- `/unblock_me` - Opt-in: Allow your messages in search results
- `/privacy_status` - Check your current privacy status

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


def parse_search_results(data: "dict"):
    result = ""
    hits = data["hits"]

    for hit in hits:
        text = hit.get("text") or hit.get("caption")
        if not text:
            # maybe sticker of media without caption
            continue
        logging.info("Hit: %s", hit)
        chat_username = get_display_name(hit["chat"])
        from_username = get_display_name(hit.get("from_user") or hit.get("sender_chat", {}))
        date = hit["date"]
        outgoing = hit.get("outgoing", False)  # Default to False if not present
        username = hit["chat"].get("username")
        from_ = hit.get("from_user", {})
        from_id = from_.get("id")
        message_id = hit.get("message_id")  # Get actual message ID, not composite ID
        chat_id = abs(hit["chat"]["id"])  # Get absolute value for private link construction
        # https://corefork.telegram.org/api/links
        deep_link = f"tg://resolve?domain={username}" if username else f"tg://user?id={from_id}"
        text_link = f"https://t.me/{username}/{message_id}" if username else f"https://t.me/c/{chat_id}/{message_id}"

        if outgoing:
            result += f"{from_username}-> [{chat_username}]({deep_link}) on {date}: \n`{text}` [👀]({text_link})\n\n"
        else:
            result += f"[{chat_username}]({deep_link}) -> me on {date}: \n`{text}` [👀]({text_link})\n\n"
    return result


def generate_navigation(page, total_pages):
    if total_pages != 1:
        if page == 1:
            # first page, only show next button
            next_button = InlineKeyboardButton("Next Page", callback_data=f"n|{page}")
            markup_content = [next_button]
        elif page == total_pages:
            # last page, only show previous button
            previous_button = InlineKeyboardButton("Previous Page", callback_data=f"p|{page}")
            markup_content = [previous_button]
        else:
            # middle page, show both previous and next button
            next_button = InlineKeyboardButton("Next Page", callback_data=f"n|{page}")
            previous_button = InlineKeyboardButton("Previous Page", callback_data=f"p|{page}")
            markup_content = [previous_button, next_button]
        markup = InlineKeyboardMarkup([markup_content])
    else:
        markup = None
    return markup


def parse_and_search(text, page=1, requester_info=None, chat_id=None) -> Tuple[str, InlineKeyboardMarkup | None]:
    """
    Parse search query and perform search.

    Args:
        text: Search query text
        page: Page number
        requester_info: Requester information for display
        chat_id: Optional chat ID to filter results (for group-specific searches)

    Returns:
        Tuple of (result_text, inline_keyboard_markup)
    """
    args = parser.parse_args(text.split())
    _type = args.type
    user = args.user
    keyword = args.keyword
    mode = args.mode
    logging.info("Search keyword: %s, type: %s, user: %s, page: %s, mode: %s, chat_id: %s",
                 keyword, _type, user, page, mode, chat_id)

    # Perform search with optional chat_id filter
    results = tgdb.search(keyword, _type, user, page, mode, chat_id=chat_id)

    # Filter results to exclude blocked users (privacy control)
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
    header += f"**Hits:** {total_hits} | **Page:** {page}/{total_pages} | **Time:** {processing_time}ms\n"

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


@app.on_message(filters.command(chat_types) & filters.text & filters.incoming)
@require_access
def type_search_handler(client: "Client", message: "types.Message"):
    parts = message.text.split(maxsplit=2)
    chat_type = parts[0][1:].upper()
    if len(parts) == 1:
        message.reply_text(f"/{chat_type} [username] keyword", quote=True, parse_mode=enums.ParseMode.MARKDOWN)
        return
    if len(parts) > 2:
        user_filter = f"-u={parts[1]}"
        keyword = parts[2]
    else:
        user_filter = ""
        keyword = parts[1]

    refined_text = f"-t={chat_type} {user_filter} {keyword}"
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    requester_info = get_requester_info(message)
    # In groups, filter search results to only this group
    group_chat_id = message.chat.id if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else None
    text, markup = parse_and_search(refined_text, requester_info=requester_info, chat_id=group_chat_id)
    message.reply_text(
        text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup, disable_web_page_preview=True
    )


@app.on_message(filters.text & filters.incoming)
@require_access
def search_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    requester_info = get_requester_info(message)
    # In groups, filter search results to only this group
    group_chat_id = message.chat.id if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else None
    text, markup = parse_and_search(message.text, requester_info=requester_info, chat_id=group_chat_id)

    if len(text) > 4096:
        logging.warning("Message too long, sending as file instead")
        file = BytesIO(text.encode())
        file.name = "search_result.txt"
        message.reply_text("Your search result is too long, sending as file instead", quote=True)
        message.reply_document(file, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup)
        file.close()
    else:
        message.reply_text(
            text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup, disable_web_page_preview=True
        )


@app.on_callback_query(filters.regex(r"n|p"))
def send_method_callback(client: "Client", callback_query: types.CallbackQuery):
    call_data = callback_query.data.split("|")
    direction, page = call_data[0], int(call_data[1])
    message = callback_query.message
    if direction == "n":
        new_page = page + 1
    elif direction == "p":
        new_page = page - 1
    else:
        raise ValueError("Invalid direction")

    # find original user query
    # /private hello
    # -t=private -u=123 hello
    # -t=private hello
    # hello
    user_query = message.reply_to_message.text

    parts = user_query.split(maxsplit=2)
    if user_query.startswith("/"):
        user_filter = f"-u={parts[1]}" if len(parts) > 2 else ""
        keyword = parts[2] if len(parts) > 2 else parts[1]
        refined_text = f"-t={parts[0][1:].upper()} {user_filter} {keyword}"
    elif len(parts) == 1:
        refined_text = parts[0]
    else:
        refined_text = user_query
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # In groups, filter search results to only this group
    group_chat_id = message.chat.id if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else None
    new_text, new_markup = parse_and_search(refined_text, new_page, chat_id=group_chat_id)
    message.edit_text(new_text, reply_markup=new_markup, disable_web_page_preview=True)


if __name__ == "__main__":
    app.run()
