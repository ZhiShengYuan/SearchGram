"""
Mirror HTTP Client

HTTP client for userbot to send messages to bot for mirroring.
Follows the same pattern as SyncHTTPClient and BotHTTPClient.
"""

import logging
from typing import Dict, Any, Optional
import httpx
from .jwt_auth import load_jwt_auth_from_config
from .mirror_models import MirrorMessage

logger = logging.getLogger(__name__)


class MirrorHTTPClient:
    """
    HTTP client for mirror operations (userbot → bot).

    Sends messages from userbot to bot for processing and mirroring
    to target channels.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 60,  # Longer timeout for file uploads
        max_retries: int = 3
    ):
        """
        Initialize mirror HTTP client.

        Args:
            base_url: Bot API base URL (e.g., "http://127.0.0.1:8081")
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries

        # HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=timeout,
            http2=True,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

        # Load JWT authentication (issuer="userbot")
        self.jwt_auth = load_jwt_auth_from_config(issuer="userbot")
        if not self.jwt_auth:
            logger.warning("JWT authentication not configured for mirror client")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with JWT authentication."""
        headers = {"Content-Type": "application/json"}

        if self.jwt_auth:
            try:
                token = self.jwt_auth.generate_token()
                headers["Authorization"] = f"Bearer {token}"
            except Exception as e:
                logger.error(f"Failed to generate JWT token: {e}")

        return headers

    def send_for_mirroring(
        self,
        message: MirrorMessage
    ) -> Dict[str, Any]:
        """
        Send message to bot for mirroring.

        Args:
            message: MirrorMessage object with content and metadata

        Returns:
            API response dict with status and details

        Raises:
            httpx.HTTPError: On HTTP errors
            Exception: On other errors
        """
        url = f"{self.base_url}/api/v1/mirror/process"

        # Convert message to API format (includes base64 encoding)
        payload = message.to_api_dict()

        # Log request (without file data to avoid bloat)
        log_payload = {k: v for k, v in payload.items() if k != "file_data"}
        if payload.get("file_data"):
            log_payload["file_data"] = f"<{len(payload['file_data'])} bytes>"
        logger.info(f"Sending message for mirroring: {log_payload}")

        # Make request with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                logger.info(f"Mirror request successful: {result.get('status')}")
                return result

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"Mirror HTTP error (attempt {attempt + 1}/{self.max_retries}): "
                    f"{e.response.status_code} - {e.response.text}"
                )
                # Retry on server errors (5xx)
                if attempt < self.max_retries - 1 and e.response.status_code >= 500:
                    continue
                raise

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"Mirror timeout (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    continue
                raise

            except Exception as e:
                last_error = e
                logger.error(f"Mirror request error: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    continue
                raise

        # If all retries failed
        raise last_error or Exception("Mirror request failed after retries")

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a mirror task.

        Args:
            task_id: Task ID

        Returns:
            Task status dict
        """
        url = f"{self.base_url}/api/v1/mirror/task/{task_id}"

        try:
            response = self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to get task status: {e}")
            raise

    def pause_task(self, task_id: str) -> Dict[str, Any]:
        """
        Pause a mirror task.

        Args:
            task_id: Task ID

        Returns:
            API response dict
        """
        url = f"{self.base_url}/api/v1/mirror/pause"

        try:
            response = self.client.post(
                url,
                json={"task_id": task_id},
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to pause task: {e}")
            raise

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """
        Resume a paused mirror task.

        Args:
            task_id: Task ID

        Returns:
            API response dict
        """
        url = f"{self.base_url}/api/v1/mirror/resume"

        try:
            response = self.client.post(
                url,
                json={"task_id": task_id},
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to resume task: {e}")
            raise

    def health_check(self) -> bool:
        """
        Check if bot mirror API is available.

        Returns:
            True if available, False otherwise
        """
        url = f"{self.base_url}/health"

        try:
            response = self.client.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "ok"

        except Exception as e:
            logger.warning(f"Mirror API health check failed: {e}")
            return False

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Example configuration
    client = MirrorHTTPClient(base_url="http://127.0.0.1:8081")

    # Test health check
    if client.health_check():
        print("✓ Mirror API is available")
    else:
        print("✗ Mirror API is not available")
        sys.exit(1)

    # Example: Send a text message for mirroring
    message = MirrorMessage(
        task_id="task_1",
        source_chat_id=-1001234567890,
        source_msg_id=12345,
        text="Test message for mirroring",
        has_media=False
    )

    try:
        result = client.send_for_mirroring(message)
        print(f"Mirror result: {result}")
    except Exception as e:
        print(f"Mirror failed: {e}")

    # Example: Send a message with media
    message_with_media = MirrorMessage(
        task_id="task_1",
        source_chat_id=-1001234567890,
        source_msg_id=12346,
        caption="Test photo",
        has_media=True,
        media_type="photo",
        file_data=b"\x89PNG\r\n\x1a\n...",  # Example PNG data
        file_size=1024,
        file_name="test.png"
    )

    try:
        result = client.send_for_mirroring(message_with_media)
        print(f"Mirror with media result: {result}")
    except Exception as e:
        print(f"Mirror with media failed: {e}")

    client.close()
