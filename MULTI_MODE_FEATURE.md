# Multi-Mode Access Control & Group Search Filtering

## Overview

SearchGram now supports **multiple access control modes simultaneously** and **automatic group-specific search filtering** for enhanced security and flexibility.

## New Features

### 1. Multi-Mode Access Control

The bot can now operate in multiple modes at the same time:

**Configuration**:
```json
{
  "bot": {
    "mode": ["private", "group"],
    "allowed_groups": [-1001234567890],
    "allowed_users": [123456789, 987654321]
  }
}
```

**Available Modes**:
- `"private"` - Owner-only access
- `"group"` - Group whitelisting
- `"public"` - Public access (not recommended)

**Mode Combinations**:
| Configuration | Behavior |
|---------------|----------|
| `"private"` | Only owner can use the bot anywhere |
| `"group"` | Bot works in whitelisted groups; allowed_users in private chats |
| `["private", "group"]` | Owner + allowed_users in private; anyone in whitelisted groups |
| `"public"` | Anyone can use the bot anywhere |

### 2. Group-Specific Search Filtering

**Problem Solved**: Previously, searching in a group would return results from ALL indexed chats, potentially leaking private messages.

**New Behavior**:
- **Group searches** → Automatically filtered to show only messages from that specific group
- **Private searches** → Still return results from all indexed chats (full access)

**Implementation**:
The bot automatically detects the chat type and applies `chat_id` filter:
```python
# Automatically applied when searching in groups
if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
    results = search(keyword, chat_id=message.chat.id)
```

## Use Cases

### Use Case 1: Personal Bot + Team Groups

**Scenario**: You want to use SearchGram privately for your own messages, but also enable it for your work team in specific groups.

**Configuration**:
```json
{
  "bot": {
    "mode": ["private", "group"],
    "allowed_groups": [-1001234567890, -1009876543210],
    "allowed_users": []
  }
}
```

**Result**:
- You (owner) can search privately → sees all your indexed messages
- Team members search in work groups → only see messages from their specific group
- No cross-group message leakage

### Use Case 2: Multiple Group Bot with Delegate Access

**Scenario**: Bot operates in several groups, and you want specific trusted users to have private access too.

**Configuration**:
```json
{
  "bot": {
    "mode": ["private", "group"],
    "allowed_groups": [-1001111111111, -1002222222222],
    "allowed_users": [123456789, 987654321]
  }
}
```

**Result**:
- Owner + allowed_users can search privately → full access to all indexed messages
- Group members search in their groups → scoped to that group only
- Different groups can't see each other's messages

### Use Case 3: Group-Only Bot (No Private Access)

**Scenario**: You want the bot to work ONLY in groups, not in private chats (except for owner).

**Configuration**:
```json
{
  "bot": {
    "mode": "group",
    "allowed_groups": [-1001234567890],
    "allowed_users": []
  }
}
```

**Result**:
- Owner can use privately (owner always has access)
- Group members can only use in whitelisted groups
- No one else can use the bot in private chats
- Group searches are scoped to that group

## Security Benefits

### 1. Privacy Protection

**Before**:
- Group A member searches in Group A → sees messages from Groups A, B, C, private chats
- **PRIVACY LEAK!**

**After**:
- Group A member searches in Group A → sees only messages from Group A
- **Privacy protected!**

### 2. Flexible Access Control

**Before**:
- Single mode only: Either private OR group OR public
- No granular control

**After**:
- Multiple modes: private + group simultaneously
- Fine-grained control with allowed_users and allowed_groups
- Different access levels for different contexts

### 3. Group Isolation

Each group operates independently:
- Group members can't access other groups' messages
- Private searches (owner/allowed_users) still have full access
- Perfect for multi-team environments

## Implementation Details

### Changes Made

1. **config_loader.py** (`searchgram/config_loader.py:231-236`)
   - Added support for array-based mode configuration
   - Backward compatible with string mode

2. **access_control.py** (`searchgram/access_control.py:31-107`)
   - Updated `AccessController` to handle multiple modes
   - New logic for multi-mode access checking
   - Maintains backward compatibility

3. **engine.py** (`searchgram/engine.py:58`)
   - Added `chat_id` parameter to `search()` method signature
   - Optional parameter for group-specific filtering

4. **http_engine.py** (`searchgram/http_engine.py:196-231`)
   - Added `chat_id` parameter to search implementation
   - Passes chat_id to Go search service

5. **bot.py** (`searchgram/bot.py:253-399`)
   - Updated `parse_and_search()` to accept `chat_id`
   - Auto-detects group chats and applies filter
   - Applied to all search handlers (text, slash commands, pagination)

### API Changes

**Search Method Signature**:
```python
# Before
def search(keyword, _type=None, user=None, page=1, mode=None)

# After
def search(keyword, _type=None, user=None, page=1, mode=None, chat_id=None)
```

