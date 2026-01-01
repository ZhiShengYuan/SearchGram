#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - sync_api.py
# HTTP API for sync task management (replaces file-based IPC)

__author__ = "Benny <benny.think@gmail.com>"

import logging
import threading
from datetime import datetime
from typing import Optional

from flask import Flask, jsonify, request

from .config_loader import get_config
from .jwt_auth import load_jwt_auth_from_config

# Flask app for sync API
app = Flask(__name__)

# Global sync manager reference (set by client.py)
_sync_manager = None

# Global JWT authenticator (initialized in init_sync_api)
_jwt_auth = None


def init_sync_api(sync_manager):
    """Initialize the sync API with a sync manager instance."""
    global _sync_manager, _jwt_auth
    _sync_manager = sync_manager

    # Initialize JWT authentication
    # This service receives requests from the bot, so:
    # - issuer: "userbot" (this service)
    # - audience: "userbot" (expected in incoming tokens)
    try:
        _jwt_auth = load_jwt_auth_from_config(issuer="userbot", audience="userbot")
        if _jwt_auth:
            logging.info("Sync API initialized with JWT authentication enabled")
        else:
            logging.warning("Sync API initialized WITHOUT authentication - not recommended for production")
    except Exception as e:
        logging.error(f"Failed to initialize JWT auth for sync API: {e}")
        # Continue without auth but log the error
        _jwt_auth = None

    logging.info("Sync API initialized")


