# JSON-Only Configuration Migration Guide

## What Changed?

SearchGram now uses **JSON-only configuration**. All environment variable support has been removed.

### Before (Old System)
```bash
# Environment variables
export APP_ID=123456
export APP_HASH=abc123
export TOKEN=123456:ABC-DEF
# ... many more env vars

# Could also use config.json with env var fallback
# Priority: ENV > JSON > Defaults
```

### After (New System)
```json
// config.json - ONLY source of configuration
{
  "telegram": {
    "app_id": 123456,
    "app_hash": "abc123",
    "bot_token": "123456:ABC-DEF"
  }
}

// No environment variables supported
// No fallback chain - just config.json
```

---

## Why This Change?

**Problems with Environment Variables:**
1. ❌ Configuration scattered across multiple places
2. ❌ Priority confusion (which takes precedence?)
3. ❌ Hard to version control
4. ❌ Difficult to validate
5. ❌ Docker/deployment complexity

**Benefits of JSON-Only:**
1. ✅ Single source of truth
2. ✅ Easy to version control and diff
3. ✅ Built-in validation on startup
4. ✅ Clear error messages
5. ✅ Simpler deployment
6. ✅ Type safety with JSON schema

---

## Migration Steps

### Step 1: Check Current Configuration

If you're using environment variables:
```bash
# Check what you have set
env | grep -E '(APP_ID|APP_HASH|TOKEN|OWNER_ID|ENGINE)'
```

### Step 2: Run Migration Tool

```bash
python migrate_config.py
```

The wizard will:
- Ask for all required settings
- Migrate sync.ini if it exists
- Create config.json
- Backup existing files

### Step 3: Verify config.json

```bash
# Check JSON syntax
python -m json.tool config.json

# Test loading
python -c "from searchgram.config_loader import APP_ID, ENGINE; print(f'APP_ID: {APP_ID}, ENGINE: {ENGINE}')"
```

### Step 4: Remove Environment Variables (Optional)

```bash
# Clear environment variables
unset APP_ID APP_HASH TOKEN OWNER_ID ENGINE
# ... etc

# They won't be used anyway, but clean up for clarity
```

### Step 5: Restart SearchGram

```bash
# Stop old processes
pkill -f "python.*client.py"
pkill -f "python.*bot.py"

# Start with new config
python searchgram/client.py &
python searchgram/bot.py &
```

---

## Configuration File Structure

### Minimal config.json

```json
{
  "telegram": {
    "app_id": 123456,
    "app_hash": "your_hash_here",
    "bot_token": "123456:ABC-DEF",
    "owner_id": 260260121
  },
  "search_engine": {
    "engine": "elastic",
    "elastic": {
      "host": "http://elasticsearch:9200",
      "user": "elastic",
      "password": "changeme"
    }
  }
}
```

All other settings use sensible defaults!

### Complete config.json

See `config.example.json` for all available options.

---

## Required Fields

SearchGram validates these fields on startup:

| Field | Description | Example |
|-------|-------------|---------|
| `telegram.app_id` | Telegram API ID | `123456` |
| `telegram.app_hash` | Telegram API Hash | `"abc123def456"` |
| `telegram.bot_token` | Bot token | `"123456:ABC-DEF"` |
| `telegram.owner_id` | Your user ID | `260260121` |
| `search_engine.engine` | Search backend | `"elastic"` |

**Missing any of these?** You'll get a clear error message on startup:

```
❌ Missing required configuration fields in config.json:
  - telegram.app_id (Telegram API ID)
  - telegram.app_hash (Telegram API Hash)

Please update your config.json file.
```

---

## Error Messages & Solutions

### Error: Configuration file not found

```
❌ Configuration file not found: config.json

SearchGram requires a JSON configuration file.

Quick setup:
1. Copy example: cp config.example.json config.json
2. Edit config.json with your settings
3. Or run migration: python migrate_config.py
```

**Solution:**
```bash
python migrate_config.py
# Or
cp config.example.json config.json
# Then edit config.json
```

### Error: Invalid JSON

```
❌ Invalid JSON in configuration file: config.json
Error: Expecting ',' delimiter: line 10 column 5
```

**Solution:**
```bash
# Validate JSON
python -m json.tool config.json

# Fix syntax error at line 10
# Common issues:
# - Missing comma between fields
# - Trailing comma in last field
# - Quotes around numbers (should be: 123, not: "123")
```

### Error: Missing required fields

```
❌ Missing required configuration fields in config.json:
  - telegram.bot_token (Bot Token)
  - search_engine.engine (Search Engine Type)
```

**Solution:**
Add the missing fields to config.json:
```json
{
  "telegram": {
    "bot_token": "123456:ABC-DEF"
  },
  "search_engine": {
    "engine": "elastic"
  }
}
```

---

## Docker Deployment

### Method 1: Mount config.json

