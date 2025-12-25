#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - config.py
# 4/5/22 09:10
#

__author__ = "Benny <benny.think@gmail.com>"

import os

APP_ID = int(os.getenv("APP_ID", 321232123))
APP_HASH = os.getenv("APP_HASH", "23231321")
TOKEN = os.getenv("TOKEN", "1234")  # id:hash

######### search engine settings #########
# MeiliSearch, by default it's meili in docker-compose
MEILI_HOST = os.getenv("MEILI_HOST", "http://meili:7700")
# Using bot token for simplicity
MEILI_PASS = os.getenv("MEILI_MASTER_KEY", TOKEN)

# If you want to use MongoDB as search engine, you need to set this
MONGO_HOST = os.getenv("MONGO_HOST", "mongo")

# available values: meili, mongo, zinc, elastic, default: meili
ENGINE = os.getenv("ENGINE", "meili").lower()

# If you want to use Zinc as search engine, you need to set username and password
ZINC_HOST = os.getenv("ZINC_HOST", "http://zinc:4080")
ZINC_USER = os.getenv("ZINC_FIRST_ADMIN_USER", "root")
ZINC_PASS = os.getenv("ZINC_FIRST_ADMIN_PASSWORD", "root")

# If you want to use Elasticsearch as search engine, you need to set host and credentials
ELASTIC_HOST = os.getenv("ELASTIC_HOST", "http://elasticsearch:9200")
ELASTIC_USER = os.getenv("ELASTIC_USER", "elastic")
ELASTIC_PASS = os.getenv("ELASTIC_PASS", "changeme")

####################################
# Your own user id, for example: 260260121
OWNER_ID = os.getenv("OWNER_ID", "260260121")
BOT_ID = int(TOKEN.split(":")[0])

# Bot access control settings
# Modes: "private" (owner only), "group" (whitelisted groups), "public" (anyone)
BOT_MODE = os.getenv("BOT_MODE", "private").lower()

# Comma-separated list of group IDs where bot can work (for group mode)
# Example: "-1001234567890,-1009876543210"
ALLOWED_GROUPS = os.getenv("ALLOWED_GROUPS", "").split(",") if os.getenv("ALLOWED_GROUPS") else []
ALLOWED_GROUPS = [int(g.strip()) for g in ALLOWED_GROUPS if g.strip()]

# Comma-separated list of additional user IDs who can use the bot
# Example: "123456789,987654321"
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "").split(",") if os.getenv("ALLOWED_USERS") else []
ALLOWED_USERS = [int(u.strip()) for u in ALLOWED_USERS if u.strip()]

# Privacy settings
PRIVACY_STORAGE = os.getenv("PRIVACY_STORAGE", "privacy_data.json")

PROXY = os.getenv("PROXY")
# example proxy configuration
# PROXY = {"scheme": "socks5", "hostname": "localhost", "port": 1080}

IPv6 = bool(os.getenv("IPv6", False))
