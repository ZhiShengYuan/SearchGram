#!/usr/bin/env python3
# coding: utf-8

# SearchGram - __init__.py
# 2023-11-18  16:26

from .config_loader import ENGINE

# Only HTTP search engine is supported (via Go microservice)
AVAILABLE_ENGINES = ["http"]

if ENGINE == "http":
    print("Using HTTP (Go service) search engine with JWT authentication")
    from .http_engine import SearchEngine
else:
    raise ValueError(
        f"Unsupported engine '{ENGINE}'. Only 'http' engine is supported.\n"
        f"Legacy engines (meili, mongo, zinc, elastic) have been removed.\n"
        f"Please update your config.json to use: \"engine\": \"http\""
    )
