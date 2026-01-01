#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - sync_ipc.py
# IPC (Inter-Process Communication) for bot-to-client sync task management

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

# IPC file paths
SYNC_COMMANDS_FILE = "sync_commands.json"
SYNC_STATUS_FILE = "sync_status.json"


class SyncCommand:
    """Represents a sync command from bot to client."""

    def __init__(self, action: str, chat_id: Optional[int] = None, requested_by: Optional[int] = None):
        """
        Create a sync command.

        Args:
            action: Command action - 'add', 'pause', 'resume', 'status'
            chat_id: Target chat ID (None for 'status' action)
            requested_by: User ID who requested this command
        """
        self.action = action
        self.chat_id = chat_id
        self.requested_by = requested_by
        self.timestamp = datetime.utcnow().isoformat()
        self.command_id = f"{action}_{chat_id}_{int(time.time() * 1000)}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "command_id": self.command_id,
            "action": self.action,
            "chat_id": self.chat_id,
            "requested_by": self.requested_by,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SyncCommand':
        """Create instance from dictionary."""
        cmd = cls(
            action=data["action"],
            chat_id=data.get("chat_id"),
            requested_by=data.get("requested_by")
        )
        cmd.timestamp = data.get("timestamp", datetime.utcnow().isoformat())
        cmd.command_id = data.get("command_id", cmd.command_id)
        return cmd


class SyncIPCWriter:
    """
    Bot-side IPC writer. Sends commands to client process.

    Usage:
        writer = SyncIPCWriter()
        writer.send_command("add", chat_id=123456789, requested_by=owner_id)
        status = writer.get_status()
    """

    def __init__(self, commands_file: str = SYNC_COMMANDS_FILE, status_file: str = SYNC_STATUS_FILE):
        self.commands_file = commands_file
        self.status_file = status_file
        self.lock = threading.Lock()

    def send_command(self, action: str, chat_id: Optional[int] = None, requested_by: Optional[int] = None) -> str:
        """
        Send a command to client process.

        Args:
            action: 'add', 'pause', 'resume', 'status'
            chat_id: Target chat ID
            requested_by: User ID who requested

        Returns:
            command_id: Unique identifier for tracking
        """
        command = SyncCommand(action, chat_id, requested_by)

        try:
            with self.lock:
                # Read existing commands
                commands = []
                if os.path.exists(self.commands_file):
                    try:
                        with open(self.commands_file, 'r') as f:
                            data = json.load(f)
                            commands = data.get("commands", [])
                    except (json.JSONDecodeError, KeyError):
                        logging.warning("Corrupted commands file, resetting")
                        commands = []

                # Add new command
                commands.append(command.to_dict())

                # Write atomically
                temp_file = f"{self.commands_file}.tmp"
                with open(temp_file, 'w') as f:
                    json.dump({
                        "last_updated": datetime.utcnow().isoformat(),
                        "commands": commands
                    }, f, indent=2)
                os.replace(temp_file, self.commands_file)

                logging.info(f"Sent sync command: {action} for chat {chat_id} (ID: {command.command_id})")
                return command.command_id

        except Exception as e:
            logging.error(f"Failed to send sync command: {e}")
            raise

    def get_status(self) -> Optional[dict]:
        """
        Read sync status from client process.

        Returns:
            Status dict with 'chats' array or None if not available
        """
        try:
            if not os.path.exists(self.status_file):
                return None

            with open(self.status_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to read sync status: {e}")
            return None


class SyncIPCReader:
    """
    Client-side IPC reader. Processes commands from bot.

    Usage:
        reader = SyncIPCReader()
        commands = reader.read_commands()  # Returns list of SyncCommand objects
        reader.clear_commands()
    """

    def __init__(self, commands_file: str = SYNC_COMMANDS_FILE, status_file: str = SYNC_STATUS_FILE):
        self.commands_file = commands_file
        self.status_file = status_file
        self.lock = threading.Lock()

    def read_commands(self) -> List[SyncCommand]:
        """
        Read pending commands from file.

        Returns:
            List of SyncCommand objects
        """
        try:
            if not os.path.exists(self.commands_file):
                return []

            with self.lock:
                with open(self.commands_file, 'r') as f:
                    data = json.load(f)

                commands = []
                for cmd_data in data.get("commands", []):
                    try:
                        commands.append(SyncCommand.from_dict(cmd_data))
                    except Exception as e:
                        logging.error(f"Failed to parse command: {e}")

                return commands

        except Exception as e:
            logging.error(f"Failed to read sync commands: {e}")
            return []

    def clear_commands(self):
        """Clear all processed commands."""
        try:
            with self.lock:
                if os.path.exists(self.commands_file):
                    os.remove(self.commands_file)
                    logging.debug("Cleared sync commands file")
        except Exception as e:
            logging.error(f"Failed to clear sync commands: {e}")

    def write_status(self, progress_map: Dict[int, 'SyncProgress']):
        """
        Write current sync status for bot to read.

        Args:
            progress_map: Dict mapping chat_id to SyncProgress object
        """
        try:
            with self.lock:
                data = {
                    "last_updated": datetime.utcnow().isoformat(),
                    "chats": [progress.to_dict() for progress in progress_map.values()]
                }

                # Atomic write
                temp_file = f"{self.status_file}.tmp"
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                os.replace(temp_file, self.status_file)

                logging.debug(f"Updated sync status: {len(progress_map)} chats")

        except Exception as e:
            logging.error(f"Failed to write sync status: {e}")
