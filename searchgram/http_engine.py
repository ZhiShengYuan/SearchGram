#!/usr/local/bin/python3
# coding: utf-8

# SearchGram - http_engine.py
# HTTP client adapter for Go search service

__author__ = "Benny <benny.think@gmail.com>"

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from searchgram.engine import BasicSearchEngine


class HTTPSearchEngine(BasicSearchEngine):
    """
    HTTP/2 client adapter for Go-based search service.

    This adapter implements the BasicSearchEngine interface but delegates
    all operations to a remote Go service via HTTP REST API with HTTP/2 support
    and connection pooling (remux).
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        """
        Initialize HTTP/2 search engine client with connection pooling.

        Args:
            base_url: Base URL of the Go search service (e.g., "http://searchgram-engine:8080")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        if self.api_key:
            headers['X-API-Key'] = self.api_key

        # Create httpx client with HTTP/2 support and connection pooling
        # limits control connection pooling behavior
        limits = httpx.Limits(
            max_keepalive_connections=20,  # Keep up to 20 idle connections alive
            max_connections=100,            # Maximum total connections
            keepalive_expiry=30.0,         # Keep connections alive for 30 seconds
        )

        # Transport with HTTP/2 enabled
        transport = httpx.HTTPTransport(
            http2=True,                    # Enable HTTP/2
            retries=max_retries,           # Retry failed requests
        )

        # Create persistent client with HTTP/2 and connection pooling
        self.client = httpx.Client(
            http2=True,                    # Enable HTTP/2
            timeout=httpx.Timeout(timeout),
            limits=limits,
            transport=transport,
            headers=headers,
            follow_redirects=True,
        )

        logging.info(f"HTTP/2 search engine initialized: {base_url} (connection pooling enabled)")

        # Verify connectivity
        self._verify_connection()

    def __del__(self):
        """Cleanup: close the HTTP client and connections."""
        if hasattr(self, 'client'):
            try:
                self.client.close()
            except Exception:
                pass

    def _verify_connection(self):
        """Verify connection to the Go service."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            response.raise_for_status()

            # Log HTTP version for verification
            http_version = getattr(response, 'http_version', 'unknown')
            if http_version == 'HTTP/2':
                logging.info(f"Successfully connected to search service with HTTP/2 🚀")
            else:
                logging.info(f"Successfully connected to search service ({http_version})")
        except httpx.HTTPError as e:
            logging.error(f"Failed to connect to search service: {e}")
            raise ConnectionError(f"Cannot connect to search service at {self.base_url}: {e}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an HTTP/2 request to the Go service with automatic retries.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (e.g., "/api/v1/search")
            **kwargs: Additional arguments for httpx

        Returns:
            JSON response as dict

        Raises:
            Exception: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.client.request(
                method=method,
                url=url,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get('message', error_msg)
            except Exception:
                pass

            logging.error(f"HTTP request failed: {error_msg}")
            raise Exception(f"Search service error: {error_msg}")

        except httpx.HTTPError as e:
            logging.error(f"Request failed: {e}")
            raise Exception(f"Search service request failed: {e}")

    def _convert_message_to_dict(self, message: "types.Message") -> Dict[str, Any]:
        """
        Convert a Pyrogram message to a dictionary payload.

        Args:
            message: Pyrogram message object

        Returns:
            Dictionary payload for API
        """
        return {
            "id": f"{message.chat.id}-{message.id}",
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

    def upsert(self, message: "types.Message") -> None:
        """
        Index or update a message.

        Args:
            message: Pyrogram message object
        """
        # Prepare payload
        payload = self._convert_message_to_dict(message)

        # Make request
        self._make_request("POST", "/api/v1/upsert", json=payload)
        logging.debug(f"Upserted message: {payload['id']}")

    def upsert_batch(self, messages: List["types.Message"]) -> Dict[str, Any]:
        """
        Index or update multiple messages in a single batch request.

        Args:
            messages: List of Pyrogram message objects

        Returns:
            Dictionary with batch operation results
        """
        if not messages:
            return {"indexed_count": 0, "failed_count": 0, "errors": []}

        # Convert all messages to payloads
        payloads = [self._convert_message_to_dict(msg) for msg in messages]

        # Prepare batch request
        batch_payload = {
            "messages": payloads
        }

        # Make request
        result = self._make_request("POST", "/api/v1/upsert/batch", json=batch_payload)

        logging.info(
            f"Batch upsert completed: {result.get('indexed_count', 0)} indexed, "
            f"{result.get('failed_count', 0)} failed out of {len(messages)} messages"
        )

        return result

    def search(
        self,
        keyword: str,
        _type: str = None,
        user: str = None,
        page: int = 1,
        mode: str = None,
        blocked_users: List[int] = None,
        chat_id: int = None
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
            chat_id: Optional chat ID to filter results (for group-specific searches)

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

        if chat_id:
            payload["chat_id"] = chat_id

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
