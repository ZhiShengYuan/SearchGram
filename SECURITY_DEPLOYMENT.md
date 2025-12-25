# Secure Internet Deployment Guide for SearchGram Engine

This guide covers best practices for safely exposing the searchgram-engine service to the internet.

## ⚠️ Security Considerations

Before exposing the Go service to the internet, understand the risks:

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Unauthorized Access** | Anyone can search/modify your data | API key authentication + rate limiting |
| **DDoS Attacks** | Service unavailable | Cloudflare, rate limiting, auto-scaling |
| **Data Leakage** | Private messages exposed | HTTPS/TLS, authentication, input validation |
| **Injection Attacks** | Database compromise | Input sanitization, parameterized queries |
| **Resource Exhaustion** | High costs | Rate limiting, quotas, monitoring |

## 🛡️ Security Layers (Defense in Depth)

```
Internet
    ↓
[1. Firewall/WAF] ← DDoS protection, IP filtering
    ↓
[2. Reverse Proxy] ← TLS termination, rate limiting
    ↓
[3. API Gateway] ← Authentication, authorization
    ↓
[4. Go Service] ← Input validation, logging
    ↓
[5. Elasticsearch] ← Network isolation, authentication
```

## 🔐 Recommended Architecture

### Option 1: Cloudflare Tunnel (Easiest, Most Secure)

**Best for**: Small to medium deployments, zero public IP needed

```
Internet → Cloudflare → Tunnel → Go Service (Private)
           (DDoS)      (Encrypted)
```

**Advantages**:
- ✅ No port forwarding needed
- ✅ Built-in DDoS protection
- ✅ Free SSL/TLS certificates
- ✅ Hide your server IP
- ✅ Web Application Firewall (WAF)
- ✅ Rate limiting included

**Setup**:

```bash
# 1. Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# 2. Authenticate
cloudflared tunnel login

# 3. Create tunnel
cloudflared tunnel create searchgram-engine

# 4. Configure tunnel
cat > ~/.cloudflared/config.yml <<EOF
tunnel: <TUNNEL-ID>
credentials-file: /root/.cloudflared/<TUNNEL-ID>.json

ingress:
  - hostname: searchgram-api.yourdomain.com
    service: http://localhost:8080
  - service: http_status:404
EOF

# 5. Route DNS
cloudflared tunnel route dns searchgram-engine searchgram-api.yourdomain.com

# 6. Run tunnel
cloudflared tunnel run searchgram-engine

# 7. Install as service
sudo cloudflared service install
```

**Docker Compose Integration**:

```yaml
services:
  searchgram-engine:
    build: ./searchgram-engine
    environment:
      - ENGINE_AUTH_ENABLED=true
      - ENGINE_AUTH_API_KEY=${API_KEY}
    networks:
      - private-network

  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - searchgram-engine
    networks:
      - private-network

networks:
  private-network:
    internal: true  # No external access except via tunnel
```

### Option 2: Nginx Reverse Proxy + Let's Encrypt (Traditional)

**Best for**: Full control, self-hosted

```
Internet → Nginx → Go Service
         (HTTPS)  (HTTP localhost)
```

**Setup**:

```bash
# 1. Install Nginx and Certbot
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx

# 2. Configure Nginx
sudo nano /etc/nginx/sites-available/searchgram-engine
```

```nginx
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# Upstream
upstream searchgram_backend {
    server localhost:8080;
    keepalive 32;
}

server {
    listen 80;
    server_name searchgram-api.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name searchgram-api.yourdomain.com;

    # SSL Configuration (certbot will add these)
    ssl_certificate /etc/letsencrypt/live/searchgram-api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/searchgram-api.yourdomain.com/privkey.pem;

    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Rate Limiting
    limit_req zone=api_limit burst=20 nodelay;
    limit_conn conn_limit 10;

    # Max body size
    client_max_body_size 1M;

    # Timeouts
    proxy_connect_timeout 30s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;

    # Access logs
    access_log /var/log/nginx/searchgram-access.log combined;
    error_log /var/log/nginx/searchgram-error.log warn;

    # API endpoints
    location /api/ {
        # IP whitelist (optional)
        # allow 1.2.3.4;  # Your Python bot server IP
        # deny all;

        proxy_pass http://searchgram_backend;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed in future)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint (public)
    location /health {
        proxy_pass http://searchgram_backend;
        access_log off;
    }

    # Block everything else
    location / {
        return 404;
    }
}
```

