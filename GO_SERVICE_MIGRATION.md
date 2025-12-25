# Migration Guide: Go Search Service

This guide helps you migrate from direct Elasticsearch connection to the new Go search service architecture.

## What's Changing?

### Before (Direct Connection)
```
Python Bot → Elasticsearch (Python client)
```
- Python directly connects to Elasticsearch
- ES credentials in Python config
- Limited performance (~100-200 req/s)
- High memory usage (~200MB)

### After (Go Microservice)
```
Python Bot → Go Service → Elasticsearch
         (HTTP API)    (CJK optimized)
```
- Go service handles all ES operations
- ES credentials isolated in Go service
- High performance (~1000-5000 req/s)
- Low memory usage (~50-100MB)

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| **Performance** | 100-200 req/s | 1000-5000 req/s |
| **Memory (Python)** | ~200MB | ~50MB |
| **Security** | ES creds in Python | Isolated in Go |
| **Scalability** | Vertical only | Horizontal + Vertical |
| **Deployment** | Single process | Microservices |

## Migration Steps

### Step 1: Update Configuration

#### Update config.json

**Old (Direct ES):**
```json
{
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

**New (Go Service):**
```json
{
  "search_engine": {
    "engine": "http",
    "http": {
      "base_url": "http://searchgram-engine:8080",
      "api_key": null,
      "timeout": 30,
      "max_retries": 3
    }
  }
}
```

**Note**: You can keep the old `elastic` config for fallback if needed.

### Step 2: Update Docker Compose

Add the Go service to your `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # NEW: Go Search Service
  searchgram-engine:
    build: ./searchgram-engine
    container_name: searchgram-engine
    restart: always
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      - ENGINE_TYPE=elasticsearch
      - ENGINE_ELASTICSEARCH_HOST=http://elasticsearch:9200
      - ENGINE_ELASTICSEARCH_USERNAME=elastic
      - ENGINE_ELASTICSEARCH_PASSWORD=changeme
    depends_on:
      - elasticsearch
    networks:
      - searchgram-network

  # UPDATED: Client now uses HTTP engine
  client:
    image: bennythink/searchgram
    volumes:
      - ./config.json:/SearchGram/config.json:ro  # Mount config
    depends_on:
      - searchgram-engine  # Wait for Go service
    networks:
      - searchgram-network

  # UPDATED: Bot now uses HTTP engine
  bot:
    image: bennythink/searchgram
    volumes:
      - ./config.json:/SearchGram/config.json:ro  # Mount config
    depends_on:
      - searchgram-engine  # Wait for Go service
    networks:
      - searchgram-network

  # Elasticsearch (no changes needed)
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.17.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=true
      - ELASTIC_PASSWORD=changeme
    networks:
      - searchgram-network

networks:
  searchgram-network:
    driver: bridge
```

### Step 3: Build Go Service

```bash
# Navigate to Go service directory
cd searchgram-engine

# Test build locally (optional)
go build -o searchgram-engine

# Or build Docker image
docker build -t searchgram-engine .
```

### Step 4: Deploy

#### For Docker Compose:

```bash
# 1. Stop existing services
docker-compose down

# 2. Start new services (builds Go service automatically)
docker-compose up -d

# 3. Check logs
docker-compose logs -f searchgram-engine

# 4. Verify Go service is running
curl http://localhost:8080/health
```

#### For Local Development:

```bash
# Terminal 1: Start Go service
cd searchgram-engine
go run main.go

# Terminal 2: Start Elasticsearch
docker run -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "ELASTIC_PASSWORD=changeme" \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0

# Terminal 3: Start Python client
python searchgram/client.py

# Terminal 4: Start Python bot
python searchgram/bot.py
```

### Step 5: Verify Migration

```bash
# 1. Check Go service health
curl http://localhost:8080/api/v1/ping

# Expected response:
# {
#   "status": "ok",
#   "engine": "elasticsearch",
#   "total_documents": 0,
#   "uptime_seconds": 42
# }

# 2. Test search via Go service
curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "test", "page": 1}'

# 3. Check Python bot logs
# Should see: "Using HTTP (Go service) as search engine"
docker-compose logs bot | grep "search engine"

# 4. Test bot in Telegram
# Send a message to your bot and search for it
```

## Migration Strategies

### Strategy 1: Direct Migration (Recommended)

**Best for**: Small deployments, can afford brief downtime

```bash
1. Update config.json (engine: "http")
2. Update docker-compose.yml
3. docker-compose down
4. docker-compose up -d
```

**Downtime**: ~2-5 minutes

### Strategy 2: Parallel Deployment

**Best for**: Large deployments, zero downtime required

```bash
# 1. Deploy Go service alongside existing setup
docker-compose up -d searchgram-engine

# 2. Verify Go service works
curl http://localhost:8080/api/v1/ping

# 3. Update config.json gradually
#    - First update bot only
#    - Monitor for issues
#    - Then update client

# 4. Remove old direct ES connection
```

**Downtime**: None

### Strategy 3: Blue-Green Deployment

**Best for**: Production, need instant rollback

```bash
# Keep two config files:
# - config.blue.json (engine: "elastic")
# - config.green.json (engine: "http")

# 1. Deploy Go service
docker-compose up -d searchgram-engine

# 2. Switch to green config
ln -sf config.green.json config.json

# 3. Restart Python services
docker-compose restart client bot

