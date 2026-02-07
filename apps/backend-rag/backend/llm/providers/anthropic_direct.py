"""
Anthropic Direct Provider — Claude Sonnet 4.5 for WhatsApp (Zan persona)

Uses Anthropic API directly (not OpenRouter) for natural, intelligent responses.
Designed for WhatsApp conversational responses with human-like quality.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024  # WhatsApp responses — room for complete answers


class AnthropicDirectProvider:
    """Direct Anthropic API provider for fast WhatsApp responses."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = MAX_TOKENS,
    ):
        self._api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._model = model
        self._max_tokens = max_tokens
        self._client: httpx.AsyncClient | None = None

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a response using Claude.

        Args:
            system_prompt: System prompt (Zero persona)
            messages: Conversation history [{"role": "user/assistant", "content": "..."}]
            max_tokens: Max response tokens (default 1024)
            temperature: Creativity (0.7 for natural conversation)

        Returns:
            Response text
        """
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        client = await self._get_client()

        payload = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": messages,
        }

        response = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )

        result = response.json()

        if response.status_code != 200:
            error = result.get("error", {}).get("message", "Unknown error")
            logger.error(f"Anthropic API error: {error}")
            raise ValueError(f"Anthropic API error: {error}")

        # Extract text from response
        content = result.get("content", [])
        text_parts = [block["text"] for block in content if block.get("type") == "text"]
        return "".join(text_parts)


# Singleton
anthropic_provider = AnthropicDirectProvider()
