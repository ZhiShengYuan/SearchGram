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

**Search Engine Abstraction**: The project uses a plugin architecture via `searchgram/__init__.py` that dynamically loads search backends based on the `ENGINE` config:
- `http` (recommended): Go search service via HTTP API - best performance, security, scalability
- `meili`: MeiliSearch - typo-tolerant, fuzzy search (legacy, direct connection)
- `mongo`: MongoDB - regex-based search with CJK conversion (legacy, direct connection)
- `zinc`: ZincSearch - full-text search (legacy, direct connection)
- `elastic`: Elasticsearch - CJK-optimized (legacy, direct connection)

**Recommended Setup**: Use `engine: http` to leverage the Go search service for better performance and security. The Go service handles Elasticsearch connection pooling, credentials, and optimization internally.

All engines implement the `BasicSearchEngine` interface from `searchgram/engine.py` with methods: `upsert()`, `search()`, `ping()`, `clear_db()`, and `delete_user()`.

## Configuration

SearchGram now supports **JSON-based configuration** with fallback to environment variables. Configuration priority (highest to lowest):
1. Environment variables
2. `config.json` file
3. Default values

All configuration is managed by `searchgram/config_loader.py`:

**Telegram Credentials:**
- `APP_ID`, `APP_HASH`: Telegram API credentials from https://my.telegram.org/
- `TOKEN`: Bot token from @BotFather
- `OWNER_ID`: User ID of the bot owner (always has full access)

**Search Engine Settings:**
- `ENGINE`: Search backend (`http`, `meili`, `mongo`, `zinc`, or `elastic`)
- For `http` (recommended):
  - `HTTP_BASE_URL`: Go search service URL (default: `http://searchgram-engine:8080`)
  - `HTTP_API_KEY`: Optional API key for authentication
  - `HTTP_TIMEOUT`: Request timeout in seconds (default: 30)
  - `HTTP_MAX_RETRIES`: Max retry attempts (default: 3)
- For legacy direct connections:
  - `MEILI_HOST`, `MONGO_HOST`, `ZINC_HOST`, `ELASTIC_HOST`: Search engine endpoints
  - `ELASTIC_USER`, `ELASTIC_PASS`: Elasticsearch authentication credentials

**Access Control (NEW):**
- `BOT_MODE`: Access control mode - `private` (owner only), `group` (whitelisted groups), `public` (anyone)
- `ALLOWED_GROUPS`: Comma-separated list of group IDs where bot can work (e.g., "-1001234567890,-1009876543210")
- `ALLOWED_USERS`: Comma-separated list of additional user IDs who can use the bot (e.g., "123456789,987654321")

**Privacy Settings (NEW):**
- `PRIVACY_STORAGE`: Path to privacy data JSON file (default: "privacy_data.json")

**Network Settings:**
- `PROXY`: Optional proxy configuration (dict or JSON string)
- `IPv6`: Enable IPv6 support

## Running the Application

**For development/local:**
```bash
# First-time setup: login to client (creates session files)
python searchgram/client.py

# Run both processes (requires two terminals):
python searchgram/client.py  # Terminal 1
python searchgram/bot.py     # Terminal 2
```

**For Docker:**
```bash
# Start all services (includes search engine)
make up

# Stop services
make down
```

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

**Access Control** (`access_control.py`): Three-tier permission system
- **Private Mode**: Only OWNER_ID can use the bot (default, most secure)
- **Group Mode**: Bot works in whitelisted groups (`ALLOWED_GROUPS`) and for specific users (`ALLOWED_USERS`)
- **Public Mode**: Anyone can use the bot (not recommended, no privacy protection)
- Decorators: `@require_access` for general commands, `@require_owner` for admin commands

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
- `/ping` - Check bot health and database stats (owner only)
- `/delete` - Delete messages from specific chat (owner only)
- `/{chat_type} [username] keyword` - Type-specific search (PRIVATE, GROUP, CHANNEL, etc.)

**Privacy Commands (NEW):**
- `/block_me` - Opt-out: Remove yourself from search results
- `/unblock_me` - Opt-in: Allow your messages in search results
- `/privacy_status` - Check your current privacy status

**Search Syntax:**
- Global search: Just send any text message
- Type filter: `-t=GROUP keyword`
- User filter: `-u=username keyword` or `-u=userid keyword`
- Exact match: `-m=e keyword` or `"keyword"`
- Combined: `-t=GROUP -u=username -m=e keyword`

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

# Docker operations
make up          # Start docker-compose services
make down        # Stop docker-compose services
make upgrade     # Pull latest code and image, restart
```

## Group Mode Setup

To enable the bot in groups:

1. Set environment variables:
```bash
BOT_MODE=group
ALLOWED_GROUPS=-1001234567890,-1009876543210
ALLOWED_USERS=123456789,987654321
```

2. Add bot to the group
3. Users can search with the same syntax
4. Search results show who requested them
5. Anyone in the group can use `/block_me` for privacy

## Search Engine Notes

- **MeiliSearch**: Configured with custom ranking rules prioritizing timestamp, supports typo tolerance, requires filterable attributes setup on `chat.id`, `chat.username`, `chat.type`
- **MongoDB**: Uses regex search with `zhconv` library for simplified/traditional Chinese conversion
- **Zinc**: Uses QueryString queries with bool filters, exact match mode not fully implemented
- **Elasticsearch**: CJK-optimized with bigram tokenization, supports exact and fuzzy matching, advanced filtering on chat type/user, timestamp-based sorting. Uses custom analyzers for optimal Chinese/Japanese/Korean text search performance. Recommended for high-volume deployments and best search quality.

All search results return a standardized dict format with `hits`, `totalHits`, `totalPages`, `page`, `hitsPerPage` keys.

### Elasticsearch Configuration

Elasticsearch implementation includes:
- **CJK Bigram Tokenization**: Optimized for Chinese, Japanese, Korean text
- **Dual Analyzers**: CJK analyzer for fuzzy search + exact analyzer for phrase matching
- **Filterable Fields**: Chat ID, username, type for precise filtering
- **Performance Tuning**: Configurable sharding, replica settings, and deep pagination support
- **Index Settings**: Automatic index creation with proper mappings on first run
- **Security**: Supports basic authentication (username/password)

Environment variables for Elasticsearch:
- `ELASTIC_HOST`: Elasticsearch endpoint (default: `http://elasticsearch:9200`)
- `ELASTIC_USER`: Username for authentication (default: `elastic`)
- `ELASTIC_PASS`: Password for authentication (default: `changeme`)