```bash
# 3. Enable site
sudo ln -s /etc/nginx/sites-available/searchgram-engine /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 4. Get SSL certificate
sudo certbot --nginx -d searchgram-api.yourdomain.com

# 5. Auto-renewal
sudo certbot renew --dry-run
```

### Option 3: API Gateway (AWS/GCP/Azure)

**Best for**: Enterprise, cloud-native deployments

**AWS API Gateway + Lambda:**

```yaml
# Use AWS API Gateway with:
# - API Keys for authentication
# - Usage plans and throttling
# - WAF for DDoS protection
# - CloudWatch for monitoring
# - Lambda@Edge for custom logic
```

**Google Cloud API Gateway:**

```yaml
# Use GCP API Gateway with:
# - API key or OAuth2 authentication
# - Rate limiting and quotas
# - Cloud Armor for DDoS
# - Cloud Monitoring
```

## 🔑 Enable Authentication

### Option 1: API Key (Simple, Recommended for Start)

**Update Go Service Config**:

```yaml
# searchgram-engine/config.yaml
auth:
  enabled: true
  api_key: "your-strong-random-api-key-here"  # Generate with: openssl rand -hex 32
```

**Environment Variable**:

```bash
# docker-compose.yml
environment:
  - ENGINE_AUTH_ENABLED=true
  - ENGINE_AUTH_API_KEY=${API_KEY}  # From .env file
```

**Python Client Config**:

```json
{
  "search_engine": {
    "engine": "http",
    "http": {
      "base_url": "https://searchgram-api.yourdomain.com",
      "api_key": "your-strong-random-api-key-here",
      "timeout": 30
    }
  }
}
```

**Generate Strong API Key**:

```bash
# Method 1: OpenSSL
openssl rand -hex 32

# Method 2: Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Method 3: UUID
uuidgen | tr -d '-'
```

### Option 2: JWT Tokens (Advanced)

**For multiple clients with different permissions**:

Add JWT middleware to Go service:

```go
// middleware/jwt.go
package middleware

import (
    "github.com/gin-gonic/gin"
    "github.com/golang-jwt/jwt/v5"
)

func JWTAuth(secret string) gin.HandlerFunc {
    return func(c *gin.Context) {
        tokenString := c.GetHeader("Authorization")
        // ... JWT validation logic
    }
}
```

### Option 3: OAuth2 (Production)

Use OAuth2 providers (Google, GitHub, Auth0) for authentication.

## 🚦 Rate Limiting

### In Nginx (Recommended):

```nginx
# Limit to 10 requests per second per IP
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# Allow burst of 20 requests
limit_req zone=api_limit burst=20 nodelay;
```

### In Go Service:

Add rate limiting middleware:

```bash
# Add to go.mod
go get github.com/ulule/limiter/v3
```

```go
// middleware/ratelimit.go
package middleware

import (
    "github.com/gin-gonic/gin"
    "github.com/ulule/limiter/v3"
    "github.com/ulule/limiter/v3/drivers/store/memory"
)

func RateLimiter() gin.HandlerFunc {
    rate := limiter.Rate{
        Period: 1 * time.Second,
        Limit:  10,
    }
    store := memory.NewStore()
    instance := limiter.New(store, rate)

    return func(c *gin.Context) {
        context, err := instance.Get(c, c.ClientIP())
        if err != nil {
            c.JSON(500, gin.H{"error": "rate limiter error"})
            c.Abort()
            return
        }

        if context.Reached {
            c.JSON(429, gin.H{"error": "rate limit exceeded"})
            c.Abort()
            return
        }

        c.Next()
    }
}
```

