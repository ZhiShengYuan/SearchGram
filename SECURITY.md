# SearchGram Security Documentation

## JWT Authentication Implementation

All HTTP APIs in SearchGram are protected with **Ed25519-signed JWT tokens** for authentication.

### Overview

SearchGram uses a **microservice architecture** with three main services:

1. **Go Search Service** (port 8080) - Elasticsearch backend for message indexing/search
2. **Python Userbot Service** (port 8082) - Sync API for on-demand chat indexing
3. **Python Bot Service** - Telegram bot interface for users

All HTTP communication between these services requires valid JWT authentication.

---

## Authentication Architecture

### Service Identity

Each service has a unique **issuer** identifier:

- **`bot`** - The Telegram bot service
- **`userbot`** - The client/userbot sync service
- **`search`** - The Go search engine service

### Token Flow

```
┌─────────┐                    ┌──────────┐                    ┌────────┐
│   Bot   │ ──JWT(bot→search)→ │  Search  │                    │        │
│ Service │                    │  Engine  │                    │ User-  │
│         │ ←─────────────────  │  (Go)    │ ←JWT(userbot→search)│ bot    │
└─────────┘                    └──────────┘                    │ Service│
     │                                                          │        │
     │                                                          └────────┘
     │                                                               ▲
     └───────────────JWT(bot→userbot)──────────────────────────────┘
```

**Flow Examples:**

1. **Bot → Search**: Bot searches for messages
   - Bot generates JWT with `iss=bot`, `aud=search`
   - Search service verifies token from `bot` issuer

2. **Bot → Userbot**: Bot triggers sync task
   - Bot generates JWT with `iss=bot`, `aud=userbot`
   - Userbot service verifies token from `bot` issuer

3. **Userbot → Search**: Userbot indexes messages
   - Userbot generates JWT with `iss=userbot`, `aud=search`
   - Search service verifies token from `userbot` issuer

---

## Configuration

### Required Settings

Add to your `config.json`:

```json
{
  "auth": {
    "use_jwt": true,
    "public_key_path": "./keys/public_key.pem",
    "private_key_path": "./keys/private_key.pem",
    "token_ttl": 300
  }
}
```

**IMPORTANT:** All services **must** share the same Ed25519 key pair.

### Configuration Options

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `auth.use_jwt` | boolean | **Yes** | Enable JWT authentication (**must be true** for production) |
| `auth.public_key_path` | string | Yes* | Path to Ed25519 public key PEM file |
| `auth.private_key_path` | string | Yes* | Path to Ed25519 private key PEM file |
| `auth.public_key_inline` | string/array | Yes* | Inline public key (alternative to file path) |
| `auth.private_key_inline` | string/array | Yes* | Inline private key (alternative to file path) |
| `auth.token_ttl` | integer | No | Token TTL in seconds (default: 300) |

\* Either file paths OR inline keys must be provided

---

## Key Generation

### Generate Ed25519 Keys

```bash
# Create keys directory
mkdir -p keys

# Generate private key
openssl genpkey -algorithm ed25519 -out keys/private_key.pem

# Extract public key
openssl pkey -in keys/private_key.pem -pubout -out keys/public_key.pem

# Set secure permissions
chmod 600 keys/private_key.pem
chmod 644 keys/public_key.pem
```

### Inline Key Format

If you prefer inline keys in config (e.g., for Docker secrets):

**Option 1: Single string with \n**
```json
{
  "auth": {
    "public_key_inline": "-----BEGIN PUBLIC KEY-----\\nMCowBQYDK2VwAyEA...\\n-----END PUBLIC KEY-----"
  }
}
```

**Option 2: Array of lines**
```json
{
  "auth": {
    "public_key_inline": [
      "-----BEGIN PUBLIC KEY-----",
      "MCowBQYDK2VwAyEA...",
      "-----END PUBLIC KEY-----"
    ]
  }
}
```

---

## Protected Endpoints

### Go Search Service (port 8080)

**Public Endpoints** (no auth required):
- `GET /` - Service info
- `GET /health` - Health check

**Protected Endpoints** (require JWT from `bot`, `userbot`, or `search`):
- `POST /api/v1/upsert` - Index single message
- `POST /api/v1/upsert/batch` - Batch indexing
- `POST /api/v1/search` - Search messages
- `POST /api/v1/messages/soft-delete` - Soft delete message
- `DELETE /api/v1/messages` - Delete messages
- `DELETE /api/v1/users/:user_id` - Delete user data
- `DELETE /api/v1/clear` - Clear database
- `POST /api/v1/dedup` - Deduplicate messages
- `DELETE /api/v1/commands` - Clean commands
- `GET /api/v1/ping` - Engine ping
- `GET /api/v1/stats` - Statistics
- `GET /api/v1/status` - Status check
- `POST /api/v1/stats/user` - User activity stats

### Python Userbot Sync API (port 8082)

**Public Endpoints**:
- `GET /health` - Health check

**Protected Endpoints** (require JWT from `bot`):
- `POST /api/v1/sync` - Add chat to sync queue
- `GET /api/v1/sync/status` - Get sync status
- `POST /api/v1/sync/pause` - Pause sync task
- `POST /api/v1/sync/resume` - Resume sync task

---

## Security Features

### Token Security

- **Algorithm**: EdDSA (Ed25519) - faster and more secure than RSA
- **Expiration**: Tokens expire after `token_ttl` seconds (default: 5 minutes)
- **Unique IDs**: Each token has a unique `jti` (JWT ID)
- **Audience Validation**: Tokens are bound to specific target services
- **Issuer Validation**: Only whitelisted issuers are accepted

### Backward Compatibility

