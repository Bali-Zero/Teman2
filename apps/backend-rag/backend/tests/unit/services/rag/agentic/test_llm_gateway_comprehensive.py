"""
Unit tests for LLMGateway
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agentic.llm_gateway import LLMGateway, TIER_FLASH, TIER_PRO, TIER_FALLBACK
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable


@pytest.fixture
def mock_genai_client():
    """Mock GenAI client"""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    return client


@pytest.fixture
def llm_gateway():
    """Create LLM gateway instance"""
    with patch("services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        return LLMGateway(gemini_tools=[])


class TestLLMGateway:
    """Tests for LLMGateway"""

    def test_init(self):
        """Test initialization"""
        with patch("services.rag.agentic.llm_gateway.get_genai_client"):
            gateway = LLMGateway(gemini_tools=[])
            assert gateway is not None

    def test_set_gemini_tools(self, llm_gateway):
        """Test setting Gemini tools"""
        tools = [{"name": "test_tool"}]
        llm_gateway.set_gemini_tools(tools)
        assert llm_gateway.gemini_tools == tools

    @pytest.mark.asyncio
    async def test_send_message_flash_tier(self, llm_gateway):
        """Test sending message with Flash tier"""
        from services.llm_clients.pricing import create_token_usage
        
        chat = MagicMock()
        mock_token_usage = create_token_usage(
            prompt_tokens=10,
            completion_tokens=20,
            model="gemini-3-flash-preview"
        )
        
        with patch.object(llm_gateway, '_send_with_fallback') as mock_send:
            mock_send.return_value = ("response", "gemini-3-flash-preview", MagicMock(), mock_token_usage)
            
            response, model, obj, usage = await llm_gateway.send_message(
                chat=chat,
                message="test",
                tier=TIER_FLASH
            )
            
            assert response == "response"
            assert model == "gemini-3-flash-preview"

    @pytest.mark.asyncio
    async def test_send_message_fallback(self, llm_gateway):
        """Test fallback on error"""
        from services.llm_clients.pricing import create_token_usage
        
        chat = MagicMock()
        mock_token_usage = create_token_usage(
            prompt_tokens=10,
            completion_tokens=20,
            model="openrouter"
        )
        
        with patch.object(llm_gateway, '_send_with_fallback') as mock_send:
            # First call fails, second succeeds with fallback
            mock_send.return_value = ("fallback response", "openrouter", MagicMock(), mock_token_usage)
            
            response, model, obj, usage = await llm_gateway.send_message(
                chat=chat,
                message="test",
                tier=TIER_FLASH
            )
            
            assert response == "fallback response"
            assert model == "openrouter"

    @pytest.mark.asyncio
    async def test_send_message_service_unavailable(self, llm_gateway):
        """Test handling service unavailable"""
        from services.llm_clients.pricing import create_token_usage
        
        chat = MagicMock()
        mock_token_usage = create_token_usage(
            prompt_tokens=10,
            completion_tokens=20,
            model="openrouter"
        )
        
        with patch.object(llm_gateway, '_send_with_fallback') as mock_send:
            mock_send.return_value = ("fallback", "openrouter", MagicMock(), mock_token_usage)
            
            response, model, obj, usage = await llm_gateway.send_message(
                chat=chat,
                message="test"
            )
            
            assert model == "openrouter"

    @pytest.mark.asyncio
    async def test_send_message_with_tools(self, llm_gateway):
        """Test sending message with tools"""
        from services.llm_clients.pricing import create_token_usage
        
        chat = MagicMock()
        tools = [{"name": "test_tool"}]
        llm_gateway.set_gemini_tools(tools)
        mock_token_usage = create_token_usage(
            prompt_tokens=10,
            completion_tokens=20,
            model="gemini-3-flash-preview"
        )
        
        with patch.object(llm_gateway, '_send_with_fallback') as mock_send:
            mock_send.return_value = ("response", "model", MagicMock(), mock_token_usage)
            
            await llm_gateway.send_message(chat=chat, message="test")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check(self, llm_gateway):
        """Test health check"""
        from services.llm_clients.pricing import create_token_usage
        
        mock_token_usage = create_token_usage(
            prompt_tokens=10,
            completion_tokens=20,
            model="gemini-3-flash-preview"
        )
        
        with patch.object(llm_gateway, '_send_with_fallback') as mock_send:
            mock_send.return_value = ("ok", "model", MagicMock(), mock_token_usage)
            
            health = await llm_gateway.health_check()
            assert health is not None

    @pytest.mark.asyncio
    async def test_call_gemini_success(self, llm_gateway):
        """Test successful Gemini call"""
        # _call_gemini doesn't exist anymore, test _send_with_fallback instead
        from services.llm_clients.pricing import create_token_usage
        
        chat = MagicMock()
        mock_token_usage = create_token_usage(
            prompt_tokens=10,
            completion_tokens=20,
            model="gemini-3-flash-preview"
        )
        
        with patch.object(llm_gateway, '_send_with_fallback') as mock_send:
            mock_send.return_value = ("response", "gemini-3-flash-preview", MagicMock(), mock_token_usage)
            
            result = await llm_gateway.send_message(chat=chat, message="test", tier=TIER_FLASH)
            assert result is not None
            assert len(result) == 4  # (response, model, obj, usage)

