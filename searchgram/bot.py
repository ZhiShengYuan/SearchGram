#!/usr/local/bin/python3
# coding: utf-8

"""
SearchGram - bot.py
Modified so that:
 - The owner (as defined by OWNER_ID) can search all messages.
 - All other users can only search messages from the allowed groups (if they are a member).
 - When a search command is issued from a group chat (and the group is allowed),
   the search is limited to that group.
 - A new command `/search` is accepted (both in private and group chats).
"""

__author__ = "Benny <benny.think@gmail.com>"

import argparse
import logging
import pickle
from io import BytesIO
from typing import Tuple

import redis
from pyrogram import Client, enums, filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from __init__ import SearchEngine
from config import OWNER_ID, TOKEN
from init_client import get_client
from utils import setup_logger

# --- Redis Setup ---
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# --- Allowed groups configuration ---
# Allowed groups are defined as an array of strings.
ALLOWED_GROUP_IDS = ["-1001234567890", "-1009876543210"]

tgdb = SearchEngine()
setup_logger()
app = get_client(TOKEN)
# chat_types here are names of chat types (e.g., "private", "group", etc.)
chat_types = [i for i in dir(enums.ChatType) if not i.startswith("_")]

parser = argparse.ArgumentParser()
parser.add_argument("keyword", help="the keyword to be searched")
parser.add_argument("-t", "--type", help="the type of message", default=None)
parser.add_argument("-u", "--user", help="the user who sent the message", default=None)
parser.add_argument("-m", "--mode", help="match mode, e: exact match, other value is fuzzy search", default=None)


def get_user_allowed_groups(client: "Client", user_id: int) -> list:
    """
    Returns a list of allowed group IDs (as strings) in which the user is a member.
    If the user is not a member of any allowed group, returns an empty list.
    """
    allowed_groups = []
    for group_id in ALLOWED_GROUP_IDS:
        try:
            # get_chat_member expects an integer chat id.
            member = client.get_chat_member(int(group_id), user_id)
            if member.status not in ("left", "kicked"):
                allowed_groups.append(group_id)
        except Exception as e:
            logging.error("Error checking membership for group %s: %s", group_id, e)
    return allowed_groups


def get_display_name(chat: dict):
    if chat.get("title"):
        return chat["title"]
    first_name = chat.get("first_name", "")
    last_name = chat.get("last_name", "")
    username = chat.get("username", "")
    if first_name or last_name:
        return f"{first_name} {last_name}".strip()
    else:
        return username


def parse_search_results(data: "dict", group_filter=None):
    """
    Convert raw search hits to a formatted text result.
    If group_filter is not None, then only include hits coming from one of those groups.
    group_filter can be a single value or a list.
    """
    result = ""
    hits = data.get("hits", [])
    for hit in hits:
        if group_filter is not None:
            # If group_filter is a list, only include the hit if its chat ID (as string)
            # is in that list; otherwise, if group_filter is a single value, check equality.
            if isinstance(group_filter, list):
                if str(hit["chat"]["id"]) not in group_filter:
                    continue
            else:
                if str(hit["chat"]["id"]) != str(group_filter):
                    continue
        text = hit.get("text") or hit.get("caption")
        if not text:
            continue  # Skip messages without text or caption.
        logging.info("Hit: %s", hit)
        chat_username = get_display_name(hit["chat"])
        from_username = get_display_name(hit.get("from_user") or hit.get("sender_chat", {}))
        date = hit["date"]
        outgoing = hit["outgoing"]
        username = hit["chat"].get("username")
        from_ = hit.get("from_user", {})
        from_id = from_.get("id")
        message_id = hit["id"]
        deep_link = f"tg://resolve?domain={username}" if username else f"tg://user?id={from_id}"
        text_link = f"https://t.me/{username}/{message_id}" if username else f"https://t.me/c/{from_id}/{message_id}"
        if outgoing:
            result += f"{from_username} -> [{chat_username}]({deep_link}) on {date}:\n`{text}` [👀]({text_link})\n\n"
        else:
            result += f"[{chat_username}]({deep_link}) -> me on {date}:\n`{text}` [👀]({text_link})\n\n"
    return result


def generate_navigation(page, total_pages):
    if total_pages != 1:
        if page == 1:
            next_button = InlineKeyboardButton("Next Page", callback_data=f"n|{page}")
            markup_content = [next_button]
        elif page == total_pages:
            previous_button = InlineKeyboardButton("Previous Page", callback_data=f"p|{page}")
            markup_content = [previous_button]
        else:
            previous_button = InlineKeyboardButton("Previous Page", callback_data=f"p|{page}")
            next_button = InlineKeyboardButton("Next Page", callback_data=f"n|{page}")
            markup_content = [previous_button, next_button]
        markup = InlineKeyboardMarkup([markup_content])
    else:
        markup = None
    return markup


