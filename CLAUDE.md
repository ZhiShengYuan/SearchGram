# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SearchGram is a Telegram bot that improves search experience for CJK (Chinese, Japanese, Korean) languages and provides message backup functionality. It works by intercepting incoming/outgoing messages via a user client session and indexing them into a search engine, then providing a bot interface for searching.

## Architecture

The project has a **microservice architecture** with three main components:

1. **Go Search Service** (`searchgram-engine/`):
   - Standalone Go microservice that handles all search engine operations
   - Runs in the same LAN as Elasticsearch for low-latency access
   - Exposes REST API (port 8080) for Python services to communicate
   - Benefits: Better performance, credential isolation, horizontal scalability
   - CJK-optimized Elasticsearch backend with bigram tokenization

2. **Client Process** (`searchgram/client.py`):
   - Runs as a user session (requires phone number login)
   - Intercepts all incoming/outgoing messages (except from the bot itself)
   - Sends messages to Go search service via HTTP API for indexing
   - Handles background chat history sync from `config.json`

3. **Bot Process** (`searchgram/bot.py`):
   - Runs as a Telegram bot (uses bot token)
   - Provides search interface via commands and text messages
   - Supports three access modes: private (owner only), group (whitelisted), public (anyone)
   - Sends search queries to Go service via HTTP API
   - Parses search queries and returns paginated results with inline navigation
   - Includes privacy controls: users can opt-out via `/block_me` command
   - Filters search results to exclude messages from blocked users

**Search Engine**: The project uses HTTP-based search via a Go microservice (`searchgram-engine/`). Configuration:
- Only `engine: http` is supported (legacy engines removed for security and maintainability)
- Search service endpoint: `services.search.base_url` (unified with other service endpoints)
- Authentication: JWT-based (configured in `auth` section) - **required, no fallback**
- The Go service handles Elasticsearch connection pooling, credentials, and CJK optimization internally
- **Go service configuration**: Reads from `search_service` section in unified `config.json`
  - Elasticsearch settings: `search_service.elasticsearch.*`
  - Server settings: `search_service.server.*`
  - Logging: `search_service.logging.*`
  - Cache: `search_service.cache.*`

The HTTP search engine implements the `BasicSearchEngine` interface from `searchgram/engine.py` with methods: `upsert()`, `search()`, `ping()`, `clear_db()`, `delete_user()`, and `dedup()`.

## Configuration

SearchGram uses a **unified JSON-based configuration** (`config.json`) for all services. Configuration priority (highest to lowest):
1. Environment variables
2. `config.json` file
3. Default values

The unified config file is shared between:
- **Python services** (bot and client): Loaded via `searchgram/config_loader.py`
- **Go search service**: Loaded via `searchgram-engine/config/config.go`

All services read from the same `config.json` file, which reduces duplication and ensures consistency.

**Telegram Credentials:**
- `APP_ID`, `APP_HASH`: Telegram API credentials from https://my.telegram.org/
- `TOKEN`: Bot token from @BotFather
- `OWNER_ID`: User ID of the bot owner (always has full access)

**Search Engine Settings:**
- `ENGINE`: Search backend (only `http` is supported - legacy engines removed)
- Search service endpoint: `services.search.base_url` (default: `http://127.0.0.1:8080`)
- HTTP client settings:
  - `search_engine.http.timeout`: Request timeout in seconds (default: 30)
  - `search_engine.http.max_retries`: Max retry attempts (default: 3)
- Authentication: Uses JWT from `auth` section (required)

**Access Control:**
- `BOT_MODE`: Access control mode - `private` (owner only), `group` (whitelisted groups), `public` (anyone)
- `ALLOWED_GROUPS`: List of all group IDs that are indexed and searchable (defines the complete set of groups)
- `ALLOWED_USERS`: List of user IDs who can use the bot (must also be configured in user_group_permissions for group access)
- `ADMINS`: List of admin user IDs who can search ALL indexed groups (like owner but without admin command access)
- `USER_GROUP_PERMISSIONS`: Per-user group access control - maps user_id (string) to list of group_ids they can search

