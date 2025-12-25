#!/usr/bin/env python3
# coding: utf-8

# SearchGram - migrate_config.py
# Migration tool to convert old config to JSON format

"""
Migration utility for SearchGram configuration.

This script helps migrate from:
1. Environment variables / old config.py -> config.json
2. sync.ini -> config.json sync section + sync_progress.json
"""

import configparser
import json
import os
import sys


def migrate_sync_ini_to_json():
    """Migrate sync.ini to new JSON format."""
    if not os.path.exists("sync.ini"):
        print("No sync.ini found, skipping sync migration")
        return []

    print("📄 Found sync.ini, migrating...")

    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = lambda option: option
    config.read("sync.ini")

    sync_chats = []

    # Extract chats from [sync] section
    if config.has_section("sync"):
        for chat_id in config.options("sync"):
            try:
                sync_chats.append(int(chat_id))
                print(f"  ✓ Added chat {chat_id} to sync list")
            except ValueError:
                print(f"  ⚠ Skipping invalid chat ID: {chat_id}")

    print(f"✅ Migrated {len(sync_chats)} chats from sync.ini")
    return sync_chats


def create_config_json_interactive():
    """Interactive config.json creation."""
    print("\n" + "="*60)
    print("SearchGram Configuration Setup")
    print("="*60 + "\n")

    print("This wizard will help you create a config.json file.")
    print("Press Enter to use the default value shown in [brackets]")
    print("\n⚠️  All configuration must be in config.json (no environment variables)\n")

    config = {
        "telegram": {},
        "search_engine": {
            "meili": {},
            "mongo": {},
            "zinc": {},
            "elastic": {}
        },
        "bot": {},
        "privacy": {},
        "sync": {}
    }

    # Telegram settings
    print("--- Telegram Settings (Required) ---")

    app_id = input("APP_ID (from https://my.telegram.org/): ").strip()
    if not app_id:
        print("❌ APP_ID is required!")
        sys.exit(1)
    config["telegram"]["app_id"] = int(app_id)

    app_hash = input("APP_HASH (from https://my.telegram.org/): ").strip()
    if not app_hash:
        print("❌ APP_HASH is required!")
        sys.exit(1)
    config["telegram"]["app_hash"] = app_hash

    token = input("BOT_TOKEN (from @BotFather): ").strip()
    if not token:
        print("❌ BOT_TOKEN is required!")
        sys.exit(1)
    config["telegram"]["bot_token"] = token

    owner_id = input("OWNER_ID (your user ID): ").strip()
    if not owner_id:
        print("❌ OWNER_ID is required!")
        sys.exit(1)
    config["telegram"]["owner_id"] = int(owner_id)

    proxy = input("PROXY (JSON format, or press Enter to skip): ").strip()
    if proxy:
        try:
            config["telegram"]["proxy"] = json.loads(proxy)
        except:
            print("  ⚠ Invalid JSON, skipping proxy")
            config["telegram"]["proxy"] = None
    else:
        config["telegram"]["proxy"] = None

    ipv6 = input("Enable IPv6? (y/N): ").strip().lower()
    config["telegram"]["ipv6"] = ipv6 == 'y'

    # Search engine settings
    print("\n--- Search Engine Settings ---")

    engine = input("Engine (meili/mongo/zinc/elastic) [meili]: ").strip().lower()
    config["search_engine"]["engine"] = engine or "meili"

    print(f"\nConfiguring {config['search_engine']['engine']}...")

    if config["search_engine"]["engine"] == "meili":
        meili_host = input(f"MeiliSearch Host [http://meili:7700]: ").strip()
        config["search_engine"]["meili"]["host"] = meili_host or "http://meili:7700"
        meili_key = input("MeiliSearch Master Key (optional): ").strip()
        config["search_engine"]["meili"]["master_key"] = meili_key or None

    elif config["search_engine"]["engine"] == "mongo":
        mongo_host = input("MongoDB Host [mongo]: ").strip()
        config["search_engine"]["mongo"]["host"] = mongo_host or "mongo"
        mongo_port = input("MongoDB Port [27017]: ").strip()
        config["search_engine"]["mongo"]["port"] = int(mongo_port) if mongo_port else 27017

    elif config["search_engine"]["engine"] == "zinc":
        zinc_host = input("Zinc Host [http://zinc:4080]: ").strip()
        config["search_engine"]["zinc"]["host"] = zinc_host or "http://zinc:4080"
        zinc_user = input("Zinc User [root]: ").strip()
        config["search_engine"]["zinc"]["user"] = zinc_user or "root"
        zinc_pass = input("Zinc Password [root]: ").strip()
        config["search_engine"]["zinc"]["password"] = zinc_pass or "root"

    elif config["search_engine"]["engine"] == "elastic":
        elastic_host = input("Elasticsearch Host [http://elasticsearch:9200]: ").strip()
        config["search_engine"]["elastic"]["host"] = elastic_host or "http://elasticsearch:9200"
        elastic_user = input("Elasticsearch User [elastic]: ").strip()
        config["search_engine"]["elastic"]["user"] = elastic_user or "elastic"
        elastic_pass = input("Elasticsearch Password [changeme]: ").strip()
        config["search_engine"]["elastic"]["password"] = elastic_pass or "changeme"

    # Bot access control
    print("\n--- Bot Access Control ---")

    bot_mode = input("Bot Mode (private/group/public) [private]: ").strip().lower()
    config["bot"]["mode"] = bot_mode or "private"

    if config["bot"]["mode"] == "group":
        groups = input("Allowed Groups (comma-separated IDs): ").strip()
        if groups:
            config["bot"]["allowed_groups"] = [int(g.strip()) for g in groups.split(",")]
        else:
            config["bot"]["allowed_groups"] = []

        users = input("Allowed Users (comma-separated IDs): ").strip()
        if users:
            config["bot"]["allowed_users"] = [int(u.strip()) for u in users.split(",")]
        else:
            config["bot"]["allowed_users"] = []
    else:
        config["bot"]["allowed_groups"] = []
        config["bot"]["allowed_users"] = []

    # Privacy settings
    print("\n--- Privacy Settings ---")
    privacy_file = input("Privacy Storage File [privacy_data.json]: ").strip()
    config["privacy"]["storage_file"] = privacy_file or "privacy_data.json"

    # Sync settings
    print("\n--- Sync Settings ---")

    # Migrate from sync.ini if exists
    migrated_chats = migrate_sync_ini_to_json()

    sync_enabled = input("Enable sync? (Y/n): ").strip().lower()
    config["sync"]["enabled"] = sync_enabled != 'n'

    if config["sync"]["enabled"]:
        config["sync"]["checkpoint_file"] = "sync_progress.json"
        config["sync"]["batch_size"] = 100
        config["sync"]["retry_on_error"] = True
        config["sync"]["max_retries"] = 3
        config["sync"]["resume_on_restart"] = True

        if migrated_chats:
            use_migrated = input(f"Use {len(migrated_chats)} chats from sync.ini? (Y/n): ").strip().lower()
            if use_migrated != 'n':
                config["sync"]["chats"] = migrated_chats
            else:
                chats = input("Sync Chats (comma-separated IDs): ").strip()
                if chats:
                    config["sync"]["chats"] = [int(c.strip()) for c in chats.split(",")]
                else:
                    config["sync"]["chats"] = []
        else:
            chats = input("Sync Chats (comma-separated IDs): ").strip()
            if chats:
                config["sync"]["chats"] = [int(c.strip()) for c in chats.split(",")]
            else:
                config["sync"]["chats"] = []
    else:
        config["sync"]["checkpoint_file"] = "sync_progress.json"
        config["sync"]["batch_size"] = 100
        config["sync"]["retry_on_error"] = True
        config["sync"]["max_retries"] = 3
        config["sync"]["resume_on_restart"] = True
        config["sync"]["chats"] = []

    return config


