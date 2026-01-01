#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - jwt_auth.py
# JWT authentication for Python services

__author__ = "Benny <benny.think@gmail.com>"

import logging
import time
import uuid
from functools import wraps
from typing import Optional, List, Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import jwt
from flask import request, jsonify

from .config_loader import get_config


class JWTAuth:
    """
    JWT authentication using Ed25519 signing.

    Matches the Go service implementation for cross-service authentication.
    """

    def __init__(self, issuer: str, audience: str, public_key_data: Optional[bytes] = None,
                 private_key_data: Optional[bytes] = None, token_ttl: int = 300):
        """
        Initialize JWT authenticator.

        Args:
            issuer: Token issuer identifier (e.g., "bot", "userbot", "search")
            audience: Expected audience for incoming tokens (e.g., "userbot", "search")
            public_key_data: Ed25519 public key in PEM format (for verification)
            private_key_data: Ed25519 private key in PEM format (for signing)
            token_ttl: Token time-to-live in seconds (default: 300 = 5 minutes)
        """
        self.issuer = issuer
        self.audience = audience
        self.token_ttl = token_ttl

        # Load public key for verification
        self.public_key = None
        if public_key_data:
            try:
                self.public_key = serialization.load_pem_public_key(
                    public_key_data,
                    backend=default_backend()
                )
                logging.info(f"Loaded Ed25519 public key for JWT verification (issuer: {issuer})")
            except Exception as e:
                logging.error(f"Failed to load public key: {e}")
                raise

        # Load private key for signing
        self.private_key = None
        if private_key_data:
            try:
                self.private_key = serialization.load_pem_private_key(
                    private_key_data,
                    password=None,
                    backend=default_backend()
                )
                logging.info(f"Loaded Ed25519 private key for JWT signing (issuer: {issuer})")
            except Exception as e:
                logging.error(f"Failed to load private key: {e}")
                raise

    def generate_token(self, target_audience: Optional[str] = None) -> str:
        """
        Generate a JWT token for outbound requests.

        Args:
            target_audience: Target service audience (defaults to self.audience)

        Returns:
            JWT token string

        Raises:
            ValueError: If private key is not loaded
        """
        if not self.private_key:
            raise ValueError("Private key not loaded, cannot generate tokens")

        aud = target_audience or self.audience
        now = int(time.time())

        payload = {
            "iss": self.issuer,
            "aud": aud,
            "iat": now,
            "exp": now + self.token_ttl,
            "jti": str(uuid.uuid4())
        }

        token = jwt.encode(payload, self.private_key, algorithm="EdDSA")

        logging.debug(f"Generated JWT token: iss={self.issuer}, aud={aud}, jti={payload['jti']}")

        return token

    def verify_token(self, token: str, allowed_issuers: Optional[List[str]] = None) -> dict:
        """
        Verify a JWT token.

        Args:
            token: JWT token string
            allowed_issuers: List of allowed issuer values (e.g., ["bot", "userbot"])

        Returns:
            Decoded token payload (claims)

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        if not self.public_key:
            raise ValueError("Public key not loaded, cannot verify tokens")

        try:
            # Decode and verify token
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
                        f"Invalid issuer: {payload.get('iss')} not in allowed list {allowed_issuers}"
                    )

            logging.debug(f"Verified JWT token: iss={payload.get('iss')}, jti={payload.get('jti')}")

            return payload

        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token expired")
        except jwt.InvalidAudienceError:
            raise jwt.InvalidTokenError(f"Invalid audience: expected {self.audience}")
        except Exception as e:
            raise jwt.InvalidTokenError(f"Token verification failed: {str(e)}")

    def flask_middleware(self, allowed_issuers: Optional[List[str]] = None) -> Callable:
        """
        Create Flask decorator for JWT authentication.

        Args:
            allowed_issuers: List of allowed issuer values

        Returns:
            Decorator function for Flask routes

        Usage:
            @app.route('/protected')
            @jwt_auth.flask_middleware(allowed_issuers=["bot"])
            def protected_endpoint():
                return jsonify({"status": "ok"})
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Extract token from Authorization header
                auth_header = request.headers.get('Authorization')

                if not auth_header:
                    logging.warning(
                        f"Missing Authorization header: {request.method} {request.path} from {request.remote_addr}"
                    )
                    return jsonify({
                        "error": "Unauthorized",
                        "message": "Missing or invalid Authorization header"
                    }), 401

                # Check Bearer prefix
                if not auth_header.startswith('Bearer '):
                    logging.warning(
                        f"Invalid Authorization header format: {request.method} {request.path} from {request.remote_addr}"
                    )
                    return jsonify({
                        "error": "Unauthorized",
                        "message": "Invalid Authorization header format"
                    }), 401

                # Extract token
                token = auth_header[7:]  # Remove "Bearer " prefix

                # Verify token
                try:
                    claims = self.verify_token(token, allowed_issuers)
                    # Attach claims to Flask request context
                    request.jwt_claims = claims
                    request.jwt_issuer = claims.get("iss")
                except jwt.InvalidTokenError as e:
                    logging.warning(
                        f"JWT verification failed: {request.method} {request.path} from {request.remote_addr}: {str(e)}"
                    )
                    return jsonify({
                        "error": "Unauthorized",
                        "message": f"Invalid token: {str(e)}"
                    }), 401

                return f(*args, **kwargs)

            return decorated_function
        return decorator


