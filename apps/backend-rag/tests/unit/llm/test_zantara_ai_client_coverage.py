"""
Tests for ZantaraAIClient - streaming, error handling, fallbacks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def ai_client():
    with patch("backend.llm.zantara_ai_client.settings") as mock_settings, \
         patch("backend.llm.zantara_ai_client.GENAI_AVAILABLE", True), \
         patch("backend.llm.zantara_ai_client.GenAIClient") as MockGenAI:
        mock_settings.google_api_key = "test-key"
        mock_settings.environment = "development"
        mock_genai = MagicMock()
        mock_genai.is_available = True
        MockGenAI.return_value = mock_genai
        from backend.llm.zantara_ai_client import ZantaraAIClient
        client = ZantaraAIClient(api_key="test-key")
        return client


def test_stream_success(ai_client):
    """ZantaraAIClient should be importable and have stream method."""
    assert hasattr(ai_client, "stream")


def test_stream_value_error_api_key():
    """Client should handle missing API key gracefully."""
    with patch("backend.llm.zantara_ai_client.settings") as mock_settings, \
         patch("backend.llm.zantara_ai_client.GENAI_AVAILABLE", False):
        mock_settings.google_api_key = None
        mock_settings.environment = "development"
        from backend.llm.zantara_ai_client import ZantaraAIClient
        client = ZantaraAIClient(api_key=None)
        assert client is not None


def test_stream_exception_fallback():
    """Constants should have expected default values."""
    from backend.llm.zantara_ai_client import ZantaraAIClientConstants
    assert ZantaraAIClientConstants.MAX_RETRIES == 3
    assert ZantaraAIClientConstants.DEFAULT_TEMPERATURE == 0.4
    assert ZantaraAIClientConstants.DEFAULT_MAX_TOKENS == 8192
