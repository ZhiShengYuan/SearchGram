# SearchGram Pre-Deployment Checklist

## ✅ Code Verification Complete

### Code Changes Verified:
- [x] **Go Models** (`searchgram-engine/models/message.go`): All new fields added correctly
- [x] **Elasticsearch Mapping** (`searchgram-engine/engines/elasticsearch.go`): Complete index mapping with all fields
- [x] **Search Queries**: Updated to search both `text` and `caption` fields
- [x] **Dual-Field Queries**: All queries support both new and old fields for backward compatibility
- [x] **Python Converter** (`searchgram/message_converter.py`): Comprehensive message normalization
- [x] **Go Compilation**: ✅ Compiled successfully
- [x] **Python Syntax**: ✅ Valid syntax

---

## 🚨 CRITICAL: Production Deployment Steps

**⚠️ WARNING: This will DELETE all existing search index data!**

### Step 1: Backup (Optional but Recommended)

If you want to keep a backup of your current data:

```bash
# Option A: Export to JSON (for small datasets < 100k messages)
curl -X GET "localhost:9200/telegram/_search?scroll=1m&size=1000" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match_all": {}}}' > backup.json

# Option B: Elasticsearch snapshot (for large datasets)
# Create snapshot repository first
curl -X PUT "localhost:9200/_snapshot/my_backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/path/to/backup"
  }
}
'

# Take snapshot
curl -X PUT "localhost:9200/_snapshot/my_backup/snapshot_1?wait_for_completion=true"
```

### Step 2: Stop All Services

```bash
# Stop bot and client (Ctrl+C in their terminals, or kill processes)
pkill -f "python.*searchgram/bot.py"
pkill -f "python.*searchgram/client.py"
pkill -f "searchgram-engine"

# Verify all stopped
ps aux | grep searchgram
```

### Step 3: Delete Old Elasticsearch Index

```bash
# ⚠️ THIS DELETES ALL DATA - MAKE SURE YOU'VE BACKED UP IF NEEDED!
curl -X DELETE "localhost:9200/telegram"

# Verify deletion
curl -X GET "localhost:9200/telegram/_count"
# Should return: {"error":{"type":"index_not_found_exception"}}
```

### Step 4: Build New Go Service

```bash
cd /home/kexi/SearchGram/searchgram-engine
go build -o searchgram-engine

# Verify build succeeded
ls -lh searchgram-engine
# Should show executable file
```

### Step 5: Start Go Search Service

```bash
# In Terminal 1
cd /home/kexi/SearchGram/searchgram-engine
./searchgram-engine

# OR with config path
CONFIG_PATH=/path/to/config.json ./searchgram-engine
```

**Expected Output:**
```
INFO[...] Elasticsearch engine initialized host=http://localhost:9200 index=telegram
INFO[...] Created index with CJK optimization index=telegram
INFO[...] Server starting on 127.0.0.1:8080
```

**✅ Verify:** Check that "Created index with CJK optimization" appears (means new mapping was applied)

### Step 6: Start Python Client (Indexing)

```bash
# In Terminal 2
cd /home/kexi/SearchGram
python searchgram/client.py
```

**Expected Output:**
```
INFO:root:Successfully connected to search service with HTTP/2 🚀
INFO:root:Starting history synchronization...
```

### Step 7: Start Python Bot (Search Interface)

```bash
# In Terminal 3
cd /home/kexi/SearchGram
python searchgram/bot.py
```

**Expected Output:**
```
INFO:root:Bot started successfully
INFO:root:Bot mode: [your mode]
```

### Step 8: Initial Verification

**Test 1: Send a test message in Telegram**
- Send "Hello world test message" in any chat
- Check client logs for: `INFO:root:Adding new message: [chat_id]-[message_id]`

**Test 2: Verify in Elasticsearch**
```bash
curl -X GET "localhost:9200/telegram/_search?pretty&size=1" \
  -H 'Content-Type: application/json' \
  -d '{"sort": [{"timestamp": "desc"}]}'
```

**Expected Fields in Response:**
```json
{
  "_source": {
    "id": "123-456",
    "chat_id": 123,
    "chat_type": "SUPERGROUP",
    "sender_type": "user",
    "sender_id": 789,
    "sender_name": "John Doe",
    "sender_username": "johndoe",
    "sender_first_name": "John",
    "sender_last_name": "Doe",
    "content_type": "text",
    "text": "Hello world test message",
    "is_forwarded": false,
    "chat": {...},
    "from_user": {...},
    "raw_message": {...}
  }
}
```

