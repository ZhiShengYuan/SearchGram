# Running SearchGram

Quick guide for running SearchGram client and bot.

## Prerequisites

1. **Configuration file**: Create `config.json` from example
   ```bash
   cp config.example.json config.json
   # Edit config.json with your credentials
   ```

2. **Dependencies installed**:
   ```bash
   pip3 install -r requirements.txt
   # or use the install script
   ./install_deps.sh
   ```

3. **Go search service running** (if using http engine):
   ```bash
   cd searchgram-engine
   go build
   ./searchgram-engine
   ```

## Running Methods

### Method 1: Using Runner Scripts (Recommended)

The easiest way to run SearchGram:

```bash
# Terminal 1: Client (userbot)
python3 run_client.py

# Terminal 2: Bot (search interface)
python3 run_bot.py
```

**Benefits**:
- ✅ Simple commands
- ✅ Handles imports correctly
- ✅ Works from project root
- ✅ Executable scripts (`chmod +x`)

### Method 2: As Python Module

Run as a Python module from project root:

```bash
# Terminal 1: Client
python3 -m searchgram.client

# Terminal 2: Bot
python3 -m searchgram.bot
```

**Benefits**:
- ✅ Standard Python module execution
- ✅ No additional scripts needed
- ✅ Works with virtual environments

### Method 3: Direct Execution (Not Recommended)

**This will NOT work**:
```bash
cd searchgram
python3 client.py  # ❌ ModuleNotFoundError
```

**Why it fails**:
- Relative imports require package context
- `from .config_loader import ENGINE` doesn't work
- Python doesn't recognize `searchgram` as package

## Import Structure

SearchGram uses **relative imports** for proper package structure:

```python
# In searchgram/__init__.py
from .config_loader import ENGINE
from .http_engine import SearchEngine

# In searchgram/client.py
from __init__ import SearchEngine  # This imports from searchgram/__init__.py
```

**This requires running from project root as a module**.

## Troubleshooting

### Error: `ModuleNotFoundError: No module named 'searchgram'`

**Problem**: Running script directly from `searchgram/` directory

**Solution**: Run from project root using one of the recommended methods:
```bash
cd /path/to/SearchGram
python3 run_client.py
```

### Error: `ModuleNotFoundError: No module named 'config_loader'`

**Problem**: Old absolute imports or wrong working directory

**Solution**:
1. Ensure you're in project root
2. Use `python3 run_client.py` or `python3 -m searchgram.client`
3. Check `searchgram/__init__.py` uses relative imports

### Error: `Configuration file not found: config.json`

**Problem**: No config.json in current directory

**Solution**:
```bash
cp config.example.json config.json
# Edit with your settings
vim config.json
```

### Client connects but doesn't index

**Problem**: Go search service not running or not accessible

**Solution**:
```bash
# Start Go service
cd searchgram-engine
./searchgram-engine

# Verify it's running
curl http://localhost:8080/health
```

## Virtual Environment

For production, use a virtual environment:

```bash
# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run
python3 run_client.py
```

## Docker

For Docker deployments, see `Docker.md`:

```bash
# Start all services
make up

# Logs
docker-compose logs -f client
docker-compose logs -f bot
```

## First-Time Setup

Complete setup process:

```bash
# 1. Clone repository
git clone <repo_url>
cd SearchGram

# 2. Install dependencies
./install_deps.sh

# 3. Create configuration
cp config.example.json config.json
vim config.json  # Add your credentials

# 4. Build Go service
cd searchgram-engine
go build
cd ..

# 5. Login to client (first time)
python3 run_client.py
# Enter phone number, verification code
# Press Ctrl+C after login

# 6. Start Go service (Terminal 1)
cd searchgram-engine && ./searchgram-engine

# 7. Start client (Terminal 2)
python3 run_client.py

# 8. Start bot (Terminal 3)
python3 run_bot.py
```

## Process Management

### Using systemd (Linux)

Create service files for automatic startup:

```ini
# /etc/systemd/system/searchgram-engine.service
[Unit]
Description=SearchGram Go Search Engine
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/SearchGram/searchgram-engine
ExecStart=/path/to/SearchGram/searchgram-engine/searchgram-engine
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/searchgram-client.service
[Unit]
Description=SearchGram Client (Userbot)
After=network.target searchgram-engine.service
Requires=searchgram-engine.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/SearchGram
ExecStart=/usr/bin/python3 run_client.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/searchgram-bot.service
[Unit]
Description=SearchGram Bot (Search Interface)
After=network.target searchgram-engine.service
Requires=searchgram-engine.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/SearchGram
ExecStart=/usr/bin/python3 run_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable searchgram-engine searchgram-client searchgram-bot
sudo systemctl start searchgram-engine searchgram-client searchgram-bot
```

### Using screen (Simple)

```bash
# Start Go service
screen -S searchgram-engine
cd searchgram-engine && ./searchgram-engine
# Ctrl+A D to detach

# Start client
screen -S searchgram-client
python3 run_client.py
# Ctrl+A D to detach

# Start bot
screen -S searchgram-bot
python3 run_bot.py
# Ctrl+A D to detach

# Reattach
screen -r searchgram-client
```

## Summary

**Recommended commands**:
```bash
# From project root
python3 run_client.py   # Client
python3 run_bot.py      # Bot
```

**Alternative**:
```bash
# From project root
python3 -m searchgram.client   # Client
python3 -m searchgram.bot      # Bot
```

**Don't use**:
```bash
cd searchgram
python3 client.py   # ❌ Will fail with import error
```

---

For more details, see:
- [README.md](README.md) - General documentation
- [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) - Configuration guide
- [Docker.md](Docker.md) - Docker deployment
