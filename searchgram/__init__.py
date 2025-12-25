#!/usr/bin/env python3
# coding: utf-8

# SearchGram - __init__.py
# 2023-11-18  16:26

from config_loader import ENGINE

AVAILABLE_ENGINES = ["meili", "mongo", "zinc", "elastic", "http"]

if ENGINE == "meili":
    print("Using MeiliSearch as search engine")
    from searchgram.meili import SearchEngine
elif ENGINE == "mongo":
    print("Using MongoDB as search engine")
    from searchgram.mongo import SearchEngine
elif ENGINE == "zinc":
    print("Using Zinc as search engine")
    from searchgram.zinc import SearchEngine
elif ENGINE == "elastic":
    print("Using Elasticsearch as search engine")
    from searchgram.elastic import SearchEngine
elif ENGINE == "http":
    print("Using HTTP (Go service) as search engine")
    from searchgram.http_engine import SearchEngine
else:
    raise ValueError(f"Unsupported engine {ENGINE}, available engines are {AVAILABLE_ENGINES}")