**HTTP API Payload**:
```json
{
  "keyword": "search term",
  "page": 1,
  "page_size": 10,
  "exact_match": false,
  "chat_type": "GROUP",
  "username": "user123",
  "blocked_users": [123, 456],
  "chat_id": -1001234567890  // NEW: filters results to this chat
}
```

## Migration Guide

### From Single Mode to Multi-Mode

**Old Configuration**:
```json
{
  "bot": {
    "mode": "private"
  }
}
```

**New Configuration (Backward Compatible)**:
```json
{
  "bot": {
    "mode": "private"  // Still works!
  }
}
```

**Or use multi-mode**:
```json
{
  "bot": {
    "mode": ["private", "group"],
    "allowed_groups": [-1001234567890]
  }
}
```

### No Code Changes Required

- Existing configurations continue to work
- String mode automatically converted to single-element set
- Existing search calls work without modification
- `chat_id` parameter is optional (defaults to `None`)

## Testing

### Manual Testing Steps

1. **Test Multi-Mode Access**:
   ```bash
   # Set config
   "mode": ["private", "group"]

   # Test private access (owner)
   # Test private access (allowed_user)
   # Test group access (any member)
   # Test unauthorized access (should fail)
   ```

2. **Test Group Filtering**:
   ```bash
   # Index messages in Group A and Group B
   # Search in Group A → should only see Group A messages
   # Search in Group B → should only see Group B messages
   # Search privately → should see all messages
   ```

3. **Test Pagination**:
   ```bash
   # Search in group with multiple pages
   # Click "Next Page" button
   # Verify results still filtered to same group
   ```

### Automated Testing

```python
# Test access control
from searchgram.access_control import AccessController

config = {"mode": ["private", "group"]}
ac = AccessController()
assert ac.modes == {"private", "group"}

# Test search filtering
from searchgram.http_engine import HTTPSearchEngine

engine = HTTPSearchEngine("http://localhost:8080")
results = engine.search("keyword", chat_id=-1001234567890)
# Verify all results are from chat_id -1001234567890
```

## Go Service Support

The Go search service must support the `chat_id` parameter in the search API.

**Required API Update** (`searchgram-engine`):
```go
type SearchRequest struct {
    Keyword      string `json:"keyword"`
    Page         int    `json:"page"`
    PageSize     int    `json:"page_size"`
    ExactMatch   bool   `json:"exact_match"`
    ChatType     string `json:"chat_type,omitempty"`
    Username     string `json:"username,omitempty"`
    BlockedUsers []int  `json:"blocked_users,omitempty"`
    ChatID       int64  `json:"chat_id,omitempty"`  // NEW
}
```

**Elasticsearch Query**:
```go
if req.ChatID != 0 {
    must = append(must, map[string]interface{}{
        "term": map[string]interface{}{
            "chat.id": req.ChatID,
        },
    })
}
```

## Troubleshooting

### Issue: Group searches still showing all messages

**Cause**: Go service doesn't support `chat_id` filter yet

**Solution**: Update Go service to handle `chat_id` parameter in search API

### Issue: Access denied in group

**Cause**: Group not in `allowed_groups` list

**Solution**: Add group ID to config:
```json
"allowed_groups": [-1001234567890]
```

Get group ID by adding @userinfobot to the group.

### Issue: Multi-mode not working

**Cause**: Old config format

**Solution**: Update to array format:
```json
"mode": ["private", "group"]  // Not "private+group" or "private,group"
```

## Future Enhancements

Potential improvements for future versions:

1. **Per-Group Permissions**: Different allowed_users per group
2. **Search Scope Control**: Let users choose to search all chats or current chat
3. **Channel Support**: Extend filtering to channels
4. **Admin Override**: Let group admins bypass group filtering
5. **Search Statistics**: Track which groups are searched most

## References

- **Configuration**: See `CONFIG_REFERENCE.md` for full documentation
- **Access Control**: `searchgram/access_control.py`
- **Bot Logic**: `searchgram/bot.py`
- **Search Engine**: `searchgram/http_engine.py`
- **Go Service**: `searchgram-engine/` (requires update for chat_id support)

## Changelog

**Version**: 2.0.0 (Multi-Mode Release)

**Added**:
- Multi-mode access control (array-based mode configuration)
- Automatic group-specific search filtering
- `chat_id` parameter to search API
- Comprehensive documentation and examples

**Changed**:
- Access control logic to support multiple modes simultaneously
- Search handlers to auto-detect and filter group searches
- Configuration examples to show multi-mode usage

**Backward Compatibility**:
- ✅ Single string mode still supported
- ✅ Existing configurations work without changes
- ✅ Optional `chat_id` parameter (defaults to None)

---

**Ready to use!** Update your `config.json` and enjoy enhanced privacy and flexibility.
