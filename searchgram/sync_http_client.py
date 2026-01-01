#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - sync_http_client.py
# HTTP client for calling sync API on client process

__author__ = "Benny <benny.think@gmail.com>"

import logging
from typing import Dict, List, Optional

import httpx

from .jwt_auth import load_jwt_auth_from_config


class SyncHTTPClient:
    """
    HTTP client for sync API operations.

    Communicates with the sync API server running on the client process.
    Includes JWT authentication support.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:5000", timeout: int = 30):
        """
        Initialize sync HTTP client.

        Args:
            base_url: Base URL of sync API server (default: http://127.0.0.1:5000)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, http2=True)

        # Initialize JWT authentication
        # This client is used by the bot to call userbot API, so:
        # - issuer: "bot" (this service)
        # - audience: "userbot" (target service)
        try:
            self.jwt_auth = load_jwt_auth_from_config(issuer="bot", audience="userbot")
            if self.jwt_auth:
                logging.info(f"Sync HTTP client initialized with JWT auth: {self.base_url}")
            else:
                logging.warning(f"Sync HTTP client initialized WITHOUT JWT auth: {self.base_url}")
        except Exception as e:
            logging.error(f"Failed to initialize JWT auth for sync HTTP client: {e}")
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
            except Exception as e:
                logging.warning(f"Failed to generate JWT token: {e}")

        return headers

    def add_sync(self, chat_id: int, requested_by: Optional[int] = None) -> Dict:
        """
        Add a chat to the sync queue.

        Args:
            chat_id: Chat ID to sync
            requested_by: User ID who requested (optional)

        Returns:
            Response dict with success status and message

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}/api/v1/sync"
        payload = {"chat_id": chat_id}
        if requested_by:
            payload["requested_by"] = requested_by

        response = self.client.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_sync_status(self, chat_id: Optional[int] = None) -> Dict:
        """
        Get sync status for all tasks or a specific chat.

        Args:
            chat_id: Optional chat ID to filter

        Returns:
            Response dict with chats array

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}/api/v1/sync/status"
        params = {"chat_id": chat_id} if chat_id else {}

        response = self.client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def pause_sync(self, chat_id: int) -> Dict:
        """
        Pause a sync task.

        Args:
            chat_id: Chat ID to pause

        Returns:
            Response dict with success status

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}/api/v1/sync/pause"
        payload = {"chat_id": chat_id}

        response = self.client.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def resume_sync(self, chat_id: int) -> Dict:
        """
        Resume a paused sync task.

        Args:
            chat_id: Chat ID to resume

        Returns:
            Response dict with success status

        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}/api/v1/sync/resume"
        payload = {"chat_id": chat_id}

        response = self.client.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        """
        Check if sync API server is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/health"
            response = self.client.get(url, timeout=5)
            return response.status_code == 200 and response.json().get("status") == "healthy"
        except Exception as e:
            logging.debug(f"Sync API health check failed: {e}")
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
