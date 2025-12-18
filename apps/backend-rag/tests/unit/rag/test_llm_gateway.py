"""
Unit Tests for LLMGateway

Tests the LLM Gateway's ability to:
- Initialize Gemini models correctly
- Route requests to appropriate model tiers
- Cascade fallback on quota/service errors
- Handle OpenRouter fallback
- Perform health checks
- Lazy load OpenRouter client

Author: Nuzantara Team
Date: 2025-12-17
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from services.rag.agentic.llm_gateway import (
    TIER_FLASH,
    TIER_LITE,
    TIER_OPENROUTER,
    TIER_PRO,
    LLMGateway,
)


@pytest.fixture
def mock_settings():
    """Mock settings with fake API key."""
    with patch("services.rag.agentic.llm_gateway.settings") as mock:
        mock.google_api_key = "fake_google_api_key_for_testing"
        yield mock


@pytest.fixture
def mock_genai():
    """Mock google.generativeai module."""
    with patch("services.rag.agentic.llm_gateway.genai") as mock:
        # Mock GenerativeModel to return mock model instances
        mock_pro = MagicMock()
        mock_flash = MagicMock()
        mock_lite = MagicMock()

        def create_model(model_name):
            if "pro" in model_name.lower():
                return mock_pro
            elif "lite" in model_name.lower():
                return mock_lite
            else:
                return mock_flash

        mock.GenerativeModel = MagicMock(side_effect=create_model)
        mock.mock_pro = mock_pro
        mock.mock_flash = mock_flash
        mock.mock_lite = mock_lite
        yield mock


@pytest.fixture
def llm_gateway(mock_settings, mock_genai):
    """Create LLMGateway instance with mocked dependencies."""
    gateway = LLMGateway(gemini_tools=[])
    return gateway


class TestLLMGatewayInitialization:
    """Test suite for LLMGateway initialization."""

    def test_gateway_initializes_successfully(self, mock_settings, mock_genai):
        """Test that LLMGateway initializes with all Gemini models."""
        gateway = LLMGateway()

        # Verify Gemini was configured
        mock_genai.configure.assert_called_once_with(api_key="fake_google_api_key_for_testing")

        # Verify all models were created
        assert gateway.model_pro is not None
        assert gateway.model_flash is not None
        assert gateway.model_flash_lite is not None

        # Verify OpenRouter client is not initialized yet (lazy)
        assert gateway._openrouter_client is None

    def test_gateway_accepts_gemini_tools(self, mock_settings, mock_genai):
        """Test that gateway accepts and stores Gemini tool declarations."""
        fake_tools = [{"name": "test_tool", "description": "Test"}]
        gateway = LLMGateway(gemini_tools=fake_tools)

        assert gateway.gemini_tools == fake_tools


class TestLLMGatewaySendMessage:
    """Test suite for send_message functionality."""

    @pytest.mark.asyncio
    async def test_flash_tier_success(self, llm_gateway, mock_genai):
        """Test successful Flash model response."""
        # Mock chat and response
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Flash response to your query"
        mock_chat.send_message_async = AsyncMock(return_value=mock_response)

        # Mock Flash model start_chat
        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_chat)

        # Send message with Flash tier
        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="What is KITAS?",
            tier=TIER_FLASH,
        )

        # Assertions
        assert text == "Flash response to your query"
        assert model_name == "gemini-2.0-flash"
        assert response_obj == mock_response
        mock_chat.send_message_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_pro_tier_success(self, llm_gateway, mock_genai):
        """Test successful Pro model response."""
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Pro response with deep analysis"
        mock_chat.send_message_async = AsyncMock(return_value=mock_response)

        mock_genai.mock_pro.start_chat = MagicMock(return_value=mock_chat)

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Analyze this complex legal document",
            tier=TIER_PRO,
        )

        assert text == "Pro response with deep analysis"
        assert model_name == "gemini-2.5-pro"
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_lite_tier_success(self, llm_gateway, mock_genai):
        """Test successful Flash-Lite model response."""
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Quick lite response"
        mock_chat.send_message_async = AsyncMock(return_value=mock_response)

        mock_genai.mock_lite.start_chat = MagicMock(return_value=mock_chat)

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Simple question",
            tier=TIER_LITE,
        )

        assert text == "Quick lite response"
        assert model_name == "gemini-2.0-flash-lite"
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_function_calling_enabled(self, llm_gateway, mock_genai):
        """Test that function calling is enabled when tools are provided."""
        llm_gateway.gemini_tools = [{"name": "test_tool"}]

        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Response with tool call"
        mock_chat.send_message_async = AsyncMock(return_value=mock_response)

        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_chat)

        await llm_gateway.send_message(
            chat=None,
            message="Use a tool",
            tier=TIER_FLASH,
            enable_function_calling=True,
        )

        # Verify tools were passed to send_message_async
        call_kwargs = mock_chat.send_message_async.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == llm_gateway.gemini_tools

    @pytest.mark.asyncio
    async def test_function_calling_disabled(self, llm_gateway, mock_genai):
        """Test that function calling can be disabled."""
        llm_gateway.gemini_tools = [{"name": "test_tool"}]

        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Response without tools"
        mock_chat.send_message_async = AsyncMock(return_value=mock_response)

        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_chat)

        await llm_gateway.send_message(
            chat=None,
            message="No tools needed",
            tier=TIER_FLASH,
            enable_function_calling=False,
        )

        # Verify tools were NOT passed
        call_kwargs = mock_chat.send_message_async.call_args[1]
        assert "tools" not in call_kwargs


class TestLLMGatewayFallbackCascade:
    """Test suite for automatic fallback cascade logic."""

    @pytest.mark.asyncio
    async def test_fallback_flash_to_lite_on_quota(self, llm_gateway, mock_genai):
        """Test fallback from Flash to Flash-Lite when quota exceeded."""
        # Mock Flash to raise ResourceExhausted
        mock_flash_chat = MagicMock()
        mock_flash_chat.send_message_async = AsyncMock(
            side_effect=ResourceExhausted("Quota exceeded for Flash")
        )
        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_flash_chat)

        # Mock Flash-Lite to succeed
        mock_lite_chat = MagicMock()
        mock_lite_response = MagicMock()
        mock_lite_response.text = "Flash-Lite fallback response"
        mock_lite_chat.send_message_async = AsyncMock(return_value=mock_lite_response)
        mock_genai.mock_lite.start_chat = MagicMock(return_value=mock_lite_chat)

        # Send message (should fallback to Lite)
        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Test query",
            tier=TIER_FLASH,
        )

        # Assertions
        assert text == "Flash-Lite fallback response"
        assert model_name == "gemini-2.0-flash-lite"
        assert mock_flash_chat.send_message_async.called
        assert mock_lite_chat.send_message_async.called

    @pytest.mark.asyncio
    async def test_fallback_pro_to_flash_on_service_unavailable(self, llm_gateway, mock_genai):
        """Test fallback from Pro to Flash when service unavailable."""
        # Mock Pro to raise ServiceUnavailable
        mock_pro_chat = MagicMock()
        mock_pro_chat.send_message_async = AsyncMock(
            side_effect=ServiceUnavailable("Service temporarily unavailable")
        )
        mock_genai.mock_pro.start_chat = MagicMock(return_value=mock_pro_chat)

        # Mock Flash to succeed
        mock_flash_chat = MagicMock()
        mock_flash_response = MagicMock()
        mock_flash_response.text = "Flash fallback response"
        mock_flash_chat.send_message_async = AsyncMock(return_value=mock_flash_response)
        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_flash_chat)

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Test query",
            tier=TIER_PRO,
        )

        assert text == "Flash fallback response"
        assert model_name == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_fallback_lite_to_openrouter_on_quota(self, llm_gateway, mock_genai):
        """Test fallback from Flash-Lite to OpenRouter when quota exceeded."""
        # Mock Flash-Lite to raise ResourceExhausted
        mock_lite_chat = MagicMock()
        mock_lite_chat.send_message_async = AsyncMock(
            side_effect=ResourceExhausted("Lite quota exceeded")
        )
        mock_genai.mock_lite.start_chat = MagicMock(return_value=mock_lite_chat)

        # Mock OpenRouter client
        with patch.object(llm_gateway, "_call_openrouter") as mock_openrouter:
            mock_openrouter.return_value = "OpenRouter fallback response"

            text, model_name, response_obj = await llm_gateway.send_message(
                chat=None,
                message="Test query",
                tier=TIER_LITE,
            )

            # Should fallback to OpenRouter
            assert "OpenRouter fallback response" in text
            assert model_name == "openrouter-fallback"
            assert response_obj is None  # OpenRouter doesn't return response object
            assert mock_openrouter.called

    @pytest.mark.asyncio
    async def test_complete_cascade_flash_to_openrouter(self, llm_gateway, mock_genai):
        """Test complete cascade: Flash → Lite → OpenRouter."""
        # Mock Flash to fail
        mock_flash_chat = MagicMock()
        mock_flash_chat.send_message_async = AsyncMock(
            side_effect=ResourceExhausted("Flash quota exceeded")
        )
        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_flash_chat)

        # Mock Flash-Lite to also fail
        mock_lite_chat = MagicMock()
        mock_lite_chat.send_message_async = AsyncMock(
            side_effect=ResourceExhausted("Lite quota exceeded")
        )
        mock_genai.mock_lite.start_chat = MagicMock(return_value=mock_lite_chat)

        # Mock OpenRouter to succeed
        with patch.object(llm_gateway, "_call_openrouter") as mock_openrouter:
            mock_openrouter.return_value = "OpenRouter final fallback"

            text, model_name, response_obj = await llm_gateway.send_message(
                chat=None,
                message="Test query",
                tier=TIER_FLASH,
            )

            # Should reach OpenRouter
            assert "OpenRouter final fallback" in text
            assert model_name == "openrouter-fallback"
            assert mock_flash_chat.send_message_async.called
            assert mock_lite_chat.send_message_async.called
            assert mock_openrouter.called


class TestLLMGatewayOpenRouter:
    """Test suite for OpenRouter fallback functionality."""

    @pytest.mark.asyncio
    async def test_openrouter_client_lazy_loading(self, llm_gateway):
        """Test that OpenRouter client is lazy-loaded."""
        # Initially None
        assert llm_gateway._openrouter_client is None

        # Mock OpenRouterClient
        with patch("services.rag.agentic.llm_gateway.OpenRouterClient") as MockClient:
            mock_client_instance = MagicMock()
            MockClient.return_value = mock_client_instance

            # Get client (should initialize)
            client = llm_gateway._get_openrouter_client()

            assert client == mock_client_instance
            assert llm_gateway._openrouter_client == mock_client_instance
            MockClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_openrouter_client_cached_after_first_load(self, llm_gateway):
        """Test that OpenRouter client is cached after first initialization."""
        with patch("services.rag.agentic.llm_gateway.OpenRouterClient") as MockClient:
            mock_client_instance = MagicMock()
            MockClient.return_value = mock_client_instance

            # First call
            client1 = llm_gateway._get_openrouter_client()
            # Second call
            client2 = llm_gateway._get_openrouter_client()

            # Should return same instance
            assert client1 == client2
            # Should only initialize once
            assert MockClient.call_count == 1

    @pytest.mark.asyncio
    async def test_call_openrouter_success(self, llm_gateway):
        """Test successful OpenRouter API call."""
        # Mock OpenRouter client
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "OpenRouter generated response"
        mock_result.model_name = "openai/gpt-4"
        mock_client.complete = AsyncMock(return_value=mock_result)

        llm_gateway._openrouter_client = mock_client

        messages = [{"role": "user", "content": "Test query"}]
        response = await llm_gateway._call_openrouter(messages, "System prompt")

        assert response == "OpenRouter generated response"
        mock_client.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_openrouter_raises_if_client_unavailable(self, llm_gateway):
        """Test that _call_openrouter raises error if client not available."""
        # Mock _get_openrouter_client to return None
        with patch.object(llm_gateway, "_get_openrouter_client", return_value=None):
            with pytest.raises(RuntimeError, match="OpenRouter client not available"):
                await llm_gateway._call_openrouter([], "System prompt")


class TestLLMGatewayHealthCheck:
    """Test suite for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, llm_gateway, mock_genai):
        """Test health check when all models are healthy."""
        # Mock all models to respond successfully
        mock_flash_chat = MagicMock()
        mock_flash_response = MagicMock()
        mock_flash_response.text = "pong"
        mock_flash_chat.send_message_async = AsyncMock(return_value=mock_flash_response)
        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_flash_chat)

        mock_pro_chat = MagicMock()
        mock_pro_response = MagicMock()
        mock_pro_response.text = "pong"
        mock_pro_chat.send_message_async = AsyncMock(return_value=mock_pro_response)
        mock_genai.mock_pro.start_chat = MagicMock(return_value=mock_pro_chat)

        mock_lite_chat = MagicMock()
        mock_lite_response = MagicMock()
        mock_lite_response.text = "pong"
        mock_lite_chat.send_message_async = AsyncMock(return_value=mock_lite_response)
        mock_genai.mock_lite.start_chat = MagicMock(return_value=mock_lite_chat)

        # Mock OpenRouter client
        with patch.object(llm_gateway, "_get_openrouter_client", return_value=MagicMock()):
            status = await llm_gateway.health_check()

        assert status["gemini_flash"] is True
        assert status["gemini_pro"] is True
        assert status["gemini_flash_lite"] is True
        assert status["openrouter"] is True

    @pytest.mark.asyncio
    async def test_health_check_flash_unhealthy(self, llm_gateway, mock_genai):
        """Test health check when Flash model fails."""
        # Mock Flash to raise error
        mock_flash_chat = MagicMock()
        mock_flash_chat.send_message_async = AsyncMock(side_effect=Exception("Connection error"))
        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_flash_chat)

        # Mock Pro to succeed
        mock_pro_chat = MagicMock()
        mock_pro_response = MagicMock()
        mock_pro_response.text = "pong"
        mock_pro_chat.send_message_async = AsyncMock(return_value=mock_pro_response)
        mock_genai.mock_pro.start_chat = MagicMock(return_value=mock_pro_chat)

        # Mock Lite to succeed
        mock_lite_chat = MagicMock()
        mock_lite_response = MagicMock()
        mock_lite_response.text = "pong"
        mock_lite_chat.send_message_async = AsyncMock(return_value=mock_lite_response)
        mock_genai.mock_lite.start_chat = MagicMock(return_value=mock_lite_chat)

        with patch.object(llm_gateway, "_get_openrouter_client", return_value=MagicMock()):
            status = await llm_gateway.health_check()

        assert status["gemini_flash"] is False  # Flash failed
        assert status["gemini_pro"] is True
        assert status["gemini_flash_lite"] is True
        assert status["openrouter"] is True

    @pytest.mark.asyncio
    async def test_health_check_openrouter_unavailable(self, llm_gateway, mock_genai):
        """Test health check when OpenRouter client fails to initialize."""
        # Mock all Gemini models to succeed
        for mock_model in [mock_genai.mock_flash, mock_genai.mock_pro, mock_genai.mock_lite]:
            mock_chat = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "pong"
            mock_chat.send_message_async = AsyncMock(return_value=mock_response)
            mock_model.start_chat = MagicMock(return_value=mock_chat)

        # Mock OpenRouter to fail
        with patch.object(llm_gateway, "_get_openrouter_client", return_value=None):
            status = await llm_gateway.health_check()

        assert status["gemini_flash"] is True
        assert status["gemini_pro"] is True
        assert status["gemini_flash_lite"] is True
        assert status["openrouter"] is False  # OpenRouter unavailable


