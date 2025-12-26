# SearchGram Architecture - Go Search Service

## Overview

SearchGram now uses a **microservice architecture** with a separate Go-based search service that abstracts all search engine operations from the main Python application.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     SearchGram Ecosystem                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────────┐              │
│  │   Telegram   │         │   Telegram Bot   │              │
│  │   User API   │◄───────►│    (Python)      │              │
│  └──────────────┘         └─────────┬────────┘              │
│                                      │                        │
│                                      │ HTTP REST API          │
│                                      ▼                        │
│                          ┌──────────────────┐                │
│                          │  Search Service  │                │
│                          │   (Golang)       │                │
│                          │                  │                │
│                          │  - Upsert        │                │
│                          │  - Search        │                │
│                          │  - Delete        │                │
│                          │  - Ping/Health   │                │
│                          └────────┬─────────┘                │
│                                   │                          │
│                                   │ Native Protocol          │
│                                   ▼                          │
│                          ┌──────────────────┐                │
│                          │  Elasticsearch   │                │
│                          │  (or others)     │                │
│                          └──────────────────┘                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Benefits

### 1. Performance
- **Go Performance**: Go is 10-100x faster than Python for I/O operations
- **Connection Pooling**: Efficient ES connection reuse
- **Concurrent Requests**: Go's goroutines handle parallel searches efficiently
- **Lower Memory**: Go uses less memory than Python for equivalent workload

### 2. Security
- **Credential Isolation**: ES credentials only in Go service, not in Python
- **Network Isolation**: ES can be on private network, only Go service exposed
- **API Authentication**: Optional API key authentication between services
- **Rate Limiting**: Built-in rate limiting in Go service

### 3. Scalability
- **Horizontal Scaling**: Run multiple Go service instances
- **Load Balancing**: Distribute load across instances
- **Independent Deployment**: Update search service without touching bot
- **Multi-Client Support**: Multiple bots can share one search service

### 4. Abstraction
- **Backend Agnostic**: Switch ES/Meili/Mongo without changing bot code
- **Unified Interface**: Single REST API regardless of backend
- **Easy Testing**: Mock API responses for testing
- **Version Independence**: Go and Python can upgrade independently

## Components

### 1. Go Search Service (searchgram-engine)

**Technology Stack**:
- **Language**: Go 1.21+
- **Web Framework**: Gin (high-performance HTTP router)
- **ES Client**: olivere/elastic/v7
- **Config**: Viper (YAML/JSON/ENV support)
- **Logging**: Logrus (structured logging)

**Responsibilities**:
- Accept HTTP requests from Python bot
- Validate and sanitize inputs
- Transform requests to ES queries
- Execute ES operations (index, search, delete)
- Return standardized JSON responses
- Health monitoring and metrics

**Configuration** (`config.yaml`):
```yaml
server:
  host: "0.0.0.0"
  port: 8080
  read_timeout: 30s
  write_timeout: 30s

search_engine:
  type: "elasticsearch"  # elasticsearch, meilisearch, mongodb, zinc

elasticsearch:
  host: "http://elasticsearch:9200"
  username: "elastic"
  password: "changeme"
  index: "telegram"
  shards: 3
  replicas: 1

auth:
  enabled: false
  api_key: "your-secret-api-key"

logging:
  level: "info"
  format: "json"

cache:
  enabled: true
  ttl: 300  # seconds
```

### 2. Python HTTP Client (http_engine.py)

**Responsibilities**:
- Implement `BasicSearchEngine` interface
- Convert Pyrogram messages to JSON
- Make HTTP requests to Go service
- Handle errors and retries
- Deserialize responses

**Configuration** (config.json):
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

## API Specification

### Base URL
```
http://searchgram-engine:8080/api/v1
```

### Endpoints

#### 1. Upsert Message
```http
POST /api/v1/upsert
Content-Type: application/json

{
  "id": "123456-789",
  "text": "Hello world",
  "chat": {
    "id": 123456,
    "type": "private",
    "username": "john_doe"
  },
  "from_user": {
    "id": 789,
    "username": "jane_doe",
    "first_name": "Jane"
  },
  "date": 1640000000,
  "timestamp": 1640000000
}

Response 200 OK:
{
  "success": true,
  "id": "123456-789"
}
```

