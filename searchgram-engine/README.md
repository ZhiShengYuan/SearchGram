# SearchGram Search Engine (Go)

High-performance search microservice for SearchGram written in Go.

## Overview

This is a standalone Go service that handles all search engine operations for SearchGram. It provides a REST API that the main Python bot communicates with, offering better performance, security, and scalability than direct database connections.

## Features

- **High Performance**: Go's concurrency model handles thousands of requests per second
- **CJK Optimization**: Elasticsearch backend with bigram tokenization for Chinese, Japanese, Korean
- **Secure**: Elasticsearch credentials isolated in Go service, not exposed to Python bot
- **Scalable**: Horizontal scaling with multiple instances behind a load balancer
- **Flexible**: Pluggable search engine backends (currently supports Elasticsearch)
- **Observable**: Structured JSON logging, health checks, statistics endpoints

## Architecture

```
Python Bot → HTTP API → Go Service → Elasticsearch
            (port 8080)             (CJK optimized)
```

### Benefits Over Direct Connection

| Aspect | Direct ES (Python) | Go Service |
|--------|-------------------|------------|
| Performance | ~100-200 req/s | ~1000-5000 req/s |
| Memory | ~200MB | ~50-100MB |
| Credentials | In Python config | Isolated in Go |
| Scalability | Vertical only | Horizontal + Vertical |
| Connection Pooling | Limited | Efficient |

## API Endpoints

### Message Operations
- `POST /api/v1/upsert` - Index or update a message
- `POST /api/v1/search` - Search messages
- `DELETE /api/v1/messages?chat_id=X` - Delete messages by chat
- `DELETE /api/v1/users/:user_id` - Delete user's messages
- `DELETE /api/v1/clear` - Clear entire database

### Health & Monitoring
- `GET /api/v1/ping` - Health check with stats
- `GET /api/v1/stats` - Detailed statistics
- `GET /health` - Simple health check
- `GET /` - Service information

## Configuration

### Via config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 8080

search_engine:
  type: "elasticsearch"

elasticsearch:
  host: "http://elasticsearch:9200"
  username: "elastic"
  password: "changeme"
  index: "telegram"
  shards: 3
  replicas: 1

auth:
  enabled: false
  api_key: ""

logging:
  level: "info"
  format: "json"
```

### Via Environment Variables

All config values can be set via environment variables with `ENGINE_` prefix:

```bash
ENGINE_TYPE=elasticsearch
ENGINE_ELASTICSEARCH_HOST=http://elasticsearch:9200
ENGINE_ELASTICSEARCH_USERNAME=elastic
ENGINE_ELASTICSEARCH_PASSWORD=changeme
ENGINE_LOGGING_LEVEL=info
```

## Building

### Local Build

```bash
# Install dependencies
go mod download

# Build
go build -o searchgram-engine

# Run
./searchgram-engine
```

### Docker Build

```bash
# Build image
docker build -t searchgram-engine .

# Run container
docker run -p 8080:8080 \
  -e ENGINE_TYPE=elasticsearch \
  -e ENGINE_ELASTICSEARCH_HOST=http://elasticsearch:9200 \
  searchgram-engine
```

### Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f searchgram-engine

# Stop services
docker-compose down
```

## Development

### Prerequisites

- Go 1.21 or higher
- Elasticsearch 7.x or 8.x
- Docker (optional, for containerized development)

### Running Locally

```bash
# 1. Start Elasticsearch
docker run -d \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=true" \
  -e "ELASTIC_PASSWORD=changeme" \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0

# 2. Configure service
cp config.yaml config.local.yaml
# Edit config.local.yaml with your settings

# 3. Run service
go run main.go

# 4. Test
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/ping
```

### Testing the API

```bash
# Upsert a message
curl -X POST http://localhost:8080/api/v1/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "id": "123-456",
    "text": "Hello world 你好世界",
    "chat": {"id": 123, "type": "PRIVATE"},
    "from_user": {"id": 456, "username": "alice"},
    "timestamp": 1640000000
  }'

# Search messages
curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "你好",
    "page": 1,
    "page_size": 10
  }'

# Health check
curl http://localhost:8080/api/v1/ping
```

## Project Structure

```
searchgram-engine/
├── main.go              # Application entry point
├── go.mod               # Go module definition
├── go.sum               # Dependency checksums
├── config.yaml          # Configuration file
├── Dockerfile           # Container build file
├── config/
│   └── config.go        # Configuration loading
├── models/
│   └── message.go       # Data models
├── engines/
│   ├── engine.go        # SearchEngine interface
│   └── elasticsearch.go # Elasticsearch implementation
├── handlers/
│   └── api.go           # HTTP handlers
└── middleware/
    └── auth.go          # Authentication & logging
```

## Monitoring

### Health Checks

```bash
# Kubernetes liveness probe
curl http://localhost:8080/health

# Detailed health with stats
curl http://localhost:8080/api/v1/ping
```

### Logging

Structured JSON logs to stdout:

```json
{
  "level": "info",
  "msg": "HTTP request",
  "status": 200,
  "method": "POST",
  "path": "/api/v1/search",
  "latency_ms": 45,
  "time": "2025-12-25T10:30:00Z"
}
```

### Metrics (Future)

Prometheus metrics endpoint planned:
- Request count by endpoint
- Request latency histograms
- Error rates
- Elasticsearch connection status
- Cache hit/miss ratios

## Security

### API Authentication

Enable API key authentication in config:

```yaml
auth:
  enabled: true
  api_key: "your-secret-key-here"
```

Client requests must include:
```
X-API-Key: your-secret-key-here
```

Or:
```
Authorization: Bearer your-secret-key-here
```

### Network Security

Recommended setup:
1. Run Go service and Elasticsearch on private network
2. Only expose Go service port 8080 to Python services
3. Use TLS/HTTPS in production
4. Set strong Elasticsearch password

### Docker Secrets

For production, use Docker secrets:

```yaml
version: '3.8'
services:
  searchgram-engine:
    secrets:
      - elastic_password
    environment:
      - ENGINE_ELASTICSEARCH_PASSWORD_FILE=/run/secrets/elastic_password

secrets:
  elastic_password:
    external: true
```

## Performance Tuning

### Elasticsearch Settings

```yaml
elasticsearch:
  shards: 3         # More shards for larger datasets
  replicas: 1       # More replicas for high availability
```

### Connection Pooling

The Elasticsearch client automatically manages connection pooling. Default settings are optimized for most use cases.

### Caching

Response caching planned for future release.

## Troubleshooting

### Service won't start

```bash
# Check configuration
go run main.go  # Will show config validation errors

# Test Elasticsearch connection
curl -u elastic:changeme http://localhost:9200
```

### Search returns no results

```bash
# Check index exists
curl http://localhost:8080/api/v1/ping

# Verify documents are indexed
curl http://localhost:8080/api/v1/stats
```

### High latency

- Check Elasticsearch performance
- Increase ES memory (`ES_JAVA_OPTS=-Xms1g -Xmx1g`)
- Add more ES shards for large datasets
- Enable caching (when available)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

Same as SearchGram main project.

## Support

- GitHub Issues: [https://github.com/ZhiShengYuan/SearchGram/issues](https://github.com/ZhiShengYuan/SearchGram/issues)
- Documentation: See `ARCHITECTURE.md` in the main project
