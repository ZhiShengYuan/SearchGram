#!/usr/bin/env python3
# coding: utf-8

"""
SearchGram Client Runner

This script properly runs the SearchGram client (userbot) as a module.

Usage:
    python3 run_client.py
    # or
    ./run_client.py
"""

if __name__ == "__main__":
    # Import and run as module to ensure proper imports
    import runpy
    runpy.run_module("searchgram.client", run_name="__main__")
