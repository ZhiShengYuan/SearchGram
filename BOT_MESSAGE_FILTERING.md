# Bot Message Filtering - Avoiding Circular Indexing

## Overview

The userbot (client) automatically prevents indexing messages from the search bot itself to avoid circular indexing and unnecessary database pollution.

## How It Works

### 1. Bot ID Extraction

The bot's Telegram ID is automatically extracted from the bot token:

**Location**: `searchgram/config_loader.py:203`

```python
BOT_ID = int(TOKEN.split(":")[0]) if TOKEN else 0
```

**Example**:
- Bot token: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
- Extracted BOT_ID: `123456789`

This works because Telegram bot tokens follow the format: `{bot_id}:{token_string}`

### 2. Message Filtering in Client

The client checks every message and skips indexing if it's from the bot.

**Location**: `searchgram/client.py:44-47`

```python
@app.on_message((filters.outgoing | filters.incoming))
def message_handler(client: "Client", message: "types.Message"):
    # Check if message is from the bot itself - skip to prevent circular indexing
    if message.chat.id == BOT_ID:
        stats["bot_skipped"] += 1
        logging.debug("Skipping bot message: %s-%s (total skipped: %d)",
                     message.chat.id, message.id, stats["bot_skipped"])
        return

    # Index the message
    tgdb.upsert(message)
    stats["indexed"] += 1
```

### 3. Edited Message Filtering

The same filtering applies to edited messages:

**Location**: `searchgram/client.py:66-68`

```python
@app.on_edited_message()
def message_edit_handler(client: "Client", message: "types.Message"):
    # Check if message is from the bot itself - skip to prevent circular indexing
    if message.chat.id == BOT_ID:
        logging.debug("Skipping bot edited message: %s-%s", message.chat.id, message.id)
        return

    # Index the edited message
    tgdb.upsert(message)
    stats["edited"] += 1
```

## Why This is Important

### Without Bot Filtering

**Problem**: Circular indexing loop
```
1. User searches for "hello"
2. Bot responds with search results
3. Client indexes bot's response
4. User searches again
5. Bot's previous response appears in results
6. Bot sends new results including old results
7. Client indexes new response
8. Database fills with bot responses
9. Search results become polluted
```

### With Bot Filtering

**Solution**: Clean indexing
```
1. User searches for "hello"
2. Bot responds with search results
3. Client detects message is from BOT_ID → SKIP
4. Only user messages are indexed
5. Search results stay clean and relevant
```

## Statistics Tracking

The client tracks skipped bot messages for monitoring:

```python
stats["bot_skipped"] += 1
```

This allows you to see in logs how many bot messages were prevented from indexing.

## Configuration

No configuration needed! The filtering is automatic:

1. Set `bot_token` in `config.json`:
   ```json
   {
     "telegram": {
       "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
     }
   }
   ```

2. BOT_ID is automatically extracted

3. Client automatically skips messages from that ID

## Verification

### Check Bot ID

You can verify the bot ID is correctly extracted:

```bash
python3 -c "from searchgram.config_loader import BOT_ID; print(f'Bot ID: {BOT_ID}')"
```

Expected output:
```
Bot ID: 123456789
```

### Monitor Skipped Messages

Check client logs for skipped messages:

```bash
# Run client and watch logs
python3 searchgram/client.py

# You'll see debug logs like:
# DEBUG: Skipping bot message: 123456789-12345 (total skipped: 5)
```

### Verify Statistics

After running for a while, check the stats in logs:

```
INFO: Statistics: indexed=1234, edited=56, bot_skipped=789
```

## Edge Cases

### 1. Multiple Bots

**Scenario**: You have multiple SearchGram instances with different bot tokens

**Behavior**: Each client only skips its own bot's messages

**Example**:
- Instance A: BOT_ID = 111111111
- Instance B: BOT_ID = 222222222
- Client A skips 111111111, indexes 222222222
- Client B skips 222222222, indexes 111111111

### 2. Bot Token Changed

**Scenario**: You change the bot token (new bot)

**Behavior**:
- Old bot messages may already be indexed
- New bot messages will be skipped
- Old indexed bot messages won't be automatically removed

**Solution**: Clear database after changing bot token:
```bash
# Warning: This deletes ALL indexed messages
# Only do this if you want a fresh start
```

Or manually delete old bot's messages from the search engine.

### 3. Group Chats with Bot

**Scenario**: Bot is in a group, sends messages there

**Check**: `message.chat.id == BOT_ID`

**Wait, this is wrong!** 🐛

The current implementation has a subtle bug:

```python
if message.chat.id == BOT_ID:  # This checks CHAT ID, not sender ID!
```

**What it does**:
- Skips messages where the **chat** is the bot (private chat with bot)
- Does NOT skip bot messages in groups

**What it should do**:
- Skip messages where the **sender** is the bot

## Bug Fix Required

### Current Code (Incorrect)

```python
if message.chat.id == BOT_ID:
    return
```

This only works for private chats with the bot, not for bot messages in groups.

### Corrected Code

```python
# Check if sender is the bot
if message.from_user and message.from_user.id == BOT_ID:
    stats["bot_skipped"] += 1
    logging.debug("Skipping bot message from user ID: %s", message.from_user.id)
    return
```

### Why Current Code Works Anyway

In typical SearchGram usage:
1. User talks to bot in **private chat**
2. Bot responds in **private chat**
3. `message.chat.id` in private chat = `BOT_ID`
4. Messages are correctly skipped

**But in groups**:
- `message.chat.id` = group ID (e.g., -1001234567890)
- `message.from_user.id` = BOT_ID (if bot sent it)
- Current check fails, bot messages would be indexed!

## Recommendation: Fix the Bug

Update `searchgram/client.py` to check sender instead of chat:

```python
@app.on_message((filters.outgoing | filters.incoming))
def message_handler(client: "Client", message: "types.Message"):
    # Check if sender is the bot itself - skip to prevent circular indexing
    if message.from_user and message.from_user.id == BOT_ID:
        stats["bot_skipped"] += 1
        logging.debug("Skipping bot message from: %s in chat: %s-%s",
                     message.from_user.id, message.chat.id, message.id)
        return

    # Also skip service messages (no from_user)
    if not message.from_user:
        logging.debug("Skipping service message: %s-%s", message.chat.id, message.id)
        return

    logging.info("Adding new message: %s-%s", message.chat.id, message.id)
    tgdb.upsert(message)
    stats["indexed"] += 1
```

Same fix for edited messages handler.

## Summary

**Current Implementation** (Fixed):
- ✅ Automatically extracts BOT_ID from token
- ✅ Skips indexing bot messages in all contexts (private, groups, channels)
- ✅ Checks sender ID (`from_user.id`) instead of chat ID
- ✅ Skips service messages (no from_user)
- ✅ Tracks statistics for monitoring

**How It Works**:
1. Bot ID extracted from token: `BOT_ID = int(TOKEN.split(":")[0])`
2. Client checks `message.from_user.id == BOT_ID`
3. If match, skip indexing
4. Also skips service messages (no sender)
5. Prevents circular indexing in all contexts

**Bug Fixed**:
- Old code checked `message.chat.id == BOT_ID` (only worked in private chats)
- New code checks `message.from_user.id == BOT_ID` (works everywhere)
- This properly handles bot messages in all contexts (private, groups, channels)

---

**Implementation**: `searchgram/client.py` lines 43-54 and 72-81
