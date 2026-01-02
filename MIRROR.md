# Channel Mirroring - SearchGram

## Overview

The **Channel Mirroring** feature allows automatic replication of messages from source channels to target channels with optional processing:

- **Content filtering** via whitelist/blacklist keywords or regex patterns
- **LLM-based processing** for text rewriting, content categorization, or smart filtering
- **Media support** with automatic download and re-upload (images, videos, documents)
- **Large file support** via local Telegram Bot API server
- **HTTP-based architecture** ensuring clean separation between userbot and bot

## Architecture

```
Source Channel → Userbot (downloads & monitors)
                     ↓
                 HTTP API (file as base64 JSON)
                     ↓
                 Bot (processes & uploads)
                     ↓
              Target Channel
```

### Components

1. **Userbot (client.py)**:
   - Monitors source channels for new messages
   - Downloads media files via Pyrogram
   - Sends content to bot via HTTP API

2. **Bot (bot.py)**:
   - Receives messages from userbot via HTTP
   - Applies keyword filters (whitelist/blacklist)
   - Processes text with LLM (optional)
   - Uploads to target channel (Pyrogram or local Bot API)

3. **HTTP Communication**:
   - All data exchanged via RESTful HTTP with JWT authentication
   - Files transferred as base64-encoded JSON
   - No shared file system required

## Configuration

### Basic Setup

Add mirror configuration to `config.json`:

```json
{
  "mirror": {
    "enabled": true,
    "tasks": [
      {
        "id": "crypto_news",
        "source_channel": -1001234567890,
        "target_channel": -1009876543210,
        "mirror_media": true,
        "mirror_text": true,
        "forward_mode": false,
        "llm_enabled": false,
        "keyword_whitelist": [],
        "keyword_blacklist": []
      }
    ]
  }
}
```

### LLM Configuration

Configure OpenAI-compatible API endpoint in `services.llm`:

```json
{
  "services": {
    "llm": {
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-your_api_key_here",
      "model": "gpt-3.5-turbo",
      "timeout": 30
    }
  }
}
```

**Supported LLM providers:**
- OpenAI (ChatGPT)
- Anthropic Claude (via OpenAI-compatible proxy)
- Any OpenAI-compatible endpoint (Ollama, LocalAI, etc.)

### Local Bot API (Optional)

For large file uploads (>50MB):

```json
{
  "services": {
    "local_bot_api": {
      "base_url": "http://localhost:8081/bot{token}"
    }
  }
}
```

**Setup Local Bot API:**
1. Download: https://github.com/tdlib/telegram-bot-api
2. Build and run: `telegram-bot-api --local --api-id=YOUR_API_ID --api-hash=YOUR_API_HASH`
3. Configure endpoint in `config.json`

**Note**: If not configured, SearchGram falls back to standard Pyrogram (50MB limit).

## Mirror Task Configuration

### Task Fields

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `id` | string | Unique task identifier | **Required** |
| `source_channel` | int | Source channel ID | **Required** |
| `target_channel` | int | Target channel ID | **Required** |
| `mirror_media` | bool | Mirror images/videos | `true` |
| `mirror_text` | bool | Mirror text messages | `true` |
| `forward_mode` | bool | Forward (true) or copy (false) | `false` |
| `llm_enabled` | bool | Enable LLM processing | `false` |
| `llm_mode` | string | LLM mode (see below) | `"rewrite"` |
| `llm_temperature` | float | LLM temperature (0.0-1.0) | `0.7` |
| `llm_max_tokens` | int | Max tokens in response | `null` |
| `llm_custom_prompt` | string | Custom LLM prompt | `null` |
| `keyword_whitelist` | array | Required keywords (allow only if matched) | `[]` |
| `keyword_blacklist` | array | Blocked keywords (block if matched) | `[]` |
| `keyword_case_sensitive` | bool | Case-sensitive keyword matching | `false` |
| `keyword_use_regex` | bool | Use regex patterns | `false` |

### LLM Modes

#### 1. Rewrite Mode (`"rewrite"`)
Transforms text while preserving meaning.

**Example:**
- **Input**: "Bitcoin price jumped 10% today!"
- **Output**: "BTC saw a significant 10% surge in value today."

**Configuration:**
```json
{
  "llm_enabled": true,
  "llm_mode": "rewrite",
  "llm_temperature": 0.7
}
```

#### 2. Filter Mode (`"filter"`)
Decides whether to mirror message based on content.

**Example:**
- **Input**: "Free money! Click here now!!!"
- **Output**: Blocked (LLM detects spam)