### Using Cloudflare Rate Limiting:

```
Cloudflare Dashboard → Security → WAF → Rate Limiting Rules
```

Create rule:
- **Match**: Path contains `/api/v1/search`
- **Rate**: 10 requests per 10 seconds
- **Action**: Block for 60 seconds

## 🔥 Firewall Configuration

### UFW (Ubuntu):

```bash
# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change port if needed)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (only if using Nginx)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block direct access to Go service from internet
# (should only be accessible via Nginx or localhost)
sudo ufw deny 8080/tcp

# Enable firewall
sudo ufw enable
```

### iptables:

```bash
# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Block direct access to port 8080
iptables -A INPUT -p tcp --dport 8080 -j DROP

# Default policy
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Save rules
sudo iptables-save > /etc/iptables/rules.v4
```

## 📊 Monitoring & Alerts

### Health Checks:

```bash
# Add to crontab
*/5 * * * * curl -f https://searchgram-api.yourdomain.com/health || echo "Service down!" | mail -s "Alert" admin@yourdomain.com
```

### Prometheus Metrics (Future):

```go
// Add Prometheus metrics endpoint
import "github.com/prometheus/client_golang/prometheus/promhttp"

router.GET("/metrics", gin.WrapH(promhttp.Handler()))
```

### Log Monitoring:

```bash
# Watch for errors
tail -f /var/log/nginx/searchgram-error.log

# Monitor Go service logs
docker-compose logs -f --tail=100 searchgram-engine | grep -i error
```

### Uptime Monitoring:

Use external services:
- **UptimeRobot** (free)
- **Pingdom**
- **StatusCake**
- **Healthchecks.io**

## 🔒 Security Checklist

Before going live:

- [ ] **Authentication**: API key enabled and strong (32+ chars)
- [ ] **HTTPS**: SSL/TLS certificate installed (A+ rating on SSLLabs)
- [ ] **Rate Limiting**: Configured in Nginx or Cloudflare
- [ ] **Firewall**: UFW/iptables configured, port 8080 blocked from internet
- [ ] **Reverse Proxy**: Nginx or Cloudflare tunnel in place
- [ ] **Security Headers**: HSTS, X-Frame-Options, CSP configured
- [ ] **Input Validation**: Go service validates all inputs
- [ ] **Logging**: Access logs and error logs enabled
- [ ] **Monitoring**: Health checks and alerts configured
- [ ] **Backups**: Elasticsearch data backed up regularly
- [ ] **Updates**: System and dependencies up to date
- [ ] **Network Isolation**: Elasticsearch not exposed to internet
- [ ] **DDoS Protection**: Cloudflare or similar enabled
- [ ] **IP Whitelist**: Consider restricting to known IPs
- [ ] **Secrets**: API keys in environment variables, not in git

## 🧪 Testing Security

### SSL/TLS Test:

```bash
# Test SSL configuration
curl -I https://searchgram-api.yourdomain.com

# Check SSL rating
# Visit: https://www.ssllabs.com/ssltest/
```

### Authentication Test:

```bash
# Should fail without API key
curl https://searchgram-api.yourdomain.com/api/v1/ping

# Should succeed with API key
curl -H "X-API-Key: your-api-key" https://searchgram-api.yourdomain.com/api/v1/ping
```

### Rate Limiting Test:

```bash
# Send rapid requests
for i in {1..50}; do
  curl -H "X-API-Key: your-api-key" https://searchgram-api.yourdomain.com/api/v1/ping &
done

# Should see 429 errors after limit
```

### Penetration Testing:

```bash
# Use OWASP ZAP or similar
# Test for: SQL injection, XSS, CSRF, etc.
```

## 📦 Complete Secure Deployment Example

### docker-compose.yml (Production):