def save_config(config, filename="config.json"):
    """Save configuration to JSON file."""
    # Backup existing config if it exists
    if os.path.exists(filename):
        backup_name = f"{filename}.backup"
        print(f"\n⚠️  {filename} already exists!")
        overwrite = input(f"Backup to {backup_name} and overwrite? (y/N): ").strip().lower()

        if overwrite == 'y':
            os.rename(filename, backup_name)
            print(f"✅ Backed up existing config to {backup_name}")
        else:
            print("❌ Aborted. Config not saved.")
            return False

    with open(filename, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Configuration saved to {filename}")
    return True


def main():
    """Main migration workflow."""
    print("\n🔧 SearchGram Configuration Migration Tool\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print("Automatic migration from environment variables...")
        # TODO: Implement auto-migration from env vars
        print("❌ Auto-migration not yet implemented. Use interactive mode.")
        return

    try:
        config = create_config_json_interactive()

        print("\n" + "="*60)
        print("Configuration Summary")
        print("="*60)
        print(json.dumps(config, indent=2))
        print("="*60 + "\n")

        confirm = input("Save this configuration? (Y/n): ").strip().lower()

        if confirm != 'n':
            if save_config(config):
                print("\n✅ Migration complete!")
                print("\nNext steps:")
                print("1. Review config.json")
                print("2. Restart SearchGram to use new configuration")
                print("3. Old sync.ini will be preserved (you can delete it manually)")
        else:
            print("❌ Configuration not saved.")

    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled.")
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
