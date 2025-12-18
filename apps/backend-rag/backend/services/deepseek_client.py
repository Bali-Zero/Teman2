"""
DeepSeek V3 Client - Cheapest LLM API fallback

Pricing: $0.27/1M input, $1.10/1M output (December 2025)
API: OpenAI-compatible

Fallback chain: Gemini 2.0 Flash → DeepSeek V3 → OpenRouter (free models)
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DeepSeekResponse:
    """Response from DeepSeek API"""

    content: str
    model_name: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


class DeepSeekClient:
    """
    DeepSeek V3 Client - Cheapest available LLM API.

    Pricing (December 2025):
    - Input: $0.27 per 1M tokens
    - Output: $1.10 per 1M tokens
    - Context: 64k tokens

    Use as fallback when Gemini quota is exhausted.
    """

    BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"  # DeepSeek V3

    def __init__(self, api_key: str | None = None):
        """
        Initialize DeepSeek client.

        Args:
            api_key: DeepSeek API key (defaults to settings.deepseek_api_key)
        """
        self.api_key = api_key or settings.deepseek_api_key
        if not self.api_key:
            logger.warning("⚠️ DeepSeek API key not set. Set DEEPSEEK_API_KEY env var.")

    @property
    def is_available(self) -> bool:
        """Check if DeepSeek is configured and available"""
        return bool(self.api_key)

    async def complete(
        self,
        messages: list[dict],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> DeepSeekResponse:
        """
        Generate completion from DeepSeek.

        Args:
            messages: List of messages in OpenAI format
            model: Model to use (default: deepseek-chat)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            DeepSeekResponse with content and metadata
        """
        if not self.api_key:
            raise RuntimeError("DeepSeek API key not configured")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"DeepSeek API error: {response.status_code} - {error_text}")
                raise RuntimeError(f"DeepSeek API error: {response.status_code}")

            data = response.json()

            return DeepSeekResponse(
                content=data["choices"][0]["message"]["content"],
                model_name=data.get("model", model),
                input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                output_tokens=data.get("usage", {}).get("completion_tokens", 0),
                finish_reason=data["choices"][0].get("finish_reason", "stop"),
            )

    async def complete_stream(
        self,
        messages: list[dict],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        Stream completion from DeepSeek.

        Args:
            messages: List of messages in OpenAI format
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        if not self.api_key:
            raise RuntimeError("DeepSeek API key not configured")

        async with (
            httpx.AsyncClient(timeout=120.0) as client,
            client.stream(
                "POST",
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response,
        ):
            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(f"DeepSeek streaming error: {response.status_code}")
                raise RuntimeError(f"DeepSeek API error: {response.status_code}")

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception as e:
                        logger.warning(f"Failed to parse DeepSeek stream: {e}")
                        continue


deepseek_client = DeepSeekClient()


if __name__ == "__main__":
    import asyncio

    async def test():
        logger.info("🚀 Testing DeepSeek V3 Client...")
        logger.info(f"   API Key: {'✅ Set' if settings.deepseek_api_key else '❌ Not set'}")

        if not settings.deepseek_api_key:
            logger.info("Set DEEPSEEK_API_KEY to test")
            return

        client = DeepSeekClient()

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2? Answer in one word."},
        ]

        try:
            result = await client.complete(messages)
            logger.info(f"✅ Response: {result.content}")
            logger.info(f"   Model: {result.model_name}")
            logger.info(f"   Tokens: {result.input_tokens} in, {result.output_tokens} out")
        except Exception as e:
            logger.error(f"❌ Error: {e}")

    asyncio.run(test())
