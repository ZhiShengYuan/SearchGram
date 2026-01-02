# SearchGram Refactoring - Testing Guide

## Overview

This guide helps you test the refactored indexing system with full JSON storage and normalized fields.

## Prerequisites

1. **Backup existing index** (if you have production data):
   ```bash
   # Create index snapshot or export data
   curl -X PUT "localhost:9200/_snapshot/my_backup/snapshot_1?wait_for_completion=true"
   ```

2. **Delete old index** (to use new mapping):
   ```bash
   curl -X DELETE "localhost:9200/telegram"
   ```

3. **Rebuild Go service**:
   ```bash
   cd searchgram-engine
   go build
   ```

## Test Plan

### Phase 1: Basic Functionality Tests

#### 1.1. Start Services

**Terminal 1 - Go Search Service:**
```bash
cd searchgram-engine
go run main.go
```

**Expected Output:**
```
INFO[...] Elasticsearch engine initialized host=http://localhost:9200 index=telegram
INFO[...] Created index with CJK optimization index=telegram
INFO[...] Server starting on 127.0.0.1:8080
```

**Terminal 2 - Python Client (Indexing):**
```bash
python searchgram/client.py
```

**Expected Output:**
```
INFO:root:Successfully connected to search service with HTTP/2 🚀
INFO:root:Starting history synchronization...
```

**Terminal 3 - Python Bot (Search Interface):**
```bash
python searchgram/bot.py
```

#### 1.2. Test Message Indexing

1. **Send a test message** in any Telegram chat
2. **Check client logs**:
   ```
   INFO:root:Adding new message: -1001234567890-12345
   ```
3. **Verify in Elasticsearch**:
   ```bash
   curl -X GET "localhost:9200/telegram/_search?pretty" -H 'Content-Type: application/json' -d'
   {
     "size": 1,
     "sort": [{"timestamp": "desc"}]
   }
   '
   ```

**Expected Fields in Response:**
- ✅ `id`, `message_id`, `chat_id`, `timestamp`
- ✅ `chat_type`, `chat_title`, `chat_username`
- ✅ `sender_type`, `sender_id`, `sender_name`, `sender_username`
- ✅ `sender_first_name`, `sender_last_name` (for user senders)
- ✅ `content_type`, `text`
- ✅ `is_forwarded`, `forward_*` fields (if forwarded)
- ✅ `entities` (if message has mentions/hashtags)
- ✅ `is_deleted`, `deleted_at`
- ✅ `chat`, `from_user` (backward compat)
- ✅ `raw_message` (full Pyrogram JSON)

### Phase 2: Search Functionality Tests

#### 2.1. Text Search

**Test 1: Fuzzy Search**
```
/search hello
```
**Expected:** Returns messages containing "hello" (case-insensitive, CJK-optimized)

**Test 2: Exact Match**
```
/search "hello world"
```
**Expected:** Returns messages with exact phrase "hello world"

**Test 3: Exact Match with Flag**
```
/search -m=e hello
```
**Expected:** Returns messages with exact match for "hello"

#### 2.2. Chat Type Filtering

**Test 1: Group Messages**
```
/search -t=GROUP keyword
```
**Expected:** Returns only messages from groups

**Test 2: Private Messages**
```
/search -t=PRIVATE keyword
```
**Expected:** Returns only messages from private chats

**Test 3: Channel Messages**
```
/search -t=CHANNEL keyword
```
**Expected:** Returns only messages from channels

#### 2.3. Sender Filtering

**Test 1: User by Username**
```
/search -u=johndoe keyword
```
**Expected:** Returns messages from user with username "johndoe"

**Test 2: User by ID**
```
/search -u=123456789 keyword
```
**Expected:** Returns messages from user with ID 123456789

**Test 3: Chat Sender** (send message as anonymous admin in a group)
```
/search keyword
```
**Expected:** Results include messages sent by chat (anonymous admin)
**Verify:** `sender_type="chat"` in Elasticsearch document

#### 2.4. Combined Filters

**Test: Type + User + Exact**
```
/search -t=GROUP -u=johndoe -m=e "exact phrase"
```
**Expected:** Returns only messages from groups, by user "johndoe", with exact phrase