**Configuration:**
```json
{
  "llm_enabled": true,
  "llm_mode": "filter",
  "llm_temperature": 0.3
}
```

#### 3. Categorize Mode (`"categorize"`)
Adds hashtags or categories to content.

**Example:**
- **Input**: "New Ethereum upgrade announced."
- **Output**: "New Ethereum upgrade announced. #crypto #ethereum #news"

**Configuration:**
```json
{
  "llm_enabled": true,
  "llm_mode": "categorize",
  "llm_temperature": 0.5
}
```

#### 4. Disabled (`"disabled"`)
No LLM processing (default).

### Keyword Filtering

#### Whitelist (Include Only)
Only mirror messages containing specified keywords.

```json
{
  "keyword_whitelist": ["bitcoin", "ethereum", "crypto"]
}
```

**Behavior**: Blocks all messages **except** those containing whitelisted keywords.

#### Blacklist (Exclude)
Block messages containing specified keywords.

```json
{
  "keyword_blacklist": ["scam", "spam", "ponzi"]
}
```

**Behavior**: Allows all messages **except** those containing blacklisted keywords.

#### Combined Filtering
Use both whitelist and blacklist together:

```json
{
  "keyword_whitelist": ["bitcoin", "ethereum"],
  "keyword_blacklist": ["scam", "ponzi"]
}
```

**Filter Logic:**
1. **Blacklist check first** (highest priority): Block if any blacklist keyword matches
2. **Whitelist check**: Require at least one whitelist keyword (if configured)
3. **No filters**: Allow all messages

#### Regex Patterns
Use regular expressions for advanced matching:

```json
{
  "keyword_whitelist": ["\\d{4}-\\d{2}-\\d{2}", "USD?\\$\\d+"],
  "keyword_use_regex": true
}
```

**Examples:**
- `\d{4}-\d{2}-\d{2}` - Match dates (2025-01-02)
- `USD?\$\d+` - Match prices ($499, US$1000)
- `@\w+` - Match mentions

## Usage Examples

### Example 1: Basic Mirroring (No Filters)

Mirror all content from crypto news channel:

```json
{
  "id": "crypto_mirror",
  "source_channel": -1001234567890,
  "target_channel": -1009876543210,
  "mirror_media": true,
  "mirror_text": true
}
```

### Example 2: Keyword-Filtered Mirror

Mirror only Bitcoin-related news, exclude scams:

```json
{
  "id": "bitcoin_news",
  "source_channel": -1001234567890,
  "target_channel": -1009876543210,
  "mirror_media": true,
  "mirror_text": true,
  "keyword_whitelist": ["bitcoin", "btc"],
  "keyword_blacklist": ["scam", "ponzi", "free money"]
}
```

### Example 3: LLM Rewrite + Filters

Rewrite crypto news in simpler language:

```json
{
  "id": "crypto_simplified",
  "source_channel": -1001234567890,
  "target_channel": -1009876543210,
  "mirror_media": true,
  "mirror_text": true,
  "llm_enabled": true,
  "llm_mode": "rewrite",
  "llm_temperature": 0.7,
  "llm_custom_prompt": "Rewrite the following crypto news in simple, beginner-friendly language:\n\n{text}",
  "keyword_whitelist": ["crypto", "bitcoin", "ethereum"]
}
```

### Example 4: Smart Content Filter

Use LLM to filter spam and low-quality content:

```json
{
  "id": "quality_filter",
  "source_channel": -1001234567890,
  "target_channel": -1009876543210,
  "mirror_media": false,
  "mirror_text": true,
  "llm_enabled": true,
  "llm_mode": "filter",
  "llm_temperature": 0.3,
  "llm_custom_prompt": "Analyze this message. If it's spam, low-quality, or misleading, respond 'BLOCK'. Otherwise respond 'ALLOW':\n\n{text}"
}
```

### Example 5: Auto-Categorization

Add hashtags to news articles:

```json
{
  "id": "auto_tags",
  "source_channel": -1001234567890,
  "target_channel": -1009876543210,
  "mirror_media": true,
  "mirror_text": true,
  "llm_enabled": true,
  "llm_mode": "categorize",
  "llm_temperature": 0.5
}
```

## Bot Commands (Owner Only)

### `/mirror_status`
View all mirror tasks and their statistics.

