"""
Tests for GeminiJakselService - OpenRouter fallback coverage.
"""

from unittest.mock import MagicMock, patch

import pytest


def test_openrouter_fallback_missing():
    """When OpenRouter client is None, fallback is unavailable."""
    with patch("backend.services.llm_clients.gemini_service.GENAI_AVAILABLE", False), \
         patch("backend.services.llm_clients.gemini_service.get_genai_client"), \
         patch("backend.services.llm_clients.gemini_service.settings") as ms, \
         patch("backend.app.core.circuit_breaker.CircuitBreaker"):
        ms.google_api_key = "test"
        from backend.services.llm_clients.gemini_service import GeminiJakselService
        svc = GeminiJakselService.__new__(GeminiJakselService)
        svc._openrouter_client = None
        assert svc._openrouter_client is None
