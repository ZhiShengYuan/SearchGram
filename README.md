# SearchGram

SearchGram is a Telegram bot that improves search experience for Chinese, Japanese, and Korean (CJK) languages and provides message backup functionality with advanced privacy controls and activity statistics.

# Introduction

Telegram's search function has poor support for CJK languages because there are no spaces to separate words.

Issues regarding this have been reported years ago but have yet to be resolved:

* https://github.com/tdlib/td/issues/1004
* https://bugs.telegram.org/c/724

# Features

**Search Capabilities:**
* 🔍 Text message search with CJK language support
* 🎯 Typo-tolerant and fuzzy search for Chinese, Japanese, Korean
* 🗂️ Filters for GROUP, CHANNEL, PRIVATE, SUPERGROUP, and BOT chat types
* 👤 Username/ID filtering for targeted searches
* 📎 Caption search for photos and documents
* 🔄 On-demand and background chat history sync via HTTP API
* 📄 Paginated results with inline navigation
* 🗑️ Soft-delete system (messages marked deleted but preserved for analytics)

**Privacy & Access Control:**
* 🔒 **User Privacy Controls**: Anyone can opt-out via `/block_me` command
* 🔐 **Three Access Modes**: Private (owner only), Group (whitelisted with granular permissions), Public
* 🛡️ **Privacy-First**: Blocked users automatically filtered from all search results
* 👥 **Group Support**: Works in whitelisted Telegram groups
* 📊 **Transparent**: Shows who requested searches in group mode
* 🎭 **Granular Permissions**: Per-user group access control with admin roles

**Activity & Analytics:**
* 📈 **User Activity Stats**: `/mystats` command to view message counts and activity ratios
* 💬 **Mention Tracking**: Track outgoing and incoming mentions (who you mentioned vs who mentioned you)
* ⏰ **Flexible Time Windows**: Query stats by relative periods (7d, 30d, 1y) or absolute date ranges
* 📊 **Group Analytics**: Calculate your percentage of group activity

**Performance & Reliability:**
* 🚀 **High-Performance Go Service**: Dedicated microservice for search operations (1000-5000 req/s)
* ⚡ **HTTP-Only Architecture**: Unified HTTP API for all search operations
* 🔄 **Auto-Recovery**: Resume-capable sync system with checkpoints
* 📊 **Monitoring**: Health checks, statistics, query logging, structured logging
* 🛡️ **Security**: JWT-based authentication with Ed25519 keys, Elasticsearch credentials isolated in Go service
* 🔌 **Cross-Server Support**: Bot and client can run on different machines

# search syntax

1. global search: send any message to the bot
2. chat type search: `-t=GROUP keyword`, support types are ["BOT", "CHANNEL", "GROUP", "PRIVATE", "SUPERGROUP"]
3. chat user search: `-u=user_id|username keyword`
4. exact match: `-m=e keyword` or directly `"keyword"`
5. combine of above: `-t=GROUP -u=user_id|username keyword`
6. `/private [username] keyword`: search in private chat with username, if username is omitted, search in all private
   chats. This also applies to all above search types.\n

# Commands

**Search Commands:**
```shell
/start - Start the bot and get welcome message
/help - Show comprehensive help with search syntax and privacy info
/bot - Search messages from bots
/channel - Search messages from channels
/group - Search messages from groups
/private - Search messages from private chats
/supergroup - Search messages from supergroups
```

**Privacy Commands:**
```shell
/block_me - Opt-out: Your messages won't appear in anyone's search
/unblock_me - Opt-in: Allow your messages in search results
/privacy_status - Check your current privacy status
```

**Activity Stats Commands (Group Only):**
```shell
/mystats - Show your activity stats in the last year (default)
/mystats 30d - Show stats for last 30 days
/mystats 90d at - Include mention counts (outgoing and incoming)
/mystats 2025-01-01..2025-12-31 - Custom date range
```

