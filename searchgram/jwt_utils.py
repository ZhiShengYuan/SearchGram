#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - jwt_utils.py
# JWT authentication utilities for Python services

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
import time
import uuid
from functools import wraps
from pathlib import Path
from typing import Dict, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from flask import Request, jsonify
import jwt as pyjwt


class JWTAuth:
    """JWT authentication manager using Ed25519."""

    def __init__(
        self,
        issuer: str,
        audience: str = "internal",
        private_key_path: Optional[str] = None,
        public_key_path: Optional[str] = None,
        private_key_inline: Optional[str] = None,
        public_key_inline: Optional[str] = None,
        token_ttl: int = 300,  # 5 minutes default
    ):
        """
        Initialize JWT authentication.

        Args:
            issuer: Service name ("bot", "userbot", "search")
            audience: Target audience (default: "internal")
            private_key_path: Path to Ed25519 private key (PEM format)
            public_key_path: Path to Ed25519 public key (PEM format)
            private_key_inline: Inline private key (PEM as single-line string or JSON array)
            public_key_inline: Inline public key (PEM as single-line string or JSON array)
            token_ttl: Token TTL in seconds (default: 300)
        """
        self.issuer = issuer
        self.audience = audience
        self.token_ttl = token_ttl
        self.algorithm = "EdDSA"

        # Load keys
        self.private_key = None
        self.public_key = None

        # Private key: inline takes precedence over path
        if private_key_inline:
            self.private_key = self._load_private_key_inline(private_key_inline)
        elif private_key_path:
            self.private_key = self._load_private_key(private_key_path)

        # Public key: inline takes precedence over path
        if public_key_inline:
            self.public_key = self._load_public_key_inline(public_key_inline)
        elif public_key_path:
            self.public_key = self._load_public_key(public_key_path)

        logging.info(
            f"JWT auth initialized: issuer={issuer}, audience={audience}, "
            f"has_private={self.private_key is not None}, "
            f"has_public={self.public_key is not None}"
        )

    def _load_private_key(self, path: str) -> ed25519.Ed25519PrivateKey:
        """Load Ed25519 private key from PEM file."""
        try:
            with open(path, "rb") as f:
                key_data = f.read()
            private_key = serialization.load_pem_private_key(
                key_data,
                password=None,
            )
            if not isinstance(private_key, ed25519.Ed25519PrivateKey):
                raise ValueError("Key is not an Ed25519 private key")
            logging.info(f"Loaded Ed25519 private key from {path}")
            return private_key
        except Exception as e:
            logging.error(f"Failed to load private key from {path}: {e}")
            raise

    def _load_public_key(self, path: str) -> ed25519.Ed25519PublicKey:
        """Load Ed25519 public key from PEM file."""
        try:
            with open(path, "rb") as f:
                key_data = f.read()
            public_key = serialization.load_pem_public_key(key_data)
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                raise ValueError("Key is not an Ed25519 public key")
            logging.info(f"Loaded Ed25519 public key from {path}")
            return public_key
        except Exception as e:
            logging.error(f"Failed to load public key from {path}: {e}")
            raise

    def _load_private_key_inline(self, key_data: str) -> ed25519.Ed25519PrivateKey:
        """
        Load Ed25519 private key from inline string.

        Args:
            key_data: PEM key as single-line string or JSON array

        Returns:
            Ed25519 private key
        """
        try:
            # Parse key data (handle JSON array or single-line string)
            pem_data = self._parse_inline_key(key_data)

            # Load private key
            private_key = serialization.load_pem_private_key(
                pem_data,
                password=None,
            )
            if not isinstance(private_key, ed25519.Ed25519PrivateKey):
                raise ValueError("Key is not an Ed25519 private key")
            logging.info("Loaded Ed25519 private key from inline config")
            return private_key
        except Exception as e:
            logging.error(f"Failed to load inline private key: {e}")
            raise

    def _load_public_key_inline(self, key_data: str) -> ed25519.Ed25519PublicKey:
        """
        Load Ed25519 public key from inline string.

        Args:
            key_data: PEM key as single-line string or JSON array

        Returns:
            Ed25519 public key
        """
        try:
            # Parse key data (handle JSON array or single-line string)
            pem_data = self._parse_inline_key(key_data)

            # Load public key
            public_key = serialization.load_pem_public_key(pem_data)
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                raise ValueError("Key is not an Ed25519 public key")
            logging.info("Loaded Ed25519 public key from inline config")
            return public_key
        except Exception as e:
            logging.error(f"Failed to load inline public key: {e}")
            raise

    def _parse_inline_key(self, key_data: str) -> bytes:
        """
        Parse inline key data from config.

        Supports two formats:
        1. Single-line PEM: "-----BEGIN PRIVATE KEY-----\\nMIGH...\\n-----END PRIVATE KEY-----"
        2. JSON array: ["-----BEGIN PRIVATE KEY-----", "MIGHAgE...", "-----END PRIVATE KEY-----"]

        Args:
            key_data: Key data as string or JSON array

        Returns:
            PEM data as bytes
        """
        # Try to parse as JSON array first
        try:
            lines = json.loads(key_data)
            if isinstance(lines, list):
                # Join array lines with newlines
                pem_str = "\n".join(lines)
                return pem_str.encode('utf-8')
        except (json.JSONDecodeError, TypeError):
            pass

        # Treat as single-line string with \n escape sequences
        # Replace literal \n with actual newlines
        pem_str = key_data.replace('\\n', '\n')
        return pem_str.encode('utf-8')

    def generate_token(
        self,
        target_audience: Optional[str] = None,
        additional_claims: Optional[Dict] = None,
    ) -> str:
        """
        Generate a JWT token for outbound requests.

        Args:
            target_audience: Override default audience
            additional_claims: Additional claims to include

        Returns:
            JWT token string
        """
        if not self.private_key:
            raise ValueError("Private key not loaded, cannot generate tokens")

        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": target_audience or self.audience,
            "iat": now,
            "exp": now + self.token_ttl,
            "jti": str(uuid.uuid4()),
        }

        if additional_claims:
            claims.update(additional_claims)

        # Convert private key to PEM bytes for PyJWT
        private_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        token = pyjwt.encode(
            claims,
            private_pem,
            algorithm=self.algorithm,
        )

        logging.debug(f"Generated JWT: iss={claims['iss']}, aud={claims['aud']}, jti={claims['jti']}")
        return token

    def verify_token(self, token: str, allowed_issuers: Optional[list] = None) -> Dict:
        """
        Verify a JWT token from inbound requests.

        Args:
            token: JWT token string
            allowed_issuers: List of allowed issuers (default: any)

        Returns:
            Decoded claims dict

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        if not self.public_key:
            raise ValueError("Public key not loaded, cannot verify tokens")

        # Convert public key to PEM bytes for PyJWT
        public_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        try:
            # Verify token
            claims = pyjwt.decode(
                token,
                public_pem,
                algorithms=[self.algorithm],
                audience=self.audience,
                options={
                    "require": ["iss", "aud", "iat", "exp"],
                    "verify_exp": True,
                    "verify_aud": True,
                },
            )

            # Check issuer if specified
            if allowed_issuers and claims.get("iss") not in allowed_issuers:
                raise pyjwt.InvalidTokenError(
                    f"Invalid issuer: {claims.get('iss')} not in {allowed_issuers}"
                )

            logging.debug(f"Verified JWT: iss={claims['iss']}, jti={claims.get('jti')}")
            return claims

        except pyjwt.ExpiredSignatureError as e:
            logging.warning(f"JWT token expired: {e}")
            raise
        except pyjwt.InvalidAudienceError as e:
            logging.warning(f"JWT invalid audience: {e}")
            raise
        except pyjwt.InvalidTokenError as e:
            logging.warning(f"JWT verification failed: {e}")
            raise

    def flask_middleware(self, allowed_issuers: Optional[list] = None):
        """
        Flask decorator for JWT authentication.

        Args:
            allowed_issuers: List of allowed issuers

        Returns:
            Decorator function
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                from flask import request

                # Extract token from Authorization header
                auth_header = request.headers.get("Authorization", "")
                if not auth_header.startswith("Bearer "):
                    return jsonify({
                        "error": "Unauthorized",
                        "message": "Missing or invalid Authorization header"
                    }), 401

                token = auth_header[7:]  # Remove "Bearer " prefix

                try:
                    # Verify token
                    claims = self.verify_token(token, allowed_issuers)
                    # Attach claims to request context
                    request.jwt_claims = claims
                    return f(*args, **kwargs)

                except pyjwt.ExpiredSignatureError:
                    return jsonify({
                        "error": "Unauthorized",
                        "message": "Token expired"
                    }), 401
                except pyjwt.InvalidTokenError as e:
                    return jsonify({
                        "error": "Unauthorized",
                        "message": f"Invalid token: {str(e)}"
                    }), 401

            return decorated_function
        return decorator


