#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - bot_api.py
# HTTP API for bot operations (e.g., sending files to owner)

__author__ = "Benny <benny.think@gmail.com>"

import base64
import logging
import threading
from datetime import datetime
from io import BytesIO

from flask import Flask, jsonify, request

from .config_loader import OWNER_ID, get_config
from .jwt_auth import load_jwt_auth_from_config

# Flask app for bot API
app = Flask(__name__)

# Global bot client reference (set by bot.py)
_bot_client = None

# Global JWT authenticator (initialized in init_bot_api)
_jwt_auth = None


def init_bot_api(bot_client):
    """Initialize the bot API with a bot client instance."""
    global _bot_client, _jwt_auth
    _bot_client = bot_client

    # Initialize JWT authentication
    # This service receives requests from the userbot, so:
    # - issuer: "bot" (this service)
    # - audience: "bot" (expected in incoming tokens)
    try:
        _jwt_auth = load_jwt_auth_from_config(issuer="bot", audience="bot")
        if _jwt_auth:
            logging.info("Bot API initialized with JWT authentication enabled")
        else:
            logging.warning("Bot API initialized WITHOUT authentication - not recommended for production")
    except Exception as e:
        logging.error(f"Failed to initialize JWT auth for bot API: {e}")
        # Continue without auth but log the error
        _jwt_auth = None

    logging.info("Bot API initialized")


def require_jwt_auth(allowed_issuers=None):
    """
    Decorator for Flask routes that require JWT authentication.

    Args:
        allowed_issuers: List of allowed issuer values (e.g., ["userbot"])
    """
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # If JWT auth is not configured, allow request (backward compatibility)
            if not _jwt_auth:
                logging.debug(f"JWT auth not configured, allowing request to {request.path}")
                return f(*args, **kwargs)

            # Apply JWT authentication manually
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
                import jwt as jwt_module
                claims = _jwt_auth.verify_token(token, allowed_issuers)
                # Attach claims to Flask request context
                request.jwt_claims = claims
                request.jwt_issuer = claims.get("iss")
            except jwt_module.InvalidTokenError as e:
                logging.warning(
                    f"JWT verification failed: {request.method} {request.path} from {request.remote_addr}: {str(e)}"
                )
                return jsonify({
                    "error": "Unauthorized",
                    "message": f"Invalid token: {str(e)}"
                }), 401

            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/api/v1/send_file', methods=['POST'])
@require_jwt_auth(allowed_issuers=["userbot"])
def send_file():
    """
    Send a file to the bot owner.

    Request body:
    {
        "file_data": "base64_encoded_file_content",
        "file_name": "example.json",
        "caption": "Optional caption",
        "recipient_id": 123456789  // Optional, defaults to OWNER_ID
    }

    Response:
    {
        "success": true,
        "message": "File sent successfully",
        "message_id": 12345
    }

    Authentication: Requires JWT with issuer "userbot"
    """
    if not _bot_client:
        return jsonify({"error": "Bot client not initialized"}), 500

    data = request.get_json()
    if not data or 'file_data' not in data or 'file_name' not in data:
        return jsonify({"error": "file_data and file_name are required"}), 400

    file_data_b64 = data['file_data']
    file_name = data['file_name']
    caption = data.get('caption', '')
    recipient_id = data.get('recipient_id', OWNER_ID)

    try:
        # Decode base64 file data
        file_bytes = base64.b64decode(file_data_b64)

        # Create BytesIO file
        file_obj = BytesIO(file_bytes)
        file_obj.name = file_name

        logging.info(f"Bot API: Sending file '{file_name}' ({len(file_bytes)} bytes) to {recipient_id}")

        # Send file using bot client
        sent_message = _bot_client.send_document(
            recipient_id,
            file_obj,
            caption=caption,
            file_name=file_name
        )

        logging.info(f"Bot API: Successfully sent file to {recipient_id}, message_id={sent_message.id}")

        return jsonify({
            "success": True,
            "message": "File sent successfully",
            "message_id": sent_message.id
        })

    except Exception as e:
        logging.error(f"Error sending file via bot API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def run_bot_api(host: str = "127.0.0.1", port: int = 8081):
    """
    Run the bot API server.

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to listen on (default: 8081)
    """
    logging.info(f"Starting bot API server on {host}:{port}")
    # Disable Flask's default logger to avoid duplicate logs
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)

    app.run(host=host, port=port, debug=False, threaded=True)