**✅ Critical Fields to Verify:**
- [x] `chat_id` (not nested)
- [x] `chat_type` (not nested)
- [x] `sender_type` (new field)
- [x] `sender_id` (new field)
- [x] `sender_name` (new field)
- [x] `content_type` (new field)
- [x] `raw_message` (contains full Pyrogram JSON)
- [x] `chat` (backward compat, nested)
- [x] `from_user` (backward compat, nested)

**Test 3: Search via bot**
```
/search test
```
**Expected:** Returns the message you just sent

---

## 🔍 Post-Deployment Testing

### Test Suite 1: Basic Search (5 minutes)

**1.1 Text Search**
```
/search hello
```
✅ Should return messages with "hello" in text or caption

**1.2 Exact Match**
```
/search "hello world"
```
✅ Should return messages with exact phrase

**1.3 Chat Type Filter**
```
/search -t=GROUP test
```
✅ Should return only group messages

**1.4 User Filter**
```
/search -u=yourusername test
```
✅ Should return only your messages

### Test Suite 2: Sender Types (10 minutes)

**2.1 User Sender (Normal)**
- Send message as yourself
- Search for it
- **Verify in ES:** `sender_type="user"`, `sender_id=[your_id]`

**2.2 Chat Sender (Anonymous Admin)**
- In a group, enable anonymous admins
- Send message as anonymous admin
- Search for it
- **Verify in ES:** `sender_type="chat"`, `sender_id=[chat_id]`, `sender_chat_title=[group_name]`

### Test Suite 3: Content Types (10 minutes)

**3.1 Text Message**
- Send text: "Test text message"
- **Verify in ES:** `content_type="text"`, `text="Test text message"`

**3.2 Photo with Caption**
- Send photo with caption: "Test photo"
- Search: `/search test`
- **Verify:** Message appears (caption search works)
- **Verify in ES:** `content_type="photo"`, `caption="Test photo"`

**3.3 Sticker**
- Send a sticker
- **Verify in ES:** `content_type="sticker"`, `sticker_emoji` and `sticker_set_name` are set

**3.4 Document**
- Send document with caption
- Search for caption text
- **Verify:** Document appears in results

### Test Suite 4: Forward Messages (5 minutes)

**4.1 Forward from User**
- Forward a message from another user
- **Verify in ES:** `is_forwarded=true`, `forward_from_type="user"`, `forward_from_id` is set

**4.2 Forward from Channel**
- Forward message from a channel
- **Verify in ES:** `is_forwarded=true`, `forward_from_type="chat"`, `forward_from_id=[channel_id]`

### Test Suite 5: Privacy & Access Control (5 minutes)

**5.1 Block User**
```
/block_me
```
✅ Should confirm opt-out

**5.2 Search While Blocked**
- Search for your messages
✅ Your messages should NOT appear

**5.3 Unblock**
```
/unblock_me
```
✅ Should confirm opt-in

**5.4 Search After Unblock**
- Search again
✅ Your messages should appear

### Test Suite 6: Admin Commands (5 minutes)

**6.1 Health Check**
```
/ping
```
✅ Should show:
- Search engine status
- Total messages
- Privacy stats
- Query logs
- Bot configuration

**6.2 Activity Stats**
```
/mystats
```
✅ Should show your activity in the group

**6.3 Stats with Mentions**
```
/mystats 30d at
```
✅ Should show activity + mention counts

### Test Suite 7: Performance (5 minutes)

**7.1 Batch Sync**
```
/sync -1001234567890
```
✅ Should start syncing chat
✅ Monitor logs for batch insert performance

**7.2 Search Performance**
- Search common keyword
- Check response time in bot
✅ Should be < 500ms

**7.3 Pagination**
- Search keyword with many results
- Click "Next" button repeatedly
✅ Should navigate smoothly without errors

---

## 🐛 Troubleshooting

### Issue 1: Index Creation Failed

**Error:** `failed to create index: [error details]`

**Solutions:**
1. Check Elasticsearch is running: `curl http://localhost:9200`
2. Delete old index: `curl -X DELETE "localhost:9200/telegram"`
3. Check Elasticsearch logs: `sudo journalctl -u elasticsearch -f`
4. Verify disk space: `df -h`

### Issue 2: No New Fields in Documents

**Symptom:** Documents don't have `sender_type`, `content_type`, etc.

**Solutions:**
1. Verify Go service restarted with new code
2. Check client logs for errors during indexing
3. Manually check one document:
   ```bash
   curl -X GET "localhost:9200/telegram/_search?size=1&pretty"
   ```
4. If still using old format, client may be using old code - rebuild

### Issue 3: Search Returns No Results

**Symptom:** Search queries return 0 results

