"""
Tests for GeminiProvider
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.llm.base import LLMMessage
from backend.llm.providers.gemini import GeminiProvider


class TestGeminiProvider:
    """Test suite for GeminiProvider"""

    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    def test_init(self, mock_gemini_service):
        """Test provider initialization"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        assert provider._model_name == "gemini-3-flash-preview"
        assert provider._service == mock_service
        assert provider._available is True

    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    def test_init_custom_model(self, mock_gemini_service):
        """Test provider initialization with custom model"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider(model_name="gemini-2.0-flash")

        assert provider._model_name == "gemini-2.0-flash"

    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    def test_init_failure(self, mock_gemini_service):
        """Test provider initialization failure"""
        mock_gemini_service.side_effect = Exception("Init failed")

        provider = GeminiProvider()

        assert provider._available is False
        assert provider._service is None

    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    def test_name_property(self, mock_gemini_service):
        """Test name property"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        assert provider.name == "gemini"

    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    def test_is_available_true(self, mock_gemini_service):
        """Test is_available when service is available"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        assert provider.is_available is True

    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    def test_is_available_false(self, mock_gemini_service):
        """Test is_available when service is not available"""
        mock_service = MagicMock()
        mock_service._available = False
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        assert provider.is_available is False

    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    def test_is_available_no_service(self, mock_gemini_service):
        """Test is_available when service is None"""
        mock_gemini_service.side_effect = Exception("Init failed")

        provider = GeminiProvider()

        assert provider.is_available is False

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_generate_success(self, mock_gemini_service):
        """Test successful generation"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_service.generate_response = AsyncMock(return_value="Test response")
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Test query")]
        response = await provider.generate(messages)

        assert response.content == "Test response"
        assert response.model == "gemini-3-flash-preview"
        assert response.provider == "gemini"
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_generate_not_available(self, mock_gemini_service):
        """Test generate when provider is not available"""
        mock_gemini_service.side_effect = Exception("Init failed")

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Test query")]

        with pytest.raises(RuntimeError, match="not available"):
            await provider.generate(messages)

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_generate_with_system_message(self, mock_gemini_service):
        """Test generate with system message"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_service.generate_response = AsyncMock(return_value="Response")
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [
            LLMMessage(role="system", content="System prompt"),
            LLMMessage(role="user", content="User query"),
        ]
        response = await provider.generate(messages)

        # Should pass context to service
        call_args = mock_service.generate_response.call_args
        assert "System prompt" in call_args.kwargs.get("context", "")

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_generate_with_history(self, mock_gemini_service):
        """Test generate with conversation history"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_service.generate_response = AsyncMock(return_value="Response")
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [
            LLMMessage(role="user", content="First message"),
            LLMMessage(role="assistant", content="Assistant response"),
            LLMMessage(role="user", content="Second message"),
        ]
        response = await provider.generate(messages)

        # Should pass history to service
        call_args = mock_service.generate_response.call_args
        assert call_args.kwargs.get("history") is not None

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_generate_with_context_kwarg(self, mock_gemini_service):
        """Test generate with context in kwargs"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_service.generate_response = AsyncMock(return_value="Response")
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Query")]
        response = await provider.generate(messages, context="Additional context")

        call_args = mock_service.generate_response.call_args
        assert "Additional context" in call_args.kwargs.get("context", "")

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_stream_success(self, mock_gemini_service):
        """Test successful streaming"""
        mock_service = MagicMock()
        mock_service._available = True

        async def mock_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"

        # Return the async generator directly, not wrapped in AsyncMock
        mock_service.generate_response_stream = mock_stream
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Test query")]
        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks == ["chunk1", "chunk2", "chunk3"]

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_stream_not_available(self, mock_gemini_service):
        """Test stream when provider is not available"""
        mock_gemini_service.side_effect = Exception("Init failed")

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Test query")]

        with pytest.raises(RuntimeError, match="not available"):
            async for _ in provider.stream(messages):
                pass

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_stream_with_system_message(self, mock_gemini_service):
        """Test stream with system message"""
        mock_service = MagicMock()
        mock_service._available = True

        async def mock_stream(*args, **kwargs):
            yield "response"

        mock_service.generate_response_stream = mock_stream
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [
            LLMMessage(role="system", content="System prompt"),
            LLMMessage(role="user", content="User query"),
        ]
        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)

        # Should have called the stream method
        assert len(chunks) > 0

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_stream_with_history(self, mock_gemini_service):
        """Test stream with conversation history"""
        mock_service = MagicMock()
        mock_service._available = True

        async def mock_stream(*args, **kwargs):
            yield "response"

        mock_service.generate_response_stream = mock_stream
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [
            LLMMessage(role="user", content="First"),
            LLMMessage(role="assistant", content="Response"),
            LLMMessage(role="user", content="Second"),
        ]
        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)

        # Should have called the stream method
        assert len(chunks) > 0

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_stream_with_context_kwarg(self, mock_gemini_service):
        """Test stream with context in kwargs"""
        mock_service = MagicMock()
        mock_service._available = True

        async def mock_stream(*args, **kwargs):
            yield "response"

        mock_service.generate_response_stream = mock_stream
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Query")]
        chunks = []
        async for chunk in provider.stream(messages, context="Additional context"):
            chunks.append(chunk)

        # Should have called the stream method
        assert len(chunks) > 0

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_generate_with_temperature(self, mock_gemini_service):
        """Test generate with temperature parameter"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_service.generate_response = AsyncMock(return_value="Response")
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Query")]
        response = await provider.generate(messages, temperature=0.5)

        # Temperature is passed but may not be used by underlying service
        assert response.content == "Response"

    @pytest.mark.asyncio
    @patch("backend.services.llm_clients.gemini_service.GeminiJakselService")
    async def test_generate_with_max_tokens(self, mock_gemini_service):
        """Test generate with max_tokens parameter"""
        mock_service = MagicMock()
        mock_service._available = True
        mock_service.generate_response = AsyncMock(return_value="Response")
        mock_gemini_service.return_value = mock_service

        provider = GeminiProvider()

        messages = [LLMMessage(role="user", content="Query")]
        response = await provider.generate(messages, max_tokens=2048)

        # max_tokens is passed but may not be used by underlying service
        assert response.content == "Response"