def parse_and_search(query_text, page=1, user_id=None, group_filter=None) -> Tuple[str, InlineKeyboardMarkup | None]:
    """
    Parse the query text, check the Redis cache, and perform the search.
    
    - If group_filter is None then no group filter is applied (i.e. owner searching globally in private).
    - Otherwise, group_filter can be a single group or a list of groups (as strings) to filter the search.
    """
    if user_id is None:
        raise ValueError("user_id must be provided for caching purposes")
    
    # Create a cache key. If group_filter is a list, join its sorted values.
    if group_filter is None:
        group_key = "None"
    elif isinstance(group_filter, list):
        group_key = ",".join(sorted(group_filter))
    else:
        group_key = str(group_filter)
    cache_key = f"search:{user_id}:{group_key}:{query_text}:{page}"
    
    results = None
    try:
        cached = redis_client.get(cache_key)
        if cached:
            results = pickle.loads(cached)
            logging.info("Loaded cached search result for key %s", cache_key)
    except Exception as e:
        logging.error("Failed to load cached result: %s", e)

    if results is None:
        args = parser.parse_args(query_text.split())
        _type = args.type
        user_filter_arg = args.user
        keyword = args.keyword
        mode = args.mode
        logging.info("Search keyword: %s, type: %s, user: %s, page: %s, mode: %s",
                     keyword, _type, user_filter_arg, page, mode)
        # Call search without passing an unsupported group_id parameter.
        results = tgdb.search(keyword, _type, user_filter_arg, page, mode)
        try:
            redis_client.setex(cache_key, 86400, pickle.dumps(results))
            logging.info("Cached search result for key %s", cache_key)
        except Exception as e:
            logging.error("Failed to set cache: %s", e)

    # Filter the results based on allowed groups (if group_filter is provided).
    text_result = parse_search_results(results, group_filter)
    if not text_result:
        return "No results found", None

    total_hits = results.get("totalHits", 0)
    total_pages = results.get("totalPages", 1)
    current_page = results.get("page", page)
    markup = generate_navigation(current_page, total_pages)
    final_text = f"Total Hits: {total_hits}\n{text_result}"
    return final_text, markup


# ------------------- Handlers -------------------

@app.on_message(filters.command(["start"]))
def start_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    message.reply_text("Hello, I'm search bot.", quote=True)


@app.on_message(filters.command(["help"]))
def help_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    help_text = f"""
SearchGram Search syntax Help:
1. **Global search (private chat):** Send any message to the bot.
2. **Group search:** In an allowed group, use the `/search` command to search messages of that group.
3. **Chat type search:** `-t=GROUP keyword` (support types are {chat_types})
4. **Chat user search:** `-u=user_id|username keyword`
5. **Exact match:** `-m=e keyword` or directly add double-quotes `"keyword"`
6. Combine of above: `-t=GROUP -u=user_id|username keyword`
7. `/private [username] keyword`: search in private chat with username; if omitted, search in all private chats.
    """
    message.reply_text(help_text, quote=True)


@app.on_message(filters.command(["ping"]))
def ping_handler(client: "Client", message: "types.Message"):
    # Only the owner can use the ping command.
    if message.chat.id != int(OWNER_ID):
        return
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text = tgdb.ping()
    client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)


@app.on_message(filters.command(["delete"]))
def clean_handler(client: "Client", message: "types.Message"):
    # Only the owner can use the delete command.
    if message.chat.id != int(OWNER_ID):
        return
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text = tgdb.ping()
    client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)


# Existing search handlers (for non-command texts and chat type commands)
@app.on_message(filters.command(chat_types) & filters.text & filters.incoming)
def type_search_handler(client: "Client", message: "types.Message"):
    user_id = message.from_user.id
    # In private chat, if not owner, check allowed groups.
    if message.chat.type == "private":
        if user_id != int(OWNER_ID):
            user_groups = get_user_allowed_groups(client, user_id)
            if not user_groups:
                message.reply_text("You must join one of our groups to use the search feature. Please join one first.")
                return
            group_filter = user_groups
        else:
            group_filter = None  # Owner searches globally.
    else:
        # If the command is used in a group chat here, treat it as a group search.
        group_id_str = str(message.chat.id)
        if group_id_str not in ALLOWED_GROUP_IDS:
            message.reply_text("This group is not allowed for search.")
            return
        group_filter = group_id_str

    parts = message.text.split(maxsplit=2)
    chat_type = parts[0][1:].upper()
    if len(parts) == 1:
        message.reply_text(f"/{chat_type} [username] keyword", quote=True, parse_mode=enums.ParseMode.MARKDOWN)
        return
    if len(parts) > 2:
        user_filter_arg = f"-u={parts[1]}"
        keyword = parts[2]
    else:
        user_filter_arg = ""
        keyword = parts[1]

    refined_text = f"-t={chat_type} {user_filter_arg} {keyword}"
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text, markup = parse_and_search(refined_text, user_id=user_id, group_filter=group_filter)
    message.reply_text(
        text,
        quote=True,
        parse_mode=enums.ParseMode.MARKDOWN,
        reply_markup=markup,
        disable_web_page_preview=True
    )


