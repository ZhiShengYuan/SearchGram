# SearchGram Configuration Reference

Complete guide to all configuration fields in `config.json`.

## Table of Contents

- [Telegram Section](#telegram-section)
- [Search Engine Section](#search-engine-section)
- [Bot Section](#bot-section)
- [Privacy Section](#privacy-section)
- [Sync Section](#sync-section)

---

## Telegram Section

Telegram API and bot credentials configuration.

```json
"telegram": {
  "app_id": 123456,
  "app_hash": "your_app_hash_here",
  "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "owner_id": 260260121,
  "proxy": null,
  "ipv6": false
}
```

### `app_id`
- **Type**: Integer
- **Required**: Yes
- **Description**: Telegram API application ID
- **How to get**: Register at https://my.telegram.org/apps
- **Example**: `123456`
- **Notes**: Used by the client (user session) to connect to Telegram

### `app_hash`
- **Type**: String
- **Required**: Yes
- **Description**: Telegram API application hash
- **How to get**: Register at https://my.telegram.org/apps (provided with app_id)
- **Example**: `"a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"`
- **Notes**: Keep this secret, don't share publicly

### `bot_token`
- **Type**: String
- **Required**: Yes
- **Description**: Telegram bot token for the search bot
- **How to get**: Contact @BotFather on Telegram and create a new bot
- **Example**: `"123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"`
- **Format**: `{bot_id}:{token_string}`
- **Notes**: Keep this secret, anyone with this token can control your bot

### `owner_id`
- **Type**: Integer
- **Required**: Yes
- **Description**: Telegram user ID of the bot owner
- **How to get**: Contact @userinfobot on Telegram to get your user ID
- **Example**: `260260121`
- **Permissions**: Owner has full access regardless of bot_mode setting
- **Notes**: Can execute admin commands like `/ping`, `/delete`, etc.

### `proxy`
- **Type**: Object or null
- **Required**: No
- **Default**: `null` (no proxy)
- **Description**: Proxy configuration for Telegram connections
- **Use case**: Required in countries where Telegram is blocked (e.g., China, Iran)

**Example with SOCKS5 proxy:**
```json
"proxy": {
  "scheme": "socks5",
  "hostname": "127.0.0.1",
  "port": 1080
}
```

**Example with HTTP proxy:**
```json
"proxy": {
  "scheme": "http",
  "hostname": "proxy.example.com",
  "port": 8080,
  "username": "user",
  "password": "pass"
}
```

**Supported schemes**: `socks5`, `socks4`, `http`

### `ipv6`
- **Type**: Boolean
- **Required**: No
- **Default**: `false`
- **Description**: Enable IPv6 for Telegram connections
- **Values**:
  - `true` - Use IPv6 (if your network supports it)
  - `false` - Use IPv4 only
- **Notes**: Only enable if your network has native IPv6 support

---

## Search Engine Section

Search backend configuration with support for multiple engines.

```json
"search_engine": {
  "engine": "http",
  "http": { ... },
  "meili": { ... },
  "mongo": { ... },
  "zinc": { ... },
  "elastic": { ... }
}
```

### `engine`
- **Type**: String
- **Required**: Yes
- **Description**: Which search engine backend to use
- **Options**:
  - `"http"` - **Recommended**: Go search service via HTTP API (best performance)
  - `"meili"` - MeiliSearch (typo-tolerant, fuzzy search)
  - `"mongo"` - MongoDB (regex-based search)
  - `"zinc"` - ZincSearch (full-text search)
  - `"elastic"` - Elasticsearch (CJK-optimized, direct connection)

**Recommendation**: Use `"http"` with the Go search service for best performance, security, and CJK language support.

---

### HTTP Engine (Recommended)

```json
"http": {
  "base_url": "http://searchgram-engine:8080",
  "api_key": null,
  "timeout": 30,
  "max_retries": 3
}
```

#### `base_url`
- **Type**: String
- **Required**: Yes (if using http engine)
- **Description**: URL of the Go search service
- **Examples**:
  - Docker: `"http://searchgram-engine:8080"`
  - Localhost: `"http://127.0.0.1:8080"`
  - Remote: `"http://search.example.com:8080"`
- **Notes**:
  - Supports both HTTP and HTTPS
  - HTTP/2 will be automatically used when available
  - No trailing slash needed

#### `api_key`
- **Type**: String or null
- **Required**: No
- **Default**: `null` (no authentication)
- **Description**: API key for authenticating with the Go search service
- **Example**: `"605867f6-78a0-4b40-96b0-db734d037f95"`
- **Security**: Set this if your Go service has `auth.enabled: true`
- **Notes**: Must match the `auth.api_key` in the Go service's `config.yaml`

#### `timeout`
- **Type**: Integer
- **Required**: No
- **Default**: `30`
- **Description**: Request timeout in seconds
- **Range**: 5-300 seconds
- **Recommendations**:
  - LAN deployment: 10-30 seconds
  - Internet deployment: 30-60 seconds
  - Slow connections: 60-120 seconds

#### `max_retries`
- **Type**: Integer
- **Required**: No
- **Default**: `3`
- **Description**: Maximum number of retry attempts for failed requests
- **Range**: 0-10
- **Behavior**: Automatically retries on network errors and 5xx HTTP status codes
- **Backoff**: Uses exponential backoff (1s, 2s, 4s, etc.)

---

### MeiliSearch Engine

```json
"meili": {
  "host": "http://meili:7700",
  "master_key": null
}
```

#### `host`
- **Type**: String
- **Description**: MeiliSearch server URL
- **Examples**: `"http://localhost:7700"`, `"http://meili:7700"`

#### `master_key`
- **Type**: String or null
- **Description**: MeiliSearch master key for authentication
- **Example**: `"your-meili-master-key-here"`
- **Notes**: Required if MeiliSearch has authentication enabled

---

### MongoDB Engine

```json
"mongo": {
  "host": "mongo",
  "port": 27017
}
```

#### `host`
- **Type**: String
- **Description**: MongoDB server hostname or IP
- **Examples**: `"localhost"`, `"mongo"`, `"192.168.1.100"`

#### `port`
- **Type**: Integer
- **Default**: `27017`
- **Description**: MongoDB server port
- **Standard**: 27017 is the default MongoDB port

---

### ZincSearch Engine

```json
"zinc": {
  "host": "http://zinc:4080",
  "user": "root",
  "password": "root"
}
```

#### `host`
- **Type**: String
- **Description**: ZincSearch server URL
- **Examples**: `"http://localhost:4080"`, `"http://zinc:4080"`

#### `user`
- **Type**: String
- **Default**: `"root"`
- **Description**: ZincSearch authentication username

#### `password`
- **Type**: String
- **Default**: `"root"`
- **Description**: ZincSearch authentication password
- **Security**: Change from default in production!

---

### Elasticsearch Engine

```json
"elastic": {
  "host": "http://elasticsearch:9200",
  "user": "elastic",
  "password": "changeme"
}
```

#### `host`
- **Type**: String
- **Description**: Elasticsearch server URL
- **Examples**: `"http://localhost:9200"`, `"https://es.example.com:9200"`
- **Notes**: Supports both HTTP and HTTPS

#### `user`
- **Type**: String
- **Default**: `"elastic"`
- **Description**: Elasticsearch authentication username

#### `password`
- **Type**: String
- **Default**: `"changeme"`
- **Description**: Elasticsearch authentication password
- **Security**: Always change from default in production!

---

## Bot Section

Access control and bot behavior configuration.

```json
"bot": {
  "mode": "private",
  "allowed_groups": [],
  "allowed_users": []
}
```

### `mode`
- **Type**: String or Array of strings
- **Required**: Yes
- **Description**: Bot access control mode (supports multiple modes simultaneously)
- **Single mode options**:
  - `"private"` - **Default**: Only the owner can use the bot
  - `"group"` - Bot works in whitelisted groups
  - `"public"` - Anyone can use the bot (not recommended)

**Multi-mode support (NEW)**:
The bot now supports multiple modes simultaneously by providing an array:

```json
"mode": ["private", "group"]
```

**Mode combinations**:
- `"private"` - Owner only in all chats
- `"group"` - Anyone in whitelisted groups, allowed_users in private chats
- `["private", "group"]` - Owner + allowed_users in private chats, anyone in whitelisted groups
- `["group"]` - Same as `"group"` (array with single value)
- `"public"` - Anyone anywhere (not recommended)

**Group search behavior (NEW)**:
- When searching in a group, results are automatically filtered to only show messages from that specific group
- This prevents leaking messages from other groups/chats
- Private searches still return results from all indexed chats

**Security recommendations**:
- Start with `"private"` mode
- Use `["private", "group"]` for owner + trusted groups
- Use `"group"` for group-only bot (no private access except owner)
- Avoid `"public"` unless you understand privacy implications

### `allowed_groups`
- **Type**: Array of integers
- **Required**: Only if mode is "group"
- **Default**: `[]` (empty array)
- **Description**: List of Telegram group IDs where the bot can work
- **Example**: `[-1001234567890, -1009876543210]`
- **How to get group ID**:
  1. Add @userinfobot to your group
  2. It will show the group ID (negative number)
  3. Remove @userinfobot after
- **Format**: Group IDs are always negative numbers
- **Notes**: Only works when `mode: "group"`

### `allowed_users`
- **Type**: Array of integers
- **Required**: No
- **Default**: `[]` (empty array)
- **Description**: Additional user IDs who can use the bot (outside of groups)
- **Example**: `[123456789, 987654321]`
- **How to get user ID**: Contact @userinfobot on Telegram
- **Format**: User IDs are positive numbers
- **Notes**:
  - Works in both "group" and "private" modes
  - Owner ID doesn't need to be listed here (always has access)

---

## Privacy Section

User privacy and data protection settings.

```json
"privacy": {
  "storage_file": "privacy_data.json"
}
```

### `storage_file`
- **Type**: String
- **Required**: No
- **Default**: `"privacy_data.json"`
- **Description**: File path to store privacy preferences (blocked users list)
- **Path types**:
  - Relative: `"privacy_data.json"` (in current directory)
  - Absolute: `"/var/lib/searchgram/privacy_data.json"`
- **Format**: JSON file storing user IDs who opted out via `/block_me`
- **Backup**: Recommended to backup this file regularly
- **Notes**:
  - Users can opt-out with `/block_me` command
  - Blocked users' messages won't appear in search results
  - File is automatically created if it doesn't exist

---

## Sync Section

Background chat history synchronization settings.

```json
"sync": {
  "enabled": true,
  "checkpoint_file": "sync_progress.json",
  "batch_size": 100,
  "retry_on_error": true,
  "max_retries": 3,
  "resume_on_restart": true,
  "chats": []
}
```

### `enabled`
- **Type**: Boolean
- **Required**: No
- **Default**: `true`
- **Description**: Enable/disable background sync on client startup
- **Values**:
  - `true` - Automatically sync configured chats
  - `false` - Don't sync (manual only)

### `checkpoint_file`
- **Type**: String
- **Required**: No
- **Default**: `"sync_progress.json"`
- **Description**: File to store sync progress for resume capability
- **Path types**:
  - Relative: `"sync_progress.json"`
  - Absolute: `"/var/lib/searchgram/sync_progress.json"`
- **Format**: JSON file with last synced message IDs per chat
- **Notes**: Allows resuming sync after crashes or restarts

### `batch_size`
- **Type**: Integer
- **Required**: No
- **Default**: `100`
- **Range**: 10-1000
- **Description**: Number of messages to process per batch
- **Recommendations**:
  - Small chats: 100-200
  - Large chats (millions of messages): 50-100
  - Fast network: 200-500
  - Slow network: 50-100
- **Trade-offs**:
  - Larger batch = faster sync, more memory
  - Smaller batch = slower sync, less memory, more frequent checkpoints

### `retry_on_error`
- **Type**: Boolean
- **Required**: No
- **Default**: `true`
- **Description**: Automatically retry on sync errors
- **Values**:
  - `true` - Retry failed operations
  - `false` - Stop sync on first error

### `max_retries`
- **Type**: Integer
- **Required**: No
- **Default**: `3`
- **Range**: 0-10
- **Description**: Maximum retry attempts per failed operation
- **Behavior**: Uses exponential backoff between retries
- **Notes**: Applies to both network errors and FloodWait errors

### `resume_on_restart`
- **Type**: Boolean
- **Required**: No
- **Default**: `true`
- **Description**: Resume incomplete syncs from checkpoint on restart
- **Values**:
  - `true` - Continue from last checkpoint
  - `false` - Start sync from beginning
- **Notes**: Requires `checkpoint_file` to exist

### `chats`
- **Type**: Array of objects
- **Required**: No (but needed for sync to work)
- **Default**: `[]` (empty array, no chats to sync)
- **Description**: List of chats to sync with their configurations

**Chat object structure**:
```json
{
  "id": -1001234567890,
  "name": "My Group Name",
  "enabled": true
}
```

**Example with multiple chats**:
```json
"chats": [
  {
    "id": -1001234567890,
    "name": "Tech Discussion",
    "enabled": true
  },
  {
    "id": -1009876543210,
    "name": "Project Updates",
    "enabled": true
  },
  {
    "id": 123456789,
    "name": "Personal Chat",
    "enabled": false
  }
]
```

**Chat fields**:

#### `id`
- **Type**: Integer
- **Required**: Yes
- **Description**: Telegram chat ID
- **Format**:
  - Groups/Supergroups: Negative numbers (e.g., `-1001234567890`)
  - Channels: Negative numbers (e.g., `-1001234567890`)
  - Private chats: Positive numbers (user ID)
  - Bots: Positive numbers (bot ID)
- **How to get**: Use @userinfobot or check SearchGram logs

#### `name`
- **Type**: String
- **Required**: No (but recommended)
- **Description**: Human-readable chat name for identification
- **Purpose**: Makes config file easier to read
- **Notes**: Not used by the application, just for documentation

#### `enabled`
- **Type**: Boolean
- **Required**: No
- **Default**: `true`
- **Description**: Whether to sync this chat
- **Values**:
  - `true` - Include in sync
  - `false` - Skip this chat (but keep config)
- **Use case**: Temporarily disable sync without removing chat from config

---

## Configuration Priority

SearchGram uses the following priority order (highest to lowest):

1. **Environment variables** (e.g., `OWNER_ID=123456`)
2. **config.json** file values
3. **Default values** (hardcoded in application)

This allows you to:
- Use `config.json` for most settings
- Override specific values with environment variables
- Run in Docker with environment-based configuration

---

## Complete Example Configurations

### Example 1: Private + Group Multi-Mode (Recommended)

Owner can use in private chats, allowed users can use in private, bot works in whitelisted groups:

```json
{
  "telegram": {
    "app_id": 176552,
    "app_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "owner_id": 260260121,
    "proxy": null,
    "ipv6": false
  },
  "search_engine": {
    "engine": "http",
    "http": {
      "base_url": "http://searchgram-engine:8080",
      "api_key": "secure-api-key-here",
      "timeout": 30,
      "max_retries": 3
    }
  },
  "bot": {
    "mode": ["private", "group"],
    "allowed_groups": [-1001234567890, -1009876543210],
    "allowed_users": [123456789, 987654321]
  },
  "privacy": {
    "storage_file": "/var/lib/searchgram/privacy_data.json"
  },
  "sync": {
    "enabled": true,
    "checkpoint_file": "/var/lib/searchgram/sync_progress.json",
    "batch_size": 100,
    "retry_on_error": true,
    "max_retries": 3,
    "resume_on_restart": true,
    "chats": [
      {
        "id": -1001234567890,
        "name": "Tech Discussion Group",
        "enabled": true
      },
      {
        "id": -1009876543210,
        "name": "Project Updates",
        "enabled": true
      }
    ]
  }
}
```

**Behavior**:
- Owner (260260121) can use bot in private chat → searches all indexed messages
- Allowed users (123456789, 987654321) can use bot in private chat → searches all indexed messages
- Anyone in allowed groups can use bot → searches only messages from that specific group
- Group searches automatically filtered by chat_id to prevent cross-group leaks

### Example 2: Private Only Mode

Traditional owner-only setup:

```json
{
  "telegram": {
    "app_id": 176552,
    "app_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "owner_id": 260260121,
    "proxy": {
      "scheme": "socks5",
      "hostname": "127.0.0.1",
      "port": 1080
    },
    "ipv6": false
  },
  "search_engine": {
    "engine": "http",
    "http": {
      "base_url": "http://searchgram-engine:8080",
      "api_key": "secure-api-key-here",
      "timeout": 30,
      "max_retries": 3
    }
  },
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890, -1009876543210],
    "allowed_users": [123456789, 987654321]
  },
  "privacy": {
    "storage_file": "/var/lib/searchgram/privacy_data.json"
  },
  "sync": {
    "enabled": true,
    "checkpoint_file": "/var/lib/searchgram/sync_progress.json",
    "batch_size": 100,
    "retry_on_error": true,
    "max_retries": 3,
    "resume_on_restart": true,
    "chats": [
      {
        "id": -1001234567890,
        "name": "Tech Discussion Group",
        "enabled": true
      },
      {
        "id": -1009876543210,
        "name": "Project Updates",
        "enabled": true
      }
    ]
  }
}
```

---

## Migration from Old Config

If you're migrating from the old `config.py` or environment variable setup:

### Old (config.py):
```python
APP_ID = 176552
APP_HASH = "your_hash"
TOKEN = "bot_token"
OWNER_ID = 260260121
ENGINE = "http"
HTTP_BASE_URL = "http://localhost:8080"
BOT_MODE = "private"
```

### New (config.json):
```json
{
  "telegram": {
    "app_id": 176552,
    "app_hash": "your_hash",
    "bot_token": "bot_token",
    "owner_id": 260260121
  },
  "search_engine": {
    "engine": "http",
    "http": {
      "base_url": "http://localhost:8080"
    }
  },
  "bot": {
    "mode": "private"
  }
}
```

---

## Troubleshooting

### Common Issues

**Problem**: Bot doesn't respond
**Check**:
- `bot_token` is correct
- `owner_id` matches your Telegram user ID
- Bot is running (`python3 searchgram/bot.py`)

**Problem**: Client can't connect to Telegram
**Check**:
- `app_id` and `app_hash` are correct
- `proxy` is configured if needed
- Session files exist in `searchgram/session/`

**Problem**: Search not working
**Check**:
- Search engine is running
- `engine` field matches your setup
- `http.base_url` is accessible
- Go service is running: `curl http://127.0.0.1:8080/health`

**Problem**: Sync not starting
**Check**:
- `sync.enabled` is `true`
- `sync.chats` array is not empty
- Chat IDs are correct (use @userinfobot)
- Client process is running

---

## Security Best Practices

1. **Never commit `config.json` to git** (use `config.example.json` instead)
2. **Change default passwords** for Elasticsearch, Zinc, etc.
3. **Use strong API keys** (generate with `uuidgen` or similar)
4. **Restrict bot mode** (start with "private", not "public")
5. **Keep credentials secret** (don't share bot_token or app_hash)
6. **Use HTTPS** for remote deployments
7. **Backup privacy_data.json** to preserve user opt-outs
8. **Regular updates** (keep SearchGram and dependencies updated)

---

## See Also

- [HTTP2_IMPLEMENTATION.md](HTTP2_IMPLEMENTATION.md) - HTTP/2 setup and performance
- [INSTALL_HTTP2.md](INSTALL_HTTP2.md) - Installation guide
- [README.md](README.md) - General documentation
- [Docker.md](Docker.md) - Docker deployment guide
