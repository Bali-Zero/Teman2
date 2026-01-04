"""
LLM Provider Registry

Centralized registry for LLM providers with factory functions.
"""

import logging

from llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Global provider registry
_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_provider(name: str, provider_class: type[LLMProvider]) -> None:
    """
    Register a provider class in the registry.

    Args:
        name: Provider name (e.g., "gemini", "openrouter")
        provider_class: The LLMProvider subclass to register
    """
    _PROVIDER_REGISTRY[name.lower()] = provider_class
    logger.debug(f"Registered LLM provider: {name}")


def get_provider(name: str, **kwargs) -> LLMProvider | None:
    """
    Get a provider instance by name.

    Args:
        name: Provider name (e.g., "gemini", "openrouter")
        **kwargs: Arguments passed to the provider constructor

    Returns:
        LLMProvider instance or None if not found
    """
    provider_class = _PROVIDER_REGISTRY.get(name.lower())
    if provider_class is None:
        logger.warning(f"Unknown provider: {name}")
        return None

    try:
        return provider_class(**kwargs)
    except Exception as e:
        logger.error(f"Failed to create provider {name}: {e}")
        return None


def list_providers() -> list[str]:
    """Return list of registered provider names."""
    return list(_PROVIDER_REGISTRY.keys())


def _register_builtin_providers():
    """Register all built-in providers."""
    try:
        from llm.providers.gemini import GeminiProvider

        register_provider("gemini", GeminiProvider)
    except ImportError:
        pass

    try:
        from llm.providers.openrouter import OpenRouterProvider

        register_provider("openrouter", OpenRouterProvider)
    except ImportError:
        pass

    try:
        from llm.providers.deepseek import DeepSeekProvider

        register_provider("deepseek", DeepSeekProvider)
    except ImportError:
        pass

    try:
        from llm.providers.vertex import VertexProvider

        register_provider("vertex", VertexProvider)
    except ImportError:
        pass


# Auto-register built-in providers on module import
_register_builtin_providers()