**Output:**
```
🔄 Mirror Tasks Status

Task: crypto_news
├─ Source: -1001234567890
├─ Target: -1009876543210
├─ Status: active
├─ Processed: 1,234
├─ Mirrored: 987
├─ Filtered: 247
└─ Failed: 0

Task: bitcoin_news
├─ Source: -1001111111111
├─ Target: -1002222222222
├─ Status: paused
├─ Processed: 567
├─ Mirrored: 456
├─ Filtered: 111
└─ Failed: 0

Overall Statistics:
📊 Total Tasks: 2
✅ Active: 1
⏸️ Paused: 1
📈 Total Processed: 1,801
🎯 Total Mirrored: 1,443
🚫 Total Filtered: 358
❌ Total Failed: 0
```

### `/mirror_pause <task_id>`
Pause a running mirror task.

**Usage:**
```
/mirror_pause crypto_news
```

**Output:**
```
⏸️ Mirror task 'crypto_news' paused.
```

### `/mirror_resume <task_id>`
Resume a paused mirror task.

**Usage:**
```
/mirror_resume crypto_news
```

**Output:**
```
▶️ Mirror task 'crypto_news' resumed.
```

### `/mirror_logs [limit] [task_id]`
View recent mirror operation logs.

**Usage:**
```
/mirror_logs                  # Last 20 logs (all tasks)
/mirror_logs 50               # Last 50 logs (all tasks)
/mirror_logs 20 crypto_news   # Last 20 logs for specific task
```

**Output:**
```
📋 Mirror Logs (Last 20)

2025-01-02 14:30:15
Task: crypto_news
Source: -1001234567890/12345
Target: -1009876543210/67890
Action: rewritten
Status: success
Time: 1,234ms
Media: photo

2025-01-02 14:29:42
Task: crypto_news
Source: -1001234567890/12344
Action: filtered_keyword
Status: skipped
Reason: keyword_blacklist
```

## Database Logging

All mirror operations are logged to SQLite database (`searchgram_logs.db`):

**Mirror Logs Table:**
- Task ID, source/target message IDs
- Media type and text length
- LLM actions and keyword matches
- Processing time and status
- Error messages (if failed)

**Query Statistics:**
```python
from searchgram.db_manager import get_db_manager

db = get_db_manager()

# Get statistics for all tasks
stats = db.get_mirror_statistics()
print(f"Success rate: {stats['success_rate']}%")
print(f"Average processing time: {stats['average_processing_time_ms']}ms")

# Get statistics for specific task
task_stats = db.get_mirror_statistics(task_id="crypto_news")

# Get recent logs
logs = db.get_recent_mirror_logs(limit=100, task_id="crypto_news")
```

## Performance & Optimization

### File Transfer Optimization

- **Small files (<10MB)**: Standard Pyrogram upload (MTProto)
- **Large files (>50MB)**: Local Bot API server (if configured)
- **Very large files (>2GB)**: Not supported by Telegram

### Rate Limiting

Telegram rate limits:
- **User accounts**: ~30 messages/second
- **Bot accounts**: ~20 messages/second

**Recommendations:**
- Use `delay_between_batches` in sync config to avoid FloodWait
- Monitor logs for rate limit errors
- Consider batching if mirroring high-volume channels

### LLM Cost Optimization

- Use **temperature 0.3-0.5** for filter mode (deterministic)
- Use **temperature 0.7-0.9** for rewrite mode (creative)
- Set `llm_max_tokens` to limit response length
- Cache LLM results if needed (not implemented by default)

### Memory Usage

- Files are processed in-memory (BytesIO)
- Large files (>100MB) may consume significant RAM
- Monitor memory usage with high-volume mirroring

## Troubleshooting

### Mirror not working

**Check:**
1. `mirror.enabled = true` in config
2. Bot and userbot are running
3. JWT authentication configured correctly
4. Source/target channel IDs are correct
5. Bot has admin access to target channel

**Logs:**
```bash
# Check userbot logs
grep "MirrorManager" client.log

# Check bot logs
grep "mirror_api" bot.log
```

### LLM errors

**Common issues:**
1. Invalid API key (`401 Unauthorized`)
2. Rate limiting (`429 Too Many Requests`)
3. Invalid model name
4. Timeout errors

**Solutions:**
- Verify API key in `services.llm.api_key`
- Check rate limits on LLM provider
- Increase `services.llm.timeout`
- Use fallback: disable LLM and use keyword filters

### File upload failures

**Issues:**
1. File too large (>2GB Telegram limit)
2. Invalid media type
3. Network errors

**Solutions:**
- Check file size before mirroring
- Verify media type is supported
- Use local Bot API for large files
- Check network connectivity

### Keyword filter not working

