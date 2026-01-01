#!/usr/bin/env python3
"""
Diagnostic script to check JWT authentication configuration.

This script verifies that JWT authentication is properly configured
and can generate/verify tokens.
"""

import sys
from pathlib import Path

# Add searchgram to path
sys.path.insert(0, str(Path(__file__).parent))

from searchgram.config_loader import get_config

def main():
    print("=" * 70)
    print("JWT Authentication Configuration Diagnostic")
    print("=" * 70)

    config = get_config()

    # Check if JWT is enabled
    use_jwt = config.get_bool("auth.use_jwt", False)
    print(f"\n1. JWT Enabled: {use_jwt}")

    if not use_jwt:
        print("\n   ❌ JWT authentication is DISABLED")
        print("   ⚠️  This means all HTTP APIs are unprotected!")
        print("\n   To enable JWT, add to config.json:")
        print('   {')
        print('     "auth": {')
        print('       "use_jwt": true,')
        print('       "public_key_path": "./keys/public_key.pem",')
        print('       "private_key_path": "./keys/private_key.pem"')
        print('     }')
        print('   }')
        print("\n   Generate keys with:")
        print("   mkdir -p keys")
        print("   openssl genpkey -algorithm ed25519 -out keys/private_key.pem")
        print("   openssl pkey -in keys/private_key.pem -pubout -out keys/public_key.pem")
        return 1

    # Check key configuration
    print("\n2. Key Configuration:")

    public_key_path = config.get("auth.public_key_path")
    private_key_path = config.get("auth.private_key_path")
    public_key_inline = config.get("auth.public_key_inline")
    private_key_inline = config.get("auth.private_key_inline")

    if public_key_path:
        print(f"   Public key path: {public_key_path}")
        if Path(public_key_path).exists():
            print("   ✓ Public key file exists")
        else:
            print("   ❌ Public key file NOT FOUND")
            return 1
    elif public_key_inline:
        print("   ✓ Public key inline (configured)")
    else:
        print("   ❌ No public key configured")
        return 1

    if private_key_path:
        print(f"   Private key path: {private_key_path}")
        if Path(private_key_path).exists():
            print("   ✓ Private key file exists")
        else:
            print("   ❌ Private key file NOT FOUND")
            return 1
    elif private_key_inline:
        print("   ✓ Private key inline (configured)")
    else:
        print("   ❌ No private key configured")
        return 1

    # Test JWT auth initialization
    print("\n3. Testing JWT Auth Initialization:")

    try:
        from searchgram.jwt_auth import load_jwt_auth_from_config

        # Test bot -> userbot
        print("\n   Bot -> Userbot:")
        bot_auth = load_jwt_auth_from_config(issuer="bot", audience="userbot")
        if bot_auth:
            print(f"   ✓ Initialized successfully")
            print(f"     - Has private key: {bot_auth.private_key is not None}")
            print(f"     - Has public key: {bot_auth.public_key is not None}")

            if bot_auth.private_key:
                try:
                    token = bot_auth.generate_token()
                    print(f"     - Can generate tokens: ✓")
                    print(f"     - Token: {token[:50]}...")
                except Exception as e:
                    print(f"     - ❌ Failed to generate token: {e}")
                    return 1
            else:
                print("     - ❌ No private key for token generation")
                return 1
        else:
            print("   ❌ Failed to initialize")
            return 1

        # Test bot -> search
        print("\n   Bot -> Search:")
        search_auth = load_jwt_auth_from_config(issuer="bot", audience="search")
        if search_auth and search_auth.private_key:
            token = search_auth.generate_token()
            print(f"   ✓ Can generate tokens for search service")
        else:
            print("   ❌ Failed to initialize search auth")
            return 1

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Check service endpoints
    print("\n4. Service Endpoints:")
    userbot_url = config.get("services.userbot.base_url", "http://127.0.0.1:8082")
    search_url = config.get("services.search.base_url", "http://127.0.0.1:8080")
    print(f"   Userbot API: {userbot_url}")
    print(f"   Search API: {search_url}")

    print("\n" + "=" * 70)
    print("✅ JWT Configuration is VALID")
    print("=" * 70)
    print("\nAll services should now be able to authenticate with JWT.")
    print("Check the logs for:")
    print("  - 'JWT auth initialized' messages on startup")
    print("  - 'Generated JWT token' messages when making API calls")
    print("  - No '401 Unauthorized' errors")

    return 0

if __name__ == "__main__":
    sys.exit(main())
