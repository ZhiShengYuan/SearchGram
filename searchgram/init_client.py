#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - init_client.py
# 4/5/22 12:19
#

__author__ = "Benny <benny.think@gmail.com>"

import contextlib
import json
import os
import urllib.request
from pathlib import Path

from pyrogram import Client

from .config_loader import APP_HASH, APP_ID, PROXY, IPv6

# Get the directory where this file is located (searchgram/)
_PACKAGE_DIR = Path(__file__).parent
_SESSION_DIR = _PACKAGE_DIR / "session"

# Ensure session directory exists
_SESSION_DIR.mkdir(exist_ok=True)


def get_client(token=None):
    if isinstance(PROXY, str):
        proxy = json.loads(PROXY)
    else:
        proxy = PROXY
    app_device = dict(app_version=f"SearchGram/{get_revision()}", device_model="Firefox", proxy=proxy)

    # Use absolute paths for session files
    if token:
        session_path = str(_SESSION_DIR / "bot")
        return Client(session_path, APP_ID, APP_HASH, bot_token=token, ipv6=IPv6, **app_device)
    else:
        session_path = str(_SESSION_DIR / "client")
        return Client(session_path, APP_ID, APP_HASH, ipv6=IPv6, **app_device)


def get_revision():
    url = "https://api.github.com/repos/tgbot-collection/SearchGram/commits/master"
    with contextlib.suppress(Exception):
        return json.loads(urllib.request.urlopen(url).read())["sha"][:7]
    return "0.0.0"
