#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - sync_manager.py
# Resume-capable history synchronization with checkpoint support

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from pyrogram import Client
from pyrogram.errors import FloodWait, ChannelPrivate, ChatAdminRequired

from .config_loader import (
    SYNC_BATCH_SIZE,
    SYNC_CHECKPOINT_FILE,
    SYNC_DELAY_BETWEEN_BATCHES,
    SYNC_ENABLED,
    SYNC_MAX_RETRIES,
    SYNC_RESUME_ON_RESTART,
    SYNC_RETRY_ON_ERROR,
)


class SyncProgress:
    """Tracks synchronization progress for a single chat."""

    def __init__(self, chat_id: int, total_count: int = 0):
        self.chat_id = chat_id
        self.total_count = total_count
        self.synced_count = 0
        self.last_message_id: Optional[int] = None
        self.status = "pending"  # pending, in_progress, completed, failed, paused
        self.error_count = 0
        self.last_error: Optional[str] = None
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.last_checkpoint: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "chat_id": self.chat_id,
            "total_count": self.total_count,
            "synced_count": self.synced_count,
            "last_message_id": self.last_message_id,
            "status": self.status,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "last_checkpoint": self.last_checkpoint,
            "progress_percent": round((self.synced_count / self.total_count * 100) if self.total_count > 0 else 0, 2)
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SyncProgress':
        """Create instance from dictionary."""
        progress = cls(data["chat_id"], data.get("total_count", 0))
        progress.synced_count = data.get("synced_count", 0)
        progress.last_message_id = data.get("last_message_id")
        progress.status = data.get("status", "pending")
        progress.error_count = data.get("error_count", 0)
        progress.last_error = data.get("last_error")
        progress.started_at = data.get("started_at")
        progress.completed_at = data.get("completed_at")
        progress.last_checkpoint = data.get("last_checkpoint")
        return progress


