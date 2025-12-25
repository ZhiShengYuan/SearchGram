# SearchGram

SearchGram is a Telegram bot that improves search experience for Chinese, Japanese, and Korean (CJK) languages and
provides message backup functionality.

# Introduction

Telegram's search function has poor support for CJK languages because there are no spaces to separate words.

Issues regarding this have been reported years ago but have yet to be resolved.

* https://github.com/tdlib/td/issues/1004
* https://bugs.telegram.org/c/724

# Feature

**Search Capabilities:**
* Text message search with CJK language support
* Typo-tolerant and fuzzy search for Chinese, Japanese, Korean
* Filters for GROUP, CHANNEL, PRIVATE, SUPERGROUP, and BOT chat types
* Username/ID filtering for targeted searches
* Caption search for photos and documents
* Seamless background chat history sync
* Paginated results with inline navigation

**Privacy & Access Control (NEW):**
* 🔒 **User Privacy Controls**: Anyone can opt-out via `/block_me` command
* 🔐 **Three Access Modes**: Private (owner only), Group (whitelisted), Public
* 🛡️ **Privacy-First**: Blocked users automatically filtered from all search results
* 👥 **Group Support**: Works in whitelisted Telegram groups
* 📊 **Transparent**: Shows who requested searches in group mode

**Performance & Reliability:**
* 🚀 **High-Performance Go Service**: Dedicated microservice for search operations (1000-5000 req/s)
* 🔌 **Multiple Backends**: HTTP (Go service), MeiliSearch, MongoDB, ZincSearch, Elasticsearch
* ⚡ **Optimized Architecture**: Go service with Elasticsearch for best performance and CJK support
* 🔄 **Auto-Recovery**: Resume-capable sync system with checkpoints
* 📊 **Monitoring**: Health checks, statistics, structured logging
* 🛡️ **Security**: Elasticsearch credentials isolated in Go service

# search syntax

1. global search: send any message to the bot
2. chat type search: `-t=GROUP keyword`, support types are ["BOT", "CHANNEL", "GROUP", "PRIVATE", "SUPERGROUP"]
3. chat user search: `-u=user_id|username keyword`
4. exact match: `-m=e keyword` or directly `"keyword"`
5. combine of above: `-t=GROUP -u=user_id|username keyword`
6. `/private [username] keyword`: search in private chat with username, if username is omitted, search in all private
   chats. This also applies to all above search types.\n

# commands

**Search Commands:**
```shell
/start - Start the bot
/help - Show comprehensive help with search syntax and privacy info
/ping - Check bot health and database stats (owner only)
/delete - Delete all messages from specific chat (owner only)
/bot - Search messages from bots
/channel - Search messages from channels
/group - Search messages from groups
/private - Search messages from private chats
/supergroup - Search messages from supergroups
```

**Privacy Commands (NEW):**
```shell
/block_me - Opt-out: Your messages won't appear in anyone's search
/unblock_me - Opt-in: Allow your messages in search results
/privacy_status - Check your current privacy status
```

**Why Privacy Matters:**
SearchGram indexes messages for search, but respects your privacy. Use `/block_me` anytime to remove yourself from search results. Your choice, your data! 🛡️

# Architecture

SearchGram uses a **microservice architecture** for optimal performance and scalability:

```
┌─────────────┐     HTTP API      ┌──────────────┐     Native      ┌──────────────┐
│   Telegram  │ ◄────────────────►│ Go Service   │ ◄──────────────►│ Elasticsearch│
│   Bot (Py)  │   (8080)          │ (CJK Engine) │   Protocol      │  (CJK Index) │
└─────────────┘                   └──────────────┘                 └──────────────┘
```

**Components:**
1. **Python Bot**: Telegram interface (client + bot)
2. **Go Search Service**: High-performance search operations (recommended)
3. **Search Backend**: Elasticsearch with CJK bigram tokenization

**Why This Architecture?**
- ⚡ **10x Performance**: Go service handles 1000-5000 req/s vs 100-200 req/s for Python
- 🔒 **Better Security**: Elasticsearch credentials isolated in Go service
- 📈 **Horizontal Scaling**: Run multiple Go instances behind load balancer
- 🔌 **Flexible**: Easy to switch search backends

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design and [GO_SERVICE_MIGRATION.md](GO_SERVICE_MIGRATION.md) for migration guide.

# How It Works

SearchGram works by:

