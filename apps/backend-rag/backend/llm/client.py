"""
Unified LLM Client

Provides a single interface to multiple LLM providers with automatic fallback.
"""

import logging
from typing import AsyncIterator, List, Optional

from llm.base import LLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class UnifiedLLMClient:
    """
    Unified client for accessing multiple LLM providers with automatic fallback.

    Usage:
        from llm import UnifiedLLMClient
        from llm.providers import GeminiProvider, OpenRouterProvider

        client = UnifiedLLMClient([
            GeminiProvider(),      # Primary
            OpenRouterProvider(),  # Fallback 1
        ])

        response = await client.generate([
            LLMMessage(role="user", content="Hello!")
        ])
    """

    def __init__(self, providers: List[LLMProvider]):
        """
        Initialize with a list of providers in priority order.

        Args:
            providers: List of LLMProvider instances. Order determines fallback priority.
        """
        self.providers = providers
        self._filter_available()

    def _filter_available(self):
        """Log which providers are available."""
        available = [p.name for p in self.providers if p.is_available]
        unavailable = [p.name for p in self.providers if not p.is_available]

        if available:
            logger.info(f"UnifiedLLMClient initialized with providers: {available}")
        if unavailable:
            logger.warning(f"Unavailable providers: {unavailable}")

    def get_available_providers(self) -> List[str]:
        """Return list of available provider names."""
        return [p.name for p in self.providers if p.is_available]

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response, trying providers in order until one succeeds.

        Args:
            messages: List of LLMMessage objects
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse from the first successful provider

        Raises:
            RuntimeError: If all providers fail
        """
        last_error: Optional[Exception] = None

        for provider in self.providers:
            if not provider.is_available:
                logger.debug(f"Skipping unavailable provider: {provider.name}")
                continue

            try:
                logger.info(f"Trying provider: {provider.name}")
                response = await provider.generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                logger.info(f"Success with provider: {provider.name}")
                return response

            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                last_error = e
                continue

        # All providers failed
        error_msg = f"All providers failed. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error

    async def stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream a response, trying providers in order until one succeeds.

        Args:
            messages: List of LLMMessage objects
            temperature: Sampling temperature
            **kwargs: Additional provider-specific parameters

        Yields:
            Text chunks as they are generated

        Raises:
            RuntimeError: If all providers fail
        """
        last_error: Optional[Exception] = None

        for provider in self.providers:
            if not provider.is_available:
                logger.debug(f"Skipping unavailable provider: {provider.name}")
                continue

            try:
                logger.info(f"Trying streaming with provider: {provider.name}")
                async for chunk in provider.stream(
                    messages=messages,
                    temperature=temperature,
                    **kwargs
                ):
                    yield chunk
                logger.info(f"Streaming success with provider: {provider.name}")
                return  # Successfully completed

            except Exception as e:
                logger.warning(f"Provider {provider.name} streaming failed: {e}")
                last_error = e
                continue

        # All providers failed
        error_msg = f"All providers failed for streaming. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error


def create_default_client() -> UnifiedLLMClient:
    """
    Create a UnifiedLLMClient with the default provider chain.

    Default chain (in order):
    1. Gemini (primary)
    2. OpenRouter (fallback with free models)
    3. DeepSeek (cheap fallback)

    Returns:
        Configured UnifiedLLMClient
    """
    from llm.providers import GeminiProvider, OpenRouterProvider, DeepSeekProvider

    return UnifiedLLMClient([
        GeminiProvider(),
        OpenRouterProvider(tier="rag"),
        DeepSeekProvider(),
    ])
