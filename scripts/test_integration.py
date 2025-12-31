#!/usr/bin/env python3
# coding: utf-8

"""
SearchGram Integration Test

Tests the complete HTTP/JWT integration between services.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from searchgram.jwt_utils import JWTAuth, generate_ed25519_keypair


def test_jwt_generation():
    """Test JWT key generation and token creation/verification."""
    print("\n1. Testing JWT Key Generation...")

    # Create test keys
    os.makedirs("test_keys", exist_ok=True)
    generate_ed25519_keypair("test_keys/private.key", "test_keys/public.key")

    # Test token generation
    auth = JWTAuth(
        issuer="bot",
        audience="internal",
        private_key_path="test_keys/private.key",
        public_key_path="test_keys/public.key",
    )

    token = auth.generate_token()
    print(f"   ✅ Generated JWT token: {token[:50]}...")

    # Test verification
    claims = auth.verify_token(token)
    print(f"   ✅ Verified claims: iss={claims['iss']}, aud={claims['aud']}")

    # Cleanup
    os.remove("test_keys/private.key")
    os.remove("test_keys/public.key")
    os.rmdir("test_keys")

    return auth, token


def test_message_store():
    """Test message store operations."""
    print("\n2. Testing Message Store...")

    from searchgram.message_store import MessageStore

    store = MessageStore("test_queue.db")

    # Enqueue messages
    msg1 = store.enqueue("bot", "userbot", "command", {"action": "test"})
    print(f"   ✅ Enqueued message: {msg1['id']}")

    # Dequeue messages
    result = store.dequeue("userbot", limit=10)
    assert len(result["items"]) == 1, "Should have 1 message"
    print(f"   ✅ Dequeued {len(result['items'])} message(s)")

    # Acknowledge message
    store.acknowledge(result["items"][0]["id"])
    print(f"   ✅ Acknowledged message")

    # Verify empty
    result = store.dequeue("userbot", limit=10)
    assert len(result["items"]) == 0, "Should have 0 messages"
    print(f"   ✅ Queue is empty after acknowledgment")

    # Cleanup
    store.close()
    os.remove("test_queue.db")


def test_http_server():
    """Test HTTP server endpoints (requires manual server setup)."""
    print("\n3. Testing HTTP Server Endpoints...")
    print("   ⚠️  This requires services to be running manually")
    print("   Skipping automated test - see manual testing instructions below")


def print_manual_test_instructions():
    """Print manual testing instructions."""
    print("\n" + "=" * 70)
    print("MANUAL TESTING INSTRUCTIONS")
    print("=" * 70)

    print("\n1. Generate Keys:")
    print("   python scripts/generate_keys.py")

    print("\n2. Update config.json:")
    print("""   {
     "auth": {
       "use_jwt": true,
       "issuer": "bot",  // or "userbot" or "search"
       "audience": "internal",
       "public_key_path": "keys/public.key",
       "private_key_path": "keys/private.key"
     },
     "http": {
       "listen": "127.0.0.1",
       "bot_port": 8081,
       "userbot_port": 8082
     }
   }""")

    print("\n3. Update searchgram-engine/config.yaml:")
    print("""   auth:
     use_jwt: true
     issuer: "search"
     audience: "internal"
     public_key_path: "keys/public.key"
     private_key_path: "keys/private.key"
     token_ttl: 300""")

    print("\n4. Start services:")
    print("   Terminal 1: python searchgram/client.py   # Userbot + HTTP server")
    print("   Terminal 2: python searchgram/bot.py      # Bot + HTTP server")
    print("   Terminal 3: ./searchgram-engine/searchgram-engine  # Go search service")

    print("\n5. Test endpoints with curl:")

    print("\n   a) Generate a test token:")
    print("      python -c 'from searchgram.jwt_utils import JWTAuth; \\")
    print('                 auth = JWTAuth("bot", "internal", "keys/private.key", "keys/public.key"); \\')
    print("                 print(auth.generate_token())'")

    print("\n   b) Test /v1/status endpoints:")
    print("      export TOKEN=<token-from-above>")
    print('      curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8081/v1/status')
    print('      curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8082/v1/status')
    print('      curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/v1/status')

    print("\n   c) Test message relay:")
    print('      # Send message from bot to userbot')
    print('      curl -X POST -H "Authorization: Bearer $TOKEN" \\')
    print('           -H "Content-Type: application/json" \\')
    print('           -d \'{"to": "userbot", "type": "command", "payload": {"action": "test"}}\' \\')
    print('           http://127.0.0.1:8081/v1/messages')

    print("\n      # Poll messages for userbot")
    print('      curl -H "Authorization: Bearer $TOKEN" \\')
    print('           "http://127.0.0.1:8082/v1/messages?to=userbot&limit=10"')

    print("\n   d) Test search with real timing:")
    print('      curl -X POST -H "Authorization: Bearer $TOKEN" \\')
    print('           -H "Content-Type: application/json" \\')
    print('           -d \'{"keyword": "test", "page": 1, "page_size": 10}\' \\')
    print('           http://127.0.0.1:8080/api/v1/search')
    print("      # Check response includes 'took_ms' field with real backend timing")

    print("\n6. Verify:")
    print("   - All endpoints require Authorization header (401 without it)")
    print("   - Search response includes 'took_ms' field (real timing from backend)")
    print("   - Messages can be relayed between services")
    print("   - All services report correct status and uptime")

    print("\n" + "=" * 70)


def main():
    print("=" * 70)
    print("SearchGram Integration Test")
    print("=" * 70)

    try:
        # Run automated tests
        test_jwt_generation()
        test_message_store()
        test_http_server()

        print("\n✅ Automated tests passed!")

        # Print manual test instructions
        print_manual_test_instructions()

        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