```yaml
# docker-compose.yml
version: '3.1'

services:
  client:
    image: bennythink/searchgram
    volumes:
      - ./config.json:/SearchGram/config.json:ro
      - ./sg_data/session:/SearchGram/searchgram/session
    command: ["python", "client.py"]

  bot:
    image: bennythink/searchgram
    volumes:
      - ./config.json:/SearchGram/config.json:ro
      - ./sg_data/session:/SearchGram/searchgram/session
    command: ["python", "bot.py"]
```

### Method 2: Docker Secrets (Production)

```yaml
# docker-compose.yml
version: '3.1'

services:
  client:
    image: bennythink/searchgram
    secrets:
      - searchgram_config
    command: ["sh", "-c", "cp /run/secrets/searchgram_config /SearchGram/config.json && python client.py"]

secrets:
  searchgram_config:
    file: ./config.json
```

### Method 3: Build into Image

```dockerfile
# Dockerfile
FROM python:3.10
WORKDIR /SearchGram
COPY config.json /SearchGram/
COPY . /SearchGram/
RUN pip install -r requirements.txt
```

⚠️ **Not recommended for secrets!** Better to mount as volume.

---

## Security Best Practices

### 1. Never Commit config.json

```bash
# Check .gitignore includes:
echo "config.json" >> .gitignore

# Verify it's ignored
git status | grep config.json
# Should not appear in untracked files
```

### 2. Restrict File Permissions

```bash
# Make readable only by owner
chmod 600 config.json

# Verify
ls -la config.json
# Output: -rw------- 1 user user ...
```

### 3. Use Different Configs for Environments

```bash
# Development
config.dev.json

# Production
config.prod.json

# Use different file per environment
python -c "from searchgram.config_loader import ConfigLoader; ConfigLoader('config.prod.json')"
```

### 4. Secrets Management (Production)

For production deployments:
- Use Docker secrets
- Use Kubernetes secrets
- Use HashiCorp Vault
- Use cloud provider secret managers (AWS Secrets Manager, etc.)

---

## Troubleshooting

### Q: Can I still use environment variables?

**A:** No. The new system is JSON-only. This is intentional for simplicity and clarity.

If you absolutely need environment variables (e.g., CI/CD), create config.json programmatically:

```bash
#!/bin/bash
# generate_config.sh
cat > config.json <<EOF
{
  "telegram": {
    "app_id": ${APP_ID},
    "app_hash": "${APP_HASH}",
    "bot_token": "${TOKEN}",
    "owner_id": ${OWNER_ID}
  },
  "search_engine": {
    "engine": "${ENGINE:-elastic}"
  }
}
EOF

python searchgram/client.py
```

### Q: How do I validate my config.json?

```bash
# Method 1: Python JSON validator
python -m json.tool config.json > /dev/null && echo "✅ Valid JSON" || echo "❌ Invalid JSON"

# Method 2: Load config module
python -c "from searchgram.config_loader import get_config; print('✅ Config loaded successfully')"

# Method 3: Check specific values
python searchgram/config_loader.py
```

### Q: What if I have multiple configs?

```python
# In your code
from searchgram.config_loader import ConfigLoader

# Load specific config file
config = ConfigLoader("config.production.json")
app_id = config.get_int("telegram.app_id")
```

### Q: How do I update configuration at runtime?

**A:** You can't. Configuration is loaded once at startup. Restart the process after changing config.json:

```bash
# Edit config
vim config.json

# Restart
pkill -f "python.*client.py"
python searchgram/client.py &
```

---

## Comparison Table

| Feature | Old (Env Vars) | New (JSON-Only) |
|---------|----------------|-----------------|
| **Configuration Source** | ENV > JSON > Defaults | JSON only |
| **Validation** | Runtime errors | Startup validation |
| **Version Control** | Difficult | Easy (git diff) |
| **Debugging** | Check multiple places | Single file |
| **Deployment** | Export many vars | Mount one file |
| **Security** | .env files | .gitignore config.json |
| **Documentation** | Scattered | CONFIG.md |
| **Error Messages** | Generic | Specific field names |

---

## FAQ

### Will my old setup break?

Yes, if you're using environment variables. You **must** create config.json.

### Do I lose any features?

No. All features work the same, just configured via JSON instead of ENV.

### What about sync.ini?

Still supported! The migration tool converts it to config.json format.

### Can I gradually migrate?

No. It's all-or-nothing. But migration is easy with the wizard.

### What if I find a bug?

The JSON-only system is thoroughly tested. If you find issues:
1. Check CONFIG.md documentation
2. Validate your JSON syntax
3. Check error messages (they're very helpful)
4. Report to GitHub issues if needed

---

## Summary

✅ **Simple**: One file for all config
✅ **Clear**: No priority confusion
✅ **Safe**: Validation on startup
✅ **Secure**: Easy to .gitignore
✅ **Maintainable**: Version control friendly

🚀 **Ready to migrate?** Run `python migrate_config.py` now!
