# SearchGram Upgrade Guide

## What's New in This Release

This major update brings significant improvements to SearchGram:

### 🎯 Key Features

1. **✨ Elasticsearch Support** - High-performance CJK-optimized search
2. **🔐 Privacy Controls** - User opt-out system with `/block_me` command
3. **👥 Group Support** - Multi-user access with whitelisting
4. **📊 JSON Configuration** - Structured config with environment variable fallback
5. **🔄 Resume-Capable Sync** - Checkpoint-based history synchronization that survives interruptions

---

## Upgrade Path

### Step 1: Backup Your Data

```bash
# Backup current configuration
cp sync.ini sync.ini.backup 2>/dev/null || true

# Backup session files (important!)
cp -r searchgram/session searchgram/session.backup
```

### Step 2: Pull Latest Code

```bash
git pull origin master

# Or if you have local changes
git stash
git pull origin master
git stash pop
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

New dependency added: `elasticsearch==8.17.0`

### Step 4: Migrate Configuration

**Option A: Interactive Migration (Recommended)**

```bash
python migrate_config.py
```

Follow the prompts to:
- Convert sync.ini to config.json
- Set up JSON configuration
- Configure new features

**Option B: Manual Configuration**

```bash
cp config.example.json config.json
# Edit config.json with your settings
```

**Option C: Continue Using Environment Variables**

No action needed! The new system is backwards compatible.

### Step 5: Update Docker Configuration (if using Docker)

If you want to use Elasticsearch:

```bash
# config.json or environment variable
ENGINE=elastic

# Start Elasticsearch service
docker-compose up -d elasticsearch
```

Otherwise, continue using your current search engine.

### Step 6: Restart SearchGram

```bash
# Stop old processes
pkill -f "python.*client.py"
pkill -f "python.*bot.py"

# Start new processes
python searchgram/client.py &
python searchgram/bot.py &
```

---

## Breaking Changes

### ⚠️ Module Imports

**Old:**
```python
from config import BOT_ID, TOKEN
```

**New:**
```python
from config_loader import BOT_ID, TOKEN
```

**Impact:** If you have custom scripts importing from `config.py`, update them to use `config_loader.py`.

**Fix:** Search and replace in your custom code:
```bash
find . -name "*.py" -exec sed -i 's/from config import/from config_loader import/g' {} +
```

### ⚠️ Sync System

**Old sync.ini format:**
```ini
[sync]
-1001234567890
```

**New config.json format:**
```json
{
  "sync": {
    "enabled": true,
    "chats": [-1001234567890]
  }
}
```

**Impact:** sync.ini is deprecated but still works. Migration recommended.

**Migration:** Run `python migrate_config.py` to auto-convert.

---

## New Features Guide

### 1. Elasticsearch Integration

**Setup:**

```json
{
  "search_engine": {
    "engine": "elastic",
    "elastic": {
      "host": "http://localhost:9200",
      "user": "elastic",
      "password": "changeme"
    }
  }
}
```

Or with environment variables:
```bash
export ENGINE=elastic
export ELASTIC_HOST=http://localhost:9200
export ELASTIC_USER=elastic
export ELASTIC_PASS=changeme
```

**Benefits:**
- Best CJK search quality
- High performance for millions of messages
- Advanced filtering and analytics
- Production-grade scalability

### 2. Privacy Controls

**User Commands:**
- `/block_me` - Opt-out of search results
- `/unblock_me` - Opt back in
- `/privacy_status` - Check status

**How It Works:**
- Users control their own privacy
- Blocked users automatically filtered from all searches
- Persistent across restarts
- No admin override (user privacy first!)

**Storage:** `privacy_data.json` (configure in config.json)

### 3. Group Support

**Enable Group Mode:**

```json
{
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890],
    "allowed_users": [123456789]
  }
}
```

**Features:**
- Whitelist specific groups
- Whitelist specific users
- Shows "Requested by" in group searches
- Privacy commands work for all group members

**Security:**
- Explicit whitelist (no auto-join)
- Owner always has full access
- Silent denial (no error messages in unauthorized groups)

### 4. Resume-Capable Sync

**Configuration:**

```json
{
  "sync": {
    "enabled": true,
    "checkpoint_file": "sync_progress.json",
    "batch_size": 100,
    "resume_on_restart": true,
    "chats": [-1001234567890]
  }
}
```

**Features:**
- Checkpoint every 100 messages (configurable)
- Survives crashes and interruptions
- Real-time progress updates
- Automatic FloodWait handling
- Detailed error tracking

**Resume Example:**

```bash
# Start sync
python searchgram/client.py

