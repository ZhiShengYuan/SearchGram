# SearchGram HTTP Integration Guide

This guide explains the RESTful HTTP integration with JWT authentication implemented for SearchGram.

## Overview

The implementation adds:

1. **JWT Authentication (Ed25519)**: All services communicate using JWT tokens
2. **RESTful APIs**: Bot ↔ Userbot communication via HTTP POST/GET/DELETE
3. **Real Timing Metrics**: Search backend returns actual server-side timing
4. **Removed Legacy Engines**: Only HTTP search engine is supported now

## Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Bot Service   │         │ Userbot Service │         │ Search Service  │
│  (port 8081)    │◄───────►│  (port 8082)    │         │  (port 8080)    │
│                 │  JWT    │                 │         │   (Go/Gin)      │
│  + HTTP Server  │         │  + HTTP Server  │         │                 │
│  + Telegram Bot │         │  + Telegram Userbot       │  + Elasticsearch│
└─────────┬───────┘         └─────────┬───────┘         └─────────┬───────┘
          │                           │                           │
          └───────────────────────────┴───────────────────────────┘
                          JWT Auth (Bearer Token)
                        All endpoints require auth
```

## What's Been Implemented

### 1. JWT Utilities (`searchgram/jwt_utils.py`)

- Ed25519 key generation and loading
- Token generation with configurable TTL
- Token verification with issuer/audience validation
- Flask middleware for JWT auth

### 2. Message Store (`searchgram/message_store.py`)

- SQLite-based persistent message queue
- Thread-safe operations
- Enqueue/dequeue/acknowledge operations
- Auto-cleanup of old messages

### 3. HTTP Server (`searchgram/http_server.py`)

RESTful endpoints:
- `GET /v1/status` - Health check (returns service, status, uptime, message count)
- `POST /v1/messages` - Send message to another service
- `GET /v1/messages?to=<service>` - Poll messages
- `DELETE /v1/messages/<id>` - Acknowledge message

All endpoints require JWT auth via `Authorization: Bearer <token>` header.

### 4. Go Search Service Updates

**New Files:**
- `searchgram-engine/jwt/jwt.go` - JWT middleware for Go
- `searchgram-engine/config.example.yaml` - Example config with JWT settings

**Modified Files:**
- `searchgram-engine/config/config.go` - Added JWT config
- `searchgram-engine/main.go` - Use JWT middleware instead of API key
- `searchgram-engine/handlers/api.go` - Added `GET /api/v1/status` and `took_ms` timing
- `searchgram-engine/models/message.go` - Added `TookMs` field to `SearchResponse`

### 5. Python HTTP Engine Updates (`searchgram/http_engine.py`)

- Added JWT authentication to all outbound requests
- Extract real timing from backend response (`took_ms`)
- Removed fake timing logic

### 6. Legacy Engine Removal

**Deleted files:**
- `searchgram/meili.py`
- `searchgram/mongo.py`
- `searchgram/zinc.py`
- `searchgram/elastic.py`

**Updated:**
- `searchgram/__init__.py` - Only supports `engine: "http"` now

### 7. Configuration

**Updated `config.example.json`:**
```json
{
  "services": {
    "bot": {"base_url": "http://127.0.0.1:8081"},
    "userbot": {"base_url": "http://127.0.0.1:8082"},
    "search": {"base_url": "http://127.0.0.1:8080"}
  },
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "audience": "internal",
    "public_key_path": "keys/public.key",
    "private_key_path": "keys/private.key",
    "token_ttl": 300
  },
  "http": {
    "listen": "127.0.0.1",
    "bot_port": 8081,
    "userbot_port": 8082,
    "message_queue_db": "message_queue.db"
  }
}
```

### 8. Scripts

- `scripts/generate_keys.py` - Generate Ed25519 keypair
- `scripts/test_integration.py` - Integration tests and manual test guide

## Integration into Bot and Userbot

To complete the integration, add HTTP servers to `bot.py` and `client.py`:

### For `bot.py`:

Add after imports:
```python
from searchgram.config_loader import (
    AUTH_USE_JWT, AUTH_ISSUER, AUTH_AUDIENCE,
    AUTH_PUBLIC_KEY_PATH, AUTH_PRIVATE_KEY_PATH,
    HTTP_LISTEN_HOST, HTTP_BOT_PORT, HTTP_MESSAGE_QUEUE_DB
)
from searchgram.jwt_utils import JWTAuth
from searchgram.message_store import get_message_store
from searchgram.http_server import SearchGramHTTPServer
```

Add before `app.run()`:
```python
# Initialize HTTP server for inter-service communication
if AUTH_USE_JWT:
    try:
        jwt_auth = JWTAuth(
            issuer=AUTH_ISSUER,
            audience=AUTH_AUDIENCE,
            private_key_path=AUTH_PRIVATE_KEY_PATH,
            public_key_path=AUTH_PUBLIC_KEY_PATH,
            token_ttl=300,
        )
        message_store = get_message_store(HTTP_MESSAGE_QUEUE_DB)

        # Get message count callback
        def get_message_count():
            try:
                result = tgdb.ping()
                return result.get("total_documents", 0)
            except:
                return 0

        http_server = SearchGramHTTPServer(
            service_name="bot",
            listen_host=HTTP_LISTEN_HOST,
            listen_port=HTTP_BOT_PORT,
            jwt_auth=jwt_auth,
            message_store=message_store,
            get_message_count_callback=get_message_count,
        )
        http_server.start()
        logging.info(f"✅ Bot HTTP server started on {HTTP_LISTEN_HOST}:{HTTP_BOT_PORT}")
    except Exception as e:
        logging.error(f"Failed to start HTTP server: {e}")
