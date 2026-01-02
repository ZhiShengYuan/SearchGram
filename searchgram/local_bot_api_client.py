"""
Local Telegram Bot API Client

Provides interface to local Telegram Bot API server for:
- Large file uploads (>50MB support)
- Better upload performance
- Progress tracking

The local Bot API server should be already running and configured.
"""

import logging
from typing import Optional, BinaryIO, Union
from io import BytesIO
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)


class LocalBotAPIClient:
    """
    Client for local Telegram Bot API server.

    Wraps the standard Telegram Bot API with support for large files
    and local file paths.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 300,  # 5 minutes for large files
        max_retries: int = 3
    ):
        """
        Initialize local Bot API client.

        Args:
            base_url: Local Bot API endpoint (e.g., "http://localhost:8081/bot{token}")
            token: Bot token
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        # Replace {token} placeholder if present
        self.base_url = base_url.replace("{token}", token).rstrip('/')
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries

        # HTTP client for API calls
        self.client = httpx.Client(
            timeout=timeout,
            http2=True,
            follow_redirects=True
        )

    def send_photo(
        self,
        chat_id: Union[int, str],
        photo: Union[str, bytes, BinaryIO],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False
    ) -> dict:
        """
        Send photo to chat.

        Args:
            chat_id: Target chat ID
            photo: Photo file (file path, bytes, or file-like object)
            caption: Photo caption
            parse_mode: Parsing mode ("Markdown", "HTML")
            disable_notification: Send silently

        Returns:
            API response dict
        """
        return self._send_media(
            method="sendPhoto",
            chat_id=chat_id,
            media_field="photo",
            media=photo,
            caption=caption,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )

    def send_video(
        self,
        chat_id: Union[int, str],
        video: Union[str, bytes, BinaryIO],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
        supports_streaming: bool = True
    ) -> dict:
        """
        Send video to chat.

        Args:
            chat_id: Target chat ID
            video: Video file (file path, bytes, or file-like object)
            caption: Video caption
            parse_mode: Parsing mode ("Markdown", "HTML")
            disable_notification: Send silently
            supports_streaming: Enable streaming

        Returns:
            API response dict
        """
        extra_data = {}
        if supports_streaming:
            extra_data["supports_streaming"] = "true"

        return self._send_media(
            method="sendVideo",
            chat_id=chat_id,
            media_field="video",
            media=video,
            caption=caption,
            parse_mode=parse_mode,
            disable_notification=disable_notification,
            extra_data=extra_data
        )

    def send_document(
        self,
        chat_id: Union[int, str],
        document: Union[str, bytes, BinaryIO],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
        filename: Optional[str] = None
    ) -> dict:
        """
        Send document to chat.

        Args:
            chat_id: Target chat ID
            document: Document file (file path, bytes, or file-like object)
            caption: Document caption
            parse_mode: Parsing mode ("Markdown", "HTML")
            disable_notification: Send silently
            filename: Custom filename

        Returns:
            API response dict
        """
        return self._send_media(
            method="sendDocument",
            chat_id=chat_id,
            media_field="document",
            media=document,
            caption=caption,
            parse_mode=parse_mode,
            disable_notification=disable_notification,
            filename=filename
        )

    def _send_media(
        self,
        method: str,
        chat_id: Union[int, str],
        media_field: str,
        media: Union[str, bytes, BinaryIO],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
        filename: Optional[str] = None,
        extra_data: Optional[dict] = None
    ) -> dict:
        """
        Internal method to send media files.

        Args:
            method: API method name
            chat_id: Target chat ID
            media_field: Field name for media ("photo", "video", "document")
            media: Media file
            caption: Media caption
            parse_mode: Parsing mode
            disable_notification: Send silently
            filename: Custom filename
            extra_data: Additional form data

        Returns:
            API response dict
        """
        url = f"{self.base_url}/{method}"

        # Prepare form data
        data = {
            "chat_id": str(chat_id),
        }

        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if disable_notification:
            data["disable_notification"] = "true"
        if extra_data:
            data.update(extra_data)

        # Prepare files
        files = {}

        # Handle different media input types
        if isinstance(media, str):
            # File path
            path = Path(media)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {media}")

            file_name = filename or path.name
            with open(path, 'rb') as f:
                file_content = f.read()
            files[media_field] = (file_name, BytesIO(file_content))

        elif isinstance(media, bytes):
            # Bytes
            file_name = filename or f"{media_field}.bin"
            files[media_field] = (file_name, BytesIO(media))

        elif isinstance(media, BytesIO):
            # BytesIO object
            file_name = filename or getattr(media, 'name', f"{media_field}.bin")
            files[media_field] = (file_name, media)

        else:
            # File-like object
            file_name = filename or getattr(media, 'name', f"{media_field}.bin")
            files[media_field] = (file_name, media)

        # Make request with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(url, data=data, files=files)
                response.raise_for_status()

                result = response.json()

                if not result.get("ok"):
                    error_desc = result.get("description", "Unknown error")
                    raise Exception(f"Bot API error: {error_desc}")

                logger.info(f"Successfully sent {media_field} to chat {chat_id}")
                return result["result"]

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"Bot API HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1 and e.response.status_code >= 500:
                    continue  # Retry on server errors
                raise

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Bot API error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    continue
                raise

        # If all retries failed
        raise last_error or Exception("Bot API call failed after retries")

    def get_me(self) -> dict:
        """
        Get bot information.

        Returns:
            Bot info dict
        """
        url = f"{self.base_url}/getMe"
        response = self.client.get(url)
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            raise Exception(f"Bot API error: {result.get('description')}")

        return result["result"]

    def test_connection(self) -> bool:
        """
        Test connection to local Bot API server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            bot_info = self.get_me()
            logger.info(f"Connected to bot: @{bot_info.get('username')}")
            return True
        except Exception as e:
            logger.error(f"Bot API connection test failed: {e}")
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
    logging.basicConfig(level=logging.INFO)

    # Example configuration (replace with actual values)
    client = LocalBotAPIClient(
        base_url="http://localhost:8081/bot{token}",
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    )

    # Test connection
    if client.test_connection():
        print("✓ Local Bot API connection successful")

        # Example: Send a photo
        # client.send_photo(
        #     chat_id=123456789,
        #     photo=b"...",  # Photo bytes
        #     caption="Test photo from local Bot API"
        # )
    else:
        print("✗ Local Bot API connection failed")

    client.close()
