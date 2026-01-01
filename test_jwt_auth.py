#!/usr/bin/env python3
"""
Test script for JWT authentication.

This script tests the JWT authentication flow between services.
Does not require config.json - tests JWT module in isolation.
"""

import sys
import tempfile
from pathlib import Path

# We'll import JWT classes directly without config_loader
# to avoid needing config.json for this test

# Import only what we need for testing
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend
import time
import uuid


class JWTAuth:
    """
    Minimal JWT authentication class for testing (same logic as searchgram/jwt_auth.py).
    """

    def __init__(self, issuer: str, audience: str, public_key_data=None,
                 private_key_data=None, token_ttl: int = 300):
        self.issuer = issuer
        self.audience = audience
        self.token_ttl = token_ttl

        # Load public key for verification
        self.public_key = None
        if public_key_data:
            self.public_key = serialization.load_pem_public_key(
                public_key_data,
                backend=default_backend()
            )

        # Load private key for signing
        self.private_key = None
        if private_key_data:
            self.private_key = serialization.load_pem_private_key(
                private_key_data,
                password=None,
                backend=default_backend()
            )

    def generate_token(self, target_audience=None):
        """Generate a JWT token."""
        if not self.private_key:
            raise ValueError("Private key not loaded")

        aud = target_audience or self.audience
        now = int(time.time())

        payload = {
            "iss": self.issuer,
            "aud": aud,
            "iat": now,
            "exp": now + self.token_ttl,
            "jti": str(uuid.uuid4())
        }

        return jwt.encode(payload, self.private_key, algorithm="EdDSA")

    def verify_token(self, token: str, allowed_issuers=None):
        """Verify a JWT token."""
        if not self.public_key:
            raise ValueError("Public key not loaded")

        # Decode and verify
        payload = jwt.decode(
            token,
            self.public_key,
            algorithms=["EdDSA"],
            audience=self.audience,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True
            }
        )

        # Verify issuer if specified
        if allowed_issuers:
            if payload.get("iss") not in allowed_issuers:
                raise jwt.InvalidTokenError(
                    f"Invalid issuer: {payload.get('iss')} not in {allowed_issuers}"
                )

        return payload


def generate_test_keys():
    """Generate Ed25519 key pair for testing."""
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization

    # Generate private key
    private_key = ed25519.Ed25519PrivateKey.generate()

    # Serialize private key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Extract public key and serialize to PEM
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem, public_pem


def test_jwt_basic():
    """Test basic JWT token generation and verification."""
    print("=" * 60)
    print("Test 1: Basic JWT Token Generation and Verification")
    print("=" * 60)

    # Generate test keys
    private_pem, public_pem = generate_test_keys()

    # Create bot authenticator (generates tokens)
    bot_auth = JWTAuth(
        issuer="bot",
        audience="search",
        private_key_data=private_pem,
        public_key_data=public_pem,
        token_ttl=300
    )

    # Create search service authenticator (verifies tokens)
    search_auth = JWTAuth(
        issuer="search",
        audience="search",
        public_key_data=public_pem,
        token_ttl=300
    )

    # Generate token from bot
    print("\n1. Bot generates token for search service...")
    token = bot_auth.generate_token()
    print(f"   Token generated: {token[:50]}...")

    # Verify token at search service
    print("\n2. Search service verifies token...")
    try:
        claims = search_auth.verify_token(token, allowed_issuers=["bot"])
        print(f"   ✓ Token verified successfully!")
        print(f"   Issuer: {claims.get('iss')}")
        print(f"   Audience: {claims.get('aud')}")
        print(f"   Token ID: {claims.get('jti')}")
    except Exception as e:
        print(f"   ✗ Verification failed: {e}")
        return False

    print("\n✓ Test 1 PASSED\n")
    return True