class SyncManager:
    """
    Manages history synchronization with resume capability.

    Features:
    - Checkpoint-based progress tracking
    - Resume from last position on restart
    - Batch processing with configurable size
    - Error handling with retry logic
    - FloodWait handling
    - Progress persistence to JSON
    - Sequential processing queue (only one chat synced at a time)
    """

    def __init__(self, client: Client, search_engine, checkpoint_file: str = None):
        self.client = client
        self.search_engine = search_engine
        self.checkpoint_file = checkpoint_file or SYNC_CHECKPOINT_FILE
        self.progress_map: Dict[int, SyncProgress] = {}
        self.lock = threading.Lock()
        self._load_checkpoint()

        # Worker thread for sequential processing
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._current_sync_chat_id: Optional[int] = None

    def _load_checkpoint(self):
        """Load progress from checkpoint file."""
        if not SYNC_RESUME_ON_RESTART or not os.path.exists(self.checkpoint_file):
            logging.info("No checkpoint file found or resume disabled, starting fresh sync")
            return

        try:
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)

            for chat_data in data.get("chats", []):
                progress = SyncProgress.from_dict(chat_data)
                # Only resume if not completed
                if progress.status != "completed":
                    progress.status = "pending"
                    self.progress_map[progress.chat_id] = progress
                    logging.info(
                        f"Resuming sync for chat {progress.chat_id}: "
                        f"{progress.synced_count}/{progress.total_count} messages synced"
                    )

            logging.info(f"Loaded checkpoint with {len(self.progress_map)} pending chats")

        except Exception as e:
            logging.error(f"Failed to load checkpoint: {e}")

    def _save_checkpoint(self):
        """Save progress to checkpoint file."""
        try:
            with self.lock:
                data = {
                    "last_updated": datetime.utcnow().isoformat(),
                    "chats": [progress.to_dict() for progress in self.progress_map.values()]
                }

            # Atomic write
            temp_file = f"{self.checkpoint_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, self.checkpoint_file)

            logging.debug(f"Checkpoint saved: {len(self.progress_map)} chats")

        except Exception as e:
            logging.error(f"Failed to save checkpoint: {e}")

    def add_chat(self, chat_id: int) -> bool:
        """
        Add a chat to the sync queue.

        Args:
            chat_id: Chat ID to sync

        Returns:
            bool: True if added, False if already exists
        """
        with self.lock:
            if chat_id in self.progress_map:
                existing = self.progress_map[chat_id]
                if existing.status == "completed":
                    logging.info(f"Chat {chat_id} already fully synced, re-adding")
                    # Reset for re-sync
                    self.progress_map[chat_id] = SyncProgress(chat_id)
                    return True
                else:
                    logging.info(f"Chat {chat_id} already in queue (status: {existing.status})")
                    return False
            else:
                self.progress_map[chat_id] = SyncProgress(chat_id)
                logging.info(f"Added chat {chat_id} to sync queue")
                return True

    def sync_chat(self, chat_id: int, progress_callback=None) -> bool:
        """
        Synchronize messages from a single chat.

        Args:
            chat_id: Chat ID to sync
            progress_callback: Optional callback function(progress: SyncProgress)

        Returns:
            bool: True if successful, False otherwise
        """
        with self.lock:
            if chat_id not in self.progress_map:
                self.add_chat(chat_id)
            progress = self.progress_map[chat_id]

        # Update status
        progress.status = "in_progress"
        progress.started_at = progress.started_at or datetime.utcnow().isoformat()
        self._save_checkpoint()

        try:
            # Get total message count if not already known
            if progress.total_count == 0:
                try:
                    progress.total_count = self.client.get_chat_history_count(chat_id)
                    logging.info(f"Chat {chat_id} has {progress.total_count} messages")
                except Exception as e:
                    logging.error(f"Failed to get message count for {chat_id}: {e}")
                    progress.last_error = str(e)
                    progress.status = "failed"
                    self._save_checkpoint()
                    return False

            # Calculate starting point for resume
            offset_id = progress.last_message_id if progress.last_message_id else 0
            remaining = progress.total_count - progress.synced_count

            logging.info(
                f"Starting sync for chat {chat_id}: "
                f"{remaining} messages remaining (offset_id: {offset_id})"
            )

            batch_count = 0
            error_in_batch = False
            message_batch = []

            # Check if engine supports batch insert
            supports_batch = hasattr(self.search_engine, 'upsert_batch')

            # Iterate through messages
            for message in self.client.get_chat_history(chat_id, offset_id=offset_id):
                try:
                    if supports_batch:
                        # Collect messages for batch insert
                        message_batch.append(message)
                        batch_count += 1

                        # Flush batch when threshold reached
                        if batch_count >= SYNC_BATCH_SIZE:
                            # Batch insert
                            result = self.search_engine.upsert_batch(message_batch)

                            # Update progress
                            progress.synced_count += result.get('indexed_count', len(message_batch))
                            progress.last_message_id = message_batch[-1].id
                            progress.last_checkpoint = datetime.utcnow().isoformat()

                            # Handle errors
                            if result.get('failed_count', 0) > 0:
                                progress.error_count += result['failed_count']
                                progress.last_error = f"Batch had {result['failed_count']} failures"

                            # Save checkpoint
                            self._save_checkpoint()
                            if progress_callback:
                                progress_callback(progress)

                            logging.info(
                                f"Chat {chat_id}: {progress.synced_count}/{progress.total_count} "
                                f"({progress.to_dict()['progress_percent']}%) - "
                                f"Batch: {result.get('indexed_count', 0)}/{len(message_batch)} indexed"
                            )

                            # Reset batch
                            message_batch = []
                            batch_count = 0

                            # Rate limiting: delay between batches to avoid FloodWait
                            if SYNC_DELAY_BETWEEN_BATCHES > 0:
                                logging.debug(f"Sleeping {SYNC_DELAY_BETWEEN_BATCHES}s between batches")
                                time.sleep(SYNC_DELAY_BETWEEN_BATCHES)
                    else:
                        # Fallback to individual insert
                        self.search_engine.upsert(message)

                        # Update progress
                        progress.synced_count += 1
                        progress.last_message_id = message.id
                        batch_count += 1

                        # Save checkpoint every batch
                        if batch_count >= SYNC_BATCH_SIZE:
                            progress.last_checkpoint = datetime.utcnow().isoformat()
                            self._save_checkpoint()
                            if progress_callback:
                                progress_callback(progress)

                            logging.info(
                                f"Chat {chat_id}: {progress.synced_count}/{progress.total_count} "
                                f"({progress.to_dict()['progress_percent']}%)"
                            )
                            batch_count = 0

                            # Rate limiting: delay between batches to avoid FloodWait
                            if SYNC_DELAY_BETWEEN_BATCHES > 0:
                                logging.debug(f"Sleeping {SYNC_DELAY_BETWEEN_BATCHES}s between batches")
                                time.sleep(SYNC_DELAY_BETWEEN_BATCHES)

                except FloodWait as e:
                    # Telegram rate limiting - wait and retry
                    logging.warning(f"FloodWait: sleeping for {e.value} seconds")
                    time.sleep(e.value)
                    continue

                except Exception as e:
                    logging.error(f"Error indexing message from chat {chat_id}: {e}")
                    progress.error_count += 1
                    progress.last_error = str(e)

                    if not SYNC_RETRY_ON_ERROR or progress.error_count >= SYNC_MAX_RETRIES:
                        error_in_batch = True
                        break

            # Flush remaining messages in batch
            if supports_batch and message_batch and not error_in_batch:
                try:
                    result = self.search_engine.upsert_batch(message_batch)
                    progress.synced_count += result.get('indexed_count', len(message_batch))
                    progress.last_message_id = message_batch[-1].id
                    progress.last_checkpoint = datetime.utcnow().isoformat()

                    if result.get('failed_count', 0) > 0:
                        progress.error_count += result['failed_count']

                    logging.info(f"Flushed final batch: {result.get('indexed_count', 0)} messages")
                except Exception as e:
                    logging.error(f"Error flushing final batch: {e}")
                    progress.error_count += len(message_batch)

            # Ensure buffered engine flushes all pending messages
            if hasattr(self.search_engine, 'flush'):
                logging.info(f"Flushing buffered messages for chat {chat_id}...")
                self.search_engine.flush()
                logging.info(f"Buffer flushed for chat {chat_id}")

            # Final checkpoint
            if not error_in_batch:
                progress.status = "completed"
                progress.completed_at = datetime.utcnow().isoformat()
                logging.info(f"✅ Chat {chat_id} sync completed: {progress.synced_count} messages")
            else:
                progress.status = "failed"
                logging.error(f"❌ Chat {chat_id} sync failed after {progress.error_count} errors")

            self._save_checkpoint()
            if progress_callback:
                progress_callback(progress)

            return progress.status == "completed"

        except ChannelPrivate:
            logging.error(f"Chat {chat_id} is private or not accessible")
            progress.status = "failed"
            progress.last_error = "Channel is private or not accessible"
            self._save_checkpoint()
            return False

        except ChatAdminRequired:
            logging.error(f"Admin rights required for chat {chat_id}")
            progress.status = "failed"
            progress.last_error = "Admin rights required"
            self._save_checkpoint()
            return False

        except FloodWait as e:
            logging.warning(f"FloodWait on chat {chat_id}, pausing sync for {e.value} seconds")
            progress.status = "paused"
            progress.last_error = f"FloodWait: {e.value}s"
            self._save_checkpoint()
            time.sleep(e.value)
            # Retry after waiting
            return self.sync_chat(chat_id, progress_callback)

        except Exception as e:
            logging.error(f"Unexpected error syncing chat {chat_id}: {e}")
            progress.status = "failed"
            progress.last_error = str(e)
            progress.error_count += 1
            self._save_checkpoint()
            return False

    def sync_all(self, progress_callback=None) -> Dict[int, bool]:
        """
        Synchronize all chats in the queue.

        Args:
            progress_callback: Optional callback function(progress: SyncProgress)

        Returns:
            Dict mapping chat_id to success status
        """
        results = {}

        with self.lock:
            pending_chats = [
                chat_id for chat_id, progress in self.progress_map.items()
                if progress.status in ("pending", "paused")
            ]

        logging.info(f"Starting sync for {len(pending_chats)} chats")

        for chat_id in pending_chats:
            success = self.sync_chat(chat_id, progress_callback)
            results[chat_id] = success

        return results

    def get_progress(self, chat_id: int) -> Optional[SyncProgress]:
        """Get progress for a specific chat."""
        with self.lock:
            return self.progress_map.get(chat_id)

    def get_all_progress(self) -> List[SyncProgress]:
        """Get progress for all chats."""
        with self.lock:
            return list(self.progress_map.values())

    def pause_chat(self, chat_id: int) -> bool:
        """
        Pause a sync task for a specific chat.

        Args:
            chat_id: Chat ID to pause

        Returns:
            bool: True if paused, False if not found or invalid state
        """
        with self.lock:
            if chat_id not in self.progress_map:
                logging.warning(f"Cannot pause chat {chat_id}: not in sync queue")
                return False

            progress = self.progress_map[chat_id]

            if progress.status in ("pending", "in_progress"):
                progress.status = "paused"
                self._save_checkpoint()
                logging.info(f"Paused sync for chat {chat_id}")
                return True
            else:
                logging.warning(f"Cannot pause chat {chat_id}: status is {progress.status}")
                return False

    def resume_chat(self, chat_id: int) -> bool:
        """
        Resume a paused sync task for a specific chat.

        Args:
            chat_id: Chat ID to resume

        Returns:
            bool: True if resumed, False if not found or invalid state
        """
        with self.lock:
            if chat_id not in self.progress_map:
                logging.warning(f"Cannot resume chat {chat_id}: not in sync queue")
                return False

            progress = self.progress_map[chat_id]

            if progress.status == "paused":
                progress.status = "pending"
                self._save_checkpoint()
                logging.info(f"Resumed sync for chat {chat_id}")
                return True
            else:
                logging.warning(f"Cannot resume chat {chat_id}: status is {progress.status}")
                return False

    def clear_completed(self):
        """Remove completed chats from the queue."""
        with self.lock:
            self.progress_map = {
                chat_id: progress
                for chat_id, progress in self.progress_map.items()
                if progress.status != "completed"
            }
        self._save_checkpoint()
        logging.info("Cleared completed chats from sync queue")

    def get_summary(self) -> dict:
        """Get summary statistics."""
        with self.lock:
            total = len(self.progress_map)
            completed = sum(1 for p in self.progress_map.values() if p.status == "completed")
            in_progress = sum(1 for p in self.progress_map.values() if p.status == "in_progress")
            failed = sum(1 for p in self.progress_map.values() if p.status == "failed")
            pending = sum(1 for p in self.progress_map.values() if p.status == "pending")

            total_messages = sum(p.total_count for p in self.progress_map.values())
            synced_messages = sum(p.synced_count for p in self.progress_map.values())

            return {
                "total_chats": total,
                "completed": completed,
                "in_progress": in_progress,
                "failed": failed,
                "pending": pending,
                "total_messages": total_messages,
                "synced_messages": synced_messages,
                "progress_percent": round((synced_messages / total_messages * 100) if total_messages > 0 else 0, 2)
            }

    def _sync_worker(self):
        """
        Worker thread that processes the sync queue sequentially.
        Only one chat is synced at a time to avoid rate limiting.
        """
        logging.info("Sync worker thread started")

        while self._running:
            try:
                # Find next pending chat to sync
                next_chat_id = None

                with self.lock:
                    for chat_id, progress in self.progress_map.items():
                        if progress.status == "pending":
                            next_chat_id = chat_id
                            break

                if next_chat_id:
                    # Sync this chat
                    logging.info(f"Worker thread starting sync for chat {next_chat_id}")
                    self._current_sync_chat_id = next_chat_id

                    try:
                        self.sync_chat(next_chat_id)
                    except Exception as e:
                        logging.error(f"Worker thread error syncing chat {next_chat_id}: {e}")

                    self._current_sync_chat_id = None
                else:
                    # No pending chats, sleep for a bit
                    time.sleep(1)

            except Exception as e:
                logging.error(f"Sync worker thread error: {e}")
                time.sleep(5)  # Sleep longer on error

        logging.info("Sync worker thread stopped")

    def start_worker(self):
        """Start the background worker thread for sequential sync processing."""
        if self._running:
            logging.warning("Sync worker already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._sync_worker, daemon=True, name="SyncWorker")
        self._worker_thread.start()
        logging.info("Sync worker thread started successfully")

    def stop_worker(self):
        """Stop the background worker thread."""
        if not self._running:
            logging.warning("Sync worker not running")
            return

        logging.info("Stopping sync worker thread...")
        self._running = False

        if self._worker_thread:
            self._worker_thread.join(timeout=10)
            if self._worker_thread.is_alive():
                logging.warning("Sync worker thread did not stop gracefully")
            else:
                logging.info("Sync worker thread stopped successfully")

    def is_worker_running(self) -> bool:
        """Check if the worker thread is running."""
        return self._running and self._worker_thread and self._worker_thread.is_alive()

    def get_current_sync_chat(self) -> Optional[int]:
        """Get the chat ID currently being synced, if any."""
        return self._current_sync_chat_id


if __name__ == "__main__":
    # Test sync manager
    print("SyncManager test - requires running client")
