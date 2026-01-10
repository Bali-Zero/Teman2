"""
Unit tests for ZantaraAIClient
"""

import sys
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_root = Path(__file__).parents[2]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.llm.zantara_ai_client import ZantaraAIClient, ZantaraAIClientConstants


@pytest.fixture
def mock_settings():
    """Mock settings for ZantaraAIClient"""
    mock = MagicMock()
    mock.google_api_key = "test-google-key"
    mock.environment = "development"
    mock.zantara_ai_cost_input = 0.15
    mock.zantara_ai_cost_output = 0.60
    mock.google_credentials_json = None
    return mock


@pytest.fixture
def mock_genai_client():
    """Mock GenAIClient"""
    client = MagicMock()
    client.is_available = True
    
    # Mock chat session
    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(return_value=MagicMock(text="Test response", usage_metadata=MagicMock(prompt_token_count=10, candidates_token_count=20)))
    
    async def mock_stream(*args, **kwargs):
        mock_chunk = MagicMock()
        mock_chunk.text = "Stream chunk"
        yield mock_chunk
        
    mock_chat.send_message_stream = mock_stream
    client.create_chat = MagicMock(return_value=mock_chat)
    client.generate_content = AsyncMock(return_value=MagicMock(text="Generated"))
    
    return client


@pytest.mark.asyncio
async def test_init_success(mock_settings, mock_genai_client):
    """Test successful initialization"""
    with patch("backend.llm.zantara_ai_client.settings", mock_settings):
        with patch("backend.llm.zantara_ai_client.GenAIClient", return_value=mock_genai_client):
            with patch("backend.llm.zantara_ai_client.GENAI_AVAILABLE", True):
                client = ZantaraAIClient()
                assert client.mock_mode is False
                assert client.model == "gemini-3-flash-preview"


@pytest.mark.asyncio
async def test_init_mock_mode(mock_settings):
    """Test fallback to mock mode when no credentials"""
    mock_settings.google_api_key = None
    mock_settings.google_credentials_json = None
    with patch("backend.llm.zantara_ai_client.settings", mock_settings):
        with patch("backend.llm.zantara_ai_client.GENAI_AVAILABLE", True):
            # Use patch.dict instead of patch('os.environ', {})
            with patch.dict("os.environ", {}, clear=True):
                client = ZantaraAIClient()
                assert client.mock_mode is True


@pytest.mark.asyncio
async def test_chat_async_success(mock_settings, mock_genai_client):
    """Test successful chat_async"""
    with patch("backend.llm.zantara_ai_client.settings", mock_settings):
        with patch("backend.llm.zantara_ai_client.GenAIClient", return_value=mock_genai_client):
            with patch("backend.llm.zantara_ai_client.GENAI_AVAILABLE", True):
                client = ZantaraAIClient()
                messages = [{"role": "user", "content": "Hello"}]
                response = await client.chat_async(messages)
                
                assert isinstance(response, dict)
                assert "text" in response
                assert response["provider"] == "google_genai"


@pytest.mark.asyncio
async def test_stream_success(mock_settings, mock_genai_client):
    """Test successful streaming"""
    with patch("backend.llm.zantara_ai_client.settings", mock_settings):
        with patch("backend.llm.zantara_ai_client.GenAIClient", return_value=mock_genai_client):
            with patch("backend.llm.zantara_ai_client.GENAI_AVAILABLE", True):
                client = ZantaraAIClient()
                message = "Hello"
                
                chunks = []
                async for chunk in client.stream(message, user_id="test_user"):
                    chunks.append(chunk)
                
                print(f"DEBUG CHUNKS: {chunks}")
                assert len(chunks) > 0
                assert any("Stream chunk" in str(c) or "Stream chunk" in getattr(c, "text", "") for c in chunks)


@pytest.mark.asyncio
async def test_mock_mode_chat(mock_settings):
    """Test chat in mock mode"""
    mock_settings.google_api_key = None
    mock_settings.google_credentials_json = None
    with patch("backend.llm.zantara_ai_client.settings", mock_settings):
        with patch.dict("os.environ", {}, clear=True):
            client = ZantaraAIClient()
            assert client.mock_mode is True
            
            response = await client.chat_async([{"role": "user", "content": "hi"}])
            assert "MOCK response" in response["text"]
            assert response["provider"] == "mock"