def test_jwt_cross_service():
    """Test JWT authentication between multiple services."""
    print("=" * 60)
    print("Test 2: Cross-Service Authentication")
    print("=" * 60)

    # Generate shared keys
    private_pem, public_pem = generate_test_keys()

    # Create authenticators for each service
    bot_auth = JWTAuth(
        issuer="bot",
        audience="userbot",
        private_key_data=private_pem,
        public_key_data=public_pem
    )

    userbot_auth = JWTAuth(
        issuer="userbot",
        audience="userbot",
        private_key_data=private_pem,
        public_key_data=public_pem
    )

    # Bot calls userbot sync API
    print("\n1. Bot -> Userbot: Add sync task")
    token = bot_auth.generate_token()
    print(f"   Bot generates token: {token[:50]}...")

    try:
        claims = userbot_auth.verify_token(token, allowed_issuers=["bot"])
        print(f"   ✓ Userbot verified token from bot")
        print(f"   Issuer: {claims.get('iss')}")
    except Exception as e:
        print(f"   ✗ Verification failed: {e}")
        return False

    # Userbot calls search service
    print("\n2. Userbot -> Search: Index messages")
    userbot_to_search = JWTAuth(
        issuer="userbot",
        audience="search",
        private_key_data=private_pem,
        public_key_data=public_pem
    )

    search_auth = JWTAuth(
        issuer="search",
        audience="search",
        public_key_data=public_pem
    )

    token2 = userbot_to_search.generate_token()
    print(f"   Userbot generates token: {token2[:50]}...")

    try:
        claims2 = search_auth.verify_token(token2, allowed_issuers=["userbot"])
        print(f"   ✓ Search service verified token from userbot")
        print(f"   Issuer: {claims2.get('iss')}")
    except Exception as e:
        print(f"   ✗ Verification failed: {e}")
        return False

    print("\n✓ Test 2 PASSED\n")
    return True


def test_jwt_invalid_issuer():
    """Test that tokens with invalid issuers are rejected."""
    print("=" * 60)
    print("Test 3: Invalid Issuer Rejection")
    print("=" * 60)

    private_pem, public_pem = generate_test_keys()

    # Create authenticator for unauthorized service
    attacker_auth = JWTAuth(
        issuer="attacker",
        audience="search",
        private_key_data=private_pem,
        public_key_data=public_pem
    )

    # Create search service authenticator
    search_auth = JWTAuth(
        issuer="search",
        audience="search",
        public_key_data=public_pem
    )

    # Attacker tries to generate token
    print("\n1. Attacker generates token with issuer 'attacker'...")
    token = attacker_auth.generate_token()
    print(f"   Token: {token[:50]}...")

    # Search service verifies (should fail)
    print("\n2. Search service verifies token (expecting bot/userbot)...")
    try:
        claims = search_auth.verify_token(token, allowed_issuers=["bot", "userbot"])
        print(f"   ✗ Token was accepted (SECURITY ISSUE!)")
        return False
    except Exception as e:
        print(f"   ✓ Token rejected as expected: {e}")

    print("\n✓ Test 3 PASSED\n")
    return True


def test_jwt_expired_token():
    """Test that expired tokens are rejected."""
    print("=" * 60)
    print("Test 4: Expired Token Rejection")
    print("=" * 60)

    import time

    private_pem, public_pem = generate_test_keys()

    # Create authenticators with very short TTL
    bot_auth = JWTAuth(
        issuer="bot",
        audience="search",
        private_key_data=private_pem,
        public_key_data=public_pem,
        token_ttl=1  # 1 second
    )

    search_auth = JWTAuth(
        issuer="search",
        audience="search",
        public_key_data=public_pem
    )

    # Generate token
    print("\n1. Bot generates token with 1 second TTL...")
    token = bot_auth.generate_token()
    print(f"   Token: {token[:50]}...")

    # Verify immediately (should work)
    print("\n2. Verify immediately...")
    try:
        claims = search_auth.verify_token(token, allowed_issuers=["bot"])
        print(f"   ✓ Token verified (not expired yet)")
    except Exception as e:
        print(f"   ✗ Unexpected failure: {e}")
        return False

    # Wait for token to expire
    print("\n3. Waiting 2 seconds for token to expire...")
    time.sleep(2)

    # Verify again (should fail)
    print("\n4. Verify expired token...")
    try:
        claims = search_auth.verify_token(token, allowed_issuers=["bot"])
        print(f"   ✗ Expired token was accepted (SECURITY ISSUE!)")
        return False
    except Exception as e:
        print(f"   ✓ Expired token rejected as expected: {e}")

    print("\n✓ Test 4 PASSED\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("JWT Authentication Test Suite")
    print("=" * 60 + "\n")

    tests = [
        test_jwt_basic,
        test_jwt_cross_service,
        test_jwt_invalid_issuer,
        test_jwt_expired_token,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