**Permission Hierarchy:**
1. **Owner** (`OWNER_ID`): Full access to all groups, can run admin commands (`/ping`, `/dedup`, `/delete`)
2. **Admins** (`ADMINS`): Can search all indexed groups (from `ALLOWED_GROUPS`), no admin command access
3. **Regular Users**: Can only search groups listed in their `USER_GROUP_PERMISSIONS` entry
4. **Privacy Filter**: Applied to all users except owner in private chat (blocks messages from opted-out users)

**Privacy Settings:**
- `PRIVACY_STORAGE`: Path to privacy data JSON file (default: "privacy_data.json")

**Database Settings (Query Logging):**
- `DATABASE_ENABLED`: Enable SQLite query logging (default: `true`)
- `DATABASE_PATH`: Path to SQLite database file (default: "searchgram_logs.db")

**Sync Settings:**
- `SYNC_ENABLED`: Enable background sync (default: `true`)
- `SYNC_CHECKPOINT_FILE`: Path to sync progress file (default: "sync_progress.json")
- `SYNC_BATCH_SIZE`: Messages per batch (default: 100)
- `SYNC_RETRY_ON_ERROR`: Retry failed syncs (default: `true`)
- `SYNC_MAX_RETRIES`: Max retry attempts (default: 3)
- `SYNC_RESUME_ON_RESTART`: Resume incomplete syncs on restart (default: `true`)
- `SYNC_DELAY_BETWEEN_BATCHES`: Delay between batches in seconds (default: 1.0)
- `SYNC_CLEAR_COMPLETED`: Remove completed chats from checkpoint (default: `false` - **keeps completed chats to prevent re-sync**)

**Network Settings:**
- `PROXY`: Optional proxy configuration (dict or JSON string)
- `IPv6`: Enable IPv6 support

**Go Search Service Settings** (`search_service` section):
- **Server Configuration**:
  - `server.host`: Listen address (default: `127.0.0.1`)
  - `server.port`: Listen port (default: `8080`)
  - `server.read_timeout`: HTTP read timeout (default: `"30s"`)
  - `server.write_timeout`: HTTP write timeout (default: `"30s"`)
- **Elasticsearch Configuration**:
  - `elasticsearch.host`: Elasticsearch endpoint (default: `http://localhost:9200`)
  - `elasticsearch.username`: Username for authentication (default: `"elastic"`)
  - `elasticsearch.password`: Password for authentication
  - `elasticsearch.index`: Index name (default: `"telegram"`)
  - `elasticsearch.shards`: Number of shards (default: `3`)
  - `elasticsearch.replicas`: Number of replicas (default: `1`)
- **Logging Configuration**:
  - `logging.level`: Log level - `debug`, `info`, `warn`, `error` (default: `"info"`)
  - `logging.format`: Log format - `json` or `text` (default: `"json"`)
- **Cache Configuration** (optional):
  - `cache.enabled`: Enable caching (default: `false`)
  - `cache.ttl`: Cache TTL (default: `"300s"`)

**Note**: The Go service automatically reads JWT auth settings from the top-level `auth` section, supporting both file-based keys (`public_key_path`, `private_key_path`) and inline keys (`public_key_inline`, `private_key_inline`).

## Running the Application

```bash
# First-time setup: Create config.json from example
cp config.example.json config.json
# Edit config.json with your settings

# Start the Go search service (Terminal 1)
cd searchgram-engine
go run main.go
# Or set custom config path: CONFIG_PATH=/path/to/config.json go run main.go

# First-time setup: login to client (creates session files) (Terminal 2)
python searchgram/client.py

# Run the Python services (requires two more terminals):
python searchgram/client.py  # Terminal 2 (or run in background)
python searchgram/bot.py     # Terminal 3
```

**Configuration Notes**:
- The Go service automatically detects `config.json` in the parent directory (`../config.json`) or current directory
- You can override the config path using the `CONFIG_PATH` environment variable
- For backward compatibility, the Go service still supports standalone `config.yaml` files
- The Python services use `config.json` by default, with fallback to environment variables

## Testing

```bash
# Run unit tests
python -m pytest searchgram/tests/

# Or use unittest directly
python -m unittest searchgram.tests.tests
```

Tests currently cover the argument parser for search query syntax.

## Key Implementation Details

**Message Indexing** (`client.py`): Messages are converted to JSON via Pyrogram, then augmented with:
- `ID`: Composite key `{chat_id}-{message_id}`
- `timestamp`: Unix timestamp for sorting
- **Bot Message Prevention**: Client automatically skips messages from BOT_ID to prevent circular indexing
- **Statistics Tracking**: Logs indexing rate and skipped messages every 100 messages

