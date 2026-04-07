"""
Unit tests for llm.providers.deepseek
Auto-generated test template for high coverage

NOTE: The deepseek provider was removed. DeepSeek access is now via
OpenRouter (see backend.llm.providers.openrouter). This test verifies
that the standalone module no longer exists and the OpenRouter provider
covers the DeepSeek model.
"""

import pytest


class TestDeepseek:
    """Tests for deepseek provider access"""

    def test_no_standalone_module(self):
        """Verify standalone deepseek module was removed (access via OpenRouter)"""
        with pytest.raises(ModuleNotFoundError):
            import backend.llm.providers.deepseek  # noqa: F401

    def test_openrouter_has_deepseek_model(self):
        """Verify DeepSeek is available via OpenRouter config"""
        from backend.llm.config import OpenRouterModel

        assert "deepseek" in OpenRouterModel.DEEPSEEK_CHAT.lower()
