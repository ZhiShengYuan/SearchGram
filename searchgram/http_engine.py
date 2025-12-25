#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - http_engine.py
# HTTP client adapter for Go search service

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from searchgram.engine import BasicSearchEngine


class HTTPSearchEngine(BasicSearchEngine):
    """
    HTTP client adapter for Go-based search service.

    This adapter implements the BasicSearchEngine interface but delegates
    all operations to a remote Go service via HTTP REST API.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        """
        Initialize HTTP search engine client.

        Args:
            base_url: Base URL of the Go search service (e.g., "http://searchgram-engine:8080")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

        # Create session with retry logic
        self.session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

        if self.api_key:
            self.session.headers.update({
                'X-API-Key': self.api_key
            })

        logging.info(f"HTTP search engine initialized: {base_url}")

        # Verify connectivity
        self._verify_connection()

    def _verify_connection(self):
        """Verify connection to the Go service."""
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            response.raise_for_status()
            logging.info("Successfully connected to search service")
        except requests.RequestException as e:
            logging.error(f"Failed to connect to search service: {e}")
            raise ConnectionError(f"Cannot connect to search service at {self.base_url}: {e}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an HTTP request to the Go service.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (e.g., "/api/v1/search")
            **kwargs: Additional arguments for requests

        Returns:
            JSON response as dict

        Raises:
            Exception: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as e:
            error_msg = f"HTTP error {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get('message', error_msg)
            except:
                pass

            logging.error(f"HTTP request failed: {error_msg}")
            raise Exception(f"Search service error: {error_msg}")

        except requests.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise Exception(f"Search service request failed: {e}")

    def upsert(self, message: "types.Message") -> None:
        """
        Index or update a message.

        Args:
            message: Pyrogram message object
        """
        # Convert Pyrogram message to JSON
        message_dict = json.loads(str(message))

        # Add composite ID
        message_dict["id"] = f"{message.chat.id}-{message.id}"

        # Add timestamp for sorting
        if hasattr(message, 'date') and message.date:
            message_dict["timestamp"] = int(message.date.timestamp())

        # Prepare payload
        payload = {
            "id": message_dict["id"],
            "message_id": message.id,
            "text": message.text or "",
            "chat": {
                "id": message.chat.id,
                "type": message.chat.type.name if hasattr(message.chat.type, 'name') else str(message.chat.type),
                "title": getattr(message.chat, 'title', ''),
                "username": getattr(message.chat, 'username', ''),
            },
            "from_user": {
                "id": message.from_user.id if message.from_user else 0,
                "is_bot": getattr(message.from_user, 'is_bot', False) if message.from_user else False,
                "first_name": getattr(message.from_user, 'first_name', '') if message.from_user else '',
                "last_name": getattr(message.from_user, 'last_name', '') if message.from_user else '',
                "username": getattr(message.from_user, 'username', '') if message.from_user else '',
            },
            "date": int(message.date.timestamp()) if hasattr(message, 'date') and message.date else 0,
            "timestamp": int(message.date.timestamp()) if hasattr(message, 'date') and message.date else 0,
        }

        # Make request
        self._make_request("POST", "/api/v1/upsert", json=payload)
        logging.debug(f"Upserted message: {payload['id']}")

    def search(
        self,
        keyword: str,
        _type: str = None,
        user: str = None,
        page: int = 1,
        mode: str = None,
        blocked_users: List[int] = None
    ) -> Dict[str, Any]:
        """
        Search for messages.

        Args:
            keyword: Search keyword
            _type: Chat type filter
            user: Username filter
            page: Page number (1-based)
            mode: Search mode ('e' for exact, None for fuzzy)
            blocked_users: List of user IDs to exclude

        Returns:
            Search results dict with hits, totalHits, totalPages, page, hitsPerPage
        """
        # Prepare search request
        payload = {
            "keyword": keyword,
            "page": page,
            "page_size": 10,
            "exact_match": (mode == 'e'),
        }

        if _type:
            payload["chat_type"] = _type.upper()

        if user:
            payload["username"] = user

        if blocked_users:
            payload["blocked_users"] = blocked_users

        # Make request
        result = self._make_request("POST", "/api/v1/search", json=payload)

        # Transform response to match expected format
        return {
            "hits": result.get("hits", []),
            "totalHits": result.get("total_hits", 0),
            "totalPages": result.get("total_pages", 0),
            "page": result.get("page", 1),
            "hitsPerPage": result.get("hits_per_page", 10),
        }

    def ping(self) -> Dict[str, Any]:
        """
        Ping the search engine to check health.

        Returns:
            Ping response with status, engine type, and stats
        """
        result = self._make_request("GET", "/api/v1/ping")

        # Transform to match expected format
        return {
            "status": result.get("status", "unknown"),
            "engine": result.get("engine", "http"),
            "total_documents": result.get("total_documents", 0),
        }

    def clear_db(self) -> None:
        """Clear all documents from the search index."""
        self._make_request("DELETE", "/api/v1/clear")
        logging.info("Database cleared")

    def delete(self, chat_id: int) -> int:
        """
        Delete all messages from a specific chat.

        Args:
            chat_id: Chat ID to delete messages from

        Returns:
            Number of deleted documents
        """
        result = self._make_request(
            "DELETE",
            f"/api/v1/messages?chat_id={chat_id}"
        )
        deleted_count = result.get("deleted_count", 0)
        logging.info(f"Deleted {deleted_count} messages from chat {chat_id}")
        return deleted_count

    def delete_user(self, user_id: int) -> int:
        """
        Delete all messages from a specific user (for privacy opt-out).

        Args:
            user_id: User ID to delete messages from

        Returns:
            Number of deleted documents
        """
        result = self._make_request(
            "DELETE",
            f"/api/v1/users/{user_id}"
        )
        deleted_count = result.get("deleted_count", 0)
        logging.info(f"Deleted {deleted_count} messages from user {user_id}")
        return deleted_count


# Factory function for compatibility
def SearchEngine(*args, **kwargs) -> HTTPSearchEngine:
    """
    Factory function to create HTTP search engine.

    This matches the interface of other search engines.
    """
    from searchgram.config_loader import get_config

    config = get_config()
    base_url = config.get("search_engine.http.base_url", "http://searchgram-engine:8080")
    api_key = config.get("search_engine.http.api_key")
    timeout = config.get_int("search_engine.http.timeout", 30)
    max_retries = config.get_int("search_engine.http.max_retries", 3)

    return HTTPSearchEngine(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries
    )
