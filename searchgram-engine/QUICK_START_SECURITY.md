# Quick Start: Secure Internet Deployment

This guide gets your SearchGram Engine securely exposed to the internet in 5 minutes.

## 🚀 Fastest Method: Cloudflare Tunnel

**No port forwarding, no SSL setup, built-in DDoS protection!**

### Prerequisites
- Domain name (or use Cloudflare's free subdomain)
- Cloudflare account (free)

### Steps

**1. Install Cloudflare Tunnel**
```bash
# Linux
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# macOS
brew install cloudflare/cloudflare/cloudflared
```

**2. Authenticate**
```bash
cloudflared tunnel login
```
Opens browser → Login to Cloudflare → Select domain

**3. Create Tunnel**
```bash
cloudflared tunnel create searchgram
```
Save the tunnel ID shown

**4. Configure Tunnel**
```bash
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

Paste this:
```yaml
tunnel: YOUR-TUNNEL-ID-HERE
credentials-file: /root/.cloudflared/YOUR-TUNNEL-ID.json

ingress:
  - hostname: searchgram-api.yourdomain.com
    service: http://localhost:8080
  - service: http_status:404
```

**5. Route DNS**
```bash
cloudflared tunnel route dns searchgram searchgram-api.yourdomain.com
```

**6. Enable Authentication in Go Service**
```bash
cd searchgram-engine

# Create .env file
cp .env.example .env

# Generate strong API key
openssl rand -hex 32

# Edit .env and add the API key
nano .env
```

**7. Start Everything**
```bash
# Terminal 1: Start Go service with auth
docker-compose -f docker-compose.production.yml up -d searchgram-engine elasticsearch

# Terminal 2: Start tunnel
cloudflared tunnel run searchgram
```

**8. Test**
```bash
# Without API key (should fail)
curl https://searchgram-api.yourdomain.com/api/v1/ping

# With API key (should succeed)
curl -H "X-API-Key: YOUR-API-KEY" https://searchgram-api.yourdomain.com/api/v1/ping
```

**9. Install Tunnel as Service** (optional, for auto-start)
```bash
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

**Done!** ✅

Your service is now:
- ✅ Accessible via HTTPS (automatic SSL)
- ✅ Protected by Cloudflare DDoS protection
- ✅ Authenticated with API key
- ✅ Not exposing your server IP

---

## 🔧 Alternative: Traditional Setup (Nginx + Let's Encrypt)

**For those who want full control**

### Prerequisites
- VPS/Server with public IP
- Domain name pointing to your server
- Ports 80 and 443 open

### Automated Setup

```bash
cd searchgram-engine
./setup-production.sh
```

This script will:
1. Generate secure API keys
2. Configure domain and email
3. Set up firewall (UFW)
4. Obtain SSL certificate (Let's Encrypt)
5. Start all services with Docker Compose

### Manual Setup

**1. Generate Secrets**
```bash
cd searchgram-engine
cp .env.example .env

# Generate API key
echo "API_KEY=$(openssl rand -hex 32)" >> .env

# Generate Elasticsearch password
echo "ELASTIC_PASSWORD=$(openssl rand -base64 24)" >> .env
```

**2. Configure Nginx**
```bash
# Edit nginx.conf and replace:
# - searchgram-api.yourdomain.com with your domain
nano nginx.conf
```

**3. Firewall**
```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw deny 8080/tcp  # Block direct Go service access
sudo ufw enable
```

**4. SSL Certificate**
```bash
# Install certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d searchgram-api.yourdomain.com

# Link certificates
mkdir -p ssl
ln -s /etc/letsencrypt/live/searchgram-api.yourdomain.com/fullchain.pem ssl/
ln -s /etc/letsencrypt/live/searchgram-api.yourdomain.com/privkey.pem ssl/
```

**5. Start Services**
```bash
docker-compose -f docker-compose.production.yml up -d
```

**6. Test**
```bash
curl -H "X-API-Key: YOUR-API-KEY" https://searchgram-api.yourdomain.com/api/v1/ping
```

---

## 🔐 Security Checklist

Before going live:

- [ ] **API Key Set**: Strong random key (32+ characters)
- [ ] **HTTPS Enabled**: SSL certificate installed
- [ ] **Firewall Active**: Port 8080 blocked from internet
- [ ] **Rate Limiting**: Configured in Nginx or Cloudflare
- [ ] **.env Secure**: Not committed to git, permissions 600
- [ ] **Auth Working**: Test without API key (should fail)
- [ ] **Health Check**: `/health` endpoint responds
- [ ] **Monitoring**: Set up uptime monitoring
- [ ] **Backups**: Elasticsearch data backed up
- [ ] **Updates**: System packages up to date

## 📊 Quick Test Suite

```bash
# 1. Health check (no auth needed)
curl https://searchgram-api.yourdomain.com/health

# 2. Ping without API key (should fail with 401)
curl https://searchgram-api.yourdomain.com/api/v1/ping

# 3. Ping with API key (should succeed)
curl -H "X-API-Key: YOUR-API-KEY" https://searchgram-api.yourdomain.com/api/v1/ping

# 4. Search test
curl -X POST https://searchgram-api.yourdomain.com/api/v1/search \
  -H "X-API-Key: YOUR-API-KEY" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "test", "page": 1}'

# 5. Rate limit test (should get 429 after limit)
for i in {1..50}; do
  curl -H "X-API-Key: YOUR-API-KEY" https://searchgram-api.yourdomain.com/api/v1/ping &
done
```

## 🐍 Update Python Bot Config

After deploying, update your Python bot's `config.json`:

```json
{
  "search_engine": {
    "engine": "http",
    "http": {
      "base_url": "https://searchgram-api.yourdomain.com",
      "api_key": "YOUR-API-KEY-FROM-DOT-ENV",
      "timeout": 30,
      "max_retries": 3
    }
  }
}
```

## 🔄 Maintenance

**View Logs**:
```bash
docker-compose -f docker-compose.production.yml logs -f
```

**Restart Service**:
```bash
docker-compose -f docker-compose.production.yml restart searchgram-engine
```

**Update Service**:
```bash
git pull
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d
```

**Renew SSL** (automatic with certbot, but manual if needed):
```bash
sudo certbot renew
docker-compose -f docker-compose.production.yml restart nginx
```

## ⚠️ Troubleshooting

**Service not accessible**:
- Check firewall: `sudo ufw status`
- Check DNS: `dig searchgram-api.yourdomain.com`
- Check logs: `docker-compose logs nginx`

**Authentication failing**:
- Verify API key in `.env`
- Check request header: `X-API-Key: your-key`
- View Go service logs: `docker-compose logs searchgram-engine`

**SSL errors**:
- Check certificate: `sudo certbot certificates`
- Verify nginx config: `nginx -t`
- Check nginx logs: `tail -f logs/nginx/searchgram-error.log`

## 📚 More Information

- Full security guide: [SECURITY_DEPLOYMENT.md](SECURITY_DEPLOYMENT.md)
- Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- Migration: [../GO_SERVICE_MIGRATION.md](../GO_SERVICE_MIGRATION.md)

## 💡 Recommendations

| Use Case | Recommended Method | Why |
|----------|-------------------|-----|
| **Personal/Small** | Cloudflare Tunnel | Free, easy, no port forwarding |
| **Medium** | Nginx + Let's Encrypt | Full control, self-hosted |
| **Enterprise** | API Gateway + WAF | Advanced features, compliance |

**Start with Cloudflare Tunnel** - it's the easiest and most secure option for most users!