**Privacy Controls** (`privacy.py`): User opt-out system
- Users can block themselves from search results via `/block_me`
- Blocked user IDs stored in JSON file (`privacy_data.json`)
- Search results automatically filtered to exclude blocked users
- Thread-safe operations with file-based persistence

**Access Control** (`access_control.py`): Multi-tier permission system with granular group access
- **Bot Modes**:
  - **Private Mode**: Only OWNER_ID can use the bot (default, most secure)
  - **Group Mode**: Bot works in whitelisted groups (`ALLOWED_GROUPS`) and for specific users (`ALLOWED_USERS`)
  - **Public Mode**: Anyone can use the bot (not recommended, no privacy protection)
- **Permission Roles**:
  - **Owner**: Full access to all groups, can run admin commands
  - **Admins** (`ADMINS`): Can search all indexed groups, no admin command access
  - **Regular Users**: Can only search groups listed in `USER_GROUP_PERMISSIONS`
- **Group Filtering**: Search results are automatically filtered based on user's allowed groups
  - Owner and admins: see all indexed groups
  - Regular users: see only groups they have permission for
  - Group chats: results automatically filtered to that specific group
- **Decorators**: `@require_access` for general commands, `@require_owner` for admin commands
- **Methods**: `is_owner()`, `is_admin()`, `get_allowed_groups_for_user()` for permission checks

**Search Query Syntax** (parsed via `argparse` in `bot.py`):
- `-t=TYPE`: Filter by chat type (GROUP, CHANNEL, PRIVATE, SUPERGROUP, BOT)
- `-u=USER`: Filter by username or user_id
- `-m=e`: Exact match mode
- Quotes `"keyword"`: Also triggers exact match

**Filtering Logic** (`sync.ini` file):
- `[whitelist]` section: Only index these chat IDs/usernames/types
- `[blacklist]` section: Never index these chat IDs/usernames/types
- Chat types specified with backticks: `` `PRIVATE` ``
- If whitelist exists, only whitelisted chats are indexed

**Session Management**: Client sessions are stored in `searchgram/session/` directory. The `get_client()` helper in `init_client.py` creates Pyrogram Client instances with proper proxy/IPv6 configuration.

**Background Sync** (`sync_manager.py`): Resume-capable history synchronization
- **Checkpoint System**: Progress saved to `sync_progress.json` every batch
- **Resume on Restart**: Automatically continues from last position
- **Batch Processing**: Configurable batch size (default: 100 messages)
- **Error Handling**: Retry logic with configurable max retries
- **FloodWait Handling**: Automatic waiting and retry on rate limits
- **Progress Tracking**: Real-time updates to Saved Messages
- **Configuration**: Chat list in `config.json` under `sync.chats`

**Old vs New Sync System:**
- **Old**: `sync.ini` file, no resume capability, removed chats after sync
- **New**: `config.json` + `sync_progress.json`, full resume capability, persistent progress
- **Migration**: Run `python migrate_config.py` to convert `sync.ini` to new format

## Bot Commands

**Search Commands:**
- `/start` - Start the bot and get welcome message
- `/help` - Show comprehensive help with search syntax and privacy info
- `/{chat_type} [username] keyword` - Type-specific search (PRIVATE, GROUP, CHANNEL, etc.)

**Privacy Commands:**
- `/block_me` - Opt-out: Remove yourself from search results
- `/unblock_me` - Opt-in: Allow your messages in search results
- `/privacy_status` - Check your current privacy status

**Activity Stats Commands (Group Only):**
- `/mystats` - Show your activity stats in the last year (default)
- `/mystats <time_window>` - Custom time window (e.g., `30d`, `90d`, `1y`)
- `/mystats <time_window> at` - Include mention counts (outgoing and incoming)
- `/mystats <date_range>` - Custom date range (e.g., `2025-01-01..2025-12-31`)

**Supported Time Windows:**
- Relative: `7d`, `30d`, `90d`, `365d`, `1y`, `2y`
- Date range: `YYYY-MM-DD..YYYY-MM-DD` (e.g., `2025-01-01..2025-12-31`)

