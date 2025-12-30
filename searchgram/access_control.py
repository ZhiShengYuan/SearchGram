#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - access_control.py
# Access control system for bot usage permissions

__author__ = "Benny <benny.think@gmail.com>"

import asyncio
import inspect
import logging
from functools import wraps
from typing import Callable

from pyrogram import Client, enums, types

from .config_loader import ADMINS, ALLOWED_GROUPS, ALLOWED_USERS, BOT_MODE, OWNER_ID, USER_GROUP_PERMISSIONS


class AccessController:
    """
    Manages access control for the bot.

    Supports multiple modes simultaneously:
    - private: Only owner can use the bot
    - group: Bot works in whitelisted groups
    - public: Anyone can use the bot (not recommended for privacy)

    Mode can be a single string or a list of strings for multi-mode support.
    Example: ["private", "group"] enables both private and group access.
    """

    def __init__(self):
        # Support both single mode and multi-mode
        mode_config = BOT_MODE
        if isinstance(mode_config, list):
            self.modes = set(mode_config)
        else:
            self.modes = {mode_config}

        self.owner_id = int(OWNER_ID)
        self.allowed_groups = set(ALLOWED_GROUPS)
        self.allowed_users = set(ALLOWED_USERS) | {self.owner_id}

        # Enhanced permissions
        self.admins = set(ADMINS)
        # Convert user_group_permissions dict keys from str to int
        self.user_group_permissions = {}
        for user_id_str, group_ids in USER_GROUP_PERMISSIONS.items():
            try:
                user_id = int(user_id_str)
                self.user_group_permissions[user_id] = set(group_ids) if isinstance(group_ids, list) else set()
            except (ValueError, TypeError):
                logging.warning(f"Invalid user_id in user_group_permissions: {user_id_str}")

        logging.info("Access Control initialized: modes=%s, owner=%d", self.modes, self.owner_id)
        if "group" in self.modes:
            logging.info("Allowed groups: %s", self.allowed_groups)
            logging.info("Allowed users: %s", self.allowed_users)
            logging.info("Admins: %s", self.admins)
            logging.info("User group permissions: %s", self.user_group_permissions)

    def is_owner(self, user_id: int) -> bool:
        """Check if user is the owner."""
        return user_id == self.owner_id

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin (can search all groups)."""
        return user_id in self.admins

    def is_allowed_user(self, user_id: int) -> bool:
        """Check if user is explicitly allowed."""
        return user_id in self.allowed_users

    def is_allowed_group(self, chat_id: int) -> bool:
        """Check if group is whitelisted."""
        return chat_id in self.allowed_groups

    def get_allowed_groups_for_user(self, user_id: int) -> set:
        """
        Get the set of group IDs that a user can search.

        Args:
            user_id: User ID to check

        Returns:
            Set of group IDs the user can access:
            - Owner: all indexed groups (from allowed_groups)
            - Admins: all indexed groups (from allowed_groups)
            - Regular users: groups from user_group_permissions, or empty set if not configured
        """
        # Owner and admins can access all indexed groups
        if self.is_owner(user_id) or self.is_admin(user_id):
            return self.allowed_groups

        # Regular users: return their specific permissions
        return self.user_group_permissions.get(user_id, set())

    def check_access(self, message: types.Message) -> tuple[bool, str]:
        """
        Check if user has access to use the bot.

        Supports multi-mode access control. Checks all enabled modes.

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

        # Public mode: everyone has access (if enabled)
        if "public" in self.modes:
            return True, "public"

        # Private chats
        if chat_type == enums.ChatType.PRIVATE:
            # Private mode: owner already checked above
            if "private" in self.modes:
                # Additional allowed users (when group mode is also enabled)
                if "group" in self.modes and user_id and self.is_allowed_user(user_id):
                    return True, "allowed_user"
                # If only private mode, owner-only
                if len(self.modes) == 1 and "private" in self.modes:
                    return False, "Bot is in private mode. Only owner can use it."
                # Private mode enabled but user not in allowed list
                if "group" in self.modes:
                    return False, "You are not authorized to use this bot in private messages."

        # Group/supergroup chats
        if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            # Group mode: check if group is whitelisted
            if "group" in self.modes:
                if self.is_allowed_group(chat_id):
                    return True, "allowed_group"
                return False, "This bot is not enabled for this group."

        # No matching mode
        return False, f"No access granted. Enabled modes: {', '.join(self.modes)}"

    def require_access(self, func: Callable) -> Callable:
        """
        Decorator to enforce access control on bot commands.
        Supports both sync and async handlers.

        Usage:
            @access_controller.require_access
            def my_handler(client, message):
                ...

            @access_controller.require_access
            async def my_async_handler(client, message):
                ...
        """
        @wraps(func)
        async def async_wrapper(client: Client, message: types.Message):
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
                    await client.send_message(message.chat.id, f"❌ {reason}")
                return

            logging.info(
                "Access granted for user %s in chat %s (reason: %s)",
                message.from_user.id if message.from_user else "unknown",
                message.chat.id,
                reason
            )
            if inspect.iscoroutinefunction(func):
                return await func(client, message)
            else:
                return func(client, message)

        @wraps(func)
        def sync_wrapper(client: Client, message: types.Message):
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

        # Return async wrapper if func is async, otherwise return sync wrapper
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    def require_owner(self, func: Callable) -> Callable:
        """
        Decorator to require owner access (for admin commands).
        Supports both sync and async handlers.

        Usage:
            @access_controller.require_owner
            def admin_command(client, message):
                ...

            @access_controller.require_owner
            async def async_admin_command(client, message):
                ...
        """
        @wraps(func)
        async def async_wrapper(client: Client, message: types.Message):
            user_id = message.from_user.id if message.from_user else None

            if not user_id or not self.is_owner(user_id):
                logging.warning("Owner-only command attempted by user %s", user_id)
                if message.chat.type == enums.ChatType.PRIVATE:
                    await client.send_message(message.chat.id, "❌ This command is only available to the bot owner.")
                return

            if inspect.iscoroutinefunction(func):
                return await func(client, message)
            else:
                return func(client, message)

        @wraps(func)
        def sync_wrapper(client: Client, message: types.Message):
            user_id = message.from_user.id if message.from_user else None

            if not user_id or not self.is_owner(user_id):
                logging.warning("Owner-only command attempted by user %s", user_id)
                if message.chat.type == enums.ChatType.PRIVATE:
                    client.send_message(message.chat.id, "❌ This command is only available to the bot owner.")
                return

            return func(client, message)

        # Return async wrapper if func is async, otherwise return sync wrapper
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


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
    print(f"Modes: {ac.modes}")
    print(f"Owner: {ac.owner_id}")
    print(f"Admins: {ac.admins}")
    print(f"User group permissions: {ac.user_group_permissions}")
    print(f"\nPermission checks:")
    print(f"Is owner: {ac.is_owner(ac.owner_id)}")
    print(f"Is admin: {ac.is_admin(123456)}")
    print(f"Is allowed user: {ac.is_allowed_user(123456)}")
    print(f"\nAllowed groups for owner: {ac.get_allowed_groups_for_user(ac.owner_id)}")
    print(f"Allowed groups for user 123456: {ac.get_allowed_groups_for_user(123456)}")
