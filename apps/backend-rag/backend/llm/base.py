"""
LLM Provider Base Classes

Defines the abstract interface for unified LLM provider access.
All LLM providers (Gemini, OpenRouter, DeepSeek, Vertex) implement this interface.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel


class LLMMessage(BaseModel):
    """Standard message format for LLM conversations."""

    role: str  # "user" | "assistant" | "system"
    content: str

    class Config:
        frozen = True


class LLMResponse(BaseModel):
    """Standard response format from LLM providers."""

    content: str
    model: str
    tokens_used: int | None = None
    finish_reason: str | None = None
    provider: str | None = None  # Which provider served the request


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers (Gemini, OpenRouter, DeepSeek, Vertex) must implement this interface
    to enable unified access and automatic fallback chains.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'gemini', 'openrouter')."""
        ...

    @property
    def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        return True

    @abstractmethod
    async def generate(
        self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: List of messages in the conversation
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with content and metadata
        """
        ...

    @abstractmethod
    async def stream(
        self, messages: list[LLMMessage], temperature: float = 0.7, **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream a response from the LLM.

        Args:
            messages: List of messages in the conversation
            temperature: Sampling temperature
            **kwargs: Additional provider-specific parameters

        Yields:
            Text chunks as they are generated
        """
        ...
        # Note: Must use `yield` in implementation to be a proper async generator
        if False:  # pragma: no cover
            yield ""
