#!/usr/bin/env python3
# coding: utf-8

"""
SearchGram Bot Runner

This script properly runs the SearchGram bot as a module.

Usage:
    python3 run_bot.py
    # or
    ./run_bot.py
"""

if __name__ == "__main__":
    # Import and run as module to ensure proper imports
    import runpy
    runpy.run_module("searchgram.bot", run_name="__main__")