# If interrupted (Ctrl+C, crash, power loss)
# Just restart:
python searchgram/client.py
# Sync continues from last checkpoint automatically!
```

**Check Progress:**

```bash
cat sync_progress.json | python -m json.tool
```

### 5. JSON Configuration

**Benefits:**
- Structured and readable
- Environment variable override
- Version control friendly (use .gitignore)
- Easy backup and migration

**Example:**

```json
{
  "telegram": {
    "app_id": 123456,
    "app_hash": "abc123",
    "bot_token": "123456:ABC-DEF",
    "owner_id": 260260121
  },
  "search_engine": {
    "engine": "elastic"
  },
  "bot": {
    "mode": "private"
  },
  "sync": {
    "enabled": true,
    "chats": []
  }
}
```

---

## Configuration Migration Examples

### Example 1: Simple Private Bot

**Before (environment variables):**
```bash
export APP_ID=123456
export APP_HASH=abc123
export TOKEN=123456:ABC-DEF
export OWNER_ID=260260121
export ENGINE=meili
```

**After (config.json):**
```json
{
  "telegram": {
    "app_id": 123456,
    "app_hash": "abc123",
    "bot_token": "123456:ABC-DEF",
    "owner_id": 260260121
  },
  "search_engine": {
    "engine": "meili"
  }
}
```

### Example 2: Group Bot with Sync

**Before (sync.ini + env vars):**
```ini
# sync.ini
[sync]
-1001234567890
-1009876543210
```

```bash
export BOT_MODE=group
export ALLOWED_GROUPS="-1001234567890,-1009876543210"
```

**After (config.json):**
```json
{
  "telegram": { ... },
  "search_engine": { ... },
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890, -1009876543210]
  },
  "sync": {
    "enabled": true,
    "chats": [-1001234567890, -1009876543210]
  }
}
```

---

## Testing the Upgrade

### 1. Test Configuration Loading

```bash
python -c "from searchgram.config_loader import *; print(f'APP_ID: {APP_ID}, ENGINE: {ENGINE}, BOT_MODE: {BOT_MODE}')"
```

Expected output shows your configuration values.

### 2. Test Search Engine Connection

```bash
python -c "from searchgram import SearchEngine; se = SearchEngine(); print(se.ping())"
```

Should show search engine stats.

### 3. Test Privacy System

```bash
python -c "from searchgram.privacy import privacy_manager; print(f'Blocked users: {privacy_manager.get_blocked_count()}')"
```

### 4. Test Sync Manager

```bash
python -c "from searchgram.sync_manager import SyncManager; print('Sync manager loaded successfully')"
```

### 5. Full Integration Test

1. Start client: `python searchgram/client.py`
2. Send a test message to yourself
3. Check logs for "Adding new message"
4. Start bot: `python searchgram/bot.py`
5. Send search query to bot
6. Verify results appear

---

## Rollback Instructions

If you need to rollback:

### 1. Restore Code

```bash
git checkout <previous-commit-hash>
```

### 2. Restore Configuration

```bash
cp sync.ini.backup sync.ini
# Remove config.json if created
rm config.json sync_progress.json privacy_data.json
```

### 3. Downgrade Dependencies

```bash
pip install -r requirements.txt
```

### 4. Restart Services

```bash
pkill -f "python.*client.py"
pkill -f "python.*bot.py"
python searchgram/client.py &
python searchgram/bot.py &
```

---

## Troubleshooting

### Issue: "No module named 'config_loader'"

**Cause:** Old code trying to import from config.py

**Fix:**
```bash
git pull  # Get latest code
python -c "import searchgram.config_loader"  # Verify
```

### Issue: Sync not resuming after restart

**Check:**
1. Is `sync_progress.json` present?
2. Is `resume_on_restart` true in config?
3. What's the status in checkpoint file?

```bash
cat sync_progress.json | python -m json.tool | grep status
```

**Fix:**
```json
{
  "sync": {
    "resume_on_restart": true
  }
}
```

### Issue: Privacy commands not working

**Check:**
1. Is `privacy_data.json` writable?
2. Are file permissions correct?

```bash
ls -la privacy_data.json
chmod 644 privacy_data.json
```

### Issue: Group mode not working

**Check:**
1. Is bot added to the group?
2. Is group ID in `allowed_groups`?
3. Get group ID with bot:

```python
# In group, send /start
# Check logs for chat_id
```

**Fix:**
```json
{
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890]  // Add your group ID
  }
}
```

---

## Performance Tips

### Large Message Volumes

If syncing millions of messages:

1. **Use Elasticsearch** - Best performance
2. **Increase batch size** - Reduce checkpoint overhead
3. **Monitor FloodWait** - Adjust if frequent

```json
{
  "search_engine": {
    "engine": "elastic"
  },
  "sync": {
    "batch_size": 200
  }
}
```

### Memory Optimization

```bash
# Limit Elasticsearch heap
export ES_JAVA_OPTS="-Xms512m -Xmx512m"

# Or in docker-compose.yml
environment:
  - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
```

---

## Getting Help

### Documentation

- **CONFIG.md** - Complete configuration reference
- **DESIGN.md** - Architecture and design decisions
- **CLAUDE.md** - Developer documentation
- **README.md** - User guide

### Common Questions

**Q: Can I mix environment variables and config.json?**
A: Yes! Env vars override JSON settings.

**Q: Will my old sync.ini still work?**
A: Yes for now, but migration is recommended.

**Q: Do I need to re-index messages?**
A: No, existing indexed messages work fine.

**Q: Can I switch search engines?**
A: Yes, just change `engine` setting and restart.

---

## Summary Checklist

- [ ] Backed up sync.ini and session files
- [ ] Pulled latest code
- [ ] Installed dependencies (`pip install -r requirements.txt`)
- [ ] Ran migration tool (`python migrate_config.py`) OR created config.json manually
- [ ] Tested configuration loading
- [ ] Updated Docker setup (if using Elasticsearch)
- [ ] Restarted SearchGram processes
- [ ] Tested search functionality
- [ ] Tested privacy commands
- [ ] Verified sync resume capability

**Congratulations!** 🎉 You're now running the latest SearchGram with all new features!
