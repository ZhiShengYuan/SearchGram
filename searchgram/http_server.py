#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - http_server.py
# RESTful HTTP server for bot/userbot inter-service communication

__author__ = "Benny <benny.think@gmail.com>"

import logging
import os
import platform
import socket
import threading
import time
from datetime import datetime
from typing import Dict, Optional

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from .jwt_utils import JWTAuth
from .message_store import MessageStore


class SearchGramHTTPServer:
    """
    RESTful HTTP server for inter-service communication.

    Provides:
    - GET /v1/status: Health/status endpoint
    - POST /v1/messages: Send messages to other services
    - GET /v1/messages: Poll messages for this service
    - DELETE /v1/messages/<id>: Acknowledge message
    """

    def __init__(
        self,
        service_name: str,
        listen_host: str,
        listen_port: int,
        jwt_auth: JWTAuth,
        message_store: MessageStore,
        allowed_issuers: Optional[list] = None,
        get_message_count_callback: Optional[callable] = None,
    ):
        """
        Initialize HTTP server.

        Args:
            service_name: Service name ("bot" or "userbot")
            listen_host: Host to listen on (default: "127.0.0.1")
            listen_port: Port to listen on
            jwt_auth: JWT authentication instance
            message_store: Message store instance
            allowed_issuers: List of allowed JWT issuers (default: ["bot", "userbot", "search"])
            get_message_count_callback: Optional callback to get indexed message count
        """
        self.service_name = service_name
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.jwt_auth = jwt_auth
        self.message_store = message_store
        self.allowed_issuers = allowed_issuers or ["bot", "userbot", "search"]
        self.get_message_count_callback = get_message_count_callback

        self.start_time = time.time()
        self.app = Flask(f"searchgram-{service_name}")
        self.server = None
        self.server_thread = None

        # Setup routes
        self._setup_routes()

        logging.info(
            f"HTTP server initialized: {service_name} on {listen_host}:{listen_port}"
        )

    def _setup_routes(self):
        """Setup Flask routes with JWT authentication."""

        @self.app.route("/v1/status", methods=["GET"])
        @self.jwt_auth.flask_middleware(self.allowed_issuers)
        def status():
            """
            GET /v1/status

            Health check and status endpoint.

            Returns:
                {
                    "service": "bot|userbot",
                    "status": "ok",
                    "hostname": "...",
                    "uptime_seconds": <int>,
                    "message_index_total": <int>,
                    "timestamp": "<RFC3339>"
                }
            """
            uptime_seconds = int(time.time() - self.start_time)

            # Get message count
            message_count = 0
            if self.get_message_count_callback:
                try:
                    message_count = self.get_message_count_callback()
                except Exception as e:
                    logging.error(f"Failed to get message count: {e}")

            return jsonify({
                "service": self.service_name,
                "status": "ok",
                "hostname": socket.gethostname(),
                "uptime_seconds": uptime_seconds,
                "message_index_total": message_count,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }), 200

        @self.app.route("/v1/messages", methods=["POST"])
        @self.jwt_auth.flask_middleware(self.allowed_issuers)
        def post_message():
            """
            POST /v1/messages

            Send a message to another service.

            Request body:
                {
                    "to": "bot|userbot",
                    "type": "command|info|event",
                    "payload": { ... }
                }

            Returns:
                {
                    "id": "<uuid>",
                    "created_at": "<RFC3339>"
                }
            """
            data = request.get_json()

            # Validate request
            if not data:
                return jsonify({"error": "Bad Request", "message": "Missing JSON body"}), 400

            to_service = data.get("to")
            message_type = data.get("type")
            payload = data.get("payload")

            if not to_service:
                return jsonify({"error": "Bad Request", "message": "Missing 'to' field"}), 400

            if to_service not in ["bot", "userbot", "search"]:
                return jsonify(
                    {"error": "Bad Request", "message": f"Invalid 'to' value: {to_service}"}
                ), 400

            if not message_type:
                return jsonify({"error": "Bad Request", "message": "Missing 'type' field"}), 400

            if payload is None:
                return jsonify({"error": "Bad Request", "message": "Missing 'payload' field"}), 400

            if not isinstance(payload, dict):
                return jsonify(
                    {"error": "Bad Request", "message": "'payload' must be a JSON object"}
                ), 400

            # Enqueue message
            try:
                result = self.message_store.enqueue(
                    from_service=self.service_name,
                    to_service=to_service,
                    message_type=message_type,
                    payload=payload,
                )
                return jsonify(result), 201

            except Exception as e:
                logging.error(f"Failed to enqueue message: {e}")
                return jsonify({
                    "error": "Internal Server Error",
                    "message": "Failed to enqueue message"
                }), 500

        @self.app.route("/v1/messages", methods=["GET"])
        @self.jwt_auth.flask_middleware(self.allowed_issuers)
        def get_messages():
            """
            GET /v1/messages?to=<service>&after_id=<optional>&limit=<n>

            Poll messages for a service.

            Query parameters:
                - to: Target service ("bot", "userbot", "search")
                - after_id: Optional message ID to fetch messages after
                - limit: Maximum number of messages (default: 10, max: 100)

            Returns:
                {
                    "items": [
                        {
                            "id": "...",
                            "from": "bot|userbot",
                            "to": "bot|userbot",
                            "type": "...",
                            "payload": { ... },
                            "created_at": "<RFC3339>"
                        }
                    ],
                    "next_after_id": "<id or null>"
                }
            """
            to_service = request.args.get("to")
            after_id = request.args.get("after_id")
            limit = request.args.get("limit", "10")

            # Validate parameters
            if not to_service:
                return jsonify({"error": "Bad Request", "message": "Missing 'to' parameter"}), 400

            if to_service not in ["bot", "userbot", "search"]:
                return jsonify(
                    {"error": "Bad Request", "message": f"Invalid 'to' value: {to_service}"}
                ), 400

            try:
                limit = int(limit)
                if limit < 1 or limit > 100:
                    limit = 10
            except ValueError:
                limit = 10

            # Dequeue messages
            try:
                result = self.message_store.dequeue(
                    to_service=to_service,
                    after_id=after_id,
                    limit=limit,
                )
                return jsonify(result), 200

            except Exception as e:
                logging.error(f"Failed to dequeue messages: {e}")
                return jsonify({
                    "error": "Internal Server Error",
                    "message": "Failed to retrieve messages"
                }), 500

        @self.app.route("/v1/messages/<message_id>", methods=["DELETE"])
        @self.jwt_auth.flask_middleware(self.allowed_issuers)
        def delete_message(message_id):
            """
            DELETE /v1/messages/<id>

            Acknowledge/delete a message.

            Returns:
                {
                    "success": true
                }
            """
            try:
                deleted = self.message_store.acknowledge(message_id)

                if not deleted:
                    return jsonify({
                        "error": "Not Found",
                        "message": f"Message {message_id} not found"
                    }), 404

                return jsonify({"success": True}), 200

            except Exception as e:
                logging.error(f"Failed to delete message: {e}")
                return jsonify({
                    "error": "Internal Server Error",
                    "message": "Failed to delete message"
                }), 500

        # Error handlers
        @self.app.errorhandler(404)
        def not_found(e):
            return jsonify({"error": "Not Found", "message": "Endpoint not found"}), 404

        @self.app.errorhandler(500)
        def internal_error(e):
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    def start(self):
        """Start HTTP server in background thread."""
        if self.server_thread and self.server_thread.is_alive():
            logging.warning("HTTP server already running")
            return

        # Create server
        self.server = make_server(
            self.listen_host,
            self.listen_port,
            self.app,
            threaded=True,
        )

        # Start server in background thread
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
            name=f"http-server-{self.service_name}",
        )
        self.server_thread.start()

        logging.info(
            f"✅ HTTP server started: http://{self.listen_host}:{self.listen_port} "
            f"(service={self.service_name})"
        )

    def stop(self):
        """Stop HTTP server."""
        if self.server:
            logging.info(f"Stopping HTTP server: {self.service_name}")
            self.server.shutdown()
            self.server = None
            self.server_thread = None


if __name__ == "__main__":
    # Test HTTP server
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("Testing HTTP server...")

    # Create test JWT auth
    from .jwt_utils import generate_ed25519_keypair

    os.makedirs("keys", exist_ok=True)
    generate_ed25519_keypair("keys/test_private.key", "keys/test_public.key")

    jwt_auth = JWTAuth(
        issuer="bot",
        audience="internal",
        private_key_path="keys/test_private.key",
        public_key_path="keys/test_public.key",
    )

    # Create message store
    message_store = MessageStore("test_queue.db")

    # Create server
    server = SearchGramHTTPServer(
        service_name="bot",
        listen_host="127.0.0.1",
        listen_port=8081,
        jwt_auth=jwt_auth,
        message_store=message_store,
    )

    server.start()

    print("\n✅ HTTP server running on http://127.0.0.1:8081")
    print("   Try: curl -H 'Authorization: Bearer <token>' http://127.0.0.1:8081/v1/status")
    print("\nPress Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop()

    # Cleanup
    os.remove("test_queue.db")
    os.remove("keys/test_private.key")
    os.remove("keys/test_public.key")
    os.rmdir("keys")

    print("✅ Test complete!")