**Sync Commands (Owner Only):**
```shell
/sync <chat_id> - Add a chat to the sync queue for indexing
/sync_status - Check progress of all sync tasks
/sync_pause <chat_id> - Pause an ongoing sync task
/sync_resume <chat_id> - Resume a paused sync task
/sync_list - List all sync tasks (alias for /sync_status)
```

**Admin Commands (Owner Only):**
```shell
/ping - Comprehensive bot health check with stats
/dedup - Remove duplicate messages from database
/delete <chat_id> - Soft-delete messages from specific chat
/logs [limit] - View recent query logs (default: 20, max: 100)
/logstats - View query log statistics
/settings [key] [value] - View or update database settings
/cleanup_logs - Clean up old query logs based on retention settings
```

**Why Privacy Matters:**
SearchGram indexes messages for search, but respects your privacy. Use `/block_me` anytime to remove yourself from search results. Your choice, your data! 🛡️

# Architecture

SearchGram uses a **microservice architecture** with three main components:

```
┌─────────────┐     HTTP/2 API    ┌──────────────┐     Native      ┌──────────────┐
│  Client     │ ──────────────────►│ Go Search    │ ◄──────────────►│ Elasticsearch│
│  (Userbot)  │   JWT Auth        │   Service    │   Protocol      │  (CJK Index) │
│   :8082     │                   │    :8080     │                 └──────────────┘
└─────────────┘                   └──────────────┘
       ▲                                  ▲
       │                                  │
       │         HTTP/2 API               │
       │         JWT Auth                 │
       │                                  │
       └──────────────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │  Telegram    │
              │  Bot (Py)    │
              └──────────────┘
```

**Components:**

1. **Client Process** (Python userbot):
   - Runs as a user session (requires phone number login)
   - Intercepts all incoming/outgoing messages
   - Sends messages to Go search service for indexing
   - Provides HTTP API (port 8082) for bot-controlled sync
   - Handles background chat history sync from `config.json`

2. **Bot Process** (Python bot):
   - Runs as a Telegram bot (uses bot token)
   - Provides search interface via commands and text messages
   - Sends search queries to Go service via HTTP/2 API
   - Controls sync operations via userbot HTTP API
   - Supports three access modes with granular permissions

3. **Go Search Service** (standalone microservice):
   - High-performance search operations (1000-5000 req/s)
   - CJK-optimized Elasticsearch backend with bigram tokenization
   - JWT-based authentication with Ed25519 keys
   - Runs in the same LAN as Elasticsearch for low-latency access
   - Exposes REST API (port 8080) for Python services

**Why This Architecture?**
- ⚡ **10x Performance**: Go service handles 1000-5000 req/s vs 100-200 req/s for Python
- 🔒 **Better Security**: JWT authentication, Elasticsearch credentials isolated in Go service
- 📈 **Horizontal Scaling**: Run multiple Go instances behind load balancer
- 🌐 **Cross-Server Support**: Bot and client can run on different machines
- 🔌 **Service Isolation**: Each component can be deployed and scaled independently

# How It Works

SearchGram works by:

