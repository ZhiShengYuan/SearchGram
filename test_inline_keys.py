#!/usr/bin/env python3
# coding: utf-8

"""
Test inline key support for JWT authentication
"""

import json
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from searchgram.jwt_utils import JWTAuth, generate_ed25519_keypair


def test_inline_keys():
    """Test loading keys from inline config (single-line and JSON array)."""

    print("=" * 70)
    print("Testing Inline Key Support")
    print("=" * 70)

    # Step 1: Generate test keys
    print("\n1. Generating test keypair...")
    os.makedirs("test_keys", exist_ok=True)
    generate_ed25519_keypair("test_keys/private.key", "test_keys/public.key")
    print("   ✅ Generated keys")

    # Step 2: Read keys as strings
    with open("test_keys/private.key", "r") as f:
        private_pem = f.read()
    with open("test_keys/public.key", "r") as f:
        public_pem = f.read()

    # Step 3: Test single-line format (with \n)
    print("\n2. Testing single-line format (escaped \\n)...")
    private_single = private_pem.replace('\n', '\\n')
    public_single = public_pem.replace('\n', '\\n')

    auth1 = JWTAuth(
        issuer="test",
        audience="internal",
        private_key_inline=private_single,
        public_key_inline=public_single,
    )

    token1 = auth1.generate_token()
    claims1 = auth1.verify_token(token1)
    print(f"   ✅ Single-line format works: {token1[:50]}...")
    print(f"   ✅ Verified: iss={claims1['iss']}, aud={claims1['aud']}")

    # Step 4: Test JSON array format
    print("\n3. Testing JSON array format...")
    private_array = json.dumps(private_pem.split('\n'))
    public_array = json.dumps(public_pem.split('\n'))

    auth2 = JWTAuth(
        issuer="test",
        audience="internal",
        private_key_inline=private_array,
        public_key_inline=public_array,
    )

    token2 = auth2.generate_token()
    claims2 = auth2.verify_token(token2)
    print(f"   ✅ JSON array format works: {token2[:50]}...")
    print(f"   ✅ Verified: iss={claims2['iss']}, aud={claims2['aud']}")

    # Step 5: Test file path still works
    print("\n4. Testing file path format (backward compatibility)...")
    auth3 = JWTAuth(
        issuer="test",
        audience="internal",
        private_key_path="test_keys/private.key",
        public_key_path="test_keys/public.key",
    )

    token3 = auth3.generate_token()
    claims3 = auth3.verify_token(token3)
    print(f"   ✅ File path format works: {token3[:50]}...")
    print(f"   ✅ Verified: iss={claims3['iss']}, aud={claims3['aud']}")

    # Step 6: Test inline takes precedence over path
    print("\n5. Testing inline precedence over path...")
    auth4 = JWTAuth(
        issuer="test",
        audience="internal",
        private_key_inline=private_single,  # This should be used
        public_key_inline=public_single,     # This should be used
        private_key_path="nonexistent.key",  # This should be ignored
        public_key_path="nonexistent.key",   # This should be ignored
    )

    token4 = auth4.generate_token()
    claims4 = auth4.verify_token(token4)
    print(f"   ✅ Inline takes precedence: {token4[:50]}...")
    print(f"   ✅ Verified: iss={claims4['iss']}, aud={claims4['aud']}")

    # Cleanup
    print("\n6. Cleaning up test files...")
    os.remove("test_keys/private.key")
    os.remove("test_keys/public.key")
    os.rmdir("test_keys")
    print("   ✅ Cleaned up")

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

    print("\n# Format 2: Single-line string (good for env vars)")
    print('{')
    print('  "auth": {')
    print(f'    "public_key_inline": "{public_single[:60]}...",')
    print(f'    "private_key_inline": "{private_single[:60]}..."')
    print('  }')
    print('}')

    print("\n# Format 3: JSON array (good for readability in config)")
    print('{')
    print('  "auth": {')
    print('    "public_key_inline": [')
    print('      "-----BEGIN PUBLIC KEY-----",')
    print('      "MCowBQYDK2VwAyEA...",')
    print('      "-----END PUBLIC KEY-----"')
    print('    ],')
    print('    "private_key_inline": [')
    print('      "-----BEGIN PRIVATE KEY-----",')
    print('      "MC4CAQAwBQYDK2Vw...",')
    print('      "-----END PRIVATE KEY-----"')
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
