#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - config_loader.py
# JSON-only configuration loader

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


class ConfigLoader:
    """
    JSON-only configuration loader for SearchGram.

    All configuration must be in config.json file.
    No environment variable fallbacks.
    """

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self._config: Dict[str, Any] = {}
        self._load_config()
        self._validate_required_fields()

    def _load_config(self):
        """Load configuration from JSON file."""
        if not os.path.exists(self.config_file):
            error_msg = f"""
❌ Configuration file not found: {self.config_file}

SearchGram requires a JSON configuration file.

Quick setup:
1. Copy example: cp config.example.json config.json
2. Edit config.json with your settings
3. Or run migration: python migrate_config.py

See CONFIG.md for details.
"""
            logging.error(error_msg)
            raise ConfigurationError(f"Configuration file not found: {self.config_file}")

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logging.info(f"✅ Loaded configuration from {self.config_file}")
        except json.JSONDecodeError as e:
            error_msg = f"""
❌ Invalid JSON in configuration file: {self.config_file}
Error: {e}

Fix the JSON syntax and try again.
"""
            logging.error(error_msg)
            raise ConfigurationError(f"Invalid JSON: {e}")
        except Exception as e:
            logging.error(f"Failed to load config file: {e}")
            raise ConfigurationError(f"Failed to load config: {e}")

    def _validate_required_fields(self):
        """Validate that required configuration fields are present."""
        required_fields = [
            ("telegram.app_id", "Telegram API ID"),
            ("telegram.app_hash", "Telegram API Hash"),
            ("telegram.bot_token", "Bot Token"),
            ("telegram.owner_id", "Owner User ID"),
            ("search_engine.engine", "Search Engine Type"),
        ]

        missing_fields = []
        for field_path, field_name in required_fields:
            if self.get(field_path) is None:
                missing_fields.append(f"  - {field_path} ({field_name})")

        if missing_fields:
            error_msg = f"""
❌ Missing required configuration fields in {self.config_file}:

{chr(10).join(missing_fields)}

Please update your config.json file.
See config.example.json for reference.
"""
            logging.error(error_msg)
            raise ConfigurationError(f"Missing required fields: {', '.join(f[0] for f in required_fields if f'- {f[0]}' in missing_fields)}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value from JSON.

        Args:
            key_path: Dot-separated path (e.g., "telegram.app_id")
            default: Default value if not found

        Returns:
            Configuration value from JSON or default
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value if value is not None else default

    def get_int(self, key_path: str, default: int = 0) -> int:
        """Get integer configuration value."""
        value = self.get(key_path, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_float(self, key_path: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        value = self.get(key_path, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key_path: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key_path, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)

    def get_list(self, key_path: str, default: list = None, item_type=str) -> list:
        """
        Get list configuration value.

        Args:
            key_path: Dot-separated path
            default: Default list
            item_type: Type converter for list items

        Returns:
            List of values
        """
        if default is None:
            default = []

        value = self.get(key_path, default)

        # If it's already a list, convert items to correct type
        if isinstance(value, list):
            try:
                return [item_type(item) for item in value]
            except (ValueError, TypeError):
                return default

        return default

    def get_dict(self, key_path: str, default: dict = None) -> dict:
        """Get dictionary configuration value."""
        if default is None:
            default = {}

        value = self.get(key_path, default)

        if isinstance(value, dict):
            return value

        return default

    def save_config(self, config_dict: dict):
        """Save configuration to JSON file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            logging.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")


# Global configuration instance
try:
    _config_loader = ConfigLoader()
except ConfigurationError as e:
    print(f"\nConfiguration Error: {e}\n", file=sys.stderr)
    sys.exit(1)


def get_config() -> ConfigLoader:
    """Get the global configuration loader instance."""
    return _config_loader


# Telegram configuration
APP_ID = _config_loader.get_int("telegram.app_id")
APP_HASH = _config_loader.get("telegram.app_hash")
TOKEN = _config_loader.get("telegram.bot_token")
OWNER_ID = _config_loader.get_int("telegram.owner_id")
BOT_ID = int(TOKEN.split(":")[0]) if TOKEN else 0

# Network settings
PROXY = _config_loader.get_dict("telegram.proxy", None)
IPv6 = _config_loader.get_bool("telegram.ipv6", False)

# Search engine settings
ENGINE = _config_loader.get("search_engine.engine", "meili").lower()

# MeiliSearch
MEILI_HOST = _config_loader.get("search_engine.meili.host", "http://meili:7700")
MEILI_PASS = _config_loader.get("search_engine.meili.master_key", TOKEN)

# MongoDB
MONGO_HOST = _config_loader.get("search_engine.mongo.host", "mongo")
MONGO_PORT = _config_loader.get_int("search_engine.mongo.port", 27017)

# ZincSearch
ZINC_HOST = _config_loader.get("search_engine.zinc.host", "http://zinc:4080")
ZINC_USER = _config_loader.get("search_engine.zinc.user", "root")
ZINC_PASS = _config_loader.get("search_engine.zinc.password", "root")

# Elasticsearch
ELASTIC_HOST = _config_loader.get("search_engine.elastic.host", "http://elasticsearch:9200")
ELASTIC_USER = _config_loader.get("search_engine.elastic.user", "elastic")
ELASTIC_PASS = _config_loader.get("search_engine.elastic.password", "changeme")

# Bot access control
# Support both string and list for mode
_bot_mode = _config_loader.get("bot.mode", "private")
if isinstance(_bot_mode, list):
    BOT_MODE = [m.lower() for m in _bot_mode]
else:
    BOT_MODE = _bot_mode.lower()
ALLOWED_GROUPS = _config_loader.get_list("bot.allowed_groups", [], item_type=int)
ALLOWED_USERS = _config_loader.get_list("bot.allowed_users", [], item_type=int)

# Enhanced permissions
ADMINS = _config_loader.get_list("bot.admins", [], item_type=int)
# User group permissions: dict mapping user_id (str) -> list of group_ids (int)
USER_GROUP_PERMISSIONS = _config_loader.get_dict("bot.user_group_permissions", {})

# Privacy settings
PRIVACY_STORAGE = _config_loader.get("privacy.storage_file", "privacy_data.json")

# Database settings
DATABASE_PATH = _config_loader.get("database.path", "searchgram_logs.db")
DATABASE_ENABLED = _config_loader.get_bool("database.enabled", True)

# Sync settings
SYNC_ENABLED = _config_loader.get_bool("sync.enabled", True)
SYNC_CHECKPOINT_FILE = _config_loader.get("sync.checkpoint_file", "sync_progress.json")
SYNC_BATCH_SIZE = _config_loader.get_int("sync.batch_size", 100)
SYNC_RETRY_ON_ERROR = _config_loader.get_bool("sync.retry_on_error", True)
SYNC_MAX_RETRIES = _config_loader.get_int("sync.max_retries", 3)
SYNC_RESUME_ON_RESTART = _config_loader.get_bool("sync.resume_on_restart", True)
SYNC_DELAY_BETWEEN_BATCHES = _config_loader.get_float("sync.delay_between_batches", 1.0)
SYNC_CLEAR_COMPLETED = _config_loader.get_bool("sync.clear_completed", False)

# Service endpoints (for inter-service communication)
SERVICE_BOT_URL = _config_loader.get("services.bot.base_url", "http://127.0.0.1:8081")
SERVICE_USERBOT_URL = _config_loader.get("services.userbot.base_url", "http://127.0.0.1:8082")
SERVICE_SEARCH_URL = _config_loader.get("services.search.base_url", "http://127.0.0.1:8080")

# Authentication settings (JWT)
AUTH_USE_JWT = _config_loader.get_bool("auth.use_jwt", True)
AUTH_ISSUER = _config_loader.get("auth.issuer", "bot")
AUTH_AUDIENCE = _config_loader.get("auth.audience", "internal")
AUTH_PUBLIC_KEY_PATH = _config_loader.get("auth.public_key_path", "keys/public.key")
AUTH_PRIVATE_KEY_PATH = _config_loader.get("auth.private_key_path", "keys/private.key")
AUTH_PUBLIC_KEY_INLINE = _config_loader.get("auth.public_key_inline")
AUTH_PRIVATE_KEY_INLINE = _config_loader.get("auth.private_key_inline")
AUTH_TOKEN_TTL = _config_loader.get_int("auth.token_ttl", 300)

# HTTP server settings
HTTP_LISTEN_HOST = _config_loader.get("http.listen", "127.0.0.1")
HTTP_BOT_PORT = _config_loader.get_int("http.bot_port", 8081)
HTTP_USERBOT_PORT = _config_loader.get_int("http.userbot_port", 8082)
HTTP_SEARCH_PORT = _config_loader.get_int("http.search_port", 8080)
HTTP_MESSAGE_QUEUE_DB = _config_loader.get("http.message_queue_db", "message_queue.db")
HTTP_CLEANUP_INTERVAL_HOURS = _config_loader.get_int("http.cleanup_interval_hours", 24)


if __name__ == "__main__":
    # Test configuration loading
    print(f"✅ Configuration loaded successfully!")
    print(f"\nTelegram:")
    print(f"  APP_ID: {APP_ID}")
    print(f"  OWNER_ID: {OWNER_ID}")
    print(f"\nSearch Engine:")
    print(f"  ENGINE: {ENGINE}")
    print(f"\nServices:")
    print(f"  Bot: {SERVICE_BOT_URL}")
    print(f"  Userbot: {SERVICE_USERBOT_URL}")
    print(f"  Search: {SERVICE_SEARCH_URL}")
    print(f"\nAuth:")
    print(f"  USE_JWT: {AUTH_USE_JWT}")
    print(f"  ISSUER: {AUTH_ISSUER}")
    print(f"  PUBLIC_KEY: {AUTH_PUBLIC_KEY_PATH}")
    print(f"\nHTTP Server:")
    print(f"  LISTEN: {HTTP_LISTEN_HOST}")
    print(f"  BOT_PORT: {HTTP_BOT_PORT}")
    print(f"  USERBOT_PORT: {HTTP_USERBOT_PORT}")
    print(f"\nBot:")
    print(f"  MODE: {BOT_MODE}")
    print(f"  ALLOWED_GROUPS: {ALLOWED_GROUPS}")
    print(f"  ALLOWED_USERS: {ALLOWED_USERS}")
    print(f"  ADMINS: {ADMINS}")
    print(f"  USER_GROUP_PERMISSIONS: {USER_GROUP_PERMISSIONS}")
    print(f"\nSync:")
    print(f"  ENABLED: {SYNC_ENABLED}")
    print(f"  BATCH_SIZE: {SYNC_BATCH_SIZE}")