**Stats Output Includes:**
- Your message count in the group (time window)
- Total group messages (time window)
- Your percentage of group activity
- Mention counts (if `at` flag is used):
  - Outgoing: How many times you mentioned others
  - Incoming: How many times others mentioned you

**Admin Commands (Owner Only):**
- `/ping` - Comprehensive bot health check: search engine status, total messages, privacy stats, query logs, bot configuration
- `/dedup` - Remove duplicate messages from database (requires `ENGINE=http`)
- `/delete` - Delete messages from specific chat
- `/logs [limit]` - View recent query logs (default: 20, max: 100)
- `/logstats` - View query log statistics
- `/settings [key] [value]` - View or update database settings
- `/cleanup_logs` - Clean up old query logs based on retention settings

**Sync Commands (Owner Only):**
- `/sync <chat_id>` - Add a chat to the sync queue for indexing
- `/sync_status` - Check progress of all sync tasks
- `/sync_pause <chat_id>` - Pause an ongoing sync task
- `/sync_resume <chat_id>` - Resume a paused sync task
- `/sync_list` - List all sync tasks (alias for /sync_status)

**Search Syntax:**
- Global search: Just send any text message
- Type filter: `-t=GROUP keyword`
- User filter: `-u=username keyword` or `-u=userid keyword`
- Exact match: `-m=e keyword` or `"keyword"`
- Combined: `-t=GROUP -u=username -m=e keyword`

## Deduplication

The `/dedup` command removes duplicate messages from the search index. This is useful when:
- Re-syncing chats causes duplicate indexing
- Messages were indexed multiple times due to errors
- Database optimization is needed

**How it works:**
1. Finds messages with the same `chat_id` + `message_id` combination
2. Keeps the latest version (by timestamp)
3. Deletes older duplicates using bulk operations
4. Reports number of duplicates found and removed

**Requirements:**
- Must use `ENGINE=http` (Go search service with Elasticsearch)
- Owner-only command for security
- Can take several minutes for large databases

**Usage:**
```bash
/dedup
```

The bot will show:
- Initial message with estimated time
- Progress updates every 15 seconds with elapsed time
- Number of duplicates found and removed
- Total operation time and success status

**Technical Details:**
- Uses 10-minute timeout to handle large databases
- Progress logged to server logs every 1000 composite aggregation buckets
- Processes duplicates in batches using Elasticsearch bulk delete
- Thread-safe operation with status updates

**Note:** The upsert operations are designed to be idempotent (using document IDs), so duplicates should be rare. However, this command provides a way to manually clean up the database if needed.

## Bot-Controlled Sync System (HTTP API)

SearchGram supports **on-demand chat synchronization** via bot commands using an HTTP API. This allows the bot owner to trigger indexing tasks from the bot interface without modifying `config.json`.

### Architecture

**HTTP API Server:**
- Runs on client process (default: `http://127.0.0.1:5000`)
- RESTful API with Flask
- Supports cross-server deployment (bot and client on different machines)

**Components:**
1. **Bot Side** (`sync_http_client.SyncHTTPClient`):
   - Sends HTTP requests to client's sync API
   - Retrieves real-time sync status
   - Handles connection errors gracefully

2. **Client Side** (`sync_api.py`):
   - Flask HTTP server running in background thread
   - Processes REST API calls (POST /api/v1/sync, GET /api/v1/sync/status, etc.)
   - Integrates with `SyncManager` for actual syncing
   - Thread-safe operations

### Bot Commands

**Add Chat to Sync Queue:**
```bash
/sync -1001234567890
```
- Adds chat to sync queue
- Client starts syncing immediately
- Returns command ID for tracking

**Check Sync Status:**
```bash
/sync_status
```
Shows:
- Progress percentage for each chat
- Status: pending, in_progress, completed, failed, paused
- Error counts and last error message
- Summary statistics

**Pause Sync:**
```bash
/sync_pause -1001234567890
```
- Pauses sync at next checkpoint
- Preserves progress for resume

**Resume Sync:**
```bash
/sync_resume -1001234567890
```
- Continues from last checkpoint
- Triggers sync in background thread

**List All Syncs:**
```bash
/sync_list
```
Alias for `/sync_status`.

### How It Works