```

### For `client.py`:

Same pattern as bot.py, but:
```python
http_server = SearchGramHTTPServer(
    service_name="userbot",  # <-- Change this
    listen_host=HTTP_LISTEN_HOST,
    listen_port=HTTP_USERBOT_PORT,  # <-- And this
    jwt_auth=jwt_auth,
    message_store=message_store,
    get_message_count_callback=get_message_count,
)
```

## Setup Instructions

### 1. Generate Keys

```bash
python scripts/generate_keys.py
```

This creates:
- `keys/private.key` (mode 600)
- `keys/public.key` (mode 644)

### 2. Copy Keys to Go Service

```bash
cp keys/*.key searchgram-engine/keys/
```

### 3. Update Configuration

**config.json:**
```json
{
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "public_key_path": "keys/public.key",
    "private_key_path": "keys/private.key"
  }
}
```

Note: Set `issuer` to "bot" for bot.py and "userbot" for client.py.

**searchgram-engine/config.yaml:**
```yaml
auth:
  use_jwt: true
  issuer: "search"
  audience: "internal"
  public_key_path: "keys/public.key"
  private_key_path: "keys/private.key"
  token_ttl: 300
```

### 4. Start Services

```bash
# Terminal 1: Search engine
cd searchgram-engine
./searchgram-engine

# Terminal 2: Userbot (with HTTP server)
python searchgram/client.py

# Terminal 3: Bot (with HTTP server)
python searchgram/bot.py
```

## Testing

### Automated Tests

```bash
python scripts/test_integration.py
```

### Manual Tests

```bash
# Generate token
python -c 'from searchgram.jwt_utils import JWTAuth; auth = JWTAuth("bot", "internal", "keys/private.key", "keys/public.key"); print(auth.generate_token())'

export TOKEN=<paste-token-here>

# Test status endpoints
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8081/v1/status
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8082/v1/status
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/v1/status

# Test message relay
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"to": "userbot", "type": "command", "payload": {"action": "test"}}' \
     http://127.0.0.1:8081/v1/messages

curl -H "Authorization: Bearer $TOKEN" \
     "http://127.0.0.1:8082/v1/messages?to=userbot&limit=10"

# Test search with real timing
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"keyword": "test", "page": 1, "page_size": 10}' \
     http://127.0.0.1:8080/api/v1/search | jq '.took_ms'
```

## Security Notes

1. **Keep private key secure**: Never commit `keys/private.key` to version control
2. **Use 127.0.0.1 by default**: Services listen on localhost for security
3. **Short token TTL**: Tokens expire after 5 minutes by default
4. **All endpoints require auth**: No unauthenticated access allowed
5. **Ed25519 over RS256**: Faster and more secure than RSA

## Troubleshooting

### "Missing Authorization header"

Add JWT token: `curl -H "Authorization: Bearer <token>" ...`

### "Invalid token"

- Check token hasn't expired (TTL: 300s)
- Verify public/private keys match
- Ensure `issuer` and `audience` match config

### "Connection refused"

- Verify service is running
- Check port matches config
- Ensure `listen_host` is correct

### "took_ms not in response"

- Check Go service version includes timing changes
- Verify using `/api/v1/search` (not legacy endpoint)
- Check Go service logs for errors

## API Reference

### GET /v1/status

**Auth:** Required
**Returns:**
```json
{
  "service": "bot|userbot|search",
  "status": "ok",
  "hostname": "...",
  "uptime_seconds": 123,
  "message_index_total": 456789,
  "timestamp": "2025-12-31T12:00:00Z"
}
```

### POST /v1/messages

**Auth:** Required
**Body:**
```json
{
  "to": "bot|userbot",
  "type": "command|info|event",
  "payload": { ... }
}
```

**Returns:**
```json
{
  "id": "uuid",
  "created_at": "2025-12-31T12:00:00Z"
}
```

### GET /v1/messages

**Auth:** Required
**Query Params:**
- `to`: Target service (required)
- `after_id`: Pagination cursor (optional)
- `limit`: Max messages (default: 10, max: 100)

**Returns:**
```json
{
  "items": [{
    "id": "uuid",
    "from": "bot",
    "to": "userbot",
    "type": "command",
    "payload": { ... },
    "created_at": "2025-12-31T12:00:00Z"
  }],
  "next_after_id": "uuid-or-null"
}
```

### DELETE /v1/messages/<id>

**Auth:** Required
**Returns:**
```json
{
  "success": true
}
```

### POST /api/v1/search

**Auth:** Required
**Body:**
```json
{
  "keyword": "search term",
  "page": 1,
  "page_size": 10,
  "exact_match": false,
  "chat_type": "GROUP",
  "username": "user123",
  "blocked_users": [123, 456]
}
```

**Returns:**
```json
{
  "hits": [...],
  "total_hits": 100,
  "total_pages": 10,
  "page": 1,
  "hits_per_page": 10,
  "took_ms": 42  // Real backend timing
}
```

## Migration from Legacy Engines

If you were using legacy search engines (meili, mongo, zinc, elastic):

1. **Export your data** from the old engine
2. **Switch to HTTP engine** in config: `"engine": "http"`
3. **Setup Go search service** with Elasticsearch backend
4. **Re-import your data** via the new HTTP API
5. **Remove legacy config** sections (meili, mongo, zinc, elastic)

The HTTP engine provides:
- Better performance (Go + HTTP/2)
- Better security (JWT auth)
- Better scalability (connection pooling)
- Real timing metrics
- CJK-optimized search (Elasticsearch bigram tokenization)

---

**Status:** Implementation complete, ready for integration into bot.py and client.py
