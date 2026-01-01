#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - time_utils.py
# Time window parsing utilities for stats commands

__author__ = "Benny <benny.think@gmail.com>"

import re
from datetime import datetime, timedelta
from typing import Tuple


def parse_time_window(window_str: str) -> Tuple[int, int]:
    """
    Parse a time window string into (from_timestamp, to_timestamp).

    Supported formats:
    - Relative: "7d", "30d", "90d", "365d", "1y", "2y"
    - Date range: "2025-01-01..2025-12-31"

    Args:
        window_str: Time window string

    Returns:
        Tuple of (from_timestamp, to_timestamp) as Unix timestamps

    Raises:
        ValueError: If format is invalid
    """
    window_str = window_str.strip()

    # Date range format: YYYY-MM-DD..YYYY-MM-DD
    if ".." in window_str:
        parts = window_str.split("..")
        if len(parts) != 2:
            raise ValueError("Invalid date range format. Use: YYYY-MM-DD..YYYY-MM-DD")

        try:
            from_date = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
            to_date = datetime.strptime(parts[1].strip(), "%Y-%m-%d")

            # Set to end of day for to_date
            to_date = to_date.replace(hour=23, minute=59, second=59)

            if from_date > to_date:
                raise ValueError("Start date must be before end date")

            return int(from_date.timestamp()), int(to_date.timestamp())
        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError("Invalid date format. Use: YYYY-MM-DD")
            raise

    # Relative format: Nd or Ny (days or years)
    match = re.match(r'^(\d+)([dy])$', window_str.lower())
    if not match:
        raise ValueError(
            "Invalid time window format. Use: 7d, 30d, 1y, or 2025-01-01..2025-12-31"
        )

    amount = int(match.group(1))
    unit = match.group(2)

    now = datetime.now()
    if unit == 'd':
        from_date = now - timedelta(days=amount)
    elif unit == 'y':
        from_date = now - timedelta(days=amount * 365)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")

    return int(from_date.timestamp()), int(now.timestamp())


def format_time_window(from_timestamp: int, to_timestamp: int) -> str:
    """
    Format timestamps into a human-readable string.

    Args:
        from_timestamp: Start timestamp
        to_timestamp: End timestamp

    Returns:
        Formatted string like "last 30 days" or "2025-01-01 to 2025-12-31"
    """
    from_date = datetime.fromtimestamp(from_timestamp)
    to_date = datetime.fromtimestamp(to_timestamp)

    # Check if it's a relative window (ending approximately now)
    now = datetime.now()
    if abs((to_date - now).total_seconds()) < 86400:  # Within 1 day
        days = (to_date - from_date).days
        if days < 2:
            return "last 24 hours"
        elif days == 7:
            return "last 7 days"
        elif days == 30:
            return "last 30 days"
        elif days == 90:
            return "last 90 days"
        elif days >= 365 and days <= 366:
            return "last 1 year"
        else:
            return f"last {days} days"

    # Otherwise, show date range
    return f"{from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"