def require_jwt_auth(allowed_issuers=None):
    """
    Decorator for Flask routes that require JWT authentication.

    Args:
        allowed_issuers: List of allowed issuer values (e.g., ["bot"])
    """
    def decorator(f):
        def wrapper(*args, **kwargs):
            # If JWT auth is not configured, allow request (backward compatibility)
            if not _jwt_auth:
                logging.debug(f"JWT auth not configured, allowing request to {request.path}")
                return f(*args, **kwargs)

            # Apply JWT authentication
            from functools import wraps
            @wraps(f)
            @_jwt_auth.flask_middleware(allowed_issuers=allowed_issuers)
            def authenticated_handler(*args, **kwargs):
                return f(*args, **kwargs)

            return authenticated_handler(*args, **kwargs)
        return wrapper
    return decorator


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/api/v1/sync', methods=['POST'])
@require_jwt_auth(allowed_issuers=["bot"])
def add_sync():
    """
    Add a chat to the sync queue.

    Request body:
    {
        "chat_id": -1001234567890,
        "requested_by": 123456789  # optional
    }

    Response:
    {
        "success": true,
        "chat_id": -1001234567890,
        "message": "Chat added to sync queue"
    }

    Authentication: Requires JWT with issuer "bot"
    """
    if not _sync_manager:
        return jsonify({"error": "Sync manager not initialized"}), 500

    data = request.get_json()
    if not data or 'chat_id' not in data:
        return jsonify({"error": "chat_id is required"}), 400

    chat_id = data['chat_id']

    try:
        # Add chat to sync queue
        added = _sync_manager.add_chat(chat_id)

        if added:
            # Start sync in background thread
            threading.Thread(
                target=_sync_manager.sync_chat,
                args=(chat_id,),
                daemon=True
            ).start()

            return jsonify({
                "success": True,
                "chat_id": chat_id,
                "message": "Chat added to sync queue and sync started"
            })
        else:
            # Already in queue
            progress = _sync_manager.get_progress(chat_id)
            return jsonify({
                "success": False,
                "chat_id": chat_id,
                "message": f"Chat already in queue with status: {progress.status if progress else 'unknown'}",
                "status": progress.status if progress else None
            }), 409

    except Exception as e:
        logging.error(f"Error adding chat to sync queue: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/sync/status', methods=['GET'])
@require_jwt_auth(allowed_issuers=["bot"])
def get_sync_status():
    """
    Get sync status for all tasks or a specific chat.

    Query parameters:
    - chat_id (optional): Filter by specific chat ID

    Response:
    {
        "timestamp": "2026-01-01T00:00:00",
        "chats": [
            {
                "chat_id": -1001234567890,
                "status": "in_progress",
                "progress_percent": 45.2,
                "synced_count": 4520,
                "total_count": 10000,
                "error_count": 0,
                "last_error": null,
                "started_at": "...",
                "completed_at": null,
                "last_checkpoint": "..."
            }
        ]
    }

    Authentication: Requires JWT with issuer "bot"
    """
    if not _sync_manager:
        return jsonify({"error": "Sync manager not initialized"}), 500

    try:
        chat_id_param = request.args.get('chat_id', type=int)

        if chat_id_param:
            # Get status for specific chat
            progress = _sync_manager.get_progress(chat_id_param)
            if not progress:
                return jsonify({"error": f"Chat {chat_id_param} not found in sync queue"}), 404

            return jsonify({
                "timestamp": datetime.utcnow().isoformat(),
                "chats": [progress.to_dict()]
            })
        else:
            # Get status for all chats
            all_progress = _sync_manager.get_all_progress()
            return jsonify({
                "timestamp": datetime.utcnow().isoformat(),
                "chats": [p.to_dict() for p in all_progress]
            })

    except Exception as e:
        logging.error(f"Error getting sync status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/sync/pause', methods=['POST'])
@require_jwt_auth(allowed_issuers=["bot"])
def pause_sync():
    """
    Pause a sync task.

    Request body:
    {
        "chat_id": -1001234567890
    }

    Response:
    {
        "success": true,
        "chat_id": -1001234567890,
        "message": "Sync paused"
    }

    Authentication: Requires JWT with issuer "bot"
    """
    if not _sync_manager:
        return jsonify({"error": "Sync manager not initialized"}), 500

    data = request.get_json()
    if not data or 'chat_id' not in data:
        return jsonify({"error": "chat_id is required"}), 400

    chat_id = data['chat_id']

    try:
        success = _sync_manager.pause_chat(chat_id)

        if success:
            return jsonify({
                "success": True,
                "chat_id": chat_id,
                "message": "Sync paused at next checkpoint"
            })
        else:
            return jsonify({
                "success": False,
                "chat_id": chat_id,
                "message": "Failed to pause (not found or invalid state)"
            }), 400

    except Exception as e:
        logging.error(f"Error pausing sync: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/sync/resume', methods=['POST'])
@require_jwt_auth(allowed_issuers=["bot"])
def resume_sync():
    """
    Resume a paused sync task.

    Request body:
    {
        "chat_id": -1001234567890
    }

    Response:
    {
        "success": true,
        "chat_id": -1001234567890,
        "message": "Sync resumed"
    }

    Authentication: Requires JWT with issuer "bot"
    """
    if not _sync_manager:
        return jsonify({"error": "Sync manager not initialized"}), 500

    data = request.get_json()
    if not data or 'chat_id' not in data:
        return jsonify({"error": "chat_id is required"}), 400

    chat_id = data['chat_id']

    try:
        success = _sync_manager.resume_chat(chat_id)

        if success:
            # Start sync in background thread
            threading.Thread(
                target=_sync_manager.sync_chat,
                args=(chat_id,),
                daemon=True
            ).start()

            return jsonify({
                "success": True,
                "chat_id": chat_id,
                "message": "Sync resumed from last checkpoint"
            })
        else:
            return jsonify({
                "success": False,
                "chat_id": chat_id,
                "message": "Failed to resume (not found or invalid state)"
            }), 400

    except Exception as e:
        logging.error(f"Error resuming sync: {e}")
        return jsonify({"error": str(e)}), 500


def run_sync_api(host: str = "127.0.0.1", port: int = 5000):
    """
    Run the sync API server.

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to listen on (default: 5000)
    """
    logging.info(f"Starting sync API server on {host}:{port}")
    # Disable Flask's default logger to avoid duplicate logs
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)

    app.run(host=host, port=port, debug=False, threaded=True)
