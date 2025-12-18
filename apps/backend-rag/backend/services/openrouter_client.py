"""
OpenRouter Smart AI Client - Native Fallback System

Uses OpenRouter's native 'models' array for server-side fallback (more efficient).
With $10+ credits: 1000 req/day on free models.

Free Models Available (as of 2025):
- google/gemini-2.0-flash-exp:free (1M context, best for RAG)
- meta-llama/llama-3.3-70b-instruct:free (131K context, best reasoning)
- qwen/qwen3-235b-a22b:free (40K context, powerful)
- mistralai/mistral-small-3.1-24b-instruct:free (32K context, fast)
- meta-llama/llama-3.2-3b-instruct:free (131K context, fastest)

Best Practice: Use 'models' array for automatic server-side fallback.
OpenRouter tries models in order until one succeeds.
"""

import json
import logging
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tier for routing based on task complexity"""

    FAST = "fast"  # Simple queries, quick responses
    BALANCED = "balanced"  # General purpose, good quality
    POWERFUL = "powerful"  # Complex reasoning, long context
    RAG = "rag"  # Best for RAG with large context


# Fallback chains per tier (OpenRouter tries in order)
# LIMIT: OpenRouter allows max 3 models in the 'models' array!
FALLBACK_CHAINS = {
    ModelTier.RAG: [
        "google/gemini-2.0-flash-exp:free",  # 1M context - best for RAG
        "meta-llama/llama-3.3-70b-instruct:free",  # 131K context - fallback 1
        "qwen/qwen3-235b-a22b:free",  # 40K context - fallback 2
    ],
    ModelTier.POWERFUL: [
        "meta-llama/llama-3.3-70b-instruct:free",  # Best reasoning (70B params)
        "qwen/qwen3-235b-a22b:free",  # 235B params
        "google/gemini-2.0-flash-exp:free",  # Large context fallback
    ],
    ModelTier.BALANCED: [
        "mistralai/mistral-small-3.1-24b-instruct:free",  # Good balance
        "meta-llama/llama-3.3-70b-instruct:free",  # Powerful fallback
        "google/gemini-2.0-flash-exp:free",  # Large context
    ],
    ModelTier.FAST: [
        "meta-llama/llama-3.2-3b-instruct:free",  # Fastest (3B)
        "qwen/qwen3-4b:free",  # Small & fast (4B)
        "mistralai/mistral-small-3.1-24b-instruct:free",  # Fallback
    ],
}

# Model metadata for reference
MODEL_INFO = {
    "google/gemini-2.0-flash-exp:free": {"name": "Gemini 2.0 Flash", "context": 1_000_000},
    "meta-llama/llama-3.3-70b-instruct:free": {"name": "Llama 3.3 70B", "context": 131_072},
    "qwen/qwen3-235b-a22b:free": {"name": "Qwen3 235B", "context": 40_960},
    "mistralai/mistral-small-3.1-24b-instruct:free": {
        "name": "Mistral Small 3.1",
        "context": 32_768,
    },
    "microsoft/phi-4:free": {"name": "Phi-4", "context": 16_384},
    "meta-llama/llama-3.2-3b-instruct:free": {"name": "Llama 3.2 3B", "context": 131_072},
    "qwen/qwen3-4b:free": {"name": "Qwen3 4B", "context": 40_960},
}


@dataclass
class CompletionResult:
    """Result from AI completion"""

    content: str
    model_used: str
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0  # Always 0 for free models


class OpenRouterClient:
    """
    Smart AI Client using OpenRouter's native fallback system.

    Features:
    - Native server-side fallback via 'models' array (single request!)
    - Model selection based on task tier
    - Streaming support
    - Token usage tracking
    - Rate limit: 1000 req/day with $10+ credits
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        default_tier: ModelTier = ModelTier.RAG,
        timeout: float = 120.0,  # Longer timeout for large context
        site_url: str = "https://nuzantara-rag.fly.dev",
        site_name: str = "Nuzantara RAG",
    ):
        self.api_key = api_key or settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OpenRouter API key not configured")

        self.default_tier = default_tier
        self.timeout = timeout
        self.site_url = site_url
        self.site_name = site_name

    def get_fallback_chain(self, tier: ModelTier | None = None) -> list[str]:
        """Get model IDs for fallback chain"""
        return FALLBACK_CHAINS.get(tier or self.default_tier, FALLBACK_CHAINS[ModelTier.RAG])

    def _get_headers(self) -> dict:
        """Get API headers with recommended OpenRouter headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,  # For OpenRouter rankings
            "X-Title": self.site_name,  # For OpenRouter rankings
        }

    async def complete(
        self,
        messages: list[dict],
        tier: ModelTier | None = None,
        model_id: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> CompletionResult:
        """
        Generate completion with native OpenRouter fallback.

        Uses 'models' array for server-side fallback - more efficient than
        client-side retry logic (single HTTP request handles all fallbacks).

        Args:
            messages: Chat messages in OpenAI format
            tier: Model tier for fallback chain selection
            model_id: Specific model (disables fallback chain)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional tools/functions
            **kwargs: Additional API parameters

        Returns:
            CompletionResult with content and metadata
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        # Build payload with native fallback
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        if model_id:
            # Specific model requested - no fallback
            payload["model"] = model_id
        else:
            # Use native fallback with 'models' array
            payload["models"] = self.get_fallback_chain(tier)

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions", headers=self._get_headers(), json=payload
            )
            response.raise_for_status()

            data = response.json()

            # Extract response
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")

            # Get actual model used (OpenRouter returns this)
            model_used = data.get("model", model_id or "unknown")
            model_info = MODEL_INFO.get(model_used, {"name": model_used, "context": 0})

            # Extract usage
            usage = data.get("usage", {})

            logger.info(f"OpenRouter used model: {model_info['name']}")

            return CompletionResult(
                content=content,
                model_used=model_used,
                model_name=model_info["name"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=0.0,  # Free models
            )

    async def complete_stream(
        self,
        messages: list[dict],
        tier: ModelTier | None = None,
        model_id: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming completion with native OpenRouter fallback.

        Yields text chunks as they arrive.
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }

        if model_id:
            payload["model"] = model_id
        else:
            payload["models"] = self.get_fallback_chain(tier)

        async with (
            httpx.AsyncClient(timeout=self.timeout) as client,
            client.stream(
                "POST",
                f"{self.BASE_URL}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            ) as response,
        ):
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]

                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def check_credits(self) -> dict:
        """Check remaining credits and usage stats"""
        if not self.api_key:
            return {"error": "API key not configured"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.BASE_URL}/key", headers=self._get_headers())
            if response.status_code == 200:
                return response.json()
            return {"error": f"Status {response.status_code}"}


# Singleton instance
openrouter_client = OpenRouterClient(default_tier=ModelTier.RAG)


# Convenience functions
async def smart_complete(
    prompt: str, system: str | None = None, tier: ModelTier = ModelTier.BALANCED, **kwargs
) -> CompletionResult:
    """Simple completion with optional system prompt"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    return await openrouter_client.complete(messages, tier=tier, **kwargs)


async def smart_complete_stream(
    prompt: str, system: str | None = None, tier: ModelTier = ModelTier.BALANCED, **kwargs
) -> AsyncGenerator[str, None]:
    """Simple streaming completion with optional system prompt"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async for chunk in openrouter_client.complete_stream(messages, tier=tier, **kwargs):
        yield chunk


# Test function
if __name__ == "__main__":
    import asyncio

    async def test():
        logger.info("🚀 Testing OpenRouter Native Fallback Client...")
        logger.info(f"   API Key: {'✅ Set' if openrouter_client.api_key else '❌ Not set'}")

        if not openrouter_client.api_key:
            logger.info("   Set OPENROUTER_API_KEY to test")
            return

        # Check credits
        logger.info("\n💰 Checking credits...")
        credits = await openrouter_client.check_credits()
        logger.info(f"   Credits info: {credits}")

        # Test with native fallback
        logger.info("\n📝 Test 1: RAG tier with native fallback")
        logger.info(f"   Fallback chain: {openrouter_client.get_fallback_chain(ModelTier.RAG)}")
        result = await smart_complete("What is 2+2? Reply in one word.", tier=ModelTier.RAG)
        logger.info(f"   Response: {result.content}")
        logger.info(f"   Model used: {result.model_name}")
        logger.info(f"   Tokens: {result.total_tokens}")

        # Test streaming
        logger.info("\n📝 Test 2: Streaming with native fallback")
        response_chunks = []
        async for chunk in smart_complete_stream("Count from 1 to 5.", tier=ModelTier.FAST):
            response_chunks.append(chunk)
        logger.info(f"   Response: {''.join(response_chunks)}")

        logger.info("✅ All tests passed!")

    asyncio.run(test())
