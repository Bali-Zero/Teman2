"""
Gemini LLM Provider

Wraps the existing GeminiJakselService to implement the LLMProvider interface.
"""

import logging
from collections.abc import AsyncIterator

from llm.base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """
    LLMProvider adapter for Google Gemini (via GeminiJakselService).

    Supports:
    - gemini-3-flash-preview (default)
    - gemini-2.0-flash (fallback)
    """

    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        """
        Initialize Gemini provider.

        Args:
            model_name: Model to use (default: gemini-3-flash-preview)
        """
        self._model_name = model_name
        self._service = None
        self._available = False
        self._init_service()

    def _init_service(self):
        """Lazy initialize the underlying service."""
        try:
            from services.llm_clients.gemini_service import GeminiJakselService
            self._service = GeminiJakselService(model_name=self._model_name)
            self._available = getattr(self._service, '_available', True)
            logger.info(f"GeminiProvider initialized: model={self._model_name}, available={self._available}")
        except Exception as e:
            logger.warning(f"Failed to initialize GeminiProvider: {e}")
            self._available = False

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def is_available(self) -> bool:
        return self._available and self._service is not None

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """Generate response using Gemini."""
        if not self.is_available:
            raise RuntimeError("Gemini provider not available")

        # Convert LLMMessage to service format
        history = []
        user_message = ""
        context = kwargs.get("context", "")

        for msg in messages:
            if msg.role == "system":
                context = msg.content + "\n" + context
            elif msg.role == "user":
                user_message = msg.content
            else:
                history.append({"role": msg.role, "content": msg.content})

        # Call underlying service
        content = await self._service.generate_response(
            message=user_message,
            history=history if history else None,
            context=context
        )

        return LLMResponse(
            content=content,
            model=self._model_name,
            provider=self.name,
            finish_reason="stop"
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream response using Gemini."""
        if not self.is_available:
            raise RuntimeError("Gemini provider not available")

        # Convert LLMMessage to service format
        history = []
        user_message = ""
        context = kwargs.get("context", "")

        for msg in messages:
            if msg.role == "system":
                context = msg.content + "\n" + context
            elif msg.role == "user":
                user_message = msg.content
            else:
                history.append({"role": msg.role, "content": msg.content})

        async for chunk in self._service.generate_response_stream(
            message=user_message,
            history=history if history else None,
            context=context
        ):
            yield chunk
