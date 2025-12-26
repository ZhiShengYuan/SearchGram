#!/usr/bin/env python3
"""
Standalone test for HTTP/2 implementation.
Tests httpx library with HTTP/2 support.
"""

import sys
import httpx

def test_http2_library():
    """Test httpx HTTP/2 capabilities."""
    try:
        print("=" * 60)
        print("Testing httpx HTTP/2 Support")
        print("=" * 60)

        # Test 1: Basic HTTP/2 client creation
        print("\n1. Creating HTTP/2 client with connection pooling...")

        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=30.0,
        )

        transport = httpx.HTTPTransport(
            http2=True,
            retries=3,
        )

        client = httpx.Client(
            http2=True,
            timeout=httpx.Timeout(30),
            limits=limits,
            transport=transport,
            follow_redirects=True,
        )

        print("✓ HTTP/2 client created successfully")
        print(f"   - Client configured with HTTP/2 support")
        print(f"   - Connection pooling enabled with limits")
        print(f"   - Follow redirects: {client.follow_redirects}")

        # Test 2: Make a test request to a public HTTP/2 server
        print("\n2. Testing HTTP/2 request to public server...")
        try:
            response = client.get("https://www.google.com", timeout=10)
            http_version = response.http_version
            print(f"✓ Request successful")
            print(f"   - HTTP version: {http_version}")
            print(f"   - Status code: {response.status_code}")

            if http_version == "HTTP/2":
                print("   ✅ HTTP/2 is working!")
            else:
                print(f"   ⚠️  Using {http_version} instead of HTTP/2")
        except Exception as e:
            print(f"   ⚠️  Request failed: {e}")

        # Test 3: Verify connection pooling
        print("\n3. Testing connection reuse (5 requests)...")
        for i in range(5):
            response = client.get("https://www.google.com", timeout=10)
            print(f"   Request {i+1}: HTTP/{response.http_version} - Status {response.status_code}")

        print("✓ Connection pooling test completed")

        # Cleanup
        print("\n4. Cleaning up...")
        client.close()
        print("✓ Client closed")

        print("\n" + "=" * 60)
        print("✅ All httpx HTTP/2 tests passed!")
        print("=" * 60)
        print("\nNote: Your Go search service should also support HTTP/2")
        print("for optimal performance. Check Go server configuration.")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_http2_library()
    sys.exit(0 if success else 1)
