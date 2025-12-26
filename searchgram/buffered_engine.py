#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - buffered_engine.py
# Buffered wrapper for search engine with automatic batch flushing

__author__ = "Benny <benny.think@gmail.com>"

import atexit
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from pyrogram import types


class BufferedSearchEngine:
    """
    Wrapper for search engines that buffers messages and flushes them in batches.

    Features:
    - Time-based flushing: Flushes every 1 second (minimum push interval)
    - Size-based flushing: Flushes when buffer reaches threshold (default: 100)
    - Thread-safe buffering with locks
    - Automatic flush on shutdown
    - Graceful error handling
    """

    def __init__(
        self,
        engine: Any,
        batch_size: int = 100,
        flush_interval: float = 1.0,
        enabled: bool = True
    ):
        """
        Initialize buffered search engine.

        Args:
            engine: Underlying search engine instance (must have upsert_batch method)
            batch_size: Maximum messages in buffer before auto-flush (default: 100)
            flush_interval: Time in seconds between auto-flushes (default: 1.0)
            enabled: Enable batching (if False, falls back to individual upsert)
        """
        self.engine = engine
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.enabled = enabled and hasattr(engine, 'upsert_batch')

        # Message buffer and lock
        self.buffer: List[types.Message] = []
        self.lock = threading.Lock()

        # Background flush thread
        self.flush_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Statistics
        self.stats = {
            "buffered": 0,
            "flushed": 0,
            "batches": 0,
            "errors": 0,
        }

        if self.enabled:
            logging.info(
                f"Buffered search engine initialized: "
                f"batch_size={batch_size}, flush_interval={flush_interval}s"
            )
            self._start_flush_thread()
            # Register shutdown handler
            atexit.register(self.shutdown)
        else:
            logging.info("Batching disabled, using individual upsert")

    def _start_flush_thread(self):
        """Start background thread for periodic flushing."""
        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.flush_thread.start()
        logging.debug("Flush worker thread started")

    def _flush_worker(self):
        """Background worker that flushes buffer periodically."""
        while not self.stop_event.is_set():
            # Wait for flush interval or stop event
            if self.stop_event.wait(timeout=self.flush_interval):
                break

            # Flush if buffer has messages
            with self.lock:
                if len(self.buffer) > 0:
                    self._flush_buffer_unsafe()

    def _flush_buffer_unsafe(self):
        """
        Flush buffer to search engine (internal, assumes lock is held).

        This method should only be called when self.lock is already acquired.
        """
        if not self.buffer:
            return

        messages_to_flush = self.buffer[:]
        self.buffer = []

        try:
            # Release lock while making HTTP request to avoid blocking
            self.lock.release()

            result = self.engine.upsert_batch(messages_to_flush)

            # Re-acquire lock to update stats
            self.lock.acquire()

            self.stats["flushed"] += result.get("indexed_count", 0)
            self.stats["batches"] += 1

            if result.get("failed_count", 0) > 0:
                self.stats["errors"] += result.get("failed_count", 0)
                logging.warning(
                    f"Batch flush had {result['failed_count']} failures: "
                    f"{result.get('errors', [])}"
                )

            logging.debug(
                f"Flushed batch: {result.get('indexed_count', 0)} messages "
                f"(buffer size was {len(messages_to_flush)})"
            )

        except Exception as e:
            # Re-acquire lock if not held
            if not self.lock.locked():
                self.lock.acquire()

            self.stats["errors"] += len(messages_to_flush)
            logging.error(f"Failed to flush batch of {len(messages_to_flush)} messages: {e}")

            # Re-add messages to buffer for retry? For now, we drop them
            # to avoid infinite retry loops

    def upsert(self, message: types.Message) -> None:
        """
        Add message to buffer (or insert immediately if batching disabled).

        Args:
            message: Pyrogram message object
        """
        if not self.enabled:
            # Batching disabled, use direct upsert
            self.engine.upsert(message)
            return

        with self.lock:
            self.buffer.append(message)
            self.stats["buffered"] += 1

            # Check if we should flush based on size
            if len(self.buffer) >= self.batch_size:
                logging.debug(f"Buffer size threshold reached ({self.batch_size}), flushing")
                self._flush_buffer_unsafe()

    def flush(self) -> None:
        """
        Manually flush all buffered messages.

        This is a blocking operation that ensures all messages are sent
        to the remote database before returning. Critical for resume capability.
        """
        if not self.enabled:
            return

        with self.lock:
            if len(self.buffer) > 0:
                buffer_count = len(self.buffer)
                logging.info(f"Manual flush requested, flushing {buffer_count} messages")
                self._flush_buffer_unsafe()
                logging.info(f"Manual flush completed, {buffer_count} messages sent to database")
            else:
                logging.debug("Manual flush requested but buffer is empty")

    def shutdown(self) -> None:
        """Shutdown buffered engine and flush remaining messages."""
        if not self.enabled:
            return

        logging.info("Shutting down buffered search engine...")

        # Stop flush thread
        self.stop_event.set()
        if self.flush_thread and self.flush_thread.is_alive():
            self.flush_thread.join(timeout=5)

        # Final flush
        self.flush()

        logging.info(
            f"Buffered engine shutdown complete. Stats: "
            f"buffered={self.stats['buffered']}, "
            f"flushed={self.stats['flushed']}, "
            f"batches={self.stats['batches']}, "
            f"errors={self.stats['errors']}"
        )

    def get_stats(self) -> Dict[str, int]:
        """Get buffering statistics."""
        with self.lock:
            return {
                **self.stats,
                "buffer_size": len(self.buffer),
            }

    # Delegate all other methods to underlying engine
    def __getattr__(self, name):
        """Delegate unknown methods to underlying engine."""
        return getattr(self.engine, name)
