#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - message_converter.py
# Converts Pyrogram messages to full JSON template with normalized fields

__author__ = "Benny <benny.think@gmail.com>"

import logging
from typing import Any, Dict, Optional
from pyrogram import types


class MessageConverter:
    """
    Converts Pyrogram Message objects to the new JSON template format.

    This converter:
    1. Stores the complete Pyrogram message as JSON
    2. Extracts normalized fields for efficient searching
    3. Resolves sender information (user or chat)
    4. Resolves forward information
    5. Determines content type
    """

    @staticmethod
    def _serialize_pyrogram_object(obj: Any) -> Any:
        """
        Recursively serialize a Pyrogram object to dict.

        Args:
            obj: Pyrogram object to serialize

        Returns:
            Serialized dict/list/primitive
        """
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [MessageConverter._serialize_pyrogram_object(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: MessageConverter._serialize_pyrogram_object(v) for k, v in obj.items()}
        elif hasattr(obj, '__dict__'):
            # Pyrogram objects - serialize their __dict__
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):  # Skip private attributes
                    try:
                        result[key] = MessageConverter._serialize_pyrogram_object(value)
                    except Exception as e:
                        result[key] = f"<serialization error: {str(e)}>"
            return result
        else:
            # Fallback to string representation
            return str(obj)

    @staticmethod
    def _resolve_sender(message: types.Message) -> Dict[str, Any]:
        """
        Resolve sender information from message.

        Returns normalized sender fields:
        - sender_type: "user" or "chat"
        - sender_id: User ID or chat ID
        - sender_name: Combined name or chat title
        - sender_username: Username
        - sender_first_name: First name (user only)
        - sender_last_name: Last name (user only)
        - sender_chat_title: Chat title (chat sender only)
        """
        if message.from_user:
            # Sender is a user
            first_name = getattr(message.from_user, 'first_name', '') or ''
            last_name = getattr(message.from_user, 'last_name', '') or ''
            sender_name = f"{first_name} {last_name}".strip()

            return {
                "sender_type": "user",
                "sender_id": message.from_user.id,
                "sender_name": sender_name,
                "sender_username": getattr(message.from_user, 'username', '') or '',
                "sender_first_name": first_name or None,
                "sender_last_name": last_name or None,
                "sender_chat_title": None,
            }
        elif hasattr(message, 'sender_chat') and message.sender_chat:
            # Sender is a chat (anonymous admin, channel, etc.)
            return {
                "sender_type": "chat",
                "sender_id": message.sender_chat.id,
                "sender_name": getattr(message.sender_chat, 'title', '') or '',
                "sender_username": getattr(message.sender_chat, 'username', '') or '',
                "sender_first_name": None,
                "sender_last_name": None,
                "sender_chat_title": getattr(message.sender_chat, 'title', '') or None,
            }
        else:
            # Service message (no sender)
            return {
                "sender_type": "unknown",
                "sender_id": 0,
                "sender_name": "",
                "sender_username": "",
                "sender_first_name": None,
                "sender_last_name": None,
                "sender_chat_title": None,
            }

    @staticmethod
    def _resolve_forward(message: types.Message) -> Dict[str, Any]:
        """
        Resolve forward information from message.

        Returns:
        - is_forwarded: Boolean
        - forward_from_type: "user", "chat", "name_only", or None
        - forward_from_id: User/chat ID or None
        - forward_from_name: Name or None
        - forward_timestamp: Unix timestamp or None
        """
        # Check if message is forwarded
        has_forward_date = hasattr(message, 'forward_date') and message.forward_date
        has_forward_sender_name = hasattr(message, 'forward_sender_name') and message.forward_sender_name
        has_forward_from_chat = hasattr(message, 'forward_from_chat') and message.forward_from_chat
        has_forward_from = hasattr(message, 'forward_from') and message.forward_from

        is_forwarded = bool(has_forward_date or has_forward_sender_name or has_forward_from_chat or has_forward_from)

        if not is_forwarded:
            return {
                "is_forwarded": False,
                "forward_from_type": None,
                "forward_from_id": None,
                "forward_from_name": None,
                "forward_timestamp": None,
            }

        # Determine forward source (precedence: chat > user > name_only)
        forward_timestamp = int(message.forward_date.timestamp()) if has_forward_date else None

        if has_forward_from_chat:
            # Forwarded from a chat/channel
            return {
                "is_forwarded": True,
                "forward_from_type": "chat",
                "forward_from_id": message.forward_from_chat.id,
                "forward_from_name": getattr(message.forward_from_chat, 'title', '') or '',
                "forward_timestamp": forward_timestamp,
            }
        elif has_forward_from:
            # Forwarded from a user
            first_name = getattr(message.forward_from, 'first_name', '') or ''
            last_name = getattr(message.forward_from, 'last_name', '') or ''
            forward_name = f"{first_name} {last_name}".strip()

            return {
                "is_forwarded": True,
                "forward_from_type": "user",
                "forward_from_id": message.forward_from.id,
                "forward_from_name": forward_name,
                "forward_timestamp": forward_timestamp,
            }
        elif has_forward_sender_name:
            # Forwarded from a user with hidden privacy settings (name only)
            return {
                "is_forwarded": True,
                "forward_from_type": "name_only",
                "forward_from_id": None,
                "forward_from_name": message.forward_sender_name,
                "forward_timestamp": forward_timestamp,
            }
        else:
            # Has forward_date but no other info (edge case)
            return {
                "is_forwarded": True,
                "forward_from_type": None,
                "forward_from_id": None,
                "forward_from_name": None,
                "forward_timestamp": forward_timestamp,
            }

    @staticmethod
    def _resolve_content(message: types.Message) -> Dict[str, Any]:
        """
        Resolve content information from message.

        Returns:
        - content_type: "text", "sticker", "photo", "video", "document", "other"
        - text: Message text or None
        - caption: Media caption or None
        - sticker_emoji: Sticker emoji or None
        - sticker_set_name: Sticker set name or None
        """
        # Determine content type by checking message attributes
        if message.text:
            return {
                "content_type": "text",
                "text": message.text,
                "caption": None,
                "sticker_emoji": None,
                "sticker_set_name": None,
            }
        elif hasattr(message, 'sticker') and message.sticker:
            return {
                "content_type": "sticker",
                "text": None,
                "caption": None,
                "sticker_emoji": getattr(message.sticker, 'emoji', None),
                "sticker_set_name": getattr(message.sticker, 'set_name', None),
            }
        elif hasattr(message, 'photo') and message.photo:
            return {
                "content_type": "photo",
                "text": None,
                "caption": getattr(message, 'caption', None),
                "sticker_emoji": None,
                "sticker_set_name": None,
            }
        elif hasattr(message, 'video') and message.video:
            return {
                "content_type": "video",
                "text": None,
                "caption": getattr(message, 'caption', None),
                "sticker_emoji": None,
                "sticker_set_name": None,
            }
        elif hasattr(message, 'document') and message.document:
            return {
                "content_type": "document",
                "text": None,
                "caption": getattr(message, 'caption', None),
                "sticker_emoji": None,
                "sticker_set_name": None,
            }
        elif hasattr(message, 'audio') and message.audio:
            return {
                "content_type": "audio",
                "text": None,
                "caption": getattr(message, 'caption', None),
                "sticker_emoji": None,
                "sticker_set_name": None,
            }
        elif hasattr(message, 'voice') and message.voice:
            return {
                "content_type": "voice",
                "text": None,
                "caption": getattr(message, 'caption', None),
                "sticker_emoji": None,
                "sticker_set_name": None,
            }
        elif hasattr(message, 'animation') and message.animation:
            return {
                "content_type": "animation",
                "text": None,
                "caption": getattr(message, 'caption', None),
                "sticker_emoji": None,
                "sticker_set_name": None,
            }
        else:
            # Other message types (poll, location, contact, etc.)
            return {
                "content_type": "other",
                "text": None,
                "caption": getattr(message, 'caption', None),
                "sticker_emoji": None,
                "sticker_set_name": None,
            }

    @staticmethod
    def _extract_entities(message: types.Message) -> list:
        """
        Extract message entities (mentions, hashtags, etc.).

        Returns:
            List of entity dicts
        """
        entities = []
        if hasattr(message, 'entities') and message.entities:
            for entity in message.entities:
                entity_dict = {
                    "type": entity.type.name if hasattr(entity.type, 'name') else str(entity.type),
                    "offset": entity.offset,
                    "length": entity.length,
                }
                # For text mentions, include user information
                if hasattr(entity, 'user') and entity.user:
                    entity_dict["user_id"] = entity.user.id
                    entity_dict["user"] = {
                        "id": entity.user.id,
                        "first_name": getattr(entity.user, 'first_name', ''),
                        "last_name": getattr(entity.user, 'last_name', ''),
                        "username": getattr(entity.user, 'username', ''),
                    }
                entities.append(entity_dict)
        return entities

    @staticmethod
    def convert_to_dict(message: types.Message) -> Dict[str, Any]:
        """
        Convert a Pyrogram message to the new JSON template format.

        Args:
            message: Pyrogram message object

        Returns:
            Dictionary payload for indexing
        """
        # Resolve sender, forward, and content information
        sender_info = MessageConverter._resolve_sender(message)
        forward_info = MessageConverter._resolve_forward(message)
        content_info = MessageConverter._resolve_content(message)

        # Extract entities
        entities = MessageConverter._extract_entities(message)

        # Get timestamp
        timestamp = int(message.date.timestamp()) if hasattr(message, 'date') and message.date else 0

        # Build the normalized document
        payload = {
            # Core identifiers
            "id": f"{message.chat.id}-{message.id}",
            "message_id": message.id,
            "chat_id": message.chat.id,
            "timestamp": timestamp,
            "date": timestamp,

            # Chat information
            "chat_type": message.chat.type.name if hasattr(message.chat.type, 'name') else str(message.chat.type),
            "chat_title": getattr(message.chat, 'title', '') or '',
            "chat_username": getattr(message.chat, 'username', '') or '',

            # Sender information (normalized)
            **sender_info,

            # Forward information
            **forward_info,

            # Content information
            **content_info,

            # Entities
            "entities": entities,

            # Soft-delete (always false for new messages)
            "is_deleted": False,
            "deleted_at": 0,

            # Backward compatibility (deprecated)
            "chat": {
                "id": message.chat.id,
                "type": message.chat.type.name if hasattr(message.chat.type, 'name') else str(message.chat.type),
                "title": getattr(message.chat, 'title', '') or '',
                "username": getattr(message.chat, 'username', '') or '',
            },
            "from_user": {
                "id": message.from_user.id if message.from_user else 0,
                "is_bot": getattr(message.from_user, 'is_bot', False) if message.from_user else False,
                "first_name": getattr(message.from_user, 'first_name', '') if message.from_user else '',
                "last_name": getattr(message.from_user, 'last_name', '') if message.from_user else '',
                "username": getattr(message.from_user, 'username', '') if message.from_user else '',
            },

            # Full message JSON (stored, not indexed)
            "raw_message": MessageConverter._serialize_pyrogram_object(message),
        }

        return payload

    @staticmethod
    def convert_to_dict_legacy(message: types.Message) -> Dict[str, Any]:
        """
        Convert a Pyrogram message to the old flat format (for backward compatibility).

        Args:
            message: Pyrogram message object

        Returns:
            Dictionary payload in old format
        """
        # Extract entities
        entities = MessageConverter._extract_entities(message)

        # Build the old-style flat document
        payload = {
            "id": f"{message.chat.id}-{message.id}",
            "message_id": message.id,
            "text": message.text or "",
            "chat": {
                "id": message.chat.id,
                "type": message.chat.type.name if hasattr(message.chat.type, 'name') else str(message.chat.type),
                "title": getattr(message.chat, 'title', ''),
                "username": getattr(message.chat, 'username', ''),
            },
            "from_user": {
                "id": message.from_user.id if message.from_user else 0,
                "is_bot": getattr(message.from_user, 'is_bot', False) if message.from_user else False,
                "first_name": getattr(message.from_user, 'first_name', '') if message.from_user else '',
                "last_name": getattr(message.from_user, 'last_name', '') if message.from_user else '',
                "username": getattr(message.from_user, 'username', '') if message.from_user else '',
            },
            "date": int(message.date.timestamp()) if hasattr(message, 'date') and message.date else 0,
            "timestamp": int(message.date.timestamp()) if hasattr(message, 'date') and message.date else 0,
            "entities": entities,
            "is_deleted": False,
            "deleted_at": 0,
        }

        return payload