# 4. If issues occur, rollback
ln -sf config.blue.json config.json
docker-compose restart client bot
```

## Troubleshooting

### Issue 1: Connection Refused

**Error**: `Cannot connect to search service at http://searchgram-engine:8080`

**Solution**:
```bash
# Check if Go service is running
docker-compose ps searchgram-engine

# Check Go service logs
docker-compose logs searchgram-engine

# Verify network connectivity
docker-compose exec client ping searchgram-engine
```

### Issue 2: Authentication Failed

**Error**: `Unauthorized` or `401 status code`

**Solution**:
```bash
# If API key auth is enabled in Go service,
# add it to config.json:
{
  "search_engine": {
    "engine": "http",
    "http": {
      "api_key": "your-api-key-here"
    }
  }
}
```

### Issue 3: Go Service Can't Connect to ES

**Error**: Go service logs show ES connection errors

**Solution**:
```bash
# 1. Check Elasticsearch is running
docker-compose ps elasticsearch

# 2. Test ES connection
curl -u elastic:changeme http://localhost:9200

# 3. Verify Go service config
docker-compose exec searchgram-engine env | grep ELASTIC

# 4. Check network
docker-compose exec searchgram-engine ping elasticsearch
```

### Issue 4: Search Returns No Results

**Symptom**: Bot returns empty results after migration

**Solution**:
```bash
# Check if data was migrated
curl http://localhost:8080/api/v1/stats

# If total_documents is 0, re-index:
# 1. Let client re-index new messages (automatic)
# 2. Or run sync for historical messages
#    (edit config.json sync.chats and restart client)
```

### Issue 5: Performance Degradation

**Symptom**: Searches are slower than before

**Solution**:
```bash
# 1. Check Go service resource usage
docker stats searchgram-engine

# 2. Check Elasticsearch health
curl http://localhost:8080/api/v1/ping

# 3. Increase ES memory
# In docker-compose.yml:
environment:
  - "ES_JAVA_OPTS=-Xms1g -Xmx1g"  # Increase from 512m

# 4. Check Go service logs for errors
docker-compose logs -f searchgram-engine
```

## Rollback Plan

If you need to rollback to direct Elasticsearch connection:

```bash
# 1. Update config.json
{
  "search_engine": {
    "engine": "elastic",
    "elastic": {
      "host": "http://elasticsearch:9200",
      "user": "elastic",
      "password": "changeme"
    }
  }
}

# 2. Restart Python services
docker-compose restart client bot

# 3. Optionally stop Go service
docker-compose stop searchgram-engine
```

**Data Safety**: Your data is in Elasticsearch, so switching between engines doesn't affect stored messages.

## Post-Migration Validation

### Checklist

- [ ] Go service health check passes
- [ ] Python bot logs show "Using HTTP (Go service)"
- [ ] Existing messages are searchable
- [ ] New messages are indexed correctly
- [ ] Privacy controls still work (`/block_me`)
- [ ] Performance is equal or better
- [ ] No errors in logs

### Performance Comparison

```bash
# Before migration
# Run 100 searches and measure time

# After migration
# Run same 100 searches and compare

# Expected: 2-10x improvement in throughput
```

### Monitoring

```bash
# Watch Go service metrics
watch -n 5 'curl -s http://localhost:8080/api/v1/stats'

# Watch Python logs
docker-compose logs -f --tail=100 client bot

# Watch Elasticsearch health
watch -n 10 'curl -s http://localhost:9200/_cluster/health?pretty'
```

## FAQ

### Q: Do I lose data during migration?

**A**: No. Your data stays in Elasticsearch. You're just changing how Python talks to ES (directly vs via Go service).

### Q: Can I use both engines simultaneously?

**A**: No. Only one engine can be active at a time. But you can switch between them by changing `config.json`.

### Q: Does this require re-indexing all messages?

**A**: No. Existing ES data works with the Go service immediately.

### Q: What if the Go service goes down?

**A**: Python services will fail to index/search until Go service recovers. Consider:
- Running multiple Go service instances for high availability
- Setting up restart policies in docker-compose
- Monitoring Go service health

### Q: Can I still use direct ES connection?

**A**: Yes, the legacy engines (`elastic`, `meili`, etc.) still work. But we recommend migrating to `http` for better performance.

### Q: How do I scale the Go service?

**A**: Run multiple instances behind a load balancer:

```yaml
services:
  searchgram-engine-1:
    build: ./searchgram-engine
    # ... config ...

  searchgram-engine-2:
    build: ./searchgram-engine
    # ... same config ...

  nginx:  # Load balancer
    image: nginx
    # Configure round-robin to engine-1 and engine-2
```

## Next Steps

After successful migration:

1. **Monitor**: Watch logs and metrics for 24-48 hours
2. **Optimize**: Tune ES settings based on usage patterns
3. **Scale**: Add more Go instances if needed
4. **Secure**: Enable API key authentication for production
5. **Document**: Update your deployment docs

## Support

If you encounter issues:

1. Check this guide's Troubleshooting section
2. Review Go service logs: `docker-compose logs searchgram-engine`
3. Check ARCHITECTURE.md for design details
4. Open a GitHub issue with logs and config

## Summary

✅ **Simple**: Update config.json and docker-compose.yml
✅ **Safe**: No data loss, easy rollback
✅ **Fast**: 2-10x performance improvement
✅ **Secure**: ES credentials isolated in Go service
✅ **Scalable**: Horizontal scaling support

🚀 **Ready to migrate?** Follow Step 1-5 above!
