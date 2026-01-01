# Deployment Guide - Fix 401 Unauthorized on /health

## What Changed

Fixed the Go search service to exclude `/health` and `/` endpoints from JWT authentication.

**Commits:**
- `cbadfe3` - Fix JWT config validation to accept inline keys
- `6dec7c2` - Remove emoji from startup messages for systemd compatibility
- `ca4047f` - Fix search service authentication and configuration
- `ec3ea15` - Add PyJWT and cryptography dependencies for JWT authentication

## Deployment Steps (On Remote Server)

### 1. Pull Latest Code

```bash
cd /path/to/SearchGram
git pull origin master
```

You should see these commits:
```
ec3ea15 Add PyJWT and cryptography dependencies for JWT authentication
ca4047f Fix search service authentication and configuration
6dec7c2 Remove emoji from startup messages for systemd compatibility
cbadfe3 Fix JWT config validation to accept inline keys
```

### 2. Install Python Dependencies

The Python services need PyJWT for JWT authentication:

```bash
# Activate your Python virtual environment if using one
source venv/bin/activate  # or wherever your venv is

# Install new dependencies
pip install -r requirements.txt
```

**Important:** If you see an error like `module 'jwt' has no attribute 'encode'`, you may need to uninstall the wrong `jwt` package:

```bash
pip uninstall jwt -y
pip install PyJWT==2.10.1 cryptography==44.0.0
```

### 3. Rebuild Go Service

```bash
cd searchgram-engine
go build -o searchgram-engine
```

Or if you have a Makefile:
```bash
make build
```

### 4. Restart Services

```bash
# Restart Go search service
sudo systemctl restart searchgram-engine.service

# Restart bot service (after search service is healthy)
sudo systemctl restart searchgram-bot.service

# Restart client service if needed
sudo systemctl restart searchgram-client.service
```

### 5. Verify Deployment

Check that the health endpoint is now accessible without authentication:

```bash
# This should return {"status":"healthy"} without authentication
curl https://search-api.zenkexi.com/health

# Check service status
sudo systemctl status searchgram-engine.service
sudo systemctl status searchgram-bot.service
```

### 6. Check Logs

```bash
# Search service logs
sudo journalctl -u searchgram-engine.service -f

# Bot service logs
sudo journalctl -u searchgram-bot.service -f
```

## What Was Fixed

### Before (❌ Broken):
```go
// JWT middleware applied to ALL routes
router.Use(jwtAuth.Middleware(allowedIssuers))

// Health endpoint (blocked by auth)
router.GET("/health", ...)
```

### After (✅ Fixed):
```go
// Public endpoints (no auth)
router.GET("/health", ...)
router.GET("/", ...)

// Protected API routes
v1 := router.Group("/api/v1")
v1.Use(jwtAuth.Middleware(allowedIssuers))  // Auth only on /api/v1/*
```

## Expected Behavior

After deployment:
- ✅ `/health` - Accessible without authentication
- ✅ `/` - Accessible without authentication
- 🔒 `/api/v1/*` - Requires JWT authentication
- ✅ Bot can verify connectivity during startup
- ✅ Services start without 401 errors

## Troubleshooting

### JWT Authentication Errors

If you see `AttributeError: module 'jwt' has no attribute 'encode'`:

1. **Check which jwt package is installed:**
   ```bash
   pip list | grep -i jwt
   ```

2. **Uninstall wrong package and install correct one:**
   ```bash
   pip uninstall jwt -y
   pip install PyJWT==2.10.1 cryptography==44.0.0
   ```

3. **Restart Python services:**
   ```bash
   sudo systemctl restart searchgram-bot.service
   sudo systemctl restart searchgram-client.service
   ```

### 401 Unauthorized Errors

If you still get 401 errors after deployment:

1. **Verify the service was rebuilt:**
   ```bash
   ls -lh searchgram-engine/searchgram-engine
   # Check modification time is recent
   ```

2. **Verify the service is running the new binary:**
   ```bash
   sudo systemctl status searchgram-engine.service
   # Check "Active: active (running) since [recent timestamp]"
   ```

3. **Check if old process is still running:**
   ```bash
   ps aux | grep searchgram-engine
   # Should only show the systemd-managed process
   ```

4. **Hard restart if needed:**
   ```bash
   sudo systemctl stop searchgram-engine.service
   sleep 2
   sudo systemctl start searchgram-engine.service
   ```

5. **Test health endpoint directly:**
   ```bash
   # Test on localhost (bypasses cloudflare)
   curl http://127.0.0.1:8080/health

   # Should return: {"status":"healthy"}
   ```

## Configuration Notes

The Go service now reads server configuration from both:
- `search_service.server.host` and `search_service.server.port`
- `http.listen` and `http.search_port` (takes precedence if set)

Make sure your config.json has the correct settings for your environment.
