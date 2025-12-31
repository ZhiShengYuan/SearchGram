# Inline Keys Configuration Guide

The JWT authentication system now supports **three ways** to provide keys:

## 1. File Paths (Recommended for Local Development)

```json
{
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "audience": "internal",
    "public_key_path": "keys/public.key",
    "private_key_path": "keys/private.key",
    "token_ttl": 300
  }
}
```

**Pros:**
- Clean configuration
- Easy to manage separate files
- Standard approach

**Cons:**
- Requires separate key files
- Not ideal for containerized environments

---

## 2. Single-Line String (Good for Environment Variables)

```json
{
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "audience": "internal",
    "public_key_inline": "-----BEGIN PUBLIC KEY-----\\nMCowBQYDK2VwAyEAXYZ...\\n-----END PUBLIC KEY-----",
    "private_key_inline": "-----BEGIN PRIVATE KEY-----\\nMC4CAQAwBQYDK2VwBCI...\\n-----END PRIVATE KEY-----",
    "token_ttl": 300
  }
}
```

**How to generate:**
```bash
# Generate keys
python scripts/generate_keys.py

# Convert to single-line format
cat keys/public.key | tr '\n' '\\n'
cat keys/private.key | tr '\n' '\\n'
```

Or programmatically:
```python
with open('keys/public.key', 'r') as f:
    public_single_line = f.read().replace('\n', '\\n')
print(public_single_line)
```

**Pros:**
- No external files needed
- Easy to pass via environment variables
- Works well in Docker/Kubernetes secrets

**Cons:**
- Less readable in config file

---

## 3. JSON Array (Most Readable in Config)

```json
{
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "audience": "internal",
    "public_key_inline": [
      "-----BEGIN PUBLIC KEY-----",
      "MCowBQYDK2VwAyEAXYZ1234567890abcdefghijklmnopqrstuvwxyz",
      "-----END PUBLIC KEY-----"
    ],
    "private_key_inline": [
      "-----BEGIN PRIVATE KEY-----",
      "MC4CAQAwBQYDK2VwBCIEIA1234567890abcdefghijklmnopqrstuv",
      "wxyz1234567890abcdefg=",
      "-----END PRIVATE KEY-----"
    ],
    "token_ttl": 300
  }
}
```

**How to generate:**
```python
import json

with open('keys/public.key', 'r') as f:
    public_lines = f.read().split('\n')
    # Remove empty lines
    public_lines = [line for line in public_lines if line]
    print(json.dumps(public_lines, indent=2))
```

**Pros:**
- Most readable format
- Easy to edit manually
- Clear structure

**Cons:**
- Slightly more verbose

---

## Priority Order

When both formats are provided, **inline takes precedence**:

```json
{
  "auth": {
    "public_key_inline": "...",    // This is used
    "public_key_path": "keys/public.key",  // This is ignored

    "private_key_inline": "...",   // This is used
    "private_key_path": "keys/private.key" // This is ignored
  }
}
```

This allows you to:
- Override file-based keys with inline keys
- Mix and match (inline for public, path for private, etc.)

---

## Use Cases

### Local Development
Use **file paths** - easier to manage and regenerate:
```json
{
  "auth": {
    "public_key_path": "keys/public.key",
    "private_key_path": "keys/private.key"
  }
}
```

### Docker/Kubernetes
Use **single-line inline** via environment variables:

```yaml
# docker-compose.yml
environment:
  - AUTH_PUBLIC_KEY_INLINE=${PUBLIC_KEY}
  - AUTH_PRIVATE_KEY_INLINE=${PRIVATE_KEY}
```

```bash
# .env file
PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\\nMCowBQ...\\n-----END PUBLIC KEY-----"
PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\\nMC4CA...\\n-----END PRIVATE KEY-----"
```

### Config File Deployment
Use **JSON array** - clearest to read and edit:
```json
{
  "auth": {
    "public_key_inline": [
      "-----BEGIN PUBLIC KEY-----",
      "MCowBQYDK2VwAyEA...",
      "-----END PUBLIC KEY-----"
    ]
  }
}
```

---

## Implementation Details

The `jwt_utils.py` module handles all three formats transparently:

```python
from searchgram.jwt_utils import JWTAuth

# Any of these work:
auth1 = JWTAuth(
    issuer="bot",
    public_key_path="keys/public.key",
    private_key_path="keys/private.key"
)

auth2 = JWTAuth(
    issuer="bot",
    public_key_inline="-----BEGIN PUBLIC KEY-----\\n...",
    private_key_inline="-----BEGIN PRIVATE KEY-----\\n..."
)

auth3 = JWTAuth(
    issuer="bot",
    public_key_inline='["-----BEGIN PUBLIC KEY-----", "...", "-----END PUBLIC KEY-----"]',
    private_key_inline='["-----BEGIN PRIVATE KEY-----", "...", "-----END PRIVATE KEY-----"]'
)
```

The parser automatically detects the format:
1. Tries to parse as JSON array
2. Falls back to single-line string with `\\n` escapes
3. Converts to proper PEM format

---

## Security Notes

**Single-line format:**
- Use `\\n` (escaped backslash-n), not actual newlines
- Entire key must be one JSON string

**JSON array format:**
- Each line is a separate array element
- No `\\n` needed - actual array structure

**Both formats:**
- Keep private keys secret
- Use environment variables or secret managers for production
- Don't commit keys to version control
- Rotate keys regularly

---

## Migration

If you have existing file-based keys:

```bash
# Convert to single-line
PUBLIC_INLINE=$(cat keys/public.key | python3 -c "import sys; print(repr(sys.stdin.read())[1:-1])")
PRIVATE_INLINE=$(cat keys/private.key | python3 -c "import sys; print(repr(sys.stdin.read())[1:-1])")

# Add to config.json
echo "public_key_inline: $PUBLIC_INLINE"
echo "private_key_inline: $PRIVATE_INLINE"
```

Or convert to JSON array:
```bash
python3 << 'EOF'
import json
with open('keys/public.key') as f:
    lines = [l.rstrip() for l in f if l.strip()]
print(json.dumps({"public_key_inline": lines}, indent=2))
EOF
```

---

## Examples in Config

### Minimal (file paths)
```json
{
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "public_key_path": "keys/public.key",
    "private_key_path": "keys/private.key"
  }
}
```

### Production (inline single-line)
```json
{
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "public_key_inline": "${PUBLIC_KEY_FROM_ENV}",
    "private_key_inline": "${PRIVATE_KEY_FROM_ENV}"
  }
}
```

### Readable (JSON array)
```json
{
  "auth": {
    "use_jwt": true,
    "issuer": "bot",
    "public_key_inline": [
      "-----BEGIN PUBLIC KEY-----",
      "MCowBQYDK2VwAyEAXYZ1234567890abcdefg",
      "-----END PUBLIC KEY-----"
    ],
    "private_key_inline": [
      "-----BEGIN PRIVATE KEY-----",
      "MC4CAQAwBQYDK2VwBCIEIA1234567890abc",
      "defghijklmnopqrstuvwxyz1234567890ab",
      "-----END PRIVATE KEY-----"
    ]
  }
}
```

---

## Testing

To test inline key loading:
```bash
python3 test_inline_keys_standalone.py
```

This verifies all three formats work correctly.