1. **User Client** runs as your Telegram session (requires phone login)
2. **Message Interception**: Captures all incoming/outgoing messages (except bot's own)
3. **Indexing**: Sends messages to Go service → Elasticsearch (CJK-optimized)
4. **Bot Interface**: Provides search via Telegram commands
5. **Results**: Fast, accurate search with privacy filtering

**History Sync**:
- **Background Sync**: Configure chats in `config.json` for automatic sync on startup
- **On-Demand Sync**: Use `/sync <chat_id>` command to add chats to sync queue
- **Resume Capability**: Progress saved to checkpoints, survives restarts
- **Sequential Processing**: One chat at a time to avoid rate limits

# Screenshots

![](assets/1.png)
![](assets/2.png)
![](assets/3.png)
![](assets/4.png)

# System Requirements

**Software:**
- Python 3.8+
- Go 1.19+ (for search service)
- Elasticsearch 7.x or 8.x

**Hardware Recommendations:**
- **RAM**: At least 2GB total
  - Elasticsearch: 1GB minimum (configure heap size: `ES_JAVA_OPTS=-Xms512m -Xmx512m`)
  - Go Service: ~100MB
  - Python Processes: ~200MB combined
- **Storage**: Depends on message volume (Elasticsearch indexes)
- **Network**: Low-latency connection between Go service and Elasticsearch recommended

**Search Engine:**
SearchGram now uses **HTTP-only architecture** with the Go search service:
- ✅ **HTTP (Go Service)**: High-performance microservice with Elasticsearch backend
  - 10x faster than direct connections (1000-5000 req/s)
  - CJK bigram tokenization for optimal Asian language search
  - JWT-based authentication with Ed25519 keys
  - Secure credential isolation
  - Horizontal scalability
- ❌ **Legacy Engines Removed**: MeiliSearch, MongoDB, ZincSearch, direct Elasticsearch connections are no longer supported (security and maintainability)

# Installation

**Note: Because chat history should be kept private, we do not offer any public bots.**

Please follow the steps below to install SearchGram on your own server.

## 1. Preparation

**Download and Install:**
* Clone this repository: `git clone https://github.com/BennyThink/SearchGram.git`
* Install Python 3.8+ from: https://www.python.org/downloads/
* Install Go 1.19+ from: https://go.dev/dl/
* Install Elasticsearch 7.x or 8.x:
  - Docker: `docker run -d -p 9200:9200 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:8.11.0`
  - Or download from: https://www.elastic.co/downloads/elasticsearch

**Telegram Setup:**
* Apply for APP_ID and APP_HASH from: https://my.telegram.org/
* Obtain your bot token by contacting: https://t.me/BotFather
* Obtain your user ID by contacting: https://t.me/userinfobot

## 2. Install Dependencies

**Python Dependencies:**
```bash
# Quick install using the installation script
./install_deps.sh

# Or manually with pip
pip3 install -r requirements.txt
```

**Go Dependencies** (for search service):
```bash
cd searchgram-engine
go mod download
```

## 3. Generate Authentication Keys

SearchGram requires Ed25519 keys for JWT authentication:

```bash
# Generate Ed25519 private key
openssl genpkey -algorithm ed25519 -out private_key.pem

# Extract public key
openssl pkey -in private_key.pem -pubout -out public_key.pem
```

## 4. Configure SearchGram

Create and edit `config.json` from the example template:

```bash
cp config.example.json config.json
nano config.json  # or use your favorite editor
```

**Minimal Configuration Example:**

```json
{
  "telegram": {
    "app_id": 176552,
    "app_hash": "your_app_hash",
    "token": "your_bot_token",
    "owner_id": 123456789
  },
  "auth": {
    "use_jwt": true,
    "public_key_path": "public_key.pem",
    "private_key_path": "private_key.pem",
    "issuer": "searchgram",
    "audience": "search",
    "token_ttl": 300
  },
  "services": {
    "search": {
      "base_url": "http://127.0.0.1:8080"
    },
    "userbot": {
      "base_url": "http://127.0.0.1:8082"
    }
  },
  "search_service": {
    "server": {
      "host": "127.0.0.1",
      "port": 8080
    },
    "elasticsearch": {
      "host": "http://localhost:9200",
      "username": "elastic",
      "password": "your_elasticsearch_password",
      "index": "telegram"
    }
  },
  "bot": {
    "mode": "private"
  }
}
```

**Optional: Proxy Configuration** (for China or restricted networks):

```json
{
  "telegram": {
    "proxy": {
      "scheme": "socks5",
      "hostname": "localhost",
      "port": 1080
    }
  }
}
```

**Optional: Group Mode with Granular Permissions:**

```json
{
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890, -1009876543210],
    "allowed_users": [123456789, 987654321],
    "admins": [111111111],
    "user_group_permissions": {
      "123456789": [-1001234567890],
      "987654321": [-1009876543210, -1001234567890]
    }
  }
}
```

This configuration means:
- Owner and admins can search all groups
- User 123456789 can only search group -1001234567890
- User 987654321 can search both groups

## 5. First-Time Login

Before running the services, you need to create a Telegram session:

```bash
python3 -m searchgram.client
```

Enter your phone number and verification code to log in. Session files will be saved to `searchgram/session/`. You can exit with `Ctrl + C` after successful login.

## 6. Configure Background Sync (Optional)

Configure chat history sync in `config.json`:

```json
{
  "sync": {
    "enabled": true,
    "chats": [
      {"id": -1001234567890, "name": "My Group"},
      {"id": 123456789, "name": "Friend Name"}
    ]
  }
}
```

The client will automatically sync chat history on startup with resume capability. Alternatively, use `/sync <chat_id>` command for on-demand syncing.

## 7. Run SearchGram

You need **three terminals** to run all services:

**Terminal 1 - Go Search Service:**
```bash
cd searchgram-engine
go run main.go
# Or build and run: go build && ./searchgram-engine
```

**Terminal 2 - Python Client (Userbot):**
```bash
python3 -m searchgram.client
# This will also start the HTTP API server on port 8082
```

**Terminal 3 - Python Bot:**
```bash
python3 -m searchgram.bot
```

**Quick Start Order:**
1. Start Elasticsearch (if not already running)
2. Start Go search service (Terminal 1)
3. Start Python client (Terminal 2)
4. Start Python bot (Terminal 3)

**Verify Everything Works:**
- Send `/ping` to your bot to check health status
- Try a simple search query

# Cross-Server Deployment

SearchGram supports running services on different machines:

**Example Setup:**
- **Server A** (ucre3): Runs client (userbot) and Elasticsearch
- **Server B** (nomao-lax): Runs bot and Go search service

**Configuration on Server B (`config.json`):**
```json
{
  "services": {
    "search": {
      "base_url": "http://ucre3:8080"
    },
    "userbot": {
      "base_url": "http://ucre3:8082"
    }
  }
}
```

**Configuration on Server A (`config.json`):**
```json
{
  "http": {
    "listen": "0.0.0.0",
    "userbot_port": 8082
  },
  "search_service": {
    "server": {
      "host": "0.0.0.0",
      "port": 8080
    }
  }
}
```

Make sure to configure firewall rules to allow connections between servers on ports 8080 and 8082.

# Advanced Features

## Query Logging

SearchGram includes a SQLite-based query logging system:

- **Enable/Disable**: `DATABASE_ENABLED` in config
- **Retention**: Configure via `/settings log_retention_days 60`
- **View Logs**: `/logs [limit]` (owner only)
- **Statistics**: `/logstats` (owner only)
- **Cleanup**: `/cleanup_logs` (owner only)

## Activity Statistics

Users can query their own activity stats in groups:

```
/mystats              # Last year
/mystats 30d          # Last 30 days
/mystats 90d at       # Include mentions
/mystats 2025-01-01..2025-12-31  # Custom date range
```

## Deduplication

Remove duplicate messages from the database:

```
/dedup  # Owner only
```

Useful when re-syncing chats or after indexing errors.

# Troubleshooting

**Connection Errors:**
- Verify Elasticsearch is running: `curl http://localhost:9200`
- Check Go service: `curl http://localhost:8080/health`
- Check userbot API: `curl http://localhost:8082/health`

**Authentication Errors:**
- Ensure JWT keys are generated and paths are correct in `config.json`
- Verify `auth.use_jwt` is set to `true`
- Check issuer/audience configuration matches across services

**Sync Issues:**
- Check sync status: `/sync_status`
- View client logs for FloodWait errors
- Pause and resume: `/sync_pause <chat_id>` then `/sync_resume <chat_id>`

**Search Not Working:**
- Verify messages are indexed: `/ping` shows message count
- Check Elasticsearch index: `curl http://localhost:9200/telegram/_count`
- Review Go service logs for errors

# License

This project is licensed under the GNU GENERAL PUBLIC LICENSE Version 3.
