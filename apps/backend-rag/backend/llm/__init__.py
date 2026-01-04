"""LLM clients for ZANTARA AI"""

# Unified LLM Provider System (new - no circular deps)
from .base import LLMMessage, LLMProvider, LLMResponse
from .client import UnifiedLLMClient, create_default_client

# Fallback messages (no circular deps)
from .fallback_messages import FALLBACK_MESSAGES, get_fallback_message
from .provider_registry import get_provider, list_providers, register_provider


def __getattr__(name: str):
    """
    Lazy imports for modules that may cause circular dependencies.

    This allows `from llm import X` to work without triggering circular imports
    at module load time.
    """
    if name == "PromptManager":
        from .prompt_manager import PromptManager

        return PromptManager
    if name == "RetryHandler":
        from .retry_handler import RetryHandler

        return RetryHandler
    if name == "TokenEstimator":
        from .token_estimator import TokenEstimator

        return TokenEstimator
    if name == "ZantaraAIClient":
        from .zantara_ai_client import ZantaraAIClient

        return ZantaraAIClient
    if name == "ZantaraAIClientConstants":
        from .zantara_ai_client import ZantaraAIClientConstants

        return ZantaraAIClientConstants
    raise AttributeError(f"module 'llm' has no attribute '{name}'")


__all__ = [
    # Unified LLM Provider System
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "UnifiedLLMClient",
    "create_default_client",
    "register_provider",
    "get_provider",
    "list_providers",
    # Fallback messages
    "get_fallback_message",
    "FALLBACK_MESSAGES",
    # Lazy-loaded (backward compat)
    "ZantaraAIClient",
    "ZantaraAIClientConstants",
    "PromptManager",
    "RetryHandler",
    "TokenEstimator",
]
