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

from __init__ import SearchEngine
from config import OWNER_ID, TOKEN
from init_client import get_client
from utils import setup_logger

tgdb = SearchEngine()

setup_logger()
app = get_client(TOKEN)
chat_types = [i for i in dir(enums.ChatType) if not i.startswith("_")]
parser = argparse.ArgumentParser()
parser.add_argument("keyword", help="the keyword to be searched")
parser.add_argument("-t", "--type", help="the type of message", default=None)
parser.add_argument("-u", "--user", help="the user who sent the message", default=None)
parser.add_argument("-m", "--mode", help="match mode, e: exact match, other value is fuzzy search", default=None)


def private_use(func):
    def wrapper(client: "Client", message: "types.Message"):
        chat_id = getattr(message.chat, "id", None)
        if str(chat_id) not in str(OWNER_ID):
            logging.warning("Unauthorized user or not in a group: %s", chat_id)
            return
        return func(client, message)

    return wrapper

@app.on_message(filters.command(["start"]))
def search_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    message.reply_text("Hello, I'm search bot.", quote=True)


@app.on_message(filters.command(["help"]))
def help_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    help_text = f"""
usage: /search search the message from TUNA
    """
    message.reply_text(help_text, quote=True)


@app.on_message(filters.command(["ping"]))
@private_use
def ping_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text = tgdb.ping()
    client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)


@app.on_message(filters.command(["delete"]))
@private_use
def clean_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text = tgdb.ping()
    client.send_message(message.chat.id, text, parse_mode=enums.ParseMode.MARKDOWN)


def get_name(chat: dict):
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
        chat_username = get_name(hit["chat"])
        from_username = get_name(hit.get("from_user") or hit["sender_chat"])
        date = hit["date"]
        outgoing = hit["outgoing"]
        username = hit["chat"].get("username")
        # https://corefork.telegram.org/api/links
        deep_link = f"tg://resolve?domain={username}" if username else "tg://"

        if outgoing:
            result += f"{from_username}-> [{chat_username}]({deep_link}) on {date}: \n`{text}`\n\n"
        else:
            result += f"[{chat_username}]({deep_link}) -> me on {date}: \n`{text}`\n\n"
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


def parse_and_search(text, page=1) -> Tuple[str, InlineKeyboardMarkup | None]:
    # return text and markup
    args = parser.parse_args(text.split())
    _type = args.type
    user = args.user
    keyword = args.keyword
    mode = args.mode
    logging.info("Search keyword: %s, type: %s, user: %s, page: %s, mode: %s", keyword, _type, user, page, mode)
    results = tgdb.search(keyword, _type, user, page, mode)
    text = parse_search_results(results)
    if not text:
        return "No results found", None

    total_hits = results["totalHits"]
    total_pages = results["totalPages"]
    page = results["page"]
    markup = generate_navigation(page, total_pages)
    return f"Total Hits: {total_hits}\n{text}", markup


@app.on_message(filters.command(chat_types) & filters.text & filters.incoming)
@private_use
def type_search_handler(client: "Client", message: "types.Message"):
    parts = message.text.split(maxsplit=2)
    chat_type = parts[0][1:].upper()
    if len(parts) == 1:
        message.reply_text(f"/{chat_type} [username] keyword", quote=True, parse_mode=enums.ParseMode.MARKDOWN)
        return
    if len(parts) > 2:
        keyword = parts[2]
    else:
        keyword = parts[1]

    refined_text = f"-t=group -u={message.chat.id} {keyword} "

    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text, markup = parse_and_search(refined_text)
    message.reply_text(text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup)


@app.on_message(filters.text & filters.incoming)
@private_use
def search_handler(client: "Client", message: "types.Message"):
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    text, markup = parse_and_search(message.text)
    if len(text) > 3072:
        logging.warning("Message too long, sending as file instead")
        file = BytesIO(text.encode())
        file.name = "search_result.txt"
        message.reply_text("Your search result is too long, sending as file instead", quote=True)
        message.reply_document(file, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup)
        file.close()
    else:
        message.reply_text(text, quote=True, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=markup)


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
    user_query = message.reply_to_message.text
    if user_query.startswith("/search"):
        parts = user_query.split(maxsplit=2)
        refined_text = parts[1]
        
    client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    new_text, new_markup = parse_and_search(refined_text, new_page)
    message.edit_text(new_text, reply_markup=new_markup)


if __name__ == "__main__":
    app.run()
