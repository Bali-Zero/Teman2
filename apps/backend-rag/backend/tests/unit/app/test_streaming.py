"""
Unit tests for Streaming endpoints
Target: 100% coverage
Composer: 2
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.streaming import ChatStreamRequest, _parse_history, bali_zero_chat_stream


@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"email": "test@example.com"}
    request.app.state = MagicMock()
    request.app.state.services_initialized = True
    request.app.state.intelligent_router = MagicMock()
    request.headers = {"X-API-Key": "test-key"}
    return request


@pytest.fixture
def mock_intelligent_router():
    """Mock intelligent router"""
    router = AsyncMock()
    router.stream_response = AsyncMock()
    router.stream_response.return_value = AsyncMock()
    router.stream_response.return_value.__aiter__.return_value = [{"type": "text", "data": "test"}]
    return router


class TestStreamingRouter:
    """Tests for Streaming Router"""

    def test_parse_history_valid_json(self):
        """Test parsing valid JSON history"""
        history = '[{"role": "user", "content": "test"}]'
        result = _parse_history(history)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_parse_history_invalid_json(self):
        """Test parsing invalid JSON"""
        history = "invalid json"
        result = _parse_history(history)
        assert result == []

    def test_parse_history_none(self):
        """Test parsing None"""
        result = _parse_history(None)
        assert result == []

    def test_parse_history_not_list(self):
        """Test parsing non-list JSON"""
        history = '{"not": "a list"}'
        result = _parse_history(history)
        assert result == []

    @pytest.mark.asyncio
    async def test_bali_zero_chat_stream_success(self, mock_request, mock_intelligent_router):
        """Test successful streaming"""
        mock_request.app.state.intelligent_router = mock_intelligent_router

        with patch("backend.app.streaming.validate_auth_mixed", return_value={"email": "test@example.com"}):
            response = await bali_zero_chat_stream(
                request=mock_request, query="test query", background_tasks=MagicMock()
            )

            assert response is not None

    @pytest.mark.asyncio
    async def test_bali_zero_chat_stream_empty_query(self, mock_request):
        """Test empty query"""
        with pytest.raises(Exception):  # Should raise HTTPException
            await bali_zero_chat_stream(
                request=mock_request, query="", background_tasks=MagicMock()
            )

    @pytest.mark.asyncio
    async def test_bali_zero_chat_stream_no_auth(self, mock_request):
        """Test without authentication"""
        mock_request.state.user = None

        with patch("backend.app.streaming.validate_auth_mixed", return_value=None):
            with pytest.raises(Exception):  # Should raise HTTPException
                await bali_zero_chat_stream(
                    request=mock_request, query="test", background_tasks=MagicMock()
                )

    @pytest.mark.asyncio
    async def test_bali_zero_chat_stream_services_not_initialized(self, mock_request):
        """Test when services not initialized"""
        mock_request.app.state.services_initialized = False

        with pytest.raises(Exception):  # Should raise HTTPException
            await bali_zero_chat_stream(
                request=mock_request, query="test", background_tasks=MagicMock()
            )


class TestChatStreamRequest:
    """Tests for ChatStreamRequest model"""

    def test_request_creation(self):
        """Test request creation"""
        request = ChatStreamRequest(message="test")
        assert request.message == "test"
        assert request.user_id is None

    def test_request_with_history(self):
        """Test request with history"""
        request = ChatStreamRequest(
            message="test", conversation_history=[{"role": "user", "content": "previous"}]
        )
        assert len(request.conversation_history) == 1

    def test_request_with_metadata(self):
        """Test request with metadata"""
        request = ChatStreamRequest(message="test", metadata={"key": "value"})
        assert request.metadata["key"] == "value"
