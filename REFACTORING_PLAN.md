# SearchGram Refactoring Plan: Full JSON Indexing

## Overview

This document outlines the refactoring of SearchGram's indexing and search system to support full JSON message storage with normalized fields for efficient searching.

## Goals

1. **Index full Pyrogram message JSON** - Store complete message data for future flexibility
2. **Add normalized search fields** - Extract key fields for fast filtering
3. **Improve sender search** - Support searching by both user and chat senders
4. **Maintain backward compatibility** - Existing search queries should continue working
5. **All filtering on search engine side** - No client-side filtering (performance)

## Current vs New Structure

### Current Structure (Flat)
```json
{
  "id": "123-456",
  "message_id": 456,
  "text": "Hello",
  "chat": {"id": 123, "type": "GROUP", "title": "My Group"},
  "from_user": {"id": 789, "first_name": "John", "username": "john"},
  "timestamp": 1672531200,
  "entities": [],
  "is_deleted": false
}
```

### New Structure (Hybrid: Normalized + Full JSON)
```json
{
  // Core identifiers
  "id": "123-456",
  "message_id": 456,
  "chat_id": 123,
  "timestamp": 1672531200,

  // Chat info (searchable)
  "chat_type": "SUPERGROUP",
  "chat_title": "My Group",
  "chat_username": "mygroup",

  // Sender info (normalized, searchable)
  "sender_type": "user",
  "sender_id": 789,
  "sender_name": "John Doe",
  "sender_username": "john",
  "sender_first_name": "John",
  "sender_last_name": "Doe",
  "sender_chat_title": null,

  // Forward info
  "is_forwarded": false,
  "forward_from_type": null,
  "forward_from_id": null,
  "forward_from_name": null,
  "forward_timestamp": null,

  // Content info
  "content_type": "text",
  "text": "Hello",
  "caption": null,
  "sticker_emoji": null,
  "sticker_set_name": null,

  // Entities (unchanged)
  "entities": [],

  // Soft-delete (unchanged)
  "is_deleted": false,
  "deleted_at": 0,

  // Full message (stored, not indexed)
  "raw_message": {
    "message": { /* full Pyrogram message */ },
    "normalized": { /* normalized fields */ }
  }
}
```

## Index Field Design

### 1. Core Fields (Indexed, Required)
- `id` (keyword) - Composite: `{chat_id}-{message_id}`
- `message_id` (long) - Original message ID
- `chat_id` (long) - Chat ID (for filtering)
- `timestamp` (long) - Unix timestamp (for sorting)

### 2. Chat Fields (Indexed)
- `chat_type` (keyword) - PRIVATE, GROUP, SUPERGROUP, CHANNEL, BOT
- `chat_title` (text, CJK analyzer) - Chat title
- `chat_username` (keyword) - Chat username

### 3. Sender Fields (Indexed, NEW!)
- `sender_type` (keyword) - "user" or "chat"
- `sender_id` (long) - User ID or sender chat ID
- `sender_name` (text, CJK analyzer) - Combined first + last name or chat title
- `sender_username` (keyword) - Username (user or chat)
- `sender_first_name` (text, CJK analyzer) - First name (user only)
- `sender_last_name` (text, CJK analyzer) - Last name (user only)
- `sender_chat_title` (text, CJK analyzer) - Chat title (chat sender only)

### 4. Forward Fields (Indexed, NEW!)
- `is_forwarded` (boolean)
- `forward_from_type` (keyword) - "user", "chat", "name_only"
- `forward_from_id` (long) - Forwarded from user/chat ID
- `forward_from_name` (text) - Forwarded from name
- `forward_timestamp` (long) - Forward date

### 5. Content Fields (Indexed, NEW!)
- `content_type` (keyword) - "text", "sticker", "photo", "video", "document", "other"
- `text` (text, CJK analyzer + exact) - Message text
- `caption` (text, CJK analyzer) - Media caption
- `sticker_emoji` (keyword) - Sticker emoji
- `sticker_set_name` (keyword) - Sticker set name

### 6. Entity Fields (Nested, Unchanged)
- `entities` (nested array)
  - `type` (keyword)
  - `offset` (integer)
  - `length` (integer)
  - `user_id` (long)

### 7. Soft-Delete Fields (Indexed, Unchanged)
- `is_deleted` (boolean)
- `deleted_at` (long)

### 8. Raw Message Field (Stored, NOT Indexed)
- `raw_message` (object, enabled=false) - Full Pyrogram message JSON

## Search Query Mappings

### User Requirement → Elasticsearch Query

