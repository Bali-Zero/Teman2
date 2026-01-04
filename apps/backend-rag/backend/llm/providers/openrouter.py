"""
OpenRouter LLM Provider

Wraps the existing OpenRouterClient to implement the LLMProvider interface.
"""

import logging
from collections.abc import AsyncIterator

from llm.base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """
    LLMProvider adapter for OpenRouter.

    Supports automatic fallback across free models:
    - google/gemini-2.0-flash-exp:free
    - meta-llama/llama-3.3-70b-instruct:free
    - qwen/qwen3-235b-a22b:free
    """

    def __init__(self, tier: str = "rag"):
        """
        Initialize OpenRouter provider.

        Args:
            tier: Model tier ("fast", "balanced", "powerful", "rag")
        """
        self._tier = tier
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        """Lazy initialize the underlying client."""
        try:
            from services.llm_clients.openrouter_client import ModelTier, OpenRouterClient

            tier_map = {
                "fast": ModelTier.FAST,
                "balanced": ModelTier.BALANCED,
                "powerful": ModelTier.POWERFUL,
                "rag": ModelTier.RAG,
            }
            self._model_tier = tier_map.get(self._tier, ModelTier.RAG)
            self._client = OpenRouterClient(default_tier=self._model_tier)
            self._available = bool(self._client.api_key)
            logger.info(
                f"OpenRouterProvider initialized: tier={self._tier}, available={self._available}"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OpenRouterProvider: {e}")
            self._available = False

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None

    async def generate(
        self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> LLMResponse:
        """Generate response using OpenRouter."""
        if not self.is_available:
            raise RuntimeError("OpenRouter provider not available")

        # Convert to OpenAI message format
        openai_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        result = await self._client.complete(
            messages=openai_messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )

        return LLMResponse(
            content=result.content,
            model=result.model_used,
            tokens_used=result.total_tokens,
            provider=self.name,
            finish_reason="stop",
        )

    async def stream(
        self, messages: list[LLMMessage], temperature: float = 0.7, **kwargs
    ) -> AsyncIterator[str]:
        """Stream response using OpenRouter."""
        if not self.is_available:
            raise RuntimeError("OpenRouter provider not available")

        # Convert to OpenAI message format
        openai_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        async for chunk in self._client.complete_stream(
            messages=openai_messages, temperature=temperature, **kwargs
        ):
            yield chunk
