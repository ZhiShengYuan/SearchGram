# SearchGram Configuration Guide

## Overview

SearchGram uses **JSON-only configuration** for all settings.

**IMPORTANT:**
- ✅ All configuration **must** be in `config.json`
- ❌ **No environment variables** are supported
- ✅ Clear validation and helpful error messages
- ✅ Single source of truth for all settings

## Why JSON-Only?

1. **Simplicity**: One place for all configuration
2. **Version Control**: Easy to track and diff changes
3. **Type Safety**: JSON enforces structure
4. **No Ambiguity**: No priority confusion
5. **Validation**: Required fields checked on startup

---

## Quick Start

### Option 1: Interactive Migration (Recommended)

If you have existing configuration, use the migration tool:

```bash
python migrate_config.py
```

This will:
- Guide you through all settings
- Migrate `sync.ini` to new format
- Create `config.json` automatically
- Backup existing files

### Option 2: Manual Configuration

1. Copy the example configuration:
```bash
cp config.example.json config.json
```

2. Edit `config.json` with your settings

3. Start SearchGram - it will automatically use the JSON config

### Option 3: Docker/Production Deployment

For Docker or production, mount `config.json` as a volume or secret:

```yaml
# docker-compose.yml
services:
  searchgram:
    volumes:
      - ./config.json:/app/config.json:ro
```

Or use Docker secrets for sensitive values.

---

## Configuration Structure

### config.json Example

```json
{
  "telegram": {
    "app_id": 123456,
    "app_hash": "your_app_hash_here",
    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    "owner_id": 260260121,
    "proxy": null,
    "ipv6": false
  },
  "search_engine": {
    "engine": "elastic",
    "meili": {
      "host": "http://meili:7700",
      "master_key": null
    },
    "mongo": {
      "host": "mongo",
      "port": 27017
    },
    "zinc": {
      "host": "http://zinc:4080",
      "user": "root",
      "password": "root"
    },
    "elastic": {
      "host": "http://elasticsearch:9200",
      "user": "elastic",
      "password": "changeme"
    }
  },
  "bot": {
    "mode": "private",
    "allowed_groups": [],
    "allowed_users": []
  },
  "privacy": {
    "storage_file": "privacy_data.json"
  },
  "sync": {
    "enabled": true,
    "checkpoint_file": "sync_progress.json",
    "batch_size": 100,
    "retry_on_error": true,
    "max_retries": 3,
    "resume_on_restart": true,
    "chats": []
  }
}
```

---

## Configuration Sections

### 1. Telegram Settings

**JSON Path:** `telegram.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `app_id` | int | - | Telegram API ID from https://my.telegram.org/ |
| `app_hash` | string | - | **Required** - Telegram API hash from https://my.telegram.org/ |
| `bot_token` | string | - | **Required** - Bot token from @BotFather |
| `owner_id` | int | - | **Required** - Your Telegram user ID |
| `proxy` | object/null | null | Optional - Proxy configuration (see below) |
| `ipv6` | boolean | false | Optional - Enable IPv6 support |

**Proxy Example:**
```json
"proxy": {
  "scheme": "socks5",
  "hostname": "localhost",
  "port": 1080,
  "username": "user",
  "password": "pass"
}
```

---

### 2. Search Engine Settings

**JSON Path:** `search_engine.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `engine` | string | "meili" | Search backend: `meili`, `mongo`, `zinc`, `elastic` |

#### MeiliSearch Settings

**JSON Path:** `search_engine.meili.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | string | "http://meili:7700" | MeiliSearch server URL |
| `master_key` | string/null | null | Master key for authentication |


#### MongoDB Settings

**JSON Path:** `search_engine.mongo.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | string | "mongo" | MongoDB hostname |
| `port` | int | 27017 | MongoDB port |


#### Zinc Settings