```yaml
version: '3.8'

services:
  # Go Search Service (PRIVATE - not exposed)
  searchgram-engine:
    build: ./searchgram-engine
    container_name: searchgram-engine
    restart: always
    environment:
      - ENGINE_TYPE=elasticsearch
      - ENGINE_ELASTICSEARCH_HOST=http://elasticsearch:9200
      - ENGINE_ELASTICSEARCH_USERNAME=elastic
      - ENGINE_ELASTICSEARCH_PASSWORD=${ELASTIC_PASSWORD}
      - ENGINE_AUTH_ENABLED=true
      - ENGINE_AUTH_API_KEY=${API_KEY}
      - ENGINE_LOGGING_LEVEL=info
      - ENGINE_LOGGING_FORMAT=json
    depends_on:
      - elasticsearch
    networks:
      - private-network
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Nginx Reverse Proxy (PUBLIC)
  nginx:
    image: nginx:alpine
    container_name: nginx-proxy
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./logs:/var/log/nginx
    depends_on:
      - searchgram-engine
    networks:
      - private-network
      - public-network

  # Elasticsearch (PRIVATE - not exposed)
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.17.0
    restart: always
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=true
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    volumes:
      - ./sg_data/elasticsearch:/usr/share/elasticsearch/data
    networks:
      - private-network

  # Optional: Fail2ban for brute force protection
  fail2ban:
    image: crazymax/fail2ban:latest
    container_name: fail2ban
    restart: always
    network_mode: "host"
    cap_add:
      - NET_ADMIN
      - NET_RAW
    volumes:
      - ./fail2ban:/data
      - ./logs:/var/log/nginx:ro

networks:
  private-network:
    internal: true  # No external access
  public-network:
    driver: bridge
```

### .env (Keep SECRET, add to .gitignore):

```bash
# API Authentication
API_KEY=your-strong-32-char-random-api-key-here

# Elasticsearch
ELASTIC_PASSWORD=your-strong-elasticsearch-password

# Cloudflare (if using tunnel)
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token
```

## 🚨 Incident Response Plan

If service is compromised:

1. **Immediate Actions**:
   ```bash
   # Stop service
   docker-compose down searchgram-engine

   # Block all traffic
   sudo ufw deny 443/tcp
   ```

2. **Investigation**:
   ```bash
   # Check logs
   grep -i "error\|unauthorized\|failed" /var/log/nginx/searchgram-access.log
   docker-compose logs searchgram-engine | grep -i error
   ```

3. **Remediation**:
   ```bash
   # Rotate API key
   openssl rand -hex 32 > new-api-key.txt

   # Update all clients
   # Restart service
   ```

4. **Recovery**:
   ```bash
   # Restore from backup if data compromised
   # Bring service back online
   docker-compose up -d
   ```

## 📚 Additional Resources

- **OWASP API Security Top 10**: https://owasp.org/www-project-api-security/
- **Let's Encrypt**: https://letsencrypt.org/
- **Cloudflare Tunnel**: https://www.cloudflare.com/products/tunnel/
- **Nginx Security**: https://nginx.org/en/docs/http/ngx_http_ssl_module.html
- **Go Security**: https://go.dev/doc/security/

## 💡 Best Practices Summary

| Practice | Why | How |
|----------|-----|-----|
| **Use HTTPS** | Encrypt traffic | Cloudflare or Let's Encrypt |
| **API Keys** | Authentication | Strong random keys, rotate regularly |
| **Rate Limiting** | Prevent abuse | Nginx or Cloudflare |
| **Firewall** | Block unwanted traffic | UFW or iptables |
| **Monitoring** | Detect issues early | Logs + health checks |
| **Updates** | Patch vulnerabilities | Regular security updates |
| **Backups** | Disaster recovery | Daily ES snapshots |
| **Isolation** | Limit blast radius | Private networks |

## 🎯 Recommended Setup for Most Users

**Cloudflare Tunnel + API Key Authentication**

1. Zero port forwarding (no firewall changes needed)
2. Built-in DDoS protection
3. Free SSL/TLS
4. Simple setup
5. Hide your server IP

This provides excellent security with minimal complexity!