#### 2. Search Messages
```http
POST /api/v1/search
Content-Type: application/json

{
  "keyword": "hello",
  "chat_type": "private",
  "username": "john_doe",
  "page": 1,
  "page_size": 10,
  "exact_match": false,
  "blocked_users": [123, 456]
}

Response 200 OK:
{
  "hits": [
    {
      "id": "123456-789",
      "text": "Hello world",
      "chat": {...},
      "from_user": {...},
      "timestamp": 1640000000
    }
  ],
  "total_hits": 42,
  "total_pages": 5,
  "page": 1,
  "hits_per_page": 10
}
```

#### 3. Delete Messages by Chat
```http
DELETE /api/v1/messages?chat_id=123456

Response 200 OK:
{
  "success": true,
  "deleted_count": 150
}
```

#### 4. Delete User Messages
```http
DELETE /api/v1/users/789

Response 200 OK:
{
  "success": true,
  "deleted_count": 42
}
```

#### 5. Clear Database
```http
DELETE /api/v1/clear

Response 200 OK:
{
  "success": true,
  "message": "Database cleared"
}
```

#### 6. Health Check
```http
GET /api/v1/ping

Response 200 OK:
{
  "status": "ok",
  "engine": "elasticsearch",
  "version": "7.17.0",
  "total_documents": 10000,
  "uptime_seconds": 3600
}
```

#### 7. Statistics
```http
GET /api/v1/stats

Response 200 OK:
{
  "total_documents": 10000,
  "total_chats": 42,
  "total_users": 15,
  "index_size_bytes": 1048576,
  "requests_total": 5000,
  "requests_per_minute": 25
}
```

## Deployment

### Network Security

**LAN Deployment**:
```
┌─────────────────────────────────────────────────┐
│                  Private LAN                     │
│                                                  │
│  ┌──────────────┐       ┌──────────────────┐   │
│  │ Go Service   │◄─────►│ Elasticsearch    │   │
│  │ :8080        │       │ :9200            │   │
│  └──────▲───────┘       └──────────────────┘   │
│         │                                        │
│         │ HTTP (can be internal only)           │
│         │                                        │
└─────────┼────────────────────────────────────────┘
          │
          │ Public/Firewall
          ▼
  ┌──────────────┐
  │ SearchGram   │
  │ Python Bot   │
  └──────────────┘
```

**Security Layers**:
1. **Network**: ES not exposed to internet, only Go service
2. **Authentication**: Optional API key between Python ↔ Go
3. **Firewall**: Only port 8080 exposed from LAN
4. **TLS**: HTTPS for production deployments

## Migration Path

### Phase 1: Parallel Deployment
- Run both old (direct ES) and new (Go service) in parallel
- Python can use `engine=elastic` (direct) or `engine=http` (via Go)
- Test and validate Go service

### Phase 2: Gradual Migration
- Switch to `engine=http` in config
- Monitor performance and errors
- Keep direct ES as fallback

### Phase 3: Full Migration
- Remove direct ES dependencies from Python
- Lock down ES to only accept Go service connections
- Delete old engine implementations (elastic.py, meili.py, etc.)

## Performance Expectations

### Latency
- **Direct ES (Python)**: ~50-200ms per search
- **Via Go Service**: ~60-220ms per search (adds ~10-20ms overhead)
- **With Caching**: ~5-50ms for repeated queries

### Throughput
- **Direct ES (Python)**: ~100-200 req/s (limited by Python GIL)
- **Via Go Service**: ~1000-5000 req/s (Go's concurrency model)
- **Horizontal Scaling**: Linear scaling with multiple Go instances

### Resource Usage
- **Go Service**: ~50MB RAM idle, ~200MB under load
- **Python Bot**: Reduced by ~30% (no ES client overhead)

## Monitoring

### Metrics Exposed
- `/metrics` endpoint (Prometheus format)
- Request count, latency histograms
- Error rates, ES connection status
- Cache hit/miss ratios

### Logging
- Structured JSON logs
- Request ID tracing
- Error stack traces
- Performance metrics

## Future Enhancements

1. **gRPC Support**: For even better performance
2. **GraphQL API**: Flexible query interface
3. **Search Query DSL**: Advanced search syntax
4. **Real-time Indexing**: WebSocket for live updates
5. **Multi-tenancy**: Support multiple bots/users
6. **ML Features**: Semantic search, recommendations
7. **Distributed Tracing**: OpenTelemetry integration

## Summary

The Go search service architecture provides:
- ✅ Better performance and scalability
- ✅ Enhanced security (credential isolation)
- ✅ Clean separation of concerns
- ✅ Easier testing and deployment
- ✅ Backend flexibility (easy to switch ES/Meili/etc)
- ✅ Production-ready monitoring and logging

This architecture positions SearchGram for growth while maintaining simplicity and reliability.
