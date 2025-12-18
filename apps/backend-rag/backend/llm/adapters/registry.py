from enum import Enum

from llm.adapters.base import ModelAdapter
from llm.adapters.gemini import GeminiAdapter


class ModelType(Enum):
    GEMINI_FLASH = "gemini-2.0-flash"
    GEMINI_PRO = "gemini-1.5-pro"
    GEMINI_FLASH_2_5 = "gemini-2.5-flash"
    GEMINI_PRO_2_5 = "gemini-2.5-pro"
    # Future models
    # LLAMA_4 = "llama-4-maverick"
    # QWEN_2_5 = "qwen-2.5-72b"


ADAPTER_REGISTRY = {
    ModelType.GEMINI_FLASH: GeminiAdapter,
    ModelType.GEMINI_PRO: GeminiAdapter,
    ModelType.GEMINI_FLASH_2_5: GeminiAdapter,
    ModelType.GEMINI_PRO_2_5: GeminiAdapter,
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
