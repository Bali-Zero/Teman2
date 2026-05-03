"""
OpenRouter Smart AI Client - Native Fallback System

Uses OpenRouter's native 'models' array for server-side fallback (more efficient).
With $10+ credits: 1000 req/day on free models.

Free Models Available (as of 2026):
- google/gemini-2.0-flash-exp:free (1M context, best for RAG)
- meta-llama/llama-3.3-70b-instruct:free (131K context, best reasoning)
- qwen/qwen3.5-27b (262K context, powerful hybrid DeltaNet+MoE)
- mistralai/mistral-small-3.1-24b-instruct:free (32K context, fast)
- qwen/qwen3.5-35b-a3b (262K context, fast MoE)

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

from backend.app.core.config import settings
from backend.services.observability import llm_cost_tracked, set_usage

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
        "qwen/qwen3.5-27b",  # 262K context - fallback 2
    ],
    ModelTier.POWERFUL: [
        "meta-llama/llama-3.3-70b-instruct:free",  # Best reasoning (70B params)
        "qwen/qwen3.5-27b",  # 27B dense, hybrid DeltaNet+MoE
        "google/gemini-2.0-flash-exp:free",  # Large context fallback
    ],
    ModelTier.BALANCED: [
        "mistralai/mistral-small-3.1-24b-instruct:free",  # Good balance
        "meta-llama/llama-3.3-70b-instruct:free",  # Powerful fallback
        "google/gemini-2.0-flash-exp:free",  # Large context
    ],
    ModelTier.FAST: [
        "meta-llama/llama-3.2-3b-instruct:free",  # Fastest (3B)
        "qwen/qwen3.5-35b-a3b",  # Fast MoE (3B active of 35B)
        "mistralai/mistral-small-3.1-24b-instruct:free",  # Fallback
    ],
}

# Model metadata for reference
MODEL_INFO = {
    "google/gemini-2.0-flash-exp:free": {"name": "Gemini 2.0 Flash", "context": 1_000_000},
    "meta-llama/llama-3.3-70b-instruct:free": {"name": "Llama 3.3 70B", "context": 131_072},
    "qwen/qwen3.5-27b": {"name": "Qwen3.5 27B", "context": 262_144},
    "mistralai/mistral-small-3.1-24b-instruct:free": {
        "name": "Mistral Small 3.1",
        "context": 32_768,
    },
    "microsoft/phi-4:free": {"name": "Phi-4", "context": 16_384},
    "meta-llama/llama-3.2-3b-instruct:free": {"name": "Llama 3.2 3B", "context": 131_072},
    "qwen/qwen3.5-35b-a3b": {"name": "Qwen3.5 35B-A3B", "context": 262_144},
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
    ) -> None:
        self.api_key = api_key or settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OpenRouter API key not configured")

        self.default_tier = default_tier
        self.timeout = timeout
        self.site_url = site_url
        self.site_name = site_name
        self._client: httpx.AsyncClient | None = None
        self._last_selected_model: str = "openrouter-unknown"

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("OpenRouterClient HTTP client closed.")

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

    @llm_cost_tracked(provider="openrouter", model_attr="_last_selected_model")
    async def complete(
        self,
        messages: list[dict],
        tier: ModelTier | None = None,
        model_id: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
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

        client = self._get_client()
        response = await client.post(
            f"{self.BASE_URL}/chat/completions", headers=self._get_headers(), json=payload,
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

        # Capture the dynamically-selected model for cost tracking
        self._last_selected_model = model_used

        # Extract usage
        usage = data.get("usage", {})

        # Report token usage to the cost tracking decorator
        set_usage(
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )

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

    # NOTE: streaming path is not yet cost-tracked — follow-up task.
    async def complete_stream(
        self,
        messages: list[dict],
        tier: ModelTier | None = None,
        model_id: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
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

        client = self._get_client()
        async with client.stream(
            "POST",
            f"{self.BASE_URL}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        ) as response:
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
                    except json.JSONDecodeError as decode_exc:
                        logger.debug(
                            "openrouter stream: skipping malformed chunk: %s",
                            decode_exc,
                        )
                        continue

    async def check_credits(self) -> dict:
        """Check remaining credits and usage stats"""
        if not self.api_key:
            return {"error": "API key not configured"}

        client = self._get_client()
        response = await client.get(f"{self.BASE_URL}/key", headers=self._get_headers())
        if response.status_code == 200:
            return response.json()
        return {"error": f"Status {response.status_code}"}


# Singleton instance
try:
    openrouter_client = OpenRouterClient(default_tier=ModelTier.RAG)
    logger.debug("OpenRouterClient singleton created.")
except Exception as e:
    logger.error(f"Failed to create OpenRouterClient: {e}")
    openrouter_client = None


# Convenience functions
async def smart_complete(
    prompt: str, system: str | None = None, tier: ModelTier = ModelTier.BALANCED, **kwargs,
) -> CompletionResult:
    """Simple completion with optional system prompt"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    return await openrouter_client.complete(messages, tier=tier, **kwargs)


async def smart_complete_stream(
    prompt: str, system: str | None = None, tier: ModelTier = ModelTier.BALANCED, **kwargs,
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

    async def test() -> None:
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
