#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - message_store.py
# Message queue storage for bot <-> userbot communication

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class MessageStore:
    """
    Thread-safe SQLite-based message queue for inter-service communication.

    Stores messages for relay between bot and userbot services.
    """

    def __init__(self, db_path: str = "message_queue.db"):
        """
        Initialize message store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()

        # Create database and tables
        self._init_db()

        logging.info(f"Message store initialized: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=10.0,
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                from_service TEXT NOT NULL,
                to_service TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                consumed INTEGER DEFAULT 0,
                consumed_at REAL
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_to_service
            ON messages(to_service, consumed, created_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_created_at
            ON messages(created_at)
        """)

        conn.commit()
        logging.info("Message store tables initialized")

    def enqueue(
        self,
        from_service: str,
        to_service: str,
        message_type: str,
        payload: Dict,
    ) -> Dict:
        """
        Enqueue a message for delivery.

        Args:
            from_service: Source service ("bot", "userbot", "search")
            to_service: Target service ("bot", "userbot", "search")
            message_type: Message type ("command", "info", "event", etc.)
            payload: Message payload (arbitrary JSON dict)

        Returns:
            Dict with id and created_at
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Generate unique ID
        message_id = str(uuid.uuid4())
        created_at = time.time()

        # Serialize payload
        payload_json = json.dumps(payload)

        # Insert message
        with self._lock:
            cursor.execute("""
                INSERT INTO messages (id, from_service, to_service, type, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, from_service, to_service, message_type, payload_json, created_at))

            conn.commit()

        logging.info(
            f"Enqueued message: {message_id} ({from_service} -> {to_service}, type={message_type})"
        )

        return {
            "id": message_id,
            "created_at": datetime.fromtimestamp(created_at).isoformat() + "Z",
        }

    def dequeue(
        self,
        to_service: str,
        after_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict:
        """
        Dequeue messages for a service.

        Args:
            to_service: Target service to get messages for
            after_id: Optional message ID to fetch messages after
            limit: Maximum number of messages to return

        Returns:
            Dict with items (list of messages) and next_after_id
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT id, from_service, to_service, type, payload, created_at
            FROM messages
            WHERE to_service = ? AND consumed = 0
        """
        params = [to_service]

        # Filter by after_id if provided
        if after_id:
            # Get timestamp of after_id
            cursor.execute("SELECT created_at FROM messages WHERE id = ?", (after_id,))
            row = cursor.fetchone()
            if row:
                after_timestamp = row[0]
                query += " AND created_at > ?"
                params.append(after_timestamp)

        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)

        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to list of dicts
        items = []
        for row in rows:
            items.append({
                "id": row["id"],
                "from": row["from_service"],
                "to": row["to_service"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "created_at": datetime.fromtimestamp(row["created_at"]).isoformat() + "Z",
            })

        # Determine next_after_id
        next_after_id = items[-1]["id"] if items else None

        logging.debug(
            f"Dequeued {len(items)} messages for {to_service} "
            f"(after_id={after_id}, next={next_after_id})"
        )

        return {
            "items": items,
            "next_after_id": next_after_id,
        }

    def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge (delete) a message.

        Args:
            message_id: Message ID to acknowledge

        Returns:
            True if message was deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        with self._lock:
            cursor.execute("""
                DELETE FROM messages WHERE id = ?
            """, (message_id,))

            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logging.debug(f"Acknowledged message: {message_id}")
        else:
            logging.warning(f"Message not found for acknowledgment: {message_id}")

        return deleted

    def cleanup_old_messages(self, max_age_hours: int = 24):
        """
        Clean up old consumed messages.

        Args:
            max_age_hours: Maximum age in hours (default: 24)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_timestamp = time.time() - (max_age_hours * 3600)

        with self._lock:
            cursor.execute("""
                DELETE FROM messages
                WHERE created_at < ?
            """, (cutoff_timestamp,))

            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logging.info(f"Cleaned up {deleted} old messages (older than {max_age_hours}h)")

        return deleted

    def get_stats(self) -> Dict:
        """Get message queue statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total messages
        cursor.execute("SELECT COUNT(*) FROM messages WHERE consumed = 0")
        total_pending = cursor.fetchone()[0]

        # Messages by target service
        cursor.execute("""
            SELECT to_service, COUNT(*) as count
            FROM messages
            WHERE consumed = 0
            GROUP BY to_service
        """)
        by_service = {row[0]: row[1] for row in cursor.fetchall()}

        # Oldest unconsumed message
        cursor.execute("""
            SELECT MIN(created_at) FROM messages WHERE consumed = 0
        """)
        oldest_timestamp = cursor.fetchone()[0]
        oldest_age = None
        if oldest_timestamp:
            oldest_age = int(time.time() - oldest_timestamp)

        return {
            "total_pending": total_pending,
            "by_service": by_service,
            "oldest_age_seconds": oldest_age,
        }

    def close(self):
        """Close database connection."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            delattr(self._local, "connection")


# Global message store instance
_message_store: Optional[MessageStore] = None


def get_message_store(db_path: str = "message_queue.db") -> MessageStore:
    """Get or create global message store instance."""
    global _message_store
    if _message_store is None:
        _message_store = MessageStore(db_path)
    return _message_store


if __name__ == "__main__":
    # Test message store
    logging.basicConfig(level=logging.INFO)

    print("Testing message store...")
    store = MessageStore("test_message_queue.db")

    # Enqueue messages
    print("\n1. Enqueueing messages...")
    msg1 = store.enqueue("bot", "userbot", "command", {"action": "sync", "chat_id": 123})
    print(f"   Enqueued: {msg1}")

    msg2 = store.enqueue("userbot", "bot", "info", {"status": "syncing", "progress": 50})
    print(f"   Enqueued: {msg2}")

    msg3 = store.enqueue("bot", "userbot", "command", {"action": "stop"})
    print(f"   Enqueued: {msg3}")

    # Dequeue messages
    print("\n2. Dequeueing messages for userbot...")
    result = store.dequeue("userbot", limit=10)
    print(f"   Got {len(result['items'])} messages:")
    for item in result["items"]:
        print(f"     - {item['id']}: {item['type']} from {item['from']}")
        print(f"       Payload: {item['payload']}")

    # Acknowledge first message
    print("\n3. Acknowledging first message...")
    if result["items"]:
        store.acknowledge(result["items"][0]["id"])
        print(f"   Acknowledged: {result['items'][0]['id']}")

    # Check stats
    print("\n4. Stats:")
    stats = store.get_stats()
    print(f"   Pending: {stats['total_pending']}")
    print(f"   By service: {stats['by_service']}")

    # Cleanup
    print("\n5. Cleaning up test database...")
    import os
    store.close()
    os.remove("test_message_queue.db")

    print("\n✅ Message store test passed!")
