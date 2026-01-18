"""
Comprehensive tests for OpenRouterProvider
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.base import LLMMessage
from backend.llm.providers.openrouter import OpenRouterProvider


@pytest.fixture
def mock_openrouter_client():
    """Mock OpenRouterClient"""
    client = MagicMock()
    client.api_key = "test_key"
    client.complete = AsyncMock()
    return client


@pytest.fixture
def openrouter_provider(mock_openrouter_client):
    """Create OpenRouterProvider instance"""
    with patch("backend.llm.providers.openrouter.OpenRouterClient") as mock_client_class:
        mock_client_class.return_value = mock_openrouter_client
        provider = OpenRouterProvider(tier="rag")
        return provider


class TestOpenRouterProvider:
    """Tests for OpenRouterProvider"""

    def test_init(self):
        """Test initialization"""
        with patch("backend.llm.providers.openrouter.OpenRouterClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.api_key = "test_key"
            mock_client_class.return_value = mock_client

            provider = OpenRouterProvider(tier="rag")
            assert provider.name == "openrouter"
            assert provider.is_available is True

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        with patch("backend.llm.providers.openrouter.OpenRouterClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.api_key = None
            mock_client_class.return_value = mock_client

            provider = OpenRouterProvider(tier="rag")
            assert provider.is_available is False

    def test_name_property(self, openrouter_provider):
        """Test name property"""
        assert openrouter_provider.name == "openrouter"

    def test_is_available_property(self, openrouter_provider):
        """Test is_available property"""
        assert openrouter_provider.is_available is True

    @pytest.mark.asyncio
    async def test_generate_success(self, openrouter_provider, mock_openrouter_client):
        """Test successful generation"""
        mock_response = MagicMock()
        mock_response.content = "Test response"
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        mock_openrouter_client.complete.return_value = mock_response

        messages = [LLMMessage(role="user", content="Test message")]
        response = await openrouter_provider.generate(messages)

        assert isinstance(response, LLMMessage)
        assert response.content == "Test response"

    @pytest.mark.asyncio
    async def test_generate_unavailable(self):
        """Test generation when provider unavailable"""
        with patch("backend.llm.providers.openrouter.OpenRouterClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.api_key = None
            mock_client_class.return_value = mock_client

            provider = OpenRouterProvider(tier="rag")
            messages = [LLMMessage(role="user", content="Test")]

            with pytest.raises(RuntimeError, match="not available"):
                await provider.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_stream(self, openrouter_provider, mock_openrouter_client):
        """Test streaming generation"""
        mock_chunk = MagicMock()
        mock_chunk.content = "chunk"
        mock_openrouter_client.complete.return_value = [mock_chunk]

        messages = [LLMMessage(role="user", content="Test")]
        async for chunk in openrouter_provider.generate_stream(messages):
            assert chunk is not None

    def test_tier_mapping(self):
        """Test tier mapping"""
        tier_map = {
            "fast": "fast",
            "balanced": "balanced",
            "powerful": "powerful",
            "rag": "rag",
        }

        for tier_name in tier_map:
            with patch("backend.llm.providers.openrouter.OpenRouterClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.api_key = "test_key"
                mock_client_class.return_value = mock_client

                provider = OpenRouterProvider(tier=tier_name)
                assert provider.is_available is True