1. **Bot receives command** (e.g., `/sync -1001234567890`)
2. **Bot sends HTTP POST to client**:
   ```http
   POST http://client-server:5000/api/v1/sync
   Content-Type: application/json

   {
     "chat_id": -1001234567890,
     "requested_by": 123456789
   }
   ```
3. **Client API handler**:
   - Receives HTTP request
   - Calls `sync_manager.add_chat(chat_id)`
   - Starts sync in background thread
   - Returns JSON response
4. **Client provides real-time status** via GET endpoint:
   ```http
   GET http://client-server:5000/api/v1/sync/status

   Response:
   {
     "timestamp": "2026-01-01T00:00:00",
     "chats": [{
       "chat_id": -1001234567890,
       "status": "in_progress",
       "progress_percent": 45.2,
       "synced_count": 4520,
       "total_count": 10000,
       "error_count": 0
     }]
   }
   ```
5. **Bot queries status** when user runs `/sync_status`

### Features

**Resume Capability:**
- Progress saved to `sync_progress.json` after each batch
- Survives client restarts
- Automatic resume on startup (controlled by `SYNC_RESUME_ON_RESTART`)

**Error Handling:**
- Retry logic with configurable max retries
- FloodWait handling (automatic waiting)
- Detailed error logging in status file

**Thread Safety:**
- HTTP requests processed in Flask threads
- Lock-based synchronization in SyncManager
- Status queries don't block sync operations

**Batch Processing:**
- Configurable batch size (default: 100 messages)
- Delay between batches to avoid rate limits
- Bulk insert support for efficiency

### Configuration

**Sync API Server (client process):**
- `sync_api.host`: API server host (default: `127.0.0.1`)
- `sync_api.port`: API server port (default: `5000`)

**Sync API Client (bot process):**
- `services.sync.base_url`: Sync API endpoint (default: `http://127.0.0.1:5000`)

**Sync Settings (shared):**
- `SYNC_BATCH_SIZE`: Messages per batch
- `SYNC_RETRY_ON_ERROR`: Enable retry logic
- `SYNC_MAX_RETRIES`: Max retry attempts
- `SYNC_DELAY_BETWEEN_BATCHES`: Delay in seconds

**Cross-Server Setup:**
If bot and client run on different machines, configure:
```json
{
  "services": {
    "sync": {
      "base_url": "http://client-server-ip:5000"
    }
  },
  "sync_api": {
    "host": "0.0.0.0",
    "port": 5000
  }
}
```
Ensure firewall allows connection from bot server to client server port 5000.

### Use Cases

**On-Demand Indexing:**
- User joins a new group → owner runs `/sync -1001234567890`
- Historical messages needed → add to queue without restart

**Progress Monitoring:**
- Long-running syncs → check with `/sync_status`
- Verify completion before queries

**Rate Limit Management:**
- Hit FloodWait → pause with `/sync_pause`
- Wait for cooldown → resume with `/sync_resume`

**Multiple Chats:**
- Queue multiple chats
- Process in parallel threads
- Monitor all with single status command

### Implementation Files

- `searchgram/sync_api.py` - Flask HTTP API server (runs on client)
- `searchgram/sync_http_client.py` - HTTP client for bot to call sync API
- `searchgram/bot.py` - Bot command handlers (/sync, /sync_status, etc.)
- `searchgram/client.py` - Starts sync API server in background thread
- `searchgram/sync_manager.py` - Sync logic with pause/resume methods

### API Endpoints

**POST /api/v1/sync** - Add chat to sync queue
**GET /api/v1/sync/status?chat_id=<id>** - Get sync status (all or specific chat)
**POST /api/v1/sync/pause** - Pause sync task
**POST /api/v1/sync/resume** - Resume paused sync
**GET /health** - Health check

## Query Logging System

SearchGram includes a **SQLite-based query logging system** (`db_manager.py`) that tracks all search queries with detailed metadata and configurable settings.

### Features

**Query Logs Table** (`query_logs`):
- Timestamp, user ID, username, first name
- Chat ID and type (PRIVATE/GROUP)
- Search query and filters (type, user, mode)
- Results count, page number, processing time
- Indexed for fast lookups by timestamp, user_id, chat_id

**Admin Settings Table** (`admin_settings`):
- Runtime-configurable settings stored in database
- Type-aware (bool, int, float, str, json)
- Tracks who updated settings and when

