#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - client.py
# Modified to perform DB upserts asynchronously with retry on failure and rate limit history sync.
#
__author__ = "Benny <benny.think@gmail.com>"

import configparser
import logging
import random
import threading
import time
import queue

import fakeredis
from pyrogram import Client, filters, types

from __init__ import SearchEngine
from config import BOT_ID
from init_client import get_client
from utils import setup_logger

setup_logger()

app = get_client()
tgdb = SearchEngine()
r = fakeredis.FakeStrictRedis()

# --- Asynchronous DB Upsert Setup with Retry ---
# We wrap each message with a tuple: (message, retry_count).
db_queue = queue.Queue()

def db_worker():
    """Worker thread that takes messages (with retry count) from the queue and saves them.
    
    If saving fails, the message is requeued with an increased retry counter after a delay.
    """
    while True:
        item = db_queue.get()
        if item is None:
            # A sentinel (None) can be used to shut down the worker gracefully.
            break
        msg, retries = item
        try:
            tgdb.upsert(msg)
        except Exception as e:
            logging.exception("Error upserting message (attempt %s): %s", retries, e)
            # Exponential backoff delay: e.g., 1, 2, 4, 8, ... seconds, capped at 60.
            delay = min(2 ** retries, 60)
            # Use a Timer so that the current worker thread is not blocked.
            threading.Timer(delay, lambda m=msg, r=retries: db_queue.put((m, r + 1))).start()
        finally:
            db_queue.task_done()

# Start a small pool of worker threads so that one failing message does not block all processing.
NUM_WORKERS = 3
worker_threads = []
for _ in range(NUM_WORKERS):
    t = threading.Thread(target=db_worker, daemon=True)
    t.start()
    worker_threads.append(t)
# --- End Async Setup ---

@app.on_message((filters.outgoing | filters.incoming) & ~filters.chat(BOT_ID))
def message_handler(client: "Client", message: "types.Message"):
    logging.info("Adding new message: %s-%s", message.chat.id, message.id)
    # Enqueue the message with an initial retry count of 0.
    db_queue.put((message, 0))

@app.on_edited_message(~filters.chat(BOT_ID))
def message_edit_handler(client: "Client", message: "types.Message"):
    logging.info("Editing old message: %s-%s", message.chat.id, message.id)
    db_queue.put((message, 0))

def safe_edit(msg, new_text):
    key = "sync-chat"
    if not r.exists(key):
        time.sleep(0.2)
        r.set(key, "ok", ex=2)
        msg.edit_text(new_text)

def sync_history():
    logging.info("sync_history: Sleeping for initial 30 seconds before starting sync...")
    time.sleep(30)
    logging.info("sync_history: Woke up from initial 30 seconds sleep.")

    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = lambda option: option  # Preserve case sensitivity of keys.
    config.read("sync.ini")

    if config.items("sync"):
        saved = app.send_message("me", "Starting to sync history...")
        logging.info("sync_history: Found [sync] options; starting to process sync history.")

        for uid in config.options("sync"):
            logging.info("sync_history: Processing sync for uid: %s", uid)
            total_count = app.get_chat_history_count(uid)
            log = f"Syncing history for {uid}"
            logging.info(log)
            safe_edit(saved, log)
            
            logging.info("sync_history: About to sleep for 8 seconds to avoid flooding Telegram for uid: %s", uid)
            sleep_start = time.time()
            time.sleep(8)  # Manual delay to avoid flooding Telegram
            elapsed = time.time() - sleep_start
            logging.info("sync_history: Manual sleep finished (slept for %.2f seconds) for uid: %s", elapsed, uid)
            
            chat_records = app.get_chat_history(uid)
            current = 0
            # Rate limiting: do not enqueue more than 500 messages per second.
            messages_counter = 0
            batch_start = time.time()
            for msg in chat_records:
                safe_edit(saved, f"[{current}/{total_count}] - {log}")
                current += 1
                db_queue.put((msg, 0))
                messages_counter += 1

                # If we've processed 500 messages in less than one second, sleep for the remaining time.
                if messages_counter >= 100:
                    elapsed_batch = time.time() - batch_start
                    if elapsed_batch < 1.0:
                        wait_time = 1.0 - elapsed_batch
                        logging.info("Rate limiting: processed %d messages in %.2f seconds; sleeping for %.2f seconds.", 
                                     messages_counter, elapsed_batch, wait_time)
                        time.sleep(wait_time)
                    messages_counter = 0
                    batch_start = time.time()
            config.remove_option("sync", uid)

        # Write back the modified config (with the processed sync options removed).
        with open("sync.ini", "w") as configfile:
            config.write(configfile)

        log = "Sync history complete"
        logging.info(log)
        safe_edit(saved, log)
    else:
        logging.info("sync_history: No [sync] section found or it is empty in sync.ini.")

if __name__ == "__main__":
    # Start the history sync in a separate thread.
    threading.Thread(target=sync_history, daemon=True).start()
    app.run()
