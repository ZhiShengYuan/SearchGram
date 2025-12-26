#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - client.py
# 4/4/22 22:06
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import threading
import time

import fakeredis
from pyrogram import Client, filters, types

from . import SearchEngine
from .config_loader import BOT_ID, SYNC_ENABLED, get_config
from .init_client import get_client
from .sync_manager import SyncManager
from .utils import setup_logger

setup_logger()

app = get_client()
tgdb = SearchEngine()
r = fakeredis.FakeStrictRedis()

# Initialize sync manager
sync_manager = SyncManager(app, tgdb)

# Statistics tracking
stats = {
    "indexed": 0,
    "edited": 0,
    "bot_skipped": 0,
    "start_time": time.time()
}


@app.on_message((filters.outgoing | filters.incoming))
def message_handler(client: "Client", message: "types.Message"):
    # Check if sender is the bot itself - skip to prevent circular indexing
    # Use from_user.id to check sender, not chat.id (which could be a group)
    if message.from_user and message.from_user.id == BOT_ID:
        stats["bot_skipped"] += 1
        logging.debug("Skipping bot message from user %s in chat %s-%s (total skipped: %d)",
                     message.from_user.id, message.chat.id, message.id, stats["bot_skipped"])
        return

    # Skip service messages (no from_user)
    if not message.from_user:
        logging.debug("Skipping service message: %s-%s", message.chat.id, message.id)
        return

    logging.info("Adding new message: %s-%s", message.chat.id, message.id)
    tgdb.upsert(message)
    stats["indexed"] += 1

    # Log stats every 100 messages
    if stats["indexed"] % 100 == 0:
        elapsed = time.time() - stats["start_time"]
        logging.info(
            "📊 Stats: %d indexed, %d edited, %d bot messages skipped (%.1f msgs/min)",
            stats["indexed"], stats["edited"], stats["bot_skipped"],
            (stats["indexed"] + stats["edited"]) / (elapsed / 60) if elapsed > 0 else 0
        )


@app.on_edited_message()
def message_edit_handler(client: "Client", message: "types.Message"):
    # Check if sender is the bot itself - skip to prevent circular indexing
    if message.from_user and message.from_user.id == BOT_ID:
        logging.debug("Skipping bot edited message from user %s in chat %s-%s",
                     message.from_user.id, message.chat.id, message.id)
        return

    # Skip service messages (no from_user)
    if not message.from_user:
        logging.debug("Skipping edited service message: %s-%s", message.chat.id, message.id)
        return

    logging.info("Editing old message: %s-%s", message.chat.id, message.id)
    tgdb.upsert(message)
    stats["edited"] += 1


def sync_history_new():
    """
    New sync system with resume capability and checkpoint support.
    Replaces the old sync.ini-based system.
    """
    if not SYNC_ENABLED:
        logging.info("Sync is disabled in configuration")
        return

    # Wait for client to be ready
    time.sleep(30)

    # Load chat list from config
    config = get_config()
    sync_chats = config.get_list("sync.chats", [], item_type=int)

    if not sync_chats and not sync_manager.get_all_progress():
        logging.info("No chats configured for sync and no pending syncs")
        return

    # Add new chats from config to sync queue
    for chat_id in sync_chats:
        sync_manager.add_chat(chat_id)

    # Get summary before starting
    summary = sync_manager.get_summary()
    logging.info(
        f"📊 Sync Queue: {summary['total_chats']} chats, "
        f"{summary['pending']} pending, {summary['completed']} completed, "
        f"{summary['failed']} failed"
    )

    # Send progress notification to saved messages
    try:
        progress_msg = app.send_message("me", "🔄 Starting history sync...\n\nInitializing...")
    except:
        progress_msg = None

    def update_progress(progress):
        """Callback to update progress message."""
        if not progress_msg:
            return

        try:
            # Rate limit updates
            key = f"sync-update-{progress.chat_id}"
            if not r.exists(key):
                r.set(key, "ok", ex=5)  # Update at most every 5 seconds

                summary = sync_manager.get_summary()
                text = f"""
🔄 **History Sync Progress**

**Current Chat:** `{progress.chat_id}`
**Progress:** {progress.synced_count}/{progress.total_count} ({progress.to_dict()['progress_percent']}%)
**Status:** {progress.status}

**Overall:**
• Total Chats: {summary['total_chats']}
• Completed: {summary['completed']}
• In Progress: {summary['in_progress']}
• Pending: {summary['pending']}
• Failed: {summary['failed']}

**Messages:** {summary['synced_messages']}/{summary['total_messages']} ({summary['progress_percent']}%)
                """
                progress_msg.edit_text(text.strip())
        except Exception as e:
            logging.debug(f"Failed to update progress message: {e}")

    # Start synchronization
    logging.info("🚀 Starting history synchronization...")
    results = sync_manager.sync_all(progress_callback=update_progress)

    # Final summary
    summary = sync_manager.get_summary()
    success_count = sum(1 for success in results.values() if success)
    fail_count = sum(1 for success in results.values() if not success)

    final_text = f"""
✅ **History Sync Complete**

**Results:**
• Success: {success_count} chats
• Failed: {fail_count} chats
• Total Messages: {summary['synced_messages']}

**Status:**
• Completed: {summary['completed']}
• Failed: {summary['failed']}
• Pending: {summary['pending']}

Sync checkpoint saved. You can resume anytime!
    """

    if progress_msg:
        try:
            progress_msg.edit_text(final_text.strip())
        except:
            pass

    logging.info(
        f"✅ Sync complete: {success_count} successful, {fail_count} failed, "
        f"{summary['synced_messages']} messages indexed"
    )

    # Clean up completed chats
    sync_manager.clear_completed()


if __name__ == "__main__":
    # Start sync in background thread
    threading.Thread(target=sync_history_new, daemon=True).start()
    app.run()