class TestLLMGatewayEdgeCases:
    """Test suite for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_response_without_text_attribute(self, llm_gateway, mock_genai):
        """Test handling response object without text attribute."""
        mock_chat = MagicMock()
        mock_response = MagicMock(spec=[])  # Response without 'text' attribute
        # Use PropertyMock to raise AttributeError when accessing .text
        type(mock_response).text = PropertyMock(side_effect=AttributeError("No text"))

        # Create a response that doesn't have .text but doesn't raise on hasattr
        mock_response_no_text = MagicMock()
        del mock_response_no_text.text

        mock_chat.send_message_async = AsyncMock(return_value=mock_response_no_text)
        mock_genai.mock_flash.start_chat = MagicMock(return_value=mock_chat)

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Test",
            tier=TIER_FLASH,
        )

        # Should return empty string when text attribute missing
        assert text == ""
        assert model_name == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_message_extraction_for_openrouter(self, llm_gateway):
        """Test that user query is properly extracted for OpenRouter."""
        # Mock all Gemini models to fail
        with patch.object(llm_gateway, "_call_openrouter") as mock_or:
            mock_or.return_value = "OpenRouter response"

            # Simulate a structured prompt with "User Query:" marker
            structured_message = (
                "System context here\n"
                "User Query: What is KITAS?\n"
                "IMPORTANT: Do NOT start with philosophical statements..."
            )

            text, model_name, _ = await llm_gateway.send_message(
                chat=None,
                message=structured_message,
                tier=TIER_OPENROUTER,
            )

            # Verify OpenRouter was called with extracted query
            call_args = mock_or.call_args
            messages = call_args[0][0]
            assert messages[0]["content"] == "What is KITAS?"

    @pytest.mark.asyncio
    async def test_rate_limit_429_triggers_openrouter(self, llm_gateway, mock_genai):
        """Test that 429 rate limit error triggers OpenRouter fallback."""
        mock_lite_chat = MagicMock()
        mock_lite_chat.send_message_async = AsyncMock(
            side_effect=ValueError("429 Too Many Requests")
        )
        mock_genai.mock_lite.start_chat = MagicMock(return_value=mock_lite_chat)

        with patch.object(llm_gateway, "_call_openrouter") as mock_or:
            mock_or.return_value = "OpenRouter response"

            text, model_name, _ = await llm_gateway.send_message(
                chat=None,
                message="Test",
                tier=TIER_LITE,
            )

            assert "OpenRouter response" in text
            assert model_name == "openrouter-fallback"
