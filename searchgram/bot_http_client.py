#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - bot_http_client.py
# HTTP client for calling bot API from userbot

__author__ = "Benny <benny.think@gmail.com>"

import base64
import logging
from typing import Dict

import httpx

from .jwt_auth import load_jwt_auth_from_config


class BotHTTPClient:
    """
    HTTP client for bot API operations.

    Communicates with the bot API server running on the bot process.
    Includes JWT authentication support.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8081", timeout: int = 30):
        """
        Initialize bot HTTP client.

        Args:
            base_url: Base URL of bot API server (default: http://127.0.0.1:8081)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, http2=True)

        # Initialize JWT authentication
        # This client is used by userbot to call bot API
        # Uses audience from config (e.g., "internal")
        try:
            self.jwt_auth = load_jwt_auth_from_config(issuer="userbot")
            if self.jwt_auth:
                logging.info(f"Bot HTTP client initialized with JWT auth: {self.base_url}")
            else:
                logging.warning(f"Bot HTTP client initialized WITHOUT JWT auth: {self.base_url}")
        except Exception as e:
            logging.error(f"Failed to initialize JWT auth for bot HTTP client: {e}")
            self.jwt_auth = None

    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers including JWT token if available.

        Returns:
            Dict of HTTP headers
        """
        headers = {"Content-Type": "application/json"}

        # Add JWT token if authentication is configured
        if self.jwt_auth:
            try:
                token = self.jwt_auth.generate_token()
                headers["Authorization"] = f"Bearer {token}"
                logging.debug(f"Generated JWT token for bot API request")
            except Exception as e:
                logging.error(f"Failed to generate JWT token for bot API: {e}")
                import traceback
                traceback.print_exc()
                raise
        else:
            logging.warning(f"No JWT auth configured - bot API request will likely fail with 401")

        return headers

    def send_file(self, file_bytes: bytes, file_name: str, caption: str = "", recipient_id: int = None) -> Dict:
        """
        Send a file to a recipient via the bot.

        Args:
            file_bytes: File content as bytes
            file_name: Name of the file
            caption: Optional caption for the file
            recipient_id: Optional recipient ID (defaults to OWNER_ID on bot side)

        Returns:
            Response dict with success status and message_id

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}/api/v1/send_file"

        # Encode file as base64
        file_data_b64 = base64.b64encode(file_bytes).decode('utf-8')

        payload = {
            "file_data": file_data_b64,
            "file_name": file_name,
            "caption": caption
        }

        if recipient_id:
            payload["recipient_id"] = recipient_id

        response = self.client.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        """
        Check if bot API server is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/health"
            response = self.client.get(url, timeout=5)
            return response.status_code == 200 and response.json().get("status") == "healthy"
        except Exception as e:
            logging.debug(f"Bot API health check failed: {e}")
            return False

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
