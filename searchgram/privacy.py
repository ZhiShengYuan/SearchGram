#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - privacy.py
# Privacy control system for user opt-out

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
import os
import threading
from datetime import datetime
from typing import List, Set

from config_loader import PRIVACY_STORAGE


class PrivacyManager:
    """
    Manages user privacy settings and opt-out preferences.

    Features:
    - User opt-out/opt-in for search results
    - Persistent storage of privacy preferences
    - Thread-safe operations
    - Automatic file-based persistence
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or PRIVACY_STORAGE
        self._blocked_users: Set[int] = set()
        self._lock = threading.Lock()
        self._load_from_storage()

    def _load_from_storage(self):
        """Load blocked users from persistent storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    self._blocked_users = set(data.get("blocked_users", []))
                    logging.info("Loaded %d blocked users from storage", len(self._blocked_users))
            except Exception as e:
                logging.error("Failed to load privacy data: %s", e)
                self._blocked_users = set()
        else:
            logging.info("No existing privacy data found, starting fresh")

    def _save_to_storage(self):
        """Save blocked users to persistent storage."""
        try:
            data = {
                "blocked_users": list(self._blocked_users),
                "last_updated": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
            # Write to temporary file first, then rename (atomic operation)
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, self.storage_path)
            logging.debug("Privacy data saved successfully")
        except Exception as e:
            logging.error("Failed to save privacy data: %s", e)

    def block_user(self, user_id: int) -> bool:
        """
        Block a user from appearing in search results.

        Args:
            user_id: Telegram user ID to block

        Returns:
            bool: True if user was newly blocked, False if already blocked
        """
        with self._lock:
            was_new = user_id not in self._blocked_users
            self._blocked_users.add(user_id)
            if was_new:
                self._save_to_storage()
                logging.info("User %d opted out of search results", user_id)
            return was_new

    def unblock_user(self, user_id: int) -> bool:
        """
        Unblock a user, allowing them to appear in search results again.

        Args:
            user_id: Telegram user ID to unblock

        Returns:
            bool: True if user was unblocked, False if wasn't blocked
        """
        with self._lock:
            was_blocked = user_id in self._blocked_users
            self._blocked_users.discard(user_id)
            if was_blocked:
                self._save_to_storage()
                logging.info("User %d opted back into search results", user_id)
            return was_blocked

    def is_blocked(self, user_id: int) -> bool:
        """
        Check if a user is blocked from search results.

        Args:
            user_id: Telegram user ID to check

        Returns:
            bool: True if user is blocked, False otherwise
        """
        with self._lock:
            return user_id in self._blocked_users

    def get_blocked_users(self) -> List[int]:
        """
        Get list of all blocked user IDs.

        Returns:
            List[int]: List of blocked user IDs
        """
        with self._lock:
            return list(self._blocked_users)

    def get_blocked_count(self) -> int:
        """
        Get count of blocked users.

        Returns:
            int: Number of blocked users
        """
        with self._lock:
            return len(self._blocked_users)

    def filter_search_results(self, results: dict) -> dict:
        """
        Filter search results to exclude messages from blocked users.

        Args:
            results: Search results dict with 'hits' key

        Returns:
            dict: Filtered results with blocked users removed
        """
        if not self._blocked_users:
            return results

        with self._lock:
            blocked_users = self._blocked_users.copy()

        # Filter hits
        original_hits = results.get("hits", [])
        filtered_hits = []

        for hit in original_hits:
            # Check from_user ID
            from_user = hit.get("from_user") or {}
            from_user_id = from_user.get("id")

            # Also check sender_chat for channel posts
            sender_chat = hit.get("sender_chat") or {}
            sender_chat_id = sender_chat.get("id")

            # Skip if sender is blocked
            if from_user_id in blocked_users or sender_chat_id in blocked_users:
                logging.debug("Filtered out message from blocked user %s", from_user_id or sender_chat_id)
                continue

            filtered_hits.append(hit)

        # Update counts
        removed_count = len(original_hits) - len(filtered_hits)
        results["hits"] = filtered_hits
        results["totalHits"] = max(0, results.get("totalHits", 0) - removed_count)

        # Recalculate total pages if needed
        hits_per_page = results.get("hitsPerPage", 10)
        if hits_per_page > 0:
            import math
            results["totalPages"] = math.ceil(results["totalHits"] / hits_per_page)

        if removed_count > 0:
            logging.info("Filtered %d messages from blocked users", removed_count)

        return results


# Global privacy manager instance
privacy_manager = PrivacyManager()


def filter_results(results: dict) -> dict:
    """
    Convenience function to filter search results.

    Args:
        results: Search results dict

    Returns:
        dict: Filtered results
    """
    return privacy_manager.filter_search_results(results)


if __name__ == "__main__":
    # Test the privacy manager
    pm = PrivacyManager("test_privacy.json")
    print(f"Blocked users: {pm.get_blocked_count()}")

    # Block some users
    pm.block_user(123456)
    pm.block_user(789012)
    print(f"Blocked users: {pm.get_blocked_users()}")

    # Check status
    print(f"Is 123456 blocked? {pm.is_blocked(123456)}")
    print(f"Is 999999 blocked? {pm.is_blocked(999999)}")

    # Unblock
    pm.unblock_user(123456)
    print(f"Blocked users after unblock: {pm.get_blocked_users()}")

    # Test filtering
    mock_results = {
        "hits": [
            {"from_user": {"id": 789012}, "text": "This should be filtered"},
            {"from_user": {"id": 111111}, "text": "This should remain"},
        ],
        "totalHits": 2,
        "totalPages": 1,
        "hitsPerPage": 10
    }
    filtered = pm.filter_search_results(mock_results)
    print(f"Filtered results: {len(filtered['hits'])} hits")
