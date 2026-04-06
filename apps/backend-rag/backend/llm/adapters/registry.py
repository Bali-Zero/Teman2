from enum import Enum

from backend.llm.adapters.base import ModelAdapter
from backend.llm.adapters.gemini import GeminiAdapter


class ModelType(Enum):
    """Active models only - updated 2026-04-06 (Gemini 3 Flash GA)"""

    GEMINI_FLASH = "gemini-3-flash"  # Primary tier (GA Dec 2025)
    GEMINI_FLASH_FALLBACK = "gemini-2.5-flash"  # Fallback tier


ADAPTER_REGISTRY = {
    ModelType.GEMINI_FLASH: GeminiAdapter,
    ModelType.GEMINI_FLASH_FALLBACK: GeminiAdapter,
}


def get_adapter(model_name: str) -> ModelAdapter:
    """
    Get the appropriate adapter for the given model name.
    Handles partial matches (e.g. "gemini-3-flash" matches ModelType.GEMINI_FLASH)
    """
    # Try exact match first
    try:
        model_type = ModelType(model_name)
        adapter_class = ADAPTER_REGISTRY.get(model_type)
        if adapter_class:
            return adapter_class()
    except ValueError:
        pass  # model_name not a valid ModelType enum — fall through to string matching

    # Fallback: check if known model type is in the string
    if "gemini" in model_name.lower():
        return GeminiAdapter()

    # Default fallback (could raise error, but safe default is better for now)
    return GeminiAdapter()
