#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - db_manager.py
# SQLite database manager for query logs and admin settings

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DatabaseManager:
    """
    Manages SQLite database for query logs and admin settings.
    Thread-safe with connection pooling per thread.
    """

    def __init__(self, db_path: str = "searchgram_logs.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._initialize_database()
        logging.info(f"Database manager initialized: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    @contextmanager
    def _get_cursor(self):
        """Context manager for database cursor with auto-commit."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()

    def _initialize_database(self):
        """Create database tables if they don't exist."""
        with self._lock:
            with self._get_cursor() as cursor:
                # Query logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS query_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        user_id INTEGER NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        chat_id INTEGER NOT NULL,
                        chat_type TEXT NOT NULL,
                        query TEXT NOT NULL,
                        search_type TEXT,
                        search_user TEXT,
                        search_mode TEXT,
                        results_count INTEGER,
                        page_number INTEGER DEFAULT 1,
                        processing_time_ms INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Index for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp
                    ON query_logs(timestamp DESC)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query_logs_user_id
                    ON query_logs(user_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query_logs_chat_id
                    ON query_logs(chat_id)
                """)

                # Admin settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS admin_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        value_type TEXT NOT NULL,
                        description TEXT,
                        updated_at REAL NOT NULL,
                        updated_by INTEGER NOT NULL
                    )
                """)

                # Initialize default settings if not exist
                self._initialize_default_settings(cursor)

    def _initialize_default_settings(self, cursor):
        """Initialize default admin settings."""
        default_settings = [
            ("enable_query_logging", "true", "bool", "Enable query logging", time.time(), 0),
            ("log_retention_days", "30", "int", "Days to keep query logs", time.time(), 0),
            ("max_log_entries", "100000", "int", "Maximum log entries to keep", time.time(), 0),
            ("auto_cleanup_enabled", "true", "bool", "Enable automatic log cleanup", time.time(), 0),
        ]

        for key, value, value_type, description, updated_at, updated_by in default_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO admin_settings (key, value, value_type, description, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (key, value, value_type, description, updated_at, updated_by))

    def log_query(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        chat_id: int,
        chat_type: str,
        query: str,
        search_type: Optional[str] = None,
        search_user: Optional[str] = None,
        search_mode: Optional[str] = None,
        results_count: int = 0,
        page_number: int = 1,
        processing_time_ms: int = 0
    ) -> int:
        """
        Log a search query to database.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            chat_id: Chat ID where query was made
            chat_type: Chat type (PRIVATE, GROUP, etc.)
            query: Search query text
            search_type: Type filter (GROUP, CHANNEL, etc.)
            search_user: User filter
            search_mode: Match mode (exact/fuzzy)
            results_count: Number of results returned
            page_number: Page number requested
            processing_time_ms: Query processing time in milliseconds

        Returns:
            ID of inserted log entry
        """
        # Check if logging is enabled
        if not self.get_setting("enable_query_logging", True):
            return -1

        timestamp = time.time()

        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO query_logs (
                    timestamp, user_id, username, first_name, chat_id, chat_type,
                    query, search_type, search_user, search_mode,
                    results_count, page_number, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, user_id, username, first_name, chat_id, chat_type,
                query, search_type, search_user, search_mode,
                results_count, page_number, processing_time_ms
            ))

            log_id = cursor.lastrowid
            logging.debug(f"Logged query #{log_id}: user={user_id}, query='{query}', results={results_count}")
            return log_id

    def get_recent_logs(self, limit: int = 100, user_id: Optional[int] = None) -> List[Dict]:
        """
        Get recent query logs.

        Args:
            limit: Maximum number of logs to return
            user_id: Filter by user ID (optional)

        Returns:
            List of log entries as dictionaries
        """
        with self._get_cursor() as cursor:
            if user_id:
                cursor.execute("""
                    SELECT * FROM query_logs
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM query_logs
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get logs within a date range.

        Args:
            start_date: Start datetime
            end_date: End datetime
            user_id: Filter by user ID (optional)

        Returns:
            List of log entries
        """
        start_timestamp = start_date.timestamp()
        end_timestamp = end_date.timestamp()

        with self._get_cursor() as cursor:
            if user_id:
                cursor.execute("""
                    SELECT * FROM query_logs
                    WHERE timestamp BETWEEN ? AND ? AND user_id = ?
                    ORDER BY timestamp DESC
                """, (start_timestamp, end_timestamp, user_id))
            else:
                cursor.execute("""
                    SELECT * FROM query_logs
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                """, (start_timestamp, end_timestamp))

            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get query log statistics.

        Returns:
            Dictionary with statistics
        """
        with self._get_cursor() as cursor:
            # Total queries
            cursor.execute("SELECT COUNT(*) as total FROM query_logs")
            total = cursor.fetchone()['total']

            # Queries by user (top 10)
            cursor.execute("""
                SELECT user_id, username, first_name, COUNT(*) as count
                FROM query_logs
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 10
            """)
            top_users = [dict(row) for row in cursor.fetchall()]

            # Queries by chat type
            cursor.execute("""
                SELECT chat_type, COUNT(*) as count
                FROM query_logs
                GROUP BY chat_type
                ORDER BY count DESC
            """)
            by_chat_type = [dict(row) for row in cursor.fetchall()]

            # Recent 24h stats
            yesterday = time.time() - 86400
            cursor.execute("""
                SELECT COUNT(*) as count_24h
                FROM query_logs
                WHERE timestamp > ?
            """, (yesterday,))
            count_24h = cursor.fetchone()['count_24h']

            # Average results per query
            cursor.execute("""
                SELECT AVG(results_count) as avg_results,
                       AVG(processing_time_ms) as avg_time_ms
                FROM query_logs
                WHERE results_count > 0
            """)
            averages = dict(cursor.fetchone())

            return {
                "total_queries": total,
                "queries_24h": count_24h,
                "top_users": top_users,
                "by_chat_type": by_chat_type,
                "avg_results_per_query": round(averages.get('avg_results', 0), 2),
                "avg_processing_time_ms": round(averages.get('avg_time_ms', 0), 2)
            }

    def cleanup_old_logs(self, days: Optional[int] = None) -> int:
        """
        Delete logs older than specified days.

        Args:
            days: Number of days to keep (uses setting if None)

        Returns:
            Number of deleted entries
        """
        if days is None:
            days = self.get_setting("log_retention_days", 30)

        cutoff_timestamp = time.time() - (days * 86400)

        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM query_logs WHERE timestamp < ?", (cutoff_timestamp,))
            deleted = cursor.rowcount
            logging.info(f"Cleaned up {deleted} old log entries (>{days} days)")
            return deleted

    def cleanup_excess_logs(self, max_entries: Optional[int] = None) -> int:
        """
        Delete oldest logs if total exceeds max entries.

        Args:
            max_entries: Maximum entries to keep (uses setting if None)

        Returns:
            Number of deleted entries
        """
        if max_entries is None:
            max_entries = self.get_setting("max_log_entries", 100000)

        with self._get_cursor() as cursor:
            # Count total entries
            cursor.execute("SELECT COUNT(*) as total FROM query_logs")
            total = cursor.fetchone()['total']

            if total <= max_entries:
                return 0

            # Delete oldest entries beyond max
            to_delete = total - max_entries
            cursor.execute("""
                DELETE FROM query_logs
                WHERE id IN (
                    SELECT id FROM query_logs
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
            """, (to_delete,))
            deleted = cursor.rowcount
            logging.info(f"Cleaned up {deleted} excess log entries (total was {total})")
            return deleted

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get admin setting value.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value converted to appropriate type
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT value, value_type FROM admin_settings WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row is None:
                return default

            value = row['value']
            value_type = row['value_type']

            # Convert to appropriate type
            if value_type == 'bool':
                return value.lower() in ('true', '1', 'yes', 'on')
            elif value_type == 'int':
                return int(value)
            elif value_type == 'float':
                return float(value)
            elif value_type == 'json':
                return json.loads(value)
            else:
                return value

    def set_setting(self, key: str, value: Any, updated_by: int, description: str = "") -> bool:
        """
        Set admin setting value.

        Args:
            key: Setting key
            value: Setting value
            updated_by: User ID who updated the setting
            description: Setting description

        Returns:
            True if successful
        """
        # Determine value type
        if isinstance(value, bool):
            value_type = 'bool'
            value_str = 'true' if value else 'false'
        elif isinstance(value, int):
            value_type = 'int'
            value_str = str(value)
        elif isinstance(value, float):
            value_type = 'float'
            value_str = str(value)
        elif isinstance(value, (dict, list)):
            value_type = 'json'
            value_str = json.dumps(value)
        else:
            value_type = 'str'
            value_str = str(value)

        timestamp = time.time()

        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO admin_settings (key, value, value_type, description, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (key, value_str, value_type, description, timestamp, updated_by))

            logging.info(f"Setting updated: {key}={value_str} by user {updated_by}")
            return True

    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all admin settings.

        Returns:
            Dictionary of settings with metadata
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM admin_settings ORDER BY key")
            settings = {}
            for row in cursor.fetchall():
                key = row['key']
                settings[key] = {
                    'value': self.get_setting(key),
                    'value_type': row['value_type'],
                    'description': row['description'],
                    'updated_at': row['updated_at'],
                    'updated_by': row['updated_by']
                }
            return settings

    def search_logs(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search logs by query text.

        Args:
            query: Search term
            limit: Maximum results

        Returns:
            List of matching log entries
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM query_logs
                WHERE query LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (f'%{query}%', limit))

            return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_path: str = "searchgram_logs.db") -> DatabaseManager:
    """Get or create global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager


if __name__ == "__main__":
    # Test database manager
    logging.basicConfig(level=logging.INFO)

    db = DatabaseManager("test_logs.db")

    # Test logging
    print("\n=== Testing Query Logging ===")
    log_id = db.log_query(
        user_id=12345,
        username="testuser",
        first_name="Test",
        chat_id=-1001234567890,
        chat_type="GROUP",
        query="test search",
        search_type="GROUP",
        results_count=5,
        processing_time_ms=150
    )
    print(f"Logged query with ID: {log_id}")

    # Test settings
    print("\n=== Testing Settings ===")
    db.set_setting("test_setting", True, updated_by=12345, description="Test boolean setting")
    print(f"test_setting = {db.get_setting('test_setting')}")

    # Test statistics
    print("\n=== Testing Statistics ===")
    stats = db.get_statistics()
    print(f"Total queries: {stats['total_queries']}")

    # Test recent logs
    print("\n=== Testing Recent Logs ===")
    logs = db.get_recent_logs(limit=5)
    print(f"Found {len(logs)} recent logs")

    # Cleanup
    db.close()
    Path("test_logs.db").unlink(missing_ok=True)
    print("\n✅ All tests passed!")
