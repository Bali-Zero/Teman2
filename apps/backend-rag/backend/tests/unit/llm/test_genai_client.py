"""
Unit tests for GenAIClient
Target: 100% coverage
Composer: 3
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from llm.genai_client import GenAIClient, get_genai_client


@pytest.fixture
def genai_client():
    """Create GenAI client instance"""
    with patch("llm.genai_client.genai") as mock_genai, \
         patch("llm.genai_client.types") as mock_types, \
         patch("llm.genai_client.GENAI_AVAILABLE", True):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        client = GenAIClient(api_key="test-key")
        client._client = mock_client
        client._available = True
        return client


class TestGenAIClient:
    """Tests for GenAIClient"""

    def test_init(self):
        """Test initialization"""
        with patch("llm.genai_client.genai") as mock_genai, \
             patch("llm.genai_client.GENAI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            client = GenAIClient(api_key="test-key")
            assert client is not None

    @pytest.mark.asyncio
    async def test_generate_content(self, genai_client):
        """Test content generation"""
        mock_response = MagicMock()
        mock_response.text = "test response"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        
        genai_client._client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        
        result = await genai_client.generate_content("test prompt")
        assert result["text"] == "test response"
        assert result["model"] == genai_client.DEFAULT_MODEL
        assert "usage" in result

    @pytest.mark.asyncio
    async def test_generate_content_stream(self, genai_client):
        """Test streaming content generation"""
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "chunk1"
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "chunk2"
        
        async def mock_stream(*args, **kwargs):
            yield mock_chunk1
            yield mock_chunk2
        
        # Mock must return async generator directly, not wrapped in AsyncMock
        genai_client._client.aio.models.generate_content_stream = mock_stream
        
        chunks = []
        async for chunk in genai_client.generate_content_stream("test"):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0] == "chunk1"
        assert chunks[1] == "chunk2"

    def test_get_genai_client_singleton(self):
        """Test singleton pattern"""
        with patch("llm.genai_client.genai") as mock_genai, \
             patch("llm.genai_client.GENAI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            
            # Reset singleton
            import llm.genai_client
            llm.genai_client._client_instance = None
            
            client1 = get_genai_client()
            client2 = get_genai_client()
            # Should return same instance
            assert client1 is client2