**Default Settings:**
- `enable_query_logging`: Enable/disable logging (default: `true`)
- `log_retention_days`: Days to keep logs (default: `30`)
- `max_log_entries`: Maximum log entries (default: `100000`)
- `auto_cleanup_enabled`: Auto cleanup old logs (default: `true`)

### Admin Commands

**View Logs:**
```bash
/logs              # Last 20 queries
/logs 50           # Last 50 queries
/logs 123456       # All queries from user 123456
```

**View Statistics:**
```bash
/logstats          # Shows:
                   # - Total queries, 24h queries
                   # - Average results and time
                   # - Top users
                   # - Breakdown by chat type
```

**Manage Settings:**
```bash
/settings                              # View all settings
/settings enable_query_logging false   # Disable logging
/settings log_retention_days 60        # Keep logs for 60 days
/settings max_log_entries 200000       # Increase max entries
```

**Cleanup Logs:**
```bash
/cleanup_logs      # Remove old logs based on:
                   # - log_retention_days setting
                   # - max_log_entries setting
```

### Implementation Details

**Thread-Safe:** Connection pooling per thread via `threading.local()`
**Automatic Indexing:** Indexes on timestamp, user_id, chat_id for fast queries
**Error Handling:** Logging failures don't crash the bot
**Type Conversion:** Settings automatically converted to appropriate types

**Logging Happens When:**
- Every search query (private, group, type-specific)
- Pagination (page number tracked)
- After privacy and permission filtering
- Processing time measured and recorded

**Privacy Considerations:**
- Only owner can view logs (admin-only commands)
- Can be completely disabled via `DATABASE_ENABLED=false` in config
- Logs stored locally in SQLite file
- Configurable retention and limits

### Database Schema

```sql
CREATE TABLE query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    chat_id INTEGER NOT NULL,
    chat_type TEXT NOT NULL,
    query TEXT NOT NULL,
    search_type TEXT,
    search_user TEXT,
    search_mode TEXT,
    results_count INTEGER,
    page_number INTEGER DEFAULT 1,
    processing_time_ms INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admin_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    description TEXT,
    updated_at REAL NOT NULL,
    updated_by INTEGER NOT NULL
);
```

## Soft-Delete System

SearchGram uses a **soft-delete** system for message deletion:

**How It Works:**
- When messages are deleted on Telegram, they are marked as `is_deleted=true` instead of being physically removed
- Deleted messages include a `deleted_at` timestamp
- Soft-deleted messages are automatically excluded from search results for regular users
- Owner can optionally include deleted messages in searches via `include_deleted` parameter

**Benefits:**
- Preserves historical data for analytics and statistics
- Allows activity stats to accurately reflect user activity even after messages are deleted
- Enables owner to audit deleted content if needed
- No data loss due to accidental deletions

**Implementation Details:**
- **Client Handler**: `@app.on_deleted_messages()` handler captures deletion events
- **Backend**: Elasticsearch Update By Query marks messages as deleted
- **Search Filter**: Automatically excludes deleted messages unless `include_deleted=true`
- **Stats**: By default, deleted messages are not counted in user stats (configurable)

**Database Schema:**
- `is_deleted`: Boolean field (indexed)
- `deleted_at`: Unix timestamp (when message was deleted)

**Note:** The `/delete` and `/delete_user` admin commands also use soft-delete (they no longer physically remove messages).

## Activity Stats System

The **Activity Stats** feature allows users to query their message activity in groups:

**Features:**
- Count messages sent by a user in a specific time window
- Calculate percentage of group activity
- Track mention patterns (optional):
  - **Outgoing mentions**: User mentioned others
  - **Incoming mentions**: Others mentioned the user
- Support for flexible time windows (relative or absolute date ranges)

**API Endpoint:**
```
POST /api/v1/stats/user
```

**Request Payload:**
```json
{
  "group_id": -1001234567890,
  "user_id": 123456789,
  "from_timestamp": 1640995200,
  "to_timestamp": 1672531199,
  "include_mentions": true,
  "include_deleted": false
}
```

**Response:**
```json
{
  "user_message_count": 1234,
  "group_message_total": 9950,
  "user_ratio": 0.124,
  "mentions_out": 56,
  "mentions_in": 41
}
```

