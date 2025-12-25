#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - access_control.py
# Access control system for bot usage permissions

__author__ = "Benny <benny.think@gmail.com>"

import logging
from functools import wraps
from typing import Callable

from pyrogram import Client, enums, types

from config_loader import ALLOWED_GROUPS, ALLOWED_USERS, BOT_MODE, OWNER_ID


class AccessController:
    """
    Manages access control for the bot.

    Supports three modes:
    - private: Only owner can use the bot
    - group: Bot works in whitelisted groups and for allowed users
    - public: Anyone can use the bot (not recommended for privacy)
    """

    def __init__(self):
        self.mode = BOT_MODE
        self.owner_id = int(OWNER_ID)
        self.allowed_groups = set(ALLOWED_GROUPS)
        self.allowed_users = set(ALLOWED_USERS) | {self.owner_id}

        logging.info("Access Control initialized: mode=%s, owner=%d", self.mode, self.owner_id)
        if self.mode == "group":
            logging.info("Allowed groups: %s", self.allowed_groups)
            logging.info("Allowed users: %s", self.allowed_users)

    def is_owner(self, user_id: int) -> bool:
        """Check if user is the owner."""
        return user_id == self.owner_id

    def is_allowed_user(self, user_id: int) -> bool:
        """Check if user is explicitly allowed."""
        return user_id in self.allowed_users

    def is_allowed_group(self, chat_id: int) -> bool:
        """Check if group is whitelisted."""
        return chat_id in self.allowed_groups

    def check_access(self, message: types.Message) -> tuple[bool, str]:
        """
        Check if user has access to use the bot.

        Args:
            message: Pyrogram message object

        Returns:
            tuple: (has_access: bool, reason: str)
        """
        user_id = message.from_user.id if message.from_user else None
        chat_id = message.chat.id
        chat_type = message.chat.type

        # Owner always has access
        if user_id and self.is_owner(user_id):
            return True, "owner"

        # Private mode: only owner
        if self.mode == "private":
            return False, "Bot is in private mode. Only owner can use it."

        # Public mode: everyone has access
        if self.mode == "public":
            return True, "public"

        # Group mode: check various conditions
        if self.mode == "group":
            # Direct message from allowed user
            if chat_type == enums.ChatType.PRIVATE:
                if user_id and self.is_allowed_user(user_id):
                    return True, "allowed_user"
                return False, "You are not authorized to use this bot in private messages."

            # Group/supergroup/channel
            if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                if self.is_allowed_group(chat_id):
                    return True, "allowed_group"
                return False, "This bot is not enabled for this group."

            return False, "Unknown chat type or not authorized."

        return False, f"Unknown bot mode: {self.mode}"

    def require_access(self, func: Callable) -> Callable:
        """
        Decorator to enforce access control on bot commands.

        Usage:
            @access_controller.require_access
            def my_handler(client, message):
                ...
        """
        @wraps(func)
        def wrapper(client: Client, message: types.Message):
            has_access, reason = self.check_access(message)

            if not has_access:
                logging.warning(
                    "Access denied for user %s in chat %s: %s",
                    message.from_user.id if message.from_user else "unknown",
                    message.chat.id,
                    reason
                )
                # Only send error message in private chats to avoid spam
                if message.chat.type == enums.ChatType.PRIVATE:
                    client.send_message(message.chat.id, f"❌ {reason}")
                return

            logging.info(
                "Access granted for user %s in chat %s (reason: %s)",
                message.from_user.id if message.from_user else "unknown",
                message.chat.id,
                reason
            )
            return func(client, message)

        return wrapper

    def require_owner(self, func: Callable) -> Callable:
        """
        Decorator to require owner access (for admin commands).

        Usage:
            @access_controller.require_owner
            def admin_command(client, message):
                ...
        """
        @wraps(func)
        def wrapper(client: Client, message: types.Message):
            user_id = message.from_user.id if message.from_user else None

            if not user_id or not self.is_owner(user_id):
                logging.warning("Owner-only command attempted by user %s", user_id)
                if message.chat.type == enums.ChatType.PRIVATE:
                    client.send_message(message.chat.id, "❌ This command is only available to the bot owner.")
                return

            return func(client, message)

        return wrapper


# Global access controller instance
access_controller = AccessController()


# Convenience decorators for backward compatibility and ease of use
def require_access(func: Callable) -> Callable:
    """Require basic access (respects bot mode)."""
    return access_controller.require_access(func)


def require_owner(func: Callable) -> Callable:
    """Require owner access (admin commands)."""
    return access_controller.require_owner(func)


if __name__ == "__main__":
    # Test access control
    ac = AccessController()
    print(f"Mode: {ac.mode}")
    print(f"Owner: {ac.owner_id}")
    print(f"Is owner: {ac.is_owner(ac.owner_id)}")
    print(f"Is allowed user: {ac.is_allowed_user(123456)}")