**Solutions:**
1. Check documents are indexed:
   ```bash
   curl -X GET "localhost:9200/telegram/_count"
   ```
2. Check search query logs in Go service
3. Test direct Elasticsearch query:
   ```bash
   curl -X POST "localhost:9200/telegram/_search?pretty" \
     -H 'Content-Type: application/json' \
     -d '{"query": {"match_all": {}}}'
   ```
4. Verify privacy filter not blocking all results

### Issue 4: Text/Caption Search Not Working

**Symptom:** Can't find messages by caption text

**Solutions:**
1. Verify the fix was applied (search query should include caption field)
2. Check Elasticsearch mapping has `caption` field:
   ```bash
   curl -X GET "localhost:9200/telegram/_mapping?pretty"
   ```
3. Re-index messages if needed

### Issue 5: Backward Compatibility Broken

**Symptom:** Old functionality stopped working

**Solutions:**
1. Check old fields are still populated (`chat`, `from_user`)
2. Verify dual-field queries in search logic
3. Check logs for query errors
4. Test with old-style query manually

---

## 📊 Health Monitoring

### Key Metrics to Track

**1. Index Size**
```bash
curl -X GET "localhost:9200/_cat/indices/telegram?v"
```
Expected: +20-30% larger than before (due to raw_message)

**2. Search Performance**
- Monitor bot response times
- Check logs for slow queries (> 500ms)
- Watch Elasticsearch CPU/memory usage

**3. Error Rates**
```bash
# Check Go service logs
tail -f searchgram-engine/logs.txt | grep ERROR

# Check Python logs
tail -f client.log | grep ERROR
```

**4. Index Health**
```bash
curl -X GET "localhost:9200/_cluster/health?pretty"
```
Expected: `"status": "green"` or `"yellow"`

---

## ✅ Deployment Success Criteria

All of these must be TRUE before considering deployment successful:

- [ ] Go service starts without errors
- [ ] New index created with correct mapping
- [ ] Python services connect successfully
- [ ] Test messages indexed correctly
- [ ] All new fields present in documents
- [ ] `raw_message` field populated
- [ ] Backward compatibility fields present (`chat`, `from_user`)
- [ ] Text search works (searches both text and caption)
- [ ] Chat type filtering works
- [ ] Sender filtering works (user and chat senders)
- [ ] Privacy commands work (`/block_me`)
- [ ] Admin commands work (`/ping`, `/mystats`)
- [ ] Forward messages detected correctly
- [ ] Different content types detected (text, photo, sticker, etc.)
- [ ] Search performance acceptable (< 500ms)
- [ ] No errors in logs during normal operation

---

## 🔄 Rollback Plan (If Something Goes Wrong)

If you encounter critical issues and need to rollback:

### Option 1: Restore from Backup (if you created one)

```bash
# Delete new index
curl -X DELETE "localhost:9200/telegram"

# Restore snapshot
curl -X POST "localhost:9200/_snapshot/my_backup/snapshot_1/_restore?wait_for_completion=true"
```

### Option 2: Rebuild with Old Code

```bash
# Stop services
pkill -f searchgram

# Git revert changes (if using git)
git revert HEAD

# Or manually restore old files
# Delete new index
curl -X DELETE "localhost:9200/telegram"

# Rebuild and restart with old code
cd searchgram-engine && go build
./searchgram-engine &
python searchgram/client.py &
python searchgram/bot.py &
```

---

## 📝 Notes

1. **Re-indexing:** All messages will need to be re-indexed from scratch. Use `/sync` command for important chats.

2. **Performance:** Initial sync may take time depending on number of messages. Be patient.

3. **Monitoring:** Watch logs closely for the first 24 hours after deployment.

4. **Privacy:** Privacy settings (blocked users) are preserved in `privacy_data.json`.

5. **Query Logs:** Query logs will start fresh (old logs in SQLite database remain).

6. **Backward Compatibility:** If you need to revert, old code will still work with new index via backward compat fields.

---

## 🎯 Post-Deployment Checklist (After 24 Hours)

- [ ] No critical errors in logs
- [ ] Search performance stable (< 500ms average)
- [ ] Index size stable (not growing unexpectedly)
- [ ] All features working as expected
- [ ] Users haven't reported issues
- [ ] Can proceed with normal operation

---

## 📞 Support

If you encounter issues not covered here:

1. Check logs: `searchgram-engine` logs and Python logs
2. Review `TESTING_GUIDE.md` for detailed test cases
3. Check `REFACTORING_SUMMARY.md` for implementation details
4. Consult `CLAUDE.md` for architecture information

**Remember:** This is a significant change. Take your time, test thoroughly, and don't hesitate to rollback if needed!
