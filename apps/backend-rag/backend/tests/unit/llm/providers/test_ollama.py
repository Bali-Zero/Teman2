"""
Unit tests for OllamaProvider
Target: 100% coverage
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.base import LLMMessage, LLMResponse
from backend.llm.providers.ollama import OllamaProvider


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama API response"""
    return {
        "response": "Test response from Ollama",
        "model": "qwen2.5:latest",
        "done": True,
    }


@pytest.fixture
def ollama_provider():
    """Create OllamaProvider instance"""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "qwen2.5:latest"}, {"name": "llama3.2:3b"}],
        }
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client_class.return_value.__exit__.return_value = None

        provider = OllamaProvider(model="qwen2.5:latest")
        # Initialize the _async_client attribute (implementation uses it in
        # _get_async_client but doesn't set it in __init__)
        provider._async_client = None
        return provider


class TestOllamaProvider:
    """Tests for OllamaProvider"""

    def test_init(self):
        """Test initialization"""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": [{"name": "qwen2.5:latest"}]}
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client_class.return_value.__exit__.return_value = None

            provider = OllamaProvider(model="qwen2.5:latest")
            assert provider.name == "ollama"
            assert provider._model == "qwen2.5:latest"
            assert provider._base_url == "http://localhost:11434"

    def test_init_custom_url(self):
        """Test initialization with custom URL"""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": [{"name": "qwen2.5:latest"}]}
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client_class.return_value.__exit__.return_value = None

            provider = OllamaProvider(model="qwen2.5:latest", base_url="http://custom:11434")
            assert provider._base_url == "http://custom:11434"

    def test_name_property(self, ollama_provider):
        """Test name property"""
        assert ollama_provider.name == "ollama"

    def test_is_available_property(self, ollama_provider):
        """Test is_available property"""
        assert ollama_provider.is_available is True

    @pytest.mark.asyncio
    async def test_generate_success(self, ollama_provider):
        """Test successful generation"""
        mock_response_data = {
            "response": "Test response from Ollama",
            "model": "qwen2.5:latest",
        }

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.post = AsyncMock(return_value=mock_response)

        # Mock _get_async_client to return our mock client directly
        ollama_provider._get_async_client = AsyncMock(return_value=mock_client)

        messages = [LLMMessage(role="user", content="Test message")]
        response = await ollama_provider.generate(messages)

        assert isinstance(response, LLMResponse)
        assert "Test response" in response.content

    @pytest.mark.asyncio
    async def test_generate_unavailable(self):
        """Test generation when provider unavailable"""
        provider = OllamaProvider(model="qwen2.5:latest")
        provider._async_client = None
        # Explicitly mark as unavailable (init now defers availability check)
        provider._available = False
        messages = [LLMMessage(role="user", content="Test")]

        with pytest.raises(RuntimeError, match="not available"):
            await provider.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_stream(self, ollama_provider):
        """Test streaming generation"""

        mock_chunks = [
            '{"response": "chunk1"}',
            '{"response": "chunk2"}',
            '{"response": "chunk3"}',
        ]

        async def mock_aiter_lines():
            for c in mock_chunks:
                yield c

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        @asynccontextmanager
        async def mock_stream_ctx(*args, **kwargs):
            yield mock_response

        mock_client = MagicMock()
        mock_client.stream = mock_stream_ctx

        # Mock _get_async_client to return our mock client directly
        ollama_provider._get_async_client = AsyncMock(return_value=mock_client)

        messages = [LLMMessage(role="user", content="Test")]
        chunks = []
        async for chunk in ollama_provider.generate_stream(messages):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert all(isinstance(c, LLMResponse) for c in chunks)