1. **User Client** runs as your Telegram session (requires phone login)
2. **Message Interception**: Captures all incoming/outgoing messages (except bot's own)
3. **Indexing**: Sends messages to Go service → Elasticsearch (CJK-optimized)
4. **Bot Interface**: Provides search via Telegram commands
5. **Results**: Fast, accurate search with privacy filtering

**History Sync**: SearchGram can sync chat history automatically using checkpoint-based resume system. Configure in `config.json`.

# Screenshots

![](assets/1.png)
![](assets/2.png)
![](assets/3.png)
![](assets/4.png)

# System Requirements

Any system that can run Python 3.8+ and one of the supported search engines should be able to run SearchGram.

## Supported Search Engines

SearchGram supports multiple search backends:

- **HTTP (Go Service)** ⭐ **RECOMMENDED** - High-performance Go microservice with Elasticsearch backend
  - 10x faster than direct connections (1000-5000 req/s)
  - CJK bigram tokenization for optimal Asian language search
  - Secure credential isolation
  - Horizontal scalability
- **Elasticsearch** - Direct connection (legacy, use HTTP mode instead)
- **MeiliSearch** - Fast, typo-tolerant search with good CJK support (legacy)
- **MongoDB** - Document database with regex-based search and CJK conversion (legacy)
- **ZincSearch** - Lightweight full-text search engine (legacy)

### Memory Requirements

Better to have bigger RAM for optimal performance:

- **MeiliSearch**: Can limit memory usage with `MEILI_MAX_INDEXING_MEMORY=800M` ([docs](https://www.meilisearch.com/docs/learn/configuration/instance_options#max-indexing-memory))
- **Elasticsearch**: Recommended at least 1GB RAM, configure Java heap size via `ES_JAVA_OPTS=-Xms512m -Xmx512m`
- **MongoDB**: Typically requires 1-2GB RAM for good performance
- **ZincSearch**: Lightweight, works well with limited resources

# Installation

**Note: Because chat history should be kept private, we do not offer any public bots.**

Please follow the steps below to install SearchGram on your own server.

This guide will show you how to install SearchGram with our default search engine, MeiliSearch.

**To learn how to use SearchGram in Docker with different search engines (MongoDB, ZincSearch, or Elasticsearch), please refer to the [Docker.md](Docker.md)**

### Using Elasticsearch

To use Elasticsearch instead of MeiliSearch, set the `ENGINE` environment variable to `elastic`:

```python
ENGINE = "elastic"
ELASTIC_HOST = "http://localhost:9200"
ELASTIC_USER = "elastic"
ELASTIC_PASS = "your-password"
```

Elasticsearch provides the best search quality with:
- CJK bigram tokenization for optimal Chinese/Japanese/Korean search
- Advanced filtering and sorting capabilities
- Better performance for large message volumes (millions of messages)
- Professional-grade scalability and reliability

## 1. Preparation

* Download or clone this repository
* Install Python from here: https://www.python.org/downloads/
* Install MeiliSearch from here: https://github.com/meilisearch/meilisearch
* Apply for APP_ID and APP_HASH from here: https://my.telegram.org/
* Obtain your bot token by contacting https://t.me/BotFather.
* Obtain your user ID by contacting https://t.me/blog_update_bot.

## 2. Modify environment file

Use your favorite editor to modify `config.py`, example:

```python
# Telegram credentials
APP_ID = 176552
APP_HASH = "667276jkajhw"
TOKEN = "123456:8hjhad"
OWNER_ID = "2311231"

# Search engine (meili, mongo, zinc, elastic)
ENGINE = "meili"
MEILI_HOST = "localhost"

# Access control (private, group, public)
BOT_MODE = "private"  # Default: owner only

# For group mode (optional):
# ALLOWED_GROUPS = [-1001234567890, -1009876543210]
# ALLOWED_USERS = [123456789, 987654321]
```

If you have limited network access, such as in China, you will need to set up a proxy.

```python
PROXY = {"scheme": "socks5", "hostname": "localhost", "port": 1080}
```

### Group Mode Configuration

To enable the bot in Telegram groups:

```python
BOT_MODE = "group"
ALLOWED_GROUPS = [-1001234567890]  # Your group IDs
ALLOWED_USERS = [123456789]  # Additional authorized users
```

Then add the bot to your group and anyone in the group can search (with privacy controls).

## 3. Login to client

Open a terminal (such as cmd or iTerm), navigate to the directory where you have saved the code, and then:

```shell
python client.py
```

Enter your phone number and log in to the client. You can exit by pressing `Ctrl + C`.

## 4. (optional)Setup sync id

See [here](Docker.md#6-optionalsetup-sync-id)

## 5. Run!

Open two terminals and run the following commands in each terminal:

```shell
python client.py
python bot.py
```

## 6. (Optional) Migration

* add timestamp to all your data for better sorting `python add_timestamp.py`

# Sponsor

* [Buy me a coffee](https://www.buymeacoffee.com/bennythink)
* [Afdian](https://afdian.net/@BennyThink)
* [GitHub Sponsor](https://github.com/sponsors/BennyThink)

## Stripe

If you would like to donate to the project using Stripe, please click on the button below.

You can choose the currency and payment method that best suits you.

| USD(Card, Apple Pay and Google Pay)              | SEK(Card, Apple Pay and Google Pay)              | CNY(Card, Apple Pay, Google Pay and Alipay)      |
|--------------------------------------------------|--------------------------------------------------|--------------------------------------------------|
| [USD](https://buy.stripe.com/cN203sdZB98RevC3cd) | [SEK](https://buy.stripe.com/bIYbMa9JletbevCaEE) | [CNY](https://buy.stripe.com/dR67vU4p13Ox73a6oq) |
| ![](assets/USD.png)                              | ![](assets/SEK.png)                              | ![](assets/CNY.png)                              |

# License

This project is licensed under the GNU GENERAL PUBLIC LICENSE Version 3.