def generate_ed25519_keypair(private_key_path: str, public_key_path: str):
    """
    Generate an Ed25519 keypair and save to files.

    Args:
        private_key_path: Path to save private key (PEM format)
        public_key_path: Path to save public key (PEM format)
    """
    # Generate keypair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Write to files
    Path(private_key_path).parent.mkdir(parents=True, exist_ok=True)
    Path(public_key_path).parent.mkdir(parents=True, exist_ok=True)

    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    Path(private_key_path).chmod(0o600)  # Restrict permissions

    with open(public_key_path, "wb") as f:
        f.write(public_pem)
    Path(public_key_path).chmod(0o644)

    logging.info(f"Generated Ed25519 keypair:")
    logging.info(f"  Private key: {private_key_path} (mode 600)")
    logging.info(f"  Public key: {public_key_path} (mode 644)")


if __name__ == "__main__":
    # Test key generation
    logging.basicConfig(level=logging.INFO)

    print("Generating Ed25519 keypair...")
    generate_ed25519_keypair("keys/private.key", "keys/public.key")

    print("\nTesting JWT generation and verification...")
    auth = JWTAuth(
        issuer="test",
        audience="internal",
        private_key_path="keys/private.key",
        public_key_path="keys/public.key",
    )

    token = auth.generate_token()
    print(f"Generated token: {token[:50]}...")

    claims = auth.verify_token(token)
    print(f"Verified claims: {json.dumps(claims, indent=2)}")

    print("\n✅ JWT utilities test passed!")