def load_jwt_auth_from_config(issuer: str, audience: str) -> Optional[JWTAuth]:
    """
    Load JWT authenticator from unified config.

    Args:
        issuer: Token issuer identifier for this service
        audience: Expected audience for incoming tokens

    Returns:
        JWTAuth instance or None if JWT is disabled
    """
    config = get_config()

    # Check if JWT is enabled
    use_jwt = config.get_bool("auth.use_jwt", False)
    if not use_jwt:
        logging.warning("JWT authentication is DISABLED - this is not recommended for production")
        return None

    # Load public key (required for verification)
    public_key_data = None
    public_key_inline = config.get("auth.public_key_inline")
    public_key_path = config.get("auth.public_key_path")

    if public_key_inline:
        # Handle inline key (string or array)
        if isinstance(public_key_inline, list):
            public_key_data = "\n".join(public_key_inline).encode()
        else:
            # Replace \n literals with actual newlines
            public_key_data = public_key_inline.replace("\\n", "\n").encode()
    elif public_key_path:
        try:
            with open(public_key_path, 'rb') as f:
                public_key_data = f.read()
        except Exception as e:
            logging.error(f"Failed to read public key from {public_key_path}: {e}")
            raise

    # Load private key (optional, for signing)
    private_key_data = None
    private_key_inline = config.get("auth.private_key_inline")
    private_key_path = config.get("auth.private_key_path")

    if private_key_inline:
        # Handle inline key (string or array)
        if isinstance(private_key_inline, list):
            private_key_data = "\n".join(private_key_inline).encode()
        else:
            # Replace \n literals with actual newlines
            private_key_data = private_key_inline.replace("\\n", "\n").encode()
    elif private_key_path:
        try:
            with open(private_key_path, 'rb') as f:
                private_key_data = f.read()
        except Exception as e:
            logging.error(f"Failed to read private key from {private_key_path}: {e}")
            raise

    # Get token TTL
    token_ttl = config.get_int("auth.token_ttl", 300)

    # Create JWT authenticator
    jwt_auth = JWTAuth(
        issuer=issuer,
        audience=audience,
        public_key_data=public_key_data,
        private_key_data=private_key_data,
        token_ttl=token_ttl
    )

    logging.info(
        f"JWT auth initialized: issuer={issuer}, audience={audience}, "
        f"has_public={jwt_auth.public_key is not None}, "
        f"has_private={jwt_auth.private_key is not None}"
    )

    return jwt_auth