**JSON Path:** `search_engine.zinc.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | string | "http://zinc:4080" | ZincSearch server URL |
| `user` | string | "root" | Username |
| `password` | string | "root" | Password |


#### Elasticsearch Settings (NEW)

**JSON Path:** `search_engine.elastic.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | string | "http://elasticsearch:9200" | Elasticsearch server URL |
| `user` | string | "elastic" | Username for authentication |
| `password` | string | "changeme" | Password for authentication |


---

### 3. Bot Access Control

**JSON Path:** `bot.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `mode` | string | "private" | Access mode: `private`, `group`, `public` |
| `allowed_groups` | array[int] | [] | Whitelisted group IDs (for group mode) |
| `allowed_users` | array[int] | [] | Whitelisted user IDs (for group mode) |


**Access Modes:**
- **`private`**: Only owner can use the bot (most secure)
- **`group`**: Bot works in whitelisted groups and for allowed users
- **`public`**: Anyone can use the bot (not recommended)

**Example:**
```json
{
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890, -1009876543210],
    "allowed_users": [123456789, 987654321]
  }
}
```

---

### 4. Privacy Settings

**JSON Path:** `privacy.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `storage_file` | string | "privacy_data.json" | File to store user opt-out preferences |


---

### 5. Sync Settings (NEW)

**JSON Path:** `sync.*`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | true | Enable background sync |
| `checkpoint_file` | string | "sync_progress.json" | Progress checkpoint file |
| `batch_size` | int | 100 | Messages per checkpoint save |
| `retry_on_error` | boolean | true | Retry on errors |
| `max_retries` | int | 3 | Maximum retry attempts |
| `resume_on_restart` | boolean | true | Resume from checkpoint on restart |
| `chats` | array[int] | [] | Chat IDs to sync |


**Example:**
```json
{
  "sync": {
    "enabled": true,
    "checkpoint_file": "sync_progress.json",
    "batch_size": 100,
    "retry_on_error": true,
    "max_retries": 3,
    "resume_on_restart": true,
    "chats": [-1001234567890, 123456789]
  }
}
```

---

## Resume-Capable Sync System

### How It Works

1. **Configuration**: Add chat IDs to `sync.chats` in `config.json`
2. **Automatic Checkpointing**: Progress saved every 100 messages (configurable)
3. **Resume on Restart**: If interrupted, sync continues from last checkpoint
4. **Progress Tracking**: Real-time updates sent to Saved Messages

### Checkpoint File Structure

`sync_progress.json` contains:

```json
{
  "last_updated": "2025-12-25T10:30:00",
  "chats": [
    {
      "chat_id": -1001234567890,
      "total_count": 10000,
      "synced_count": 5432,
      "last_message_id": 123456,
      "status": "in_progress",
      "error_count": 0,
      "last_error": null,
      "started_at": "2025-12-25T10:00:00",
      "completed_at": null,
      "last_checkpoint": "2025-12-25T10:29:55",
      "progress_percent": 54.32
    }
  ]
}
```

### Sync Status Values

- **`pending`**: Waiting to start
- **`in_progress`**: Currently syncing
- **`completed`**: Fully synced
- **`failed`**: Sync failed after max retries
- **`paused`**: Paused due to FloodWait or other temporary issue

### Resume Example

If sync is interrupted at 5,432 out of 10,000 messages:

1. Restart SearchGram
2. Client loads `sync_progress.json`
3. Sync continues from message 5,433
4. Progress updates continue in Saved Messages

---

## Migration from Old System

### From sync.ini to config.json

**Old System (sync.ini):**
```ini
[sync]
-1001234567890
123456789
```

**New System (config.json):**
```json
{
  "sync": {
    "enabled": true,
    "chats": [-1001234567890, 123456789]
  }
}
```

**Migration Command:**
```bash
python migrate_config.py
```

The migration tool will:
- Read your `sync.ini`
- Extract chat IDs
- Add them to `config.json`
- Preserve `sync.ini` as backup

---

## Best Practices

### Security

1. **Never commit config.json to git** - Add to `.gitignore`
2. **Use environment variables in CI/CD** - Safer than files
3. **Restrict file permissions**: `chmod 600 config.json`
4. **Use private mode by default** - Switch to group mode only when needed

