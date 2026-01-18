"""
Unit tests for OllamaProvider
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
            "models": [{"name": "qwen2.5:latest"}, {"name": "llama3.2:3b"}]
        }
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client_class.return_value.__exit__.return_value = None

        provider = OllamaProvider(model="qwen2.5:latest")
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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            messages = [LLMMessage(role="user", content="Test message")]
            response = await ollama_provider.generate(messages)

            assert isinstance(response, LLMMessage)
            assert "Test response" in response.content

    @pytest.mark.asyncio
    async def test_generate_unavailable(self):
        """Test generation when provider unavailable"""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client_class.return_value.__exit__.return_value = None

            provider = OllamaProvider(model="qwen2.5:latest")
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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.status_code = 200
            mock_stream.aiter_lines = AsyncMock(return_value=iter(mock_chunks))
            mock_client.stream = AsyncMock(return_value=mock_stream)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            messages = [LLMMessage(role="user", content="Test")]
            chunks = []
            async for chunk in ollama_provider.generate_stream(messages):
                chunks.append(chunk)

            assert len(chunks) > 0
