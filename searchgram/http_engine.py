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
from searchgram.jwt_utils import JWTAuth


class HTTPSearchEngine(BasicSearchEngine):
    """
    HTTP/2 client adapter for Go-based search service.

    This adapter implements the BasicSearchEngine interface but delegates
    all operations to a remote Go service via HTTP REST API with HTTP/2 support
    and connection pooling (remux).
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        jwt_auth: Optional[JWTAuth] = None,
    ):
        """
        Initialize HTTP/2 search engine client with connection pooling.

        Args:
            base_url: Base URL of the Go search service (e.g., "http://127.0.0.1:8080")
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            jwt_auth: JWT auth instance for authentication (required)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.jwt_auth = jwt_auth

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # JWT authentication is required
        if self.jwt_auth:
            logging.info("HTTP engine initialized with JWT authentication")
        else:
            logging.warning("HTTP engine initialized without JWT authentication - requests may fail")

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

    def _make_request(self, method: str, endpoint: str, timeout: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Make an HTTP/2 request to the Go service with automatic retries.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (e.g., "/api/v1/search")
            timeout: Optional custom timeout in seconds (overrides default)
            **kwargs: Additional arguments for httpx

        Returns:
            JSON response as dict

        Raises:
            Exception: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        # Use custom timeout if provided
        request_timeout = httpx.Timeout(timeout) if timeout else None

        # Add JWT token if available
        if self.jwt_auth:
            try:
                token = self.jwt_auth.generate_token(target_audience="internal")
                if "headers" not in kwargs:
                    kwargs["headers"] = {}
                kwargs["headers"]["Authorization"] = f"Bearer {token}"
            except Exception as e:
                logging.error(f"Failed to generate JWT token: {e}")
                raise Exception(f"Authentication error: {e}")

        try:
            response = self.client.request(
                method=method,
                url=url,
                timeout=request_timeout,
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

        # Extract real timing from backend response
        took_ms = result.get("took_ms", 0)

        # Log real search timing from backend
        if took_ms > 0:
            logging.debug(f"Search completed in {took_ms}ms (backend timing)")

        # Transform response to match expected format
        # Handle None values from API (normalize nulls to empty lists/zeros)
        return {
            "hits": result.get("hits") or [],
            "totalHits": result.get("total_hits") or 0,
            "totalPages": result.get("total_pages") or 0,
            "page": result.get("page") or 1,
            "hitsPerPage": result.get("hits_per_page") or 10,
            "took_ms": took_ms,  # Include real timing from backend
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

    def dedup(self) -> Dict[str, Any]:
        """
        Remove duplicate messages from the search index.

        Finds messages with the same chat_id + message_id combination
        and keeps only the latest version (by timestamp).

        Note: This operation can take several minutes for large databases.
              Uses a 10-minute timeout to allow completion.

        Returns:
            Dictionary with deduplication results:
            - success: bool
            - duplicates_found: int
            - duplicates_removed: int
            - message: str
        """
        logging.info("Starting deduplication (this may take several minutes)...")

        # Use 10-minute timeout for dedup operations (they can be slow on large DBs)
        result = self._make_request("POST", "/api/v1/dedup", timeout=600)

        duplicates_found = result.get("duplicates_found", 0)
        duplicates_removed = result.get("duplicates_removed", 0)
        logging.info(
            f"Deduplication complete: {duplicates_found} duplicates found, "
            f"{duplicates_removed} removed"
        )
        return result


# Factory function for compatibility
def SearchEngine(*args, **kwargs) -> HTTPSearchEngine:
    """
    Factory function to create HTTP search engine.

    This matches the interface of other search engines.
    """
    from searchgram.config_loader import get_config

    config = get_config()
    # Use unified search service endpoint
    base_url = config.get("services.search.base_url", "http://127.0.0.1:8080")
    timeout = config.get_int("search_engine.http.timeout", 30)
    max_retries = config.get_int("search_engine.http.max_retries", 3)

    # Initialize JWT auth if configured (required)
    jwt_auth = None
    use_jwt = config.get_bool("auth.use_jwt", True)
    if use_jwt:
        try:
            issuer = config.get("auth.issuer", "bot")
            audience = config.get("auth.audience", "internal")

            # Support both file paths and inline keys
            private_key_path = config.get("auth.private_key_path")
            public_key_path = config.get("auth.public_key_path")
            private_key_inline = config.get("auth.private_key_inline")
            public_key_inline = config.get("auth.public_key_inline")

            if (private_key_path or private_key_inline) and (public_key_path or public_key_inline):
                jwt_auth = JWTAuth(
                    issuer=issuer,
                    audience=audience,
                    private_key_path=private_key_path,
                    public_key_path=public_key_path,
                    private_key_inline=private_key_inline,
                    public_key_inline=public_key_inline,
                )
                logging.info("JWT authentication enabled for HTTP search engine")
            else:
                logging.error("JWT keys not configured properly")
                raise ValueError("JWT authentication requires both private and public keys")
        except Exception as e:
            logging.error(f"Failed to initialize JWT auth: {e}")
            raise ValueError(f"JWT authentication is required but initialization failed: {e}")

    return HTTPSearchEngine(
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        jwt_auth=jwt_auth,
    )
