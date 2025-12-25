# SearchGram Group & Privacy Features - Design Document

## Overview

This document outlines the design and implementation of group support and privacy controls for SearchGram.

## Architecture Changes

### 1. Privacy Control System (`privacy.py`)

**Purpose**: Allow users to opt-out of search results to protect their privacy.

**Design Decisions:**
- **Storage**: JSON file-based storage for simplicity and portability
- **Thread Safety**: Uses threading.Lock for concurrent access
- **Persistence**: Atomic writes (temp file + rename) to prevent corruption
- **Filtering**: Applied at search time, not index time (allows reversibility)

**Key Features:**
- Users can block/unblock themselves anytime
- Blocked users filtered from all search results
- Persistent across restarts
- Thread-safe for concurrent requests

**Data Structure:**
```json
{
  "blocked_users": [123456789, 987654321],
  "last_updated": "2025-12-25T10:30:00",
  "version": "1.0"
}
```

### 2. Access Control System (`access_control.py`)

**Purpose**: Control who can use the bot with three-tier permission system.

**Access Modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `private` | Owner only (default) | Personal use, maximum privacy |
| `group` | Whitelisted groups + users | Team/community use with control |
| `public` | Anyone can use | Public service (not recommended) |

**Design Decisions:**
- **Decorator Pattern**: Easy to apply to handlers
- **Granular Control**: Separate decorators for general access vs owner-only
- **Group Whitelist**: Specific group IDs must be pre-configured
- **User Whitelist**: Additional users beyond owner
- **Silent Failure in Groups**: No error messages in groups to avoid spam

**Configuration:**
```python
BOT_MODE = "group"
ALLOWED_GROUPS = [-1001234567890, -1009876543210]
ALLOWED_USERS = [123456789, 987654321]
```

### 3. Bot Enhancements (`bot.py`)

**Changes:**
1. Replaced `@private_use` with `@require_access` and `@require_owner`
2. Added privacy commands: `/block_me`, `/unblock_me`, `/privacy_status`
3. Integrated privacy filtering into search results
4. Added requester info display for group searches
5. Enhanced help text with privacy information
6. Added processing time and stats to search results

**Search Flow:**
```
User Query → Parse Args → Database Search → Privacy Filter → Format Results → Display
```

**Group Features:**
- Shows who requested the search (name + username)
- Only displays requester info in group chats
- Privacy commands work for all users

### 4. Client Enhancements (`client.py`)

**Changes:**
1. Explicit bot message filtering with statistics
2. Logging of skipped messages
3. Performance statistics every 100 messages
4. Better debugging information

**Statistics Tracked:**
- Total messages indexed
- Total edits indexed
- Bot messages skipped (prevents circular indexing)
- Messages per minute throughput

### 5. Configuration Updates (`config.py`)

**New Environment Variables:**
- `BOT_MODE`: Access control mode
- `ALLOWED_GROUPS`: Comma-separated group IDs
- `ALLOWED_USERS`: Comma-separated user IDs
- `PRIVACY_STORAGE`: Path to privacy data file

## Security Considerations

### Privacy Protection
1. **User Control**: Users decide their own privacy, not admins
2. **Immediate Effect**: Blocking takes effect instantly (no cache issues)
3. **Reversible**: Users can always opt back in
4. **Transparent**: Clear messaging about what privacy means

### Access Control
1. **Whitelist Approach**: Only explicitly allowed groups/users can access
2. **Owner Supremacy**: Owner always has full access regardless of mode
3. **Silent in Groups**: Prevents unauthorized use disclosure
4. **No Public Default**: Defaults to most restrictive mode

### Anti-Circular Indexing
1. **Bot ID Filter**: Client explicitly skips messages from BOT_ID
2. **Early Return**: Checked before any processing
3. **Logged**: All skips are logged for debugging
4. **Statistics**: Tracked separately for monitoring

## Data Flow Diagrams

### Privacy Flow
```
User sends /block_me
    ↓
Bot receives command
    ↓
privacy_manager.block_user(user_id)
    ↓
Add to blocked_users set
    ↓
Save to JSON file
    ↓
Respond to user with confirmation
```

### Search Flow with Privacy
```
User sends search query
    ↓
Access control check (require_access)
    ↓
Parse search arguments
    ↓
Query search engine
    ↓
privacy_manager.filter_search_results()
    ↓
Remove messages from blocked users
    ↓
Format and display results
```

### Group Access Check
```
Message received
    ↓
Is user owner? → Yes → Allow
    ↓ No
Is mode private? → Yes → Deny
    ↓ No
Is mode public? → Yes → Allow
    ↓ No (must be group mode)
Is private chat? → Is user in ALLOWED_USERS? → Allow/Deny
    ↓ No (must be group)
Is group in ALLOWED_GROUPS? → Yes → Allow
    ↓ No
Deny (silent)
```

## Testing Strategy

### Unit Tests
- Privacy manager: block/unblock operations
- Access controller: permission checks for all modes
- Result filtering: ensure blocked users removed

### Integration Tests
- End-to-end search with privacy filtering
- Group access control scenarios
- Bot message skip verification

### Manual Tests
1. Create test group, add bot, verify access control
2. User A blocks themselves, user B searches, verify A's messages hidden
3. Bot sends messages, verify client doesn't index them
4. Test all three access modes
5. Test privacy commands from different users

## Performance Considerations

### Privacy Filtering
- **O(n)** where n = search results (typically 10)
- Set membership check is **O(1)**
- Minimal performance impact

### Access Control
- **O(1)** lookups for owner/user checks
- **O(1)** set membership for group checks
- Happens before search, so no wasted queries

### Storage
- JSON file: simple, portable, human-readable
- Could migrate to Redis for high-volume deployments
- Current implementation suitable for <10,000 users

## Future Enhancements

### Potential Features
1. **Per-Chat Privacy**: Block only specific chats, not all messages
2. **Temporary Blocks**: Time-limited privacy (e.g., block for 24 hours)
3. **Admin Override**: Allow group admins to manage privacy for their group
4. **Privacy Dashboard**: Web UI to manage privacy settings
5. **Redis Backend**: For high-performance deployments
6. **Audit Log**: Track privacy changes for compliance

### Scalability
1. Move privacy storage to Redis for faster lookups
2. Cache access control decisions
3. Implement search result caching with privacy-aware keys
4. Add rate limiting per user/group

## Migration Path

### For Existing Deployments
1. **No Breaking Changes**: Defaults to `private` mode (same as before)
2. **Backward Compatible**: Old behavior maintained with default config
3. **Opt-In**: Group mode must be explicitly enabled
4. **No Data Migration**: Privacy storage starts fresh

### Upgrade Steps
1. Pull latest code
2. Install dependencies (no new dependencies needed)
3. Optionally configure `BOT_MODE` and allowed groups/users
4. Restart bot and client
5. Users can start using privacy commands immediately

## Conclusion

The group support and privacy control features provide:
- **User Empowerment**: Users control their own privacy
- **Flexible Access**: Three modes for different use cases
- **Production Ready**: Thread-safe, persistent, tested
- **Performance**: Minimal overhead, scales well
- **Privacy First**: Respects user choices, transparent operation

These features transform SearchGram from a personal tool to a privacy-conscious group search solution while maintaining backward compatibility and security.