@app.on_message(filters.text & filters.incoming)
def search_handler(client: "Client", message: "types.Message"):
    # This handler is for general text (not starting with a command) in private chats.
    # In a private chat, allow search if the user is allowed.
    if message.chat.type != "private":
        # Do not process plain text messages in groups here.
        return

    user_id = message.from_user.id
    if user_id != int(OWNER_ID):
        user_groups = get_user_allowed_groups(client, user_id)
        if not user_groups:
            message.reply_text("You must join one of our groups to use the search feature. Please join one first.")
            return
        group_filter = user_groups
    else:
        group_filter = None

    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text, markup = parse_and_search(message.text, user_id=user_id, group_filter=group_filter)
    if len(text) > 4096:
        logging.warning("Message too long, sending as file instead")
        file = BytesIO(text.encode())
        file.name = "search_result.txt"
        message.reply_text("Your search result is too long, sending as file instead", quote=True)
        message.reply_document(file, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup)
        file.close()
    else:
        message.reply_text(
            text,
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=markup,
            disable_web_page_preview=True
        )


# New /search command handler
@app.on_message(filters.command("search"))
def search_command_handler(client: "Client", message: "types.Message"):
    user_id = message.from_user.id
    # Determine the search context based on where the command was issued.
    if message.chat.type in ("group", "supergroup"):
        group_id_str = str(message.chat.id)
        if group_id_str not in ALLOWED_GROUP_IDS:
            message.reply_text("This group is not allowed for search.")
            return
        group_filter = group_id_str  # In-group search: restrict to this group.
    else:
        # In a private chat, if not owner, check allowed groups.
        if user_id != int(OWNER_ID):
            user_groups = get_user_allowed_groups(client, user_id)
            if not user_groups:
                message.reply_text("You must join one of our groups to use the search feature. Please join one first.")
                return
            group_filter = user_groups
        else:
            group_filter = None

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply_text("Usage: /search <query>")
        return
    query = parts[1]
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text, markup = parse_and_search(query, user_id=user_id, group_filter=group_filter)
    message.reply_text(
        text,
        quote=True,
        parse_mode=enums.ParseMode.MARKDOWN,
        reply_markup=markup,
        disable_web_page_preview=True
    )


# Callback query handler for pagination
@app.on_callback_query(filters.regex(r"^(n|p)\|"))
def send_method_callback(client: "Client", callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    # Determine search context based on the chat where the callback originated.
    if callback_query.message.chat.type in ("group", "supergroup"):
        group_id_str = str(callback_query.message.chat.id)
        if group_id_str not in ALLOWED_GROUP_IDS:
            callback_query.answer("This group is not allowed for search.", show_alert=True)
            return
        group_filter = group_id_str
    else:
        if user_id != int(OWNER_ID):
            user_groups = get_user_allowed_groups(client, user_id)
            if not user_groups:
                callback_query.answer("You must join one of our groups to use the search feature.", show_alert=True)
                return
            group_filter = user_groups
        else:
            group_filter = None

    direction, page_str = callback_query.data.split("|")
    page = int(page_str)
    if direction == "n":
        new_page = page + 1
    elif direction == "p":
        new_page = page - 1
    else:
        callback_query.answer("Invalid navigation direction.", show_alert=True)
        return

    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.text:
        user_query = callback_query.message.reply_to_message.text
    else:
        callback_query.answer("No original query found.", show_alert=True)
        return

    parts = user_query.split(maxsplit=2)
    if user_query.startswith("/"):
        user_filter_arg = f"-u={parts[1]}" if len(parts) > 2 else ""
        keyword = parts[2] if len(parts) > 2 else parts[1]
        refined_text = f"-t={parts[0][1:].upper()} {user_filter_arg} {keyword}"
    elif len(parts) == 1:
        refined_text = parts[0]
    else:
        refined_text = user_query

    client.send_chat_action(callback_query.message.chat.id, enums.ChatAction.TYPING)
    new_text, new_markup = parse_and_search(refined_text, page=new_page, user_id=user_id, group_filter=group_filter)
    try:
        callback_query.message.edit_text(new_text, reply_markup=new_markup, disable_web_page_preview=True)
    except Exception as e:
        logging.error("Failed to edit message: %s", e)
        callback_query.answer("Failed to update message.", show_alert=True)


if __name__ == "__main__":
    app.run()