For testing/development, JWT can be disabled:

```json
{
  "auth": {
    "use_jwt": false
  }
}
```

**⚠️ WARNING:** Running with `use_jwt: false` is **NOT RECOMMENDED** for production. All API endpoints will be **completely unprotected**.

### Legacy API Key Authentication

The Go service still supports legacy API key authentication as a fallback:

```json
{
  "auth": {
    "use_jwt": false,
    "enabled": true,
    "api_key": "your-secret-key-here"
  }
}
```

This is **deprecated** and will be removed in future versions. Use JWT instead.

---

## Testing JWT Authentication

A test script is provided to verify JWT functionality:

```bash
# Install dependencies (if needed)
pip3 install PyJWT cryptography

# Run tests
python3 test_jwt_auth.py
```

**Expected output:**
```
JWT Authentication Test Suite
==============================================================

Test 1: Basic JWT Token Generation and Verification
...
✓ Test 1 PASSED

Test 2: Cross-Service Authentication
...
✓ Test 2 PASSED

Test 3: Invalid Issuer Rejection
...
✓ Test 3 PASSED

Test 4: Expired Token Rejection
...
✓ Test 4 PASSED

Test Results: 4 passed, 0 failed
```

---

## Troubleshooting

### "Missing Authorization header"

**Problem:** API returns 401 Unauthorized

**Solution:** Ensure your client is sending the JWT token:
```http
Authorization: Bearer eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9...
```

### "Invalid issuer"

**Problem:** Token rejected with "Invalid issuer" error

**Solution:** Check that the token issuer is in the allowed list for the endpoint.

Example: Userbot sync API only accepts tokens from `bot` issuer.

### "Token expired"

**Problem:** Token rejected with "Token expired" error

**Solution:** Generate a new token. Tokens are short-lived (default: 5 minutes).

### "Failed to load public/private key"

**Problem:** Service fails to start with key loading error

**Solution:**
1. Verify key files exist at the specified paths
2. Check file permissions (private key should be 600)
3. Verify keys are valid Ed25519 PEM format
4. If using inline keys, ensure proper JSON escaping

### Services can't communicate

**Problem:** Bot can't call search service or userbot API

**Solution:**
1. Verify all services use the **same key pair**
2. Check `auth.use_jwt: true` in config
3. Ensure `services.search.base_url` and `services.userbot.base_url` are correct
4. Check network connectivity between services

---

## Security Best Practices

1. ✅ **Always enable JWT in production** (`auth.use_jwt: true`)
2. ✅ **Use strong key permissions** (`chmod 600` for private key)
3. ✅ **Rotate keys periodically** (at least annually)
4. ✅ **Use short token TTL** (5-10 minutes recommended)
5. ✅ **Keep keys secure** (never commit to git, use secrets management)
6. ✅ **Monitor for unauthorized access** (check logs for 401 errors)
7. ✅ **Bind services to localhost** unless cross-server deployment needed
8. ✅ **Use TLS/HTTPS** for production deployments

---

## Cross-Server Deployment

If bot and userbot run on different machines:

**On bot server (nomao-lax):**
```json
{
  "services": {
    "userbot": {
      "base_url": "http://ucre3:8082"
    }
  },
  "auth": {
    "use_jwt": true,
    "public_key_path": "./keys/public_key.pem",
    "private_key_path": "./keys/private_key.pem"
  }
}
```

**On userbot server (ucre3):**
```json
{
  "http": {
    "listen": "0.0.0.0",
    "userbot_port": 8082
  },
  "auth": {
    "use_jwt": true,
    "public_key_path": "./keys/public_key.pem",
    "private_key_path": "./keys/private_key.pem"
  }
}
```

**⚠️ IMPORTANT:** When binding to `0.0.0.0`, **JWT authentication is MANDATORY**. Configure firewall rules to restrict access.

---

## Migration from Unprotected Setup

If upgrading from an older version without JWT:

1. **Generate keys** (see Key Generation section above)

2. **Update config.json**:
   ```json
   {
     "auth": {
       "use_jwt": true,
       "public_key_path": "./keys/public_key.pem",
       "private_key_path": "./keys/private_key.pem"
     }
   }
   ```

3. **Copy keys to all servers** (if multi-server deployment)

4. **Restart all services**:
   ```bash
   # Terminal 1: Search service
   cd searchgram-engine && go run main.go

   # Terminal 2: Client/userbot
   python3 searchgram/client.py

   # Terminal 3: Bot
   python3 searchgram/bot.py
   ```

5. **Verify in logs**:
   - Go service: `JWT auth initialized`
   - Python services: `initialized with JWT authentication enabled`

---

## Implementation Details

### Go Service (searchgram-engine/)

- **Package**: `searchgram-engine/jwt/jwt.go`
- **Middleware**: Applied to `/api/v1/*` routes in `main.go`
- **Allowed issuers**: `bot`, `userbot`, `search`
- **Public endpoints**: `/`, `/health` (monitoring)

### Python Userbot Service (searchgram/)

- **Module**: `searchgram/jwt_auth.py`
- **Middleware**: `@require_jwt_auth` decorator in `sync_api.py`
- **Allowed issuers**: `bot` only
- **Public endpoints**: `/health`

### Python Bot Service (searchgram/)

- **HTTP Client**: `searchgram/sync_http_client.py`
- **Search Engine**: `searchgram/http_engine.py`
- **Token generation**: Automatic in `_get_headers()` methods
- **Issuer**: `bot`

---

## Support

For security issues, please report privately to the maintainers.

For configuration help, see:
- `CLAUDE.md` - Project architecture and configuration
- `config.example.json` - Example configuration file
- `README.md` - General project documentation