### Performance

1. **Batch size**: 100-200 for best performance (avoid FloodWait)
2. **Enable resume**: Always keep `resume_on_restart: true`
3. **Elasticsearch**: Best for large deployments (millions of messages)

### Reliability

1. **Check sync_progress.json** after interruptions
2. **Monitor error_count** in checkpoint file
3. **Failed syncs**: Investigate `last_error` field
4. **FloodWait**: Automatic handling, but reduce batch size if frequent

---

## Error Messages

### Missing config.json

```
❌ Configuration file not found: config.json

SearchGram requires a JSON configuration file.

Quick setup:
1. Copy example: cp config.example.json config.json
2. Edit config.json with your settings
3. Or run migration: python migrate_config.py
```

**Solution:** Create `config.json` using one of the methods above.

### Invalid JSON

```
❌ Invalid JSON in configuration file: config.json
Error: Expecting ',' delimiter: line 10 column 5
```

**Solution:** Fix JSON syntax. Use a JSON validator or editor with syntax checking.

### Missing Required Fields

```
❌ Missing required configuration fields in config.json:
  - telegram.app_id (Telegram API ID)
  - telegram.app_hash (Telegram API Hash)
```

**Solution:** Add the missing fields to `config.json`.

## Troubleshooting

### Config not loading

```bash
# Check if config.json exists
ls -la config.json

# Validate JSON syntax
python -m json.tool config.json

# Test config loading
python -c "from searchgram.config_loader import *; print(f'APP_ID: {APP_ID}, ENGINE: {ENGINE}')"
```

### Sync not resuming

Check `sync_progress.json`:
- Does it exist?
- Is `resume_on_restart` true?
- What's the status of pending chats?

```bash
cat sync_progress.json | python -m json.tool
```

### Configuration changes not taking effect

```bash
# Restart SearchGram after editing config.json
pkill -f "python.*client.py"
pkill -f "python.*bot.py"

# Restart
python searchgram/client.py &
python searchgram/bot.py &
```

---

## Complete Example

### Minimal config.json

```json
{
  "telegram": {
    "app_id": 123456,
    "app_hash": "abc123def456",
    "bot_token": "123456:ABC-DEF",
    "owner_id": 260260121
  },
  "search_engine": {
    "engine": "elastic",
    "elastic": {
      "host": "http://localhost:9200",
      "user": "elastic",
      "password": "changeme"
    }
  },
  "sync": {
    "enabled": true,
    "chats": [-1001234567890]
  }
}
```

### Production config.json

```json
{
  "telegram": {
    "app_id": 123456,
    "app_hash": "your_hash_here",
    "bot_token": "your_token_here",
    "owner_id": 260260121,
    "proxy": {
      "scheme": "socks5",
      "hostname": "proxy.example.com",
      "port": 1080
    },
    "ipv6": false
  },
  "search_engine": {
    "engine": "elastic",
    "elastic": {
      "host": "http://elasticsearch:9200",
      "user": "elastic",
      "password": "strong_password_here"
    }
  },
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890, -1009876543210],
    "allowed_users": [123456789, 987654321]
  },
  "privacy": {
    "storage_file": "privacy_data.json"
  },
  "sync": {
    "enabled": true,
    "checkpoint_file": "sync_progress.json",
    "batch_size": 150,
    "retry_on_error": true,
    "max_retries": 5,
    "resume_on_restart": true,
    "chats": [-1001234567890, -1009876543210]
  }
}
```

---

## Summary

✅ **JSON configuration** - Structured, easy to manage
✅ **Environment variable fallback** - Backwards compatible
✅ **Resume-capable sync** - Never lose progress
✅ **Migration tool** - Easy upgrade from old system
✅ **Checkpoint system** - Crash-resistant synchronization
✅ **Flexible access control** - Private, group, or public modes

For questions, see [CLAUDE.md](CLAUDE.md) or [README.md](README.md).
