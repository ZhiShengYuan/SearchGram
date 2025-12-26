# HTTP/2 Implementation for SearchGram

## Overview

This document describes the HTTP/2 implementation with connection pooling (remux) for the SearchGram HTTP search API client.

## Changes Made

### 1. Python Client (searchgram/http_engine.py)

**Replaced `requests` library with `httpx`** for better HTTP/2 support and modern async capabilities.

**Key Features:**
- **HTTP/2 Support**: Full HTTP/2 protocol support with multiplexing
- **Connection Pooling (Remux)**: Reuses connections efficiently
  - `max_keepalive_connections: 20` - Keep up to 20 idle connections alive
  - `max_connections: 100` - Maximum total connections
  - `keepalive_expiry: 30s` - Keep connections alive for 30 seconds
- **Automatic Retries**: Configurable retry logic for failed requests
- **Better Error Handling**: Uses httpx's native exception hierarchy

**Configuration:**
```python
limits = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=100,
    keepalive_expiry=30.0,
)

transport = httpx.HTTPTransport(
    http2=True,
    retries=max_retries,
)

client = httpx.Client(
    http2=True,
    timeout=httpx.Timeout(timeout),
    limits=limits,
    transport=transport,
)
```

### 2. Go Search Service (searchgram-engine/main.go)

**Added h2c (HTTP/2 Cleartext) support** to enable HTTP/2 over plain HTTP connections.

**Key Features:**
- **h2c Handler**: Wraps Gin router with HTTP/2 cleartext support
- **Backward Compatible**: Still supports HTTP/1.1 clients
- **No TLS Required**: Works over plain HTTP for internal LAN communication

**Implementation:**
```go
import (
    "golang.org/x/net/http2"
    "golang.org/x/net/http2/h2c"
)

h2s := &http2.Server{}
h2cHandler := h2c.NewHandler(router, h2s)

srv := &http.Server{
    Addr:    fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port),
    Handler: h2cHandler,
}
```

### 3. Dependencies

**Python (requirements.txt):**
```
httpx==0.27.2
h2==4.1.0
```

**Go (go.mod):**
```
golang.org/x/net v0.19.0  # Already present
```

## Benefits

### Performance Improvements

1. **Multiplexing**: Multiple requests over a single TCP connection
2. **Header Compression**: HPACK reduces overhead
3. **Connection Reuse**: Eliminates connection setup overhead
4. **Reduced Latency**: Faster request/response cycles

### Resource Efficiency

1. **Lower Memory Usage**: Fewer TCP connections
2. **Reduced CPU Usage**: Less connection management overhead
3. **Better Throughput**: More efficient use of network bandwidth

### Scalability

1. **Higher Concurrency**: Handle more simultaneous operations
2. **Better Resource Utilization**: Fewer file descriptors needed
3. **Improved Load Handling**: Smoother performance under load

## Testing

### Verify HTTP/2 Support

Run the standalone test:
```bash
python3 test_http2_standalone.py
```

Expected output:
```
✅ HTTP/2 is working!
```

### Test with Go Service

1. Start the Go search service:
```bash
cd searchgram-engine
./searchgram-engine
```

2. Check logs for HTTP/2 confirmation:
```
INFO[...] Starting SearchGram Search Engine with HTTP/2 support
```

3. Run SearchGram client/bot - they will automatically use HTTP/2

## HTTP/2 vs HTTP/1.1 Comparison

| Feature | HTTP/1.1 | HTTP/2 |
|---------|----------|--------|
| Multiplexing | No | Yes |
| Header Compression | No | Yes (HPACK) |
| Server Push | No | Yes |
| Binary Protocol | No | Yes |
| Connection Reuse | Limited | Excellent |
| Performance | Good | Excellent |

## Monitoring

### Python Client Logs

The client logs the HTTP version on connection:
```
INFO: Successfully connected to search service with HTTP/2 🚀
```

Or for HTTP/1.1:
```
INFO: Successfully connected to search service (HTTP/1.1)
```

### Connection Pool Stats

The httpx client maintains internal connection pool statistics. For debugging, you can inspect:
- Number of active connections
- Number of idle connections
- Connection reuse rate

## Troubleshooting

### Issue: Client still using HTTP/1.1

**Solution:**
1. Verify Go service is running with HTTP/2 support
2. Check that httpx is properly installed: `pip3 list | grep httpx`
3. Ensure h2 library is installed: `pip3 list | grep h2`

### Issue: Connection refused

**Solution:**
1. Verify Go service is running: `curl http://127.0.0.1:8083/health`
2. Check firewall settings
3. Verify configuration in config.yaml

### Issue: Performance not improving

**Solution:**
1. Check network latency between client and server
2. Verify connection pooling is working (check logs)
3. Increase keepalive connections if needed
4. Profile application to identify bottlenecks

## Configuration Tuning

### For High-Volume Deployments

Increase connection pool size:
```python
limits = httpx.Limits(
    max_keepalive_connections=50,  # Increase from 20
    max_connections=200,            # Increase from 100
    keepalive_expiry=60.0,         # Increase from 30s
)
```

### For Low-Latency Networks (LAN)

Reduce keepalive expiry:
```python
limits = httpx.Limits(
    max_keepalive_connections=10,
    max_connections=50,
    keepalive_expiry=15.0,         # Reduce from 30s
)
```

## Future Enhancements

1. **TLS Support**: Add HTTPS with native HTTP/2 (no h2c needed)
2. **Connection Metrics**: Expose connection pool statistics
3. **Dynamic Pool Sizing**: Auto-adjust based on load
4. **gRPC Migration**: Consider gRPC for even better performance

## References

- [HTTP/2 RFC 7540](https://tools.ietf.org/html/rfc7540)
- [httpx Documentation](https://www.python-httpx.org/)
- [Go http2 Package](https://pkg.go.dev/golang.org/x/net/http2)
- [h2c Specification](https://http2.github.io/http2-spec/#discover-http)
