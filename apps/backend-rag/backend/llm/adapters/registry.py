from enum import Enum

from llm.adapters.base import ModelAdapter
from llm.adapters.gemini import GeminiAdapter


class ModelType(Enum):
    """Active models only - legacy models removed 2025-12-28"""

    GEMINI_3_FLASH = "gemini-3-flash-preview"  # Primary tier (default)
    GEMINI_FLASH = "gemini-2.0-flash"  # Fallback tier (stable)


ADAPTER_REGISTRY = {
    ModelType.GEMINI_3_FLASH: GeminiAdapter,
    ModelType.GEMINI_FLASH: GeminiAdapter,
}


def get_adapter(model_name: str) -> ModelAdapter:
    """
    Get the appropriate adapter for the given model name.
    Handles partial matches (e.g. "gemini-2.0-flash" matches ModelType.GEMINI_FLASH)
    """
    # Try exact match first
    try:
        model_type = ModelType(model_name)
        adapter_class = ADAPTER_REGISTRY.get(model_type)
        if adapter_class:
            return adapter_class()
    except ValueError:
        pass

    # Fallback: check if known model type is in the string
    if "gemini" in model_name.lower():
        return GeminiAdapter()

    # Default fallback (could raise error, but safe default is better for now)
    return GeminiAdapter()
