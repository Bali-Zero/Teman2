"""
Unit tests for LLM Adapters Registry
Target: >99% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.adapters.registry import (
    ADAPTER_REGISTRY,
    ModelType,
    get_adapter,
)


class TestModelType:
    """Tests for ModelType enum"""

    def test_model_type_values(self):
        """Test ModelType enum values"""
        assert ModelType.GEMINI_FLASH.value == "gemini-3-flash"
        assert ModelType.GEMINI_FLASH_FALLBACK.value == "gemini-2.5-flash"

    def test_model_type_enum(self):
        """Test ModelType enum creation"""
        assert isinstance(ModelType.GEMINI_FLASH, ModelType)
        assert isinstance(ModelType.GEMINI_FLASH_FALLBACK, ModelType)


class TestAdapterRegistry:
    """Tests for ADAPTER_REGISTRY"""

    def test_registry_contains_models(self):
        """Test that registry contains expected models"""
        assert ModelType.GEMINI_FLASH in ADAPTER_REGISTRY
        assert ModelType.GEMINI_FLASH_FALLBACK in ADAPTER_REGISTRY

    def test_registry_has_adapters(self):
        """Test that registry has adapter classes"""
        from backend.llm.adapters.gemini import GeminiAdapter

        assert ADAPTER_REGISTRY[ModelType.GEMINI_FLASH] == GeminiAdapter
        assert ADAPTER_REGISTRY[ModelType.GEMINI_FLASH_FALLBACK] == GeminiAdapter


class TestGetAdapter:
    """Tests for get_adapter function"""

    def test_get_adapter_exact_match_gemini_3_flash(self):
        """Test getting adapter with exact match for gemini-2.0-flash-lite"""
        from backend.llm.adapters.gemini import GeminiAdapter

        result = get_adapter("gemini-2.0-flash-lite")
        assert isinstance(result, GeminiAdapter)

    def test_get_adapter_exact_match_gemini_flash(self):
        """Test getting adapter with exact match for gemini-2.0-flash"""
        from backend.llm.adapters.gemini import GeminiAdapter

        result = get_adapter("gemini-2.0-flash")
        assert isinstance(result, GeminiAdapter)

    def test_get_adapter_partial_match_gemini(self):
        """Test getting adapter with partial match (contains 'gemini')"""
        from backend.llm.adapters.gemini import GeminiAdapter

        result = get_adapter("gemini-2.5-flash")
        assert isinstance(result, GeminiAdapter)

    def test_get_adapter_partial_match_case_insensitive(self):
        """Test getting adapter with partial match case insensitive"""
        from backend.llm.adapters.gemini import GeminiAdapter

        result = get_adapter("GEMINI-2.5-FLASH")
        assert isinstance(result, GeminiAdapter)

    def test_get_adapter_invalid_model_name(self):
        """Test getting adapter with invalid model name (fallback to GeminiAdapter)"""
        from backend.llm.adapters.gemini import GeminiAdapter

        # Invalid model name will raise ValueError, then fallback to GeminiAdapter
        result = get_adapter("invalid-model-name")
        assert isinstance(result, GeminiAdapter)

    def test_get_adapter_empty_string(self):
        """Test getting adapter with empty string (fallback to GeminiAdapter)"""
        from backend.llm.adapters.gemini import GeminiAdapter

        result = get_adapter("")
        assert isinstance(result, GeminiAdapter)

    def test_get_adapter_no_gemini_in_name(self):
        """Test getting adapter with name that doesn't contain 'gemini' (default fallback)"""
        from backend.llm.adapters.gemini import GeminiAdapter

        result = get_adapter("openai-gpt-4")
        assert isinstance(result, GeminiAdapter)