**Debugging:**
```python
from searchgram.keyword_filter import KeywordFilter

filter = KeywordFilter(
    whitelist=["bitcoin"],
    blacklist=["scam"],
    case_sensitive=False
)

result = filter.check("Bitcoin price update")
print(f"Should mirror: {result.should_mirror}")
print(f"Reason: {result.reason}")
print(f"Matched keywords: {result.matched_keywords}")
```

## Security Considerations

### API Keys

- **Never commit** API keys to version control
- Store in `config.json` (gitignored)
- Use environment variables for production

### Channel Permissions

- Bot must be **admin** in target channel
- Userbot must have **read access** to source channel
- Verify permissions before configuring tasks

### Content Filtering

- Use keyword blacklist to prevent spam
- Use LLM filter mode for intelligent filtering
- Monitor logs for suspicious content

### Rate Limiting

- Respect Telegram's rate limits
- Don't mirror from high-volume channels without delays
- Use FloodWait handling (built-in)

## Examples & Use Cases

### 1. News Aggregator
Mirror crypto news from multiple sources, rewrite in consistent style:

```json
[
  {
    "id": "coindesk_news",
    "source_channel": -1001111111111,
    "target_channel": -1009999999999,
    "llm_enabled": true,
    "llm_mode": "rewrite",
    "keyword_whitelist": ["bitcoin", "ethereum", "crypto"]
  },
  {
    "id": "cointelegraph_news",
    "source_channel": -1002222222222,
    "target_channel": -1009999999999,
    "llm_enabled": true,
    "llm_mode": "rewrite",
    "keyword_whitelist": ["bitcoin", "ethereum", "crypto"]
  }
]
```

### 2. Content Moderation
Mirror community channel with spam filtering:

```json
{
  "id": "community_moderated",
  "source_channel": -1001234567890,
  "target_channel": -1009876543210,
  "llm_enabled": true,
  "llm_mode": "filter",
  "keyword_blacklist": ["scam", "free money", "click here"]
}
```

### 3. Translation & Localization
Rewrite English content for different audience:

```json
{
  "id": "simplified_crypto",
  "source_channel": -1001234567890,
  "target_channel": -1009876543210,
  "llm_enabled": true,
  "llm_mode": "rewrite",
  "llm_custom_prompt": "Rewrite this crypto news for beginners who are new to cryptocurrency:\n\n{text}"
}
```

### 4. Topic-Specific Channels
Extract specific topics from general news channel:

```json
{
  "id": "bitcoin_only",
  "source_channel": -1001234567890,
  "target_channel": -1001111111111,
  "keyword_whitelist": ["bitcoin", "btc"],
  "mirror_media": true
}
```

## API Reference

### HTTP Endpoints

**POST `/api/v1/mirror/process`** (Bot side)
- Receives message from userbot for processing
- Requires JWT authentication (issuer: "userbot")
- Request body: `MirrorMessage` (base64-encoded file data)
- Returns: `{"status": "success|skipped|failed", "target_msg_id": int}`

**GET `/api/v1/mirror/task/<task_id>`** (Bot side)
- Get status of specific mirror task
- Requires JWT authentication
- Returns: `MirrorTask` dict

**POST `/api/v1/mirror/pause`** (Bot side)
- Pause mirror task
- Request body: `{"task_id": "string"}`
- Returns: `{"status": "ok"}`

**POST `/api/v1/mirror/resume`** (Bot side)
- Resume paused mirror task
- Request body: `{"task_id": "string"}`
- Returns: `{"status": "ok"}`

### Python API

```python
from searchgram.mirror_manager import MirrorManager
from searchgram.mirror_models import MirrorTask, MirrorMessage

# Initialize manager
manager = MirrorManager()

# Get all tasks
tasks = manager.get_all_tasks()

# Pause/resume
manager.pause_task("task_id")
manager.resume_task("task_id")

# Get statistics
stats = manager.get_stats()
```

## Future Enhancements

Potential improvements:
- [ ] Scheduled mirroring (time-based filtering)
- [ ] User-specific filtering (mirror only from certain users)
- [ ] Duplicate detection (avoid re-mirroring edited messages)
- [ ] Multi-target mirroring (one source → multiple targets)
- [ ] Webhook support for external processing
- [ ] Image OCR for text extraction
- [ ] Video transcription support
- [ ] Analytics dashboard

## Support

For issues or questions:
- GitHub Issues: https://github.com/tgbot-collection/SearchGram/issues
- Documentation: See `CLAUDE.md` and `CONFIG_REFERENCE.md`
- Examples: See `config.example.json`

---

**Version**: 1.0
**Last Updated**: 2025-01-02
