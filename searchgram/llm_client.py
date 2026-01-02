"""
LLM Client for Channel Mirroring

Supports OpenAI-compatible API endpoints for text processing:
- Rewrite: Transform text while preserving meaning
- Filter: Decide whether to mirror message
- Categorize: Add tags/categories to content
"""

import logging
from typing import Optional, Dict, Any, List
import httpx
import json

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client for OpenAI-compatible LLM APIs.

    Supports custom endpoints, models, and prompts for channel mirroring.
    """

    # Default prompts for different modes
    DEFAULT_PROMPTS = {
        "rewrite": (
            "Rewrite the following message in a natural, engaging style while "
            "preserving its core meaning and information. Do not add commentary "
            "or explanations, just return the rewritten text:\n\n{text}"
        ),
        "filter": (
            "Analyze the following message and determine if it should be published. "
            "Respond with ONLY 'ALLOW' or 'BLOCK', with no other text:\n\n{text}"
        ),
        "categorize": (
            "Analyze the following message and add relevant hashtags/categories. "
            "Return the original message with hashtags appended at the end:\n\n{text}"
        ),
    }

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        timeout: int = 30,
        max_retries: int = 3,
        custom_prompts: Optional[Dict[str, str]] = None
    ):
        """
        Initialize LLM client.

        Args:
            base_url: API endpoint (e.g., "https://api.openai.com/v1")
            api_key: API authentication key
            model: Model name to use
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            custom_prompts: Override default prompts for modes
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

        # Merge custom prompts with defaults
        self.prompts = self.DEFAULT_PROMPTS.copy()
        if custom_prompts:
            self.prompts.update(custom_prompts)

        # HTTP client with retry logic
        self.client = httpx.Client(
            timeout=timeout,
            http2=True,
            headers=self._get_headers()
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authentication."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def process(
        self,
        text: str,
        mode: str = "rewrite",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        custom_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Process text with LLM.

        Args:
            text: Input text to process
            mode: Processing mode ("rewrite", "filter", "categorize")
            temperature: LLM temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            custom_prompt: Override default prompt for this request

        Returns:
            Processed text, or None if filtered out (filter mode only)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to LLM client")
            return None

        # Select prompt
        if custom_prompt:
            prompt = custom_prompt.format(text=text)
        elif mode in self.prompts:
            prompt = self.prompts[mode].format(text=text)
        else:
            logger.error(f"Unknown LLM mode: {mode}")
            return text  # Fallback to original text

        try:
            result = self._call_api(prompt, temperature, max_tokens)

            # Handle filter mode
            if mode == "filter":
                decision = result.strip().upper()
                if "BLOCK" in decision:
                    logger.info(f"LLM filtered out message: {text[:50]}...")
                    return None
                elif "ALLOW" not in decision:
                    logger.warning(f"LLM returned unexpected response: {decision}")
                    return text  # Fallback to original

            return result.strip()

        except Exception as e:
            logger.error(f"LLM processing failed: {e}", exc_info=True)
            # Fallback behavior
            if mode == "filter":
                return text  # Allow on error (fail open)
            return text  # Return original text

    def _call_api(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Call OpenAI-compatible chat completion API.

        Args:
            prompt: The prompt to send
            temperature: LLM temperature
            max_tokens: Maximum tokens in response

        Returns:
            API response text
        """
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()

                # Extract content from response
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    return content
                else:
                    raise ValueError(f"Unexpected API response format: {data}")

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"LLM API HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1 and e.response.status_code >= 500:
                    continue  # Retry on server errors
                raise

            except Exception as e:
                last_error = e
                logger.warning(f"LLM API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    continue
                raise

        # If all retries failed
        raise last_error or Exception("LLM API call failed after retries")

    def batch_process(
        self,
        texts: List[str],
        mode: str = "rewrite",
        **kwargs
    ) -> List[Optional[str]]:
        """
        Process multiple texts (sequential, not batched API calls).

        Args:
            texts: List of texts to process
            mode: Processing mode
            **kwargs: Additional arguments for process()

        Returns:
            List of processed texts (None for filtered messages)
        """
        results = []
        for text in texts:
            try:
                result = self.process(text, mode, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch processing error for text: {e}")
                results.append(text)  # Fallback to original

        return results

    def test_connection(self) -> bool:
        """
        Test LLM API connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            result = self.process("Hello", mode="rewrite")
            return result is not None
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
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
    client = LLMClient(
        base_url="https://api.openai.com/v1",
        api_key="sk-test",  # Replace with actual key
        model="gpt-3.5-turbo"
    )

    # Test rewrite mode
    original = "This is a test message about cryptocurrency."
    rewritten = client.process(original, mode="rewrite")
    print(f"Original: {original}")
    print(f"Rewritten: {rewritten}")

    # Test filter mode
    spam_message = "Click here for free money!!!"
    filtered = client.process(spam_message, mode="filter")
    print(f"Spam filtered: {filtered is None}")

    # Test categorize mode
    news = "Bitcoin price reaches new high today."
    categorized = client.process(news, mode="categorize")
    print(f"Categorized: {categorized}")

    client.close()