### Phase 3: Privacy & Access Control Tests

#### 3.1. Privacy Commands

**Test 1: Block User**
```
/block_me
```
**Expected:** "You have opted out. Your messages won't appear in searches."

**Test 2: Verify Blocked**
```
/search keyword
```
**Expected:** Your messages are excluded from results

**Test 3: Unblock User**
```
/unblock_me
```
**Expected:** "You have opted back in. Your messages can now appear in searches."

**Test 4: Privacy Status**
```
/privacy_status
```
**Expected:** Shows current privacy status

#### 3.2. Access Control (Group Mode)

**Test 1: Owner Access**
- Login as owner
- Search in all groups
**Expected:** Can search all indexed groups

**Test 2: Admin Access**
- Login as admin (from `ADMINS` list)
- Search in groups
**Expected:** Can search all indexed groups (but can't run admin commands)

**Test 3: Regular User Access**
- Login as regular user
- Search in groups
**Expected:** Can only search groups listed in `USER_GROUP_PERMISSIONS` for that user

### Phase 4: Admin Commands Tests

#### 4.1. Health Check

**Test:**
```
/ping
```

**Expected Output:**
```
🏓 Pong!

Search Engine: http
Status: healthy
📊 Total Messages: 12,345

🔐 Privacy: 3 user(s) opted out

📝 Query Logs:
  • Total Queries: 567
  • Last 24h: 42
  • Avg Time: 125ms

⚙️ Bot Configuration:
  • Mode: group
  • Allowed Groups: 5
  • Allowed Users: 12
  • Admins: 2
```

#### 4.2. Deduplication

**Test:**
```
/dedup
```

**Expected:**
```
🔄 Starting deduplication...

This may take several minutes for large databases.
Estimated time: 2-5 minutes

✅ Deduplication complete!

Found: 150 duplicates
Removed: 150 duplicates
Time: 2m 34s
```

#### 4.3. Delete Operations

**Test 1: Delete by Chat**
```
/delete -1001234567890
```
**Expected:** Soft-deletes all messages from that chat

**Test 2: Delete by User**
```
/delete 123456789
```
**Expected:** Soft-deletes all messages from that user

**Verify:** Messages are marked with `is_deleted=true` in Elasticsearch

#### 4.4. Activity Stats

**Test 1: Basic Stats**
```
/mystats
```
**Expected:** Shows user's activity in the last year

**Test 2: Custom Time Window**
```
/mystats 30d
```
**Expected:** Shows user's activity in the last 30 days

**Test 3: With Mentions**
```
/mystats 90d at
```
**Expected:** Shows stats with mention counts (outgoing and incoming)

**Test 4: Date Range**
```
/mystats 2025-01-01..2025-12-31
```
**Expected:** Shows stats for specific date range

### Phase 5: Advanced Tests

#### 5.1. Forward Message Tests

**Test:**
1. Forward a message from another chat
2. Index it (should auto-detect forward)
3. Search for it
4. **Verify in Elasticsearch:**
   - `is_forwarded=true`
   - `forward_from_type` is set correctly ("user", "chat", or "name_only")
   - `forward_from_id` is set (if available)
   - `forward_from_name` is set
   - `forward_timestamp` is set

#### 5.2. Different Content Types

**Test 1: Text Message**
- Send text message
- **Verify:** `content_type="text"`, `text` is set

**Test 2: Sticker**
- Send sticker
- **Verify:** `content_type="sticker"`, `sticker_emoji` and `sticker_set_name` are set

**Test 3: Photo**
- Send photo with caption
- **Verify:** `content_type="photo"`, `caption` is set

**Test 4: Document**
- Send document
- **Verify:** `content_type="document"`, `caption` is set (if provided)

#### 5.3. Chat Sender (Anonymous Admin)

**Test:**
1. In a group, enable anonymous admins
2. Send message as anonymous admin
3. **Verify in Elasticsearch:**
   - `sender_type="chat"`
   - `sender_id` = group chat ID
   - `sender_chat_title` = group title
   - `sender_first_name` and `sender_last_name` are null

#### 5.4. Entity Extraction

**Test:**
1. Send message with mentions: "Hello @username and @[user link]"
2. Send message with hashtags: "#test #hashtag"
3. **Verify in Elasticsearch:**
   - `entities` array is populated
   - Each entity has `type`, `offset`, `length`
   - Text mentions have `user_id` set

### Phase 6: Performance Tests

#### 6.1. Batch Indexing

**Test:**
1. Sync a large chat with `/sync -1001234567890`
2. Monitor batch performance in logs
3. **Expected:** Batch upsert handles 100 messages efficiently

#### 6.2. Search Performance

**Test:**
1. Run search query on large index (10k+ messages)
2. Check response time in bot output
3. **Expected:** < 500ms for most queries

#### 6.3. Pagination

**Test:**
1. Search for common keyword
2. Navigate through pages using inline keyboard
3. **Expected:** Smooth pagination, no errors

### Phase 7: Backward Compatibility Tests

#### 7.1. Old Field Search

**Test:**
1. Delete index and restart Go service
2. Index some messages with new format
3. Run old-style searches (they should still work via backward compat)

**Queries to Test:**
- Filter by `chat.id` (should work via fallback)
- Filter by `from_user.id` (should work via fallback)
- Filter by `chat.type` (should work via fallback)

**Expected:** All searches work via dual-field queries (new + old)

### Phase 8: Edge Cases

#### 8.1. Service Messages

**Test:**
1. User joins group (service message)
2. User leaves group (service message)
3. **Verify:** Messages are handled gracefully (no errors)

#### 8.2. Deleted Messages

**Test:**
1. Send message
2. Delete it on Telegram
3. **Verify in Elasticsearch:**
   - `is_deleted=true`
   - `deleted_at` timestamp is set
4. Search for it
5. **Expected:** Message is excluded from search results (unless owner uses `include_deleted`)

#### 8.3. Edited Messages

**Test:**
1. Send message
2. Edit it
3. **Verify:** Message is re-indexed with updated content

## Verification Checklist

After testing, verify:

- [ ] All existing search filters work correctly
- [ ] New sender fields are populated correctly
- [ ] Forward information is captured
- [ ] Content types are detected correctly
- [ ] Privacy filtering works (blocked users)
- [ ] Access control works (group permissions)
- [ ] Admin commands work (ping, dedup, delete)
- [ ] Activity stats work with mention counts
- [ ] Backward compatibility maintained
- [ ] No errors in logs during normal operation
- [ ] Performance is acceptable (< 500ms searches)
- [ ] Batch indexing works efficiently
- [ ] Full message stored in `raw_message` field

## Common Issues & Solutions

### Issue 1: Index Already Exists Error

**Error:** `index [telegram] already exists`

**Solution:**
```bash
curl -X DELETE "localhost:9200/telegram"
# Restart Go service to recreate with new mapping
```

### Issue 2: JWT Authentication Errors

**Error:** `Authentication error: failed to generate JWT token`

**Solution:**
- Check `config.json` has valid `auth` section
- Ensure Ed25519 keys are generated correctly
- Verify `use_jwt=true` in config

### Issue 3: Old Fields Missing

**Error:** Search queries fail because old fields not populated

**Solution:**
- Check `message_converter.py` populates both old and new fields
- Verify `chat` and `from_user` nested objects exist in payload

### Issue 4: Raw Message Too Large

**Error:** Document size exceeds Elasticsearch limit

**Solution:**
- Consider compressing `raw_message` field
- Or exclude very large media metadata from `raw_message`

## Success Criteria

✅ **All tests pass**
✅ **No errors in logs**
✅ **Search performance < 500ms**
✅ **Backward compatibility maintained**
✅ **Privacy & access control work correctly**
✅ **Full message JSON stored successfully**
✅ **New normalized fields searchable**

## Next Steps After Testing

1. **Monitor production usage** for 1 week
2. **Collect performance metrics**
3. **Remove backward compatibility fields** after 1 month (if desired)
4. **Update documentation** with new field structure
5. **Create migration script** for existing data (if needed)
