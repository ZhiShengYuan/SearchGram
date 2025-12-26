# Installing HTTP/2 Dependencies

The HTTP/2 dependencies are included in the main `requirements.txt` file.

## Quick Install

Simply install all dependencies:

```bash
pip3 install -r requirements.txt
```

## HTTP/2 Specific Packages

The following packages are required for HTTP/2 support:

- **httpx==0.27.2** - Modern HTTP client with HTTP/2 and connection pooling
- **h2==4.1.0** - HTTP/2 protocol implementation

## Installation Methods

### Method 1: Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Method 2: User Install

```bash
pip3 install --user -r requirements.txt
```

### Method 3: System Install (if permitted)

```bash
pip3 install -r requirements.txt
```

### Method 4: Docker (No manual install needed)

```bash
make up  # Dependencies automatically installed in container
```

## Verify Installation

Check that httpx is installed correctly:

```bash
python3 -c "import httpx; print(f'httpx {httpx.__version__} with HTTP/2 support')"
```

Expected output:
```
httpx 0.28.1 with HTTP/2 support
```

## Build Go Service

After installing Python dependencies, rebuild the Go service:

```bash
cd searchgram-engine
go build -o searchgram-engine .
```

## Test HTTP/2

Run the test script to verify HTTP/2 is working:

```bash
python3 test_http2_standalone.py
```

Expected output:
```
✅ HTTP/2 is working!
```

## Troubleshooting

### httpx not found

If you get "ModuleNotFoundError: No module named 'httpx'":

1. Ensure you're using the correct Python environment
2. Re-run: `pip3 install httpx h2`
3. Check with: `pip3 list | grep httpx`

### Go build errors

If Go build fails with http2 import errors:

```bash
cd searchgram-engine
go mod tidy
go build
```

### Still using HTTP/1.1

If the client logs show HTTP/1.1 instead of HTTP/2:

1. Verify Go service is running: `curl http://127.0.0.1:8083/health`
2. Check Go service logs for "HTTP/2 support" message
3. Restart both client and bot processes

## More Information

See [HTTP2_IMPLEMENTATION.md](HTTP2_IMPLEMENTATION.md) for detailed documentation.
