"""
Unit tests for llm.providers.vertex
Auto-generated test template for high coverage

NOTE: The standalone vertex provider was removed. Gemini access is via
the GeminiProvider (backend.llm.providers.gemini). This test verifies
that the standalone vertex module no longer exists.
"""

import pytest


class TestVertex:
    """Tests for vertex provider"""

    def test_no_standalone_module(self):
        """Verify standalone vertex module was removed (access via GeminiProvider)"""
        with pytest.raises(ModuleNotFoundError):
            import backend.llm.providers.vertex  # noqa: F401

    def test_gemini_provider_exists(self):
        """Verify GeminiProvider is the active Gemini integration"""
        from backend.llm.providers.gemini import GeminiProvider

        assert GeminiProvider is not None
