"""
DeepSeek LLM Provider

Wraps the existing DeepSeekClient to implement the LLMProvider interface.
"""

import logging
from typing import AsyncIterator, List

from llm.base import LLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class DeepSeekProvider(LLMProvider):
    """
    LLMProvider adapter for DeepSeek V3.

    Cheapest LLM API option:
    - Input: $0.27 per 1M tokens
    - Output: $1.10 per 1M tokens
    - Context: 64k tokens
    """

    def __init__(self, model: str = "deepseek-chat"):
        """
        Initialize DeepSeek provider.

        Args:
            model: Model to use (default: deepseek-chat)
        """
        self._model = model
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        """Lazy initialize the underlying client."""
        try:
            from services.llm_clients.deepseek_client import DeepSeekClient
            self._client = DeepSeekClient()
            self._available = self._client.is_available
            logger.info(f"DeepSeekProvider initialized: model={self._model}, available={self._available}")
        except Exception as e:
            logger.warning(f"Failed to initialize DeepSeekProvider: {e}")
            self._available = False

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """Generate response using DeepSeek."""
        if not self.is_available:
            raise RuntimeError("DeepSeek provider not available")

        # Convert to OpenAI message format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        result = await self._client.complete(
            messages=openai_messages,
            model=self._model,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return LLMResponse(
            content=result.content,
            model=result.model_name,
            tokens_used=result.input_tokens + result.output_tokens,
            provider=self.name,
            finish_reason=result.finish_reason
        )

    async def stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream response using DeepSeek."""
        if not self.is_available:
            raise RuntimeError("DeepSeek provider not available")

        # Convert to OpenAI message format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        async for chunk in self._client.complete_stream(
            messages=openai_messages,
            model=self._model,
            temperature=temperature,
            max_tokens=kwargs.get("max_tokens", 8192)
        ):
            yield chunk
