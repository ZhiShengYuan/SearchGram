# Rate Limiting for Telegram Message Fetching

## Problem

Telegram enforces rate limits on API requests. When fetching message history too aggressively, you'll encounter `FloodWait` errors:

```
FloodWait: sleeping for 60 seconds
```

This causes:
- ❌ Sync pauses for extended periods
- ❌ Inefficient stop-and-wait behavior
- ❌ Poor user experience during history sync

## Solution: Proactive Rate Limiting

Instead of waiting for Telegram to enforce limits (reactive), we proactively add delays between batch processing (proactive).

### Implementation

**Delay between batches** (`sync_manager.py`):

```python
# After processing each batch
if SYNC_DELAY_BETWEEN_BATCHES > 0:
    logging.debug(f"Sleeping {SYNC_DELAY_BETWEEN_BATCHES}s between batches")
    time.sleep(SYNC_DELAY_BETWEEN_BATCHES)
```

This applies to **both batch insert and individual insert modes**.

### Configuration

Add to `config.json`:

```json
{
  "sync": {
    "batch_size": 100,
    "delay_between_batches": 1.0
  }
}
```

**Options:**

- **`delay_between_batches`** (float, default: `1.0`): Seconds to wait between processing batches
  - `0.0` = No delay (aggressive, may trigger FloodWait)
  - `0.5` = Fast sync, moderate risk of FloodWait
  - `1.0` = Balanced (recommended)
  - `2.0` = Conservative, minimal FloodWait risk
  - Higher values = Slower sync but safer

## Rate Limiting Strategy

### Dual Protection

1. **Proactive Delay** (New):
   - Delays `1.0s` between batches
   - Prevents hitting rate limits
   - Smooth, predictable sync speed

2. **Reactive FloodWait Handling** (Existing):
   - Catches `FloodWait` exceptions
   - Waits for Telegram-specified duration
   - Retries the operation
   - Fallback when proactive delay isn't enough

### Example Sync Flow

**With 1 second delay between batches:**

```
Batch 1 (100 msgs) → 0.5s processing → 1.0s delay
Batch 2 (100 msgs) → 0.5s processing → 1.0s delay
Batch 3 (100 msgs) → 0.5s processing → 1.0s delay
...

Total time for 1000 messages:
- Processing: 10 batches × 0.5s = 5s
- Delays: 10 delays × 1.0s = 10s
- Total: ~15 seconds
- Rate: ~67 messages/second
```

**Without delay (aggressive):**

```
Batch 1 (100 msgs) → 0.5s processing
Batch 2 (100 msgs) → 0.5s processing
Batch 3 (100 msgs) → FloodWait 60s! ❌
Batch 4 (100 msgs) → 0.5s processing
Batch 5 (100 msgs) → FloodWait 120s! ❌
...

Total time for 1000 messages:
- Processing: 10 batches × 0.5s = 5s
- FloodWait penalties: 180s+
- Total: ~185+ seconds
- Rate: ~5 messages/second (much slower!)
```

## Performance Trade-offs

| Delay | Messages/sec | FloodWait Risk | Sync Time (10k msgs) |
|-------|--------------|----------------|---------------------|
| `0.0s` | ~200 | Very High ❌ | Variable (FloodWait) |
| `0.5s` | ~100 | Moderate ⚠️ | ~150 seconds |
| `1.0s` | ~67 | Low ✅ | ~225 seconds |
| `2.0s` | ~40 | Very Low ✅ | ~400 seconds |

**Recommendation**: Use `1.0s` for most cases. Adjust based on:
- **Larger chats** (100k+ messages): Increase to `2.0s`
- **Smaller chats** (1k messages): Can reduce to `0.5s`
- **Multiple chats syncing**: Increase to `1.5-2.0s`

## Logs

### Normal Operation (with delay)

```
INFO - Chat 123: 100/1000 (10%) - Batch: 100/100 indexed
DEBUG - Sleeping 1.0s between batches
INFO - Chat 123: 200/1000 (20%) - Batch: 100/100 indexed
DEBUG - Sleeping 1.0s between batches
INFO - Chat 123: 300/1000 (30%) - Batch: 100/100 indexed
```

### FloodWait Triggered (delay too low)

```
INFO - Chat 123: 100/1000 (10%) - Batch: 100/100 indexed
INFO - Chat 123: 200/1000 (20%) - Batch: 100/100 indexed
WARNING - FloodWait: sleeping for 60 seconds  ← Rate limit hit!
INFO - Chat 123: 300/1000 (30%) - Batch: 100/100 indexed
```

## Telegram Rate Limits

Telegram doesn't publish exact limits, but based on testing:

- **Message fetching**: ~100-200 messages per second (aggressive)
- **Safer rate**: ~50-100 messages per second (recommended)
- **FloodWait penalties**: 30-300 seconds depending on severity

Our implementation with `1.0s` delay achieves ~67 msgs/sec, well within safe limits.

## Tuning Guidelines

### If you see frequent FloodWait:

```json
{
  "sync": {
    "delay_between_batches": 2.0  // Increase delay
  }
}
```

### If sync is too slow and no FloodWait:

```json
{
  "sync": {
    "delay_between_batches": 0.5  // Decrease delay
  }
}
```

### For maximum speed (risky):

```json
{
  "sync": {
    "delay_between_batches": 0.0  // No delay, expect FloodWait
  }
}
```

## Integration with Batch Insert

Rate limiting works seamlessly with batch insert:

1. **Fetch 100 messages** from Telegram (subject to rate limit)
2. **Batch insert** to search engine (fast, HTTP/2)
3. **Wait 1 second** (rate limiting delay)
4. **Repeat**

The delay is applied **after inserting to database**, so the database insertion doesn't slow down the sync - only Telegram fetching is rate-limited.

## Real-time Messages

Real-time message indexing is **not affected** by this delay. The rate limiting only applies to:
- History sync (`sync_manager.py`)
- Bulk message fetching

Real-time messages use the buffered engine with its own batching (time + size based), independent of Telegram rate limits.

## Summary

✅ **Proactive rate limiting added**:
- 1 second delay between batches (configurable)
- Prevents FloodWait before it happens
- Smooth, predictable sync speed
- Works with both batch and individual insert modes

✅ **Reactive FloodWait handling preserved**:
- Catches FloodWait exceptions
- Waits and retries automatically
- Fallback protection

✅ **Configurable trade-off**:
- Faster sync = Higher FloodWait risk
- Slower sync = Lower FloodWait risk
- Default `1.0s` = Good balance

✅ **No impact on real-time indexing**:
- Only affects history sync
- Real-time messages use buffered engine batching
