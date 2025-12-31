#!/usr/bin/env python3
# coding: utf-8

"""
Test inline key support for JWT authentication (standalone - no config.json needed)
"""

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Import only what we need
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import jwt as pyjwt


def generate_test_keys():
    """Generate test Ed25519 keypair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')

    return private_pem, public_pem


def parse_inline_key(key_data: str) -> bytes:
    """Parse inline key (same logic as jwt_utils.py)."""
    # Try JSON array first
    try:
        lines = json.loads(key_data)
        if isinstance(lines, list):
            pem_str = "\n".join(lines)
            return pem_str.encode('utf-8')
    except (json.JSONDecodeError, TypeError):
        pass

    # Single-line with escaped \n
    pem_str = key_data.replace('\\n', '\n')
    return pem_str.encode('utf-8')


def test_inline_keys():
    """Test loading keys from inline config."""

    print("=" * 70)
    print("Testing Inline Key Support (Standalone)")
    print("=" * 70)

    # Generate test keys
    print("\n1. Generating test keypair...")
    private_pem, public_pem = generate_test_keys()
    print("   ✅ Generated Ed25519 keypair")

    # Test 1: Single-line format
    print("\n2. Testing single-line format (escaped \\n)...")
    private_single = private_pem.replace('\n', '\\n')
    public_single = public_pem.replace('\n', '\\n')

    # Parse and load
    private_bytes = parse_inline_key(private_single)
    public_bytes = parse_inline_key(public_single)

    private_key = serialization.load_pem_private_key(private_bytes, password=None)
    public_key = serialization.load_pem_public_key(public_bytes)

    # Generate and verify token
    token = pyjwt.encode({"test": "data"}, private_bytes, algorithm="EdDSA")
    decoded = pyjwt.decode(token, public_bytes, algorithms=["EdDSA"])

    print(f"   ✅ Single-line format works!")
    print(f"   Token: {token[:50]}...")
    print(f"   Decoded: {decoded}")

    # Test 2: JSON array format
    print("\n3. Testing JSON array format...")
    private_array = json.dumps(private_pem.split('\n'))
    public_array = json.dumps(public_pem.split('\n'))

    # Parse and load
    private_bytes2 = parse_inline_key(private_array)
    public_bytes2 = parse_inline_key(public_array)

    private_key2 = serialization.load_pem_private_key(private_bytes2, password=None)
    public_key2 = serialization.load_pem_public_key(public_bytes2)

    # Generate and verify token
    token2 = pyjwt.encode({"test": "data"}, private_bytes2, algorithm="EdDSA")
    decoded2 = pyjwt.decode(token2, public_bytes2, algorithms=["EdDSA"])

    print(f"   ✅ JSON array format works!")
    print(f"   Token: {token2[:50]}...")
    print(f"   Decoded: {decoded2}")

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)

    print("\n📝 Example config.json formats:")
    print("\n# Format 1: File paths (recommended for local dev)")
    print('{')
    print('  "auth": {')
    print('    "public_key_path": "keys/public.key",')
    print('    "private_key_path": "keys/private.key"')
    print('  }')
    print('}')

    print("\n# Format 2: Single-line string (good for env vars/Docker secrets)")
    print('{')
    print('  "auth": {')
    print(f'    "public_key_inline": "{public_single[:60]}...",')
    print(f'    "private_key_inline": "{private_single[:60]}..."')
    print('  }')
    print('}')

    print("\n# Format 3: JSON array (most readable in config file)")
    print('{')
    print('  "auth": {')
    print('    "public_key_inline": [')
    for i, line in enumerate(public_pem.split('\n')[:3]):
        if i < 2:
            print(f'      "{line}",')
        else:
            print(f'      "{line}..."')
            break
    print('    ],')
    print('    "private_key_inline": [')
    for i, line in enumerate(private_pem.split('\n')[:3]):
        if i < 2:
            print(f'      "{line}",')
        else:
            print(f'      "{line}..."')
            break
    print('    ]')
    print('  }')
    print('}')
    print()


if __name__ == "__main__":
    try:
        test_inline_keys()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