| User Search | Field(s) Used | Query Type |
|-------------|---------------|------------|
| `sender_chat.id` | `sender_id` + filter `sender_type="chat"` | Term |
| `sender_chat.username` | `sender_username` + filter `sender_type="chat"` | Term |
| `sender_chat.title` | `sender_chat_title` | Match |
| `from_user.id` | `sender_id` + filter `sender_type="user"` | Term |
| `from_user.username` | `sender_username` + filter `sender_type="user"` | Term |
| `from_user.first_name` | `sender_first_name` | Match |
| `from_user.last_name` | `sender_last_name` | Match |
| `chat.id` | `chat_id` | Term |
| `text` | `text` + `caption` | Match/MatchPhrase |

## Message Normalization Logic

### Sender Resolution
```python
if message.from_user:
    sender_type = "user"
    sender_id = message.from_user.id
    sender_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    sender_username = message.from_user.username
    sender_first_name = message.from_user.first_name
    sender_last_name = message.from_user.last_name
    sender_chat_title = None
elif message.sender_chat:
    sender_type = "chat"
    sender_id = message.sender_chat.id
    sender_name = message.sender_chat.title
    sender_username = message.sender_chat.username
    sender_first_name = None
    sender_last_name = None
    sender_chat_title = message.sender_chat.title
else:
    # Service message
    sender_type = "unknown"
    sender_id = 0
```

### Forward Resolution
```python
is_forwarded = bool(message.forward_date or message.forward_sender_name or message.forward_from_chat)

if message.forward_from_chat:
    forward_from_type = "chat"
    forward_from_id = message.forward_from_chat.id
    forward_from_name = message.forward_from_chat.title
elif message.forward_from:
    forward_from_type = "user"
    forward_from_id = message.forward_from.id
    forward_from_name = f"{message.forward_from.first_name or ''} {message.forward_from.last_name or ''}".strip()
elif message.forward_sender_name:
    forward_from_type = "name_only"
    forward_from_id = None
    forward_from_name = message.forward_sender_name
```

### Content Type Resolution
```python
if message.text:
    content_type = "text"
    text = message.text
    caption = None
elif message.sticker:
    content_type = "sticker"
    text = None
    caption = None
    sticker_emoji = message.sticker.emoji
    sticker_set_name = message.sticker.set_name
elif message.photo:
    content_type = "photo"
    text = None
    caption = message.caption
elif message.video:
    content_type = "video"
    text = None
    caption = message.caption
elif message.document:
    content_type = "document"
    text = None
    caption = message.caption
else:
    content_type = "other"
```

## Implementation Tasks

### Phase 1: Backend (Go Service)
- [ ] Update `models/message.go` to include new fields
- [ ] Update Elasticsearch mapping in `engines/elasticsearch.go`
- [ ] Add `raw_message` field (stored, not indexed)
- [ ] Update search queries to use new sender fields
- [ ] Ensure backward compatibility (keep old `from_user` field for now)

### Phase 2: Frontend (Python Client)
- [ ] Create `message_converter.py` with normalization logic
- [ ] Update `http_engine.py` to use new converter
- [ ] Convert full Pyrogram message to template format
- [ ] Extract normalized fields
- [ ] Test with sample messages

### Phase 3: Testing
- [ ] Test text search (fuzzy/exact)
- [ ] Test sender filtering (user and chat)
- [ ] Test chat type filtering
- [ ] Test privacy filtering (blocked users)
- [ ] Test soft-delete filtering
- [ ] Test user stats (verify mention counts)
- [ ] Test dedup operation
- [ ] Test delete operations

### Phase 4: Migration (Optional)
- [ ] Create migration script to reindex existing data
- [ ] Preserve old index as backup
- [ ] Migrate documents in batches
- [ ] Verify migrated data

## Backward Compatibility Strategy

To ensure smooth transition:

1. **Keep old fields temporarily**: `from_user`, `chat` nested objects
2. **Dual field population**: Populate both old and new fields during transition
3. **Update search logic incrementally**: Switch to new fields one query at a time
4. **Deprecation timeline**: Mark old fields deprecated after 1 month, remove after 3 months

## Benefits

1. **Full message preservation**: Complete message data available for future features
2. **Improved sender search**: Can search by user or chat sender efficiently
3. **Better forward support**: Can filter/search forwarded messages
4. **Content type filtering**: Can filter by message type (text, sticker, media)
5. **Future-proof**: New Telegram features can be added to `raw_message` without schema changes
6. **Performance**: All filtering happens in Elasticsearch (no Python post-processing)

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Index size increase (raw_message) | Store raw_message compressed, monitor disk usage |
| Breaking existing queries | Maintain old fields during transition, comprehensive testing |
| Migration downtime | Use index aliases, migrate in background |
| Complex normalization logic | Unit tests for all edge cases, handle None values |

## Timeline

- **Phase 1 (Backend)**: 2-3 days
- **Phase 2 (Frontend)**: 1-2 days
- **Phase 3 (Testing)**: 1-2 days
- **Phase 4 (Migration)**: Optional, 1-2 days

**Total**: 4-9 days