**Mention Tracking:**
- Entities are extracted from Telegram messages during indexing
- Stored in nested `entities` field with type, offset, length, user_id
- Types tracked: `mention` (username), `text_mention` (user link)
- Outgoing: Messages sent by user containing mentions
- Incoming: Messages from others with `text_mention` entities referencing the user

**Time Window Parsing:**
- Relative: `7d`, `30d`, `90d`, `365d`, `1y`, `2y`
- Absolute: `2025-01-01..2025-12-31`
- Default: 365 days (1 year)

**Privacy:**
- Regular users can only query their own stats
- Deleted messages excluded by default (owner can include)
- Only works in group chats (not private messages)

## Bot Health Monitoring

The `/ping` command provides comprehensive system health information for bot administrators.

**Example Output:**
```
🏓 Pong!

Search Engine: http
Status: healthy
📊 Total Messages: 125,430

🔐 Privacy: 3 user(s) opted out

📝 Query Logs:
  • Total Queries: 1,245
  • Last 24h: 87
  • Avg Time: 125ms

⚙️ Bot Configuration:
  • Mode: group
  • Allowed Groups: 5
  • Allowed Users: 12
  • Admins: 2
```

**Information Shown:**
- **Search Engine Status:** Engine type (http, elastic, etc.) and health status
- **Total Messages:** Count of all indexed messages in the database
- **Privacy Stats:** Number of users who opted out via `/block_me`
- **Query Logs:** Total queries, last 24h activity, average processing time
- **Bot Configuration:** Access mode, allowed groups/users, admin count

**Use Cases:**
- Quick health check before maintenance
- Monitor database growth
- Track user activity and query performance
- Verify permissions configuration

## Common Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m unittest searchgram.tests.tests

# Test privacy manager
python searchgram/privacy.py

# Test access control
python searchgram/access_control.py

# Migration: Add timestamps to existing data
python searchgram/migrations/add_timestamp.py
```

## Group Mode Setup

To enable the bot with granular group permissions in `config.json`:

### Example 1: Simple Group Mode (All users see all groups)
```json
{
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890, -1009876543210],
    "allowed_users": [123456789, 987654321],
    "admins": [],
    "user_group_permissions": {}
  }
}
```
**Behavior**: All allowed users can search all indexed groups (backward compatible).

### Example 2: Admins + Per-User Permissions
```json
{
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890, -1009876543210, -1005555555555],
    "allowed_users": [123456789, 987654321, 333333333],
    "admins": [111111111],
    "user_group_permissions": {
      "123456789": [-1001234567890],
      "987654321": [-1009876543210, -1001234567890],
      "333333333": [-1005555555555]
    }
  }
}
```
**Behavior**:
- **Owner** (from `OWNER_ID`): Can search all 3 groups
- **Admin** (111111111): Can search all 3 groups
- **User 123456789**: Can only search group -1001234567890
- **User 987654321**: Can search groups -1009876543210 and -1001234567890
- **User 333333333**: Can only search group -1005555555555

### Setup Steps:
1. Edit `config.json` with your desired permission structure
2. Add bot to the groups
3. Users can search with the same syntax (results filtered automatically)
4. Search results show who requested them
5. Anyone can use `/block_me` for privacy

## Search Engine Notes

SearchGram uses an HTTP-based search architecture with a dedicated Go microservice:

- **HTTP Search Engine** (`searchgram/http_engine.py`):
  - Communicates with Go microservice via RESTful HTTP/2 API
  - Endpoint configured via `services.search.base_url` (default: `http://127.0.0.1:8080`)
  - **Authentication**: JWT-based using Ed25519 keys (required, no API key fallback)
  - Features: Connection pooling, automatic retries, batch operations
  - All search results return a standardized dict format with `hits`, `totalHits`, `totalPages`, `page`, `hitsPerPage` keys

- **Go Search Service** (`searchgram-engine/`):
  - Elasticsearch backend with CJK optimization
  - CJK Bigram Tokenization for Chinese, Japanese, Korean text
  - Dual analyzers: CJK analyzer for fuzzy search + exact analyzer for phrase matching
  - Filterable fields: Chat ID, username, type for precise filtering
  - Performance tuning: Configurable sharding, replica settings, deep pagination support
  - Security: Credentials isolated in Go service, JWT authentication required for API access
