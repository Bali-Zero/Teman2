"""
Unit Tests for LLMGateway

Tests the LLM Gateway's ability to:
- Initialize GenAI client correctly
- Route requests to appropriate model tiers
- Cascade fallback on quota/service errors
- Handle OpenRouter fallback
- Perform health checks
- Lazy load OpenRouter client

UPDATED 2025-12-23:
- Updated mocks for new google-genai SDK via GenAIClient wrapper

Author: Nuzantara Team
Date: 2025-12-17
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from services.rag.agentic.llm_gateway import (
    TIER_FLASH,
    TIER_LITE,
    TIER_FALLBACK,
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
def mock_genai_client():
    """Mock GenAIClient from llm.genai_client."""
    mock_client = MagicMock()
    mock_client.is_available = True

    # Mock the internal _client.aio.models.generate_content
    mock_response = MagicMock()
    mock_response.text = "Test response"

    mock_aio = MagicMock()
    mock_aio.models = MagicMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)

    mock_client._client = MagicMock()
    mock_client._client.aio = mock_aio

    # Mock generate_content for health checks
    mock_client.generate_content = AsyncMock(return_value={"text": "pong"})

    # Mock create_chat
    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(return_value={"text": "Chat response"})
    mock_client.create_chat = MagicMock(return_value=mock_chat)

    return mock_client


@pytest.fixture
def llm_gateway(mock_settings, mock_genai_client):
    """Create LLMGateway instance with mocked dependencies."""
    with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
        # Patch get_genai_client which is called by LLMGateway.__init__
        with patch("services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client):
            gateway = LLMGateway(gemini_tools=[])
            return gateway


class TestLLMGatewayInitialization:
    """Test suite for LLMGateway initialization."""

    def test_gateway_initializes_successfully(self, mock_settings, mock_genai_client):
        """Test that LLMGateway initializes with GenAI client."""
        with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch(
                "services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client
            ):
                gateway = LLMGateway()

                # Verify GenAI client was created
                assert gateway._genai_client is not None
                assert gateway._available is True

                # Verify model names are set (updated to Gemini 2.5 series)
                assert gateway.model_name_pro == "gemini-2.5-pro"
                assert gateway.model_name_flash == "gemini-2.5-flash"
                assert gateway.model_name_fallback == "gemini-2.0-flash"

                # Verify OpenRouter client is not initialized yet (lazy)
                assert gateway._openrouter_client is None

    def test_gateway_accepts_gemini_tools(self, mock_settings, mock_genai_client):
        """Test that gateway accepts and stores Gemini tool declarations."""
        fake_tools = [{"name": "test_tool", "description": "Test"}]
        with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch(
                "services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client
            ):
                gateway = LLMGateway(gemini_tools=fake_tools)

                assert gateway.gemini_tools == fake_tools


class TestLLMGatewaySendMessage:
    """Test suite for send_message functionality."""

    @pytest.mark.asyncio
    async def test_flash_tier_success(self, llm_gateway, mock_genai_client):
        """Test successful Flash model response."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Flash response to your query"
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        # Send message with Flash tier
        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="What is KITAS?",
            tier=TIER_FLASH,
        )

        # Assertions (updated to Gemini 2.5 Flash)
        assert text == "Flash response to your query"
        assert model_name == "gemini-2.5-flash"
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_pro_tier_success(self, llm_gateway, mock_genai_client):
        """Test successful Pro model response."""
        mock_response = MagicMock()
        mock_response.text = "Pro response with deep analysis"
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Analyze this complex legal document",
            tier=TIER_PRO,
        )

        assert text == "Pro response with deep analysis"
        assert model_name == "gemini-2.5-pro"
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_lite_tier_success(self, llm_gateway, mock_genai_client):
        """Test successful Lite tier response (uses fallback model)."""
        mock_response = MagicMock()
        mock_response.text = "Quick lite response"
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Simple question",
            tier=TIER_LITE,
        )

        assert text == "Quick lite response"
        # TIER_LITE now uses gemini-2.0-flash (fallback model)
        assert model_name == "gemini-2.0-flash"
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_function_calling_enabled(self, llm_gateway, mock_genai_client):
        """Test that function calling is enabled when tools are provided."""
        # Tool must have name, description, and parameters (matching GenAI SDK format)
        llm_gateway.gemini_tools = [{
            "name": "test_tool",
            "description": "A test tool for testing",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "arg1": {"type": "STRING", "description": "First argument"}
                },
                "required": ["arg1"]
            }
        }]

        mock_response = MagicMock()
        mock_response.text = "Response with tool call"
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        await llm_gateway.send_message(
            chat=None,
            message="Use a tool",
            tier=TIER_FLASH,
            enable_function_calling=True,
        )

        # Verify generate_content was called
        mock_genai_client._client.aio.models.generate_content.assert_called()


class TestLLMGatewayFallbackCascade:
    """Test suite for automatic fallback cascade logic."""

    @pytest.mark.asyncio
    async def test_fallback_flash_to_fallback_on_quota(self, llm_gateway, mock_genai_client):
        """Test fallback from Flash 2.5 to 2.0 when quota exceeded."""
        # Track which model was called
        call_count = [0]

        async def mock_generate_content(model, contents, config=None):
            call_count[0] += 1
            if "2.5" in model:
                # First call (Flash 2.5) - raise quota error
                raise ResourceExhausted("Quota exceeded for Flash 2.5")
            else:
                # Second call (Fallback 2.0) - succeed
                mock_response = MagicMock()
                mock_response.text = "Fallback 2.0 response"
                return mock_response

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        # Send message (should fallback to 2.0)
        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Test query",
            tier=TIER_FLASH,
        )

        # Assertions
        assert text == "Fallback 2.0 response"
        assert model_name == "gemini-2.0-flash"
        assert call_count[0] >= 2  # Flash 2.5 failed, then 2.0 succeeded

    @pytest.mark.asyncio
    async def test_fallback_pro_to_flash_on_service_unavailable(
        self, llm_gateway, mock_genai_client
    ):
        """Test fallback from Pro to Flash when service unavailable."""
        call_count = [0]

        async def mock_generate_content(model, contents, config=None):
            call_count[0] += 1
            if "pro" in model:
                raise ServiceUnavailable("Service temporarily unavailable")
            else:
                mock_response = MagicMock()
                mock_response.text = "Flash fallback response"
                return mock_response

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Test query",
            tier=TIER_PRO,
        )

        assert text == "Flash fallback response"
        # Pro fails -> Flash 2.5 is tried next
        assert model_name == "gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_fallback_lite_raises_when_all_fail(self, llm_gateway, mock_genai_client):
        """Test that RuntimeError is raised when all Gemini models fail (no OpenRouter fallback)."""

        async def mock_generate_content(model, contents, config=None):
            raise ResourceExhausted("All models quota exceeded")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        # Should raise RuntimeError since OpenRouter is no longer automatic fallback
        with pytest.raises(RuntimeError, match="All Gemini models unavailable"):
            await llm_gateway.send_message(
                chat=None,
                message="Test query",
                tier=TIER_LITE,
            )

    @pytest.mark.asyncio
    async def test_complete_cascade_flash_raises_when_all_fail(self, llm_gateway, mock_genai_client):
        """Test complete cascade: Flash → Fallback → RuntimeError (no OpenRouter)."""

        async def mock_generate_content(model, contents, config=None):
            # All Gemini models fail
            raise ResourceExhausted("All Gemini models quota exceeded")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        # Should raise RuntimeError when all Gemini models fail
        with pytest.raises(RuntimeError, match="All Gemini models unavailable"):
            await llm_gateway.send_message(
                chat=None,
                message="Test query",
                tier=TIER_FLASH,
            )


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
    async def test_health_check_all_healthy(self, llm_gateway, mock_genai_client):
        """Test health check when all models are healthy."""
        # Mock generate_content for health checks
        mock_genai_client.generate_content = AsyncMock(return_value={"text": "pong"})

        # Mock OpenRouter client
        with patch.object(llm_gateway, "_get_openrouter_client", return_value=MagicMock()):
            status = await llm_gateway.health_check()

        assert status["gemini_flash"] is True
        assert status["gemini_pro"] is True
        # Note: gemini_flash_lite is not tested by current health_check implementation
        assert status["openrouter"] is True

    @pytest.mark.asyncio
    async def test_health_check_flash_unhealthy(self, llm_gateway, mock_genai_client):
        """Test health check when Flash model fails."""

        async def mock_generate_content(contents, model, max_output_tokens=None):
            if "flash" in model:
                raise Exception("Connection error")
            return {"text": "pong"}

        mock_genai_client.generate_content = mock_generate_content

        with patch.object(llm_gateway, "_get_openrouter_client", return_value=MagicMock()):
            status = await llm_gateway.health_check()

        assert status["gemini_flash"] is False  # Flash failed
        assert status["gemini_pro"] is True
        assert status["openrouter"] is True

    @pytest.mark.asyncio
    async def test_health_check_openrouter_unavailable(self, llm_gateway, mock_genai_client):
        """Test health check when OpenRouter client fails to initialize."""
        # Mock generate_content for all Gemini models
        mock_genai_client.generate_content = AsyncMock(return_value={"text": "pong"})

        # Mock OpenRouter to fail
        with patch.object(llm_gateway, "_get_openrouter_client", return_value=None):
            status = await llm_gateway.health_check()

        assert status["gemini_flash"] is True
        assert status["gemini_pro"] is True
        assert status["openrouter"] is False  # OpenRouter unavailable


class TestLLMGatewayEdgeCases:
    """Test suite for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_response_without_text_attribute(self, llm_gateway, mock_genai_client):
        """Test handling response object without text attribute."""
        mock_response = MagicMock(spec=[])  # Response without 'text' attribute
        del mock_response.text

        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Test",
            tier=TIER_FLASH,
        )

        # Should return empty string when text attribute missing
        assert text == ""
        # TIER_FLASH uses gemini-2.5-flash
        assert model_name == "gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_fallback_tier_uses_gemini_2_0(self, llm_gateway, mock_genai_client):
        """Test that TIER_FALLBACK uses gemini-2.0-flash model."""
        mock_response = MagicMock()
        mock_response.text = "Fallback response"

        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj = await llm_gateway.send_message(
            chat=None,
            message="Test query",
            tier=TIER_FALLBACK,
        )

        assert text == "Fallback response"
        assert model_name == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_value_error_triggers_fallback(self, llm_gateway, mock_genai_client):
        """Test that ValueError triggers fallback to next tier."""
        call_count = [0]

        async def mock_generate_content(model, contents, config=None):
            call_count[0] += 1
            if "2.5-flash" in model:
                raise ValueError("Some error")
            # Fallback to 2.0 succeeds
            mock_response = MagicMock()
            mock_response.text = "Fallback 2.0 response"
            return mock_response

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        text, model_name, _ = await llm_gateway.send_message(
            chat=None,
            message="Test",
            tier=TIER_FLASH,
        )

        assert text == "Fallback 2.0 response"
        assert model_name == "gemini-2.0-flash"


class TestLLMGatewayCreateChatWithHistory:
    """Test suite for create_chat_with_history functionality."""

    def test_create_chat_with_empty_history(self, llm_gateway, mock_genai_client):
        """Test creating chat with empty history."""
        chat = llm_gateway.create_chat_with_history(history_to_use=None, model_tier=TIER_FLASH)

        assert chat is not None
        mock_genai_client.create_chat.assert_called_once()

    def test_create_chat_with_history(self, llm_gateway, mock_genai_client):
        """Test creating chat with conversation history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        chat = llm_gateway.create_chat_with_history(history_to_use=history, model_tier=TIER_FLASH)

        assert chat is not None
        mock_genai_client.create_chat.assert_called_once()

    def test_create_chat_different_tiers(self, llm_gateway, mock_genai_client):
        """Test creating chat with different model tiers."""
        # Pro tier
        llm_gateway.create_chat_with_history(model_tier=TIER_PRO)
        call_args = mock_genai_client.create_chat.call_args
        assert call_args[1]["model"] == "gemini-2.5-pro"

        mock_genai_client.create_chat.reset_mock()

        # Lite tier (uses same model as Flash in current implementation)
        llm_gateway.create_chat_with_history(model_tier=TIER_LITE)
        call_args = mock_genai_client.create_chat.call_args
        # TIER_LITE uses model_name_flash (gemini-2.5-flash) in create_chat_with_history
        assert call_args[1]["model"] == "gemini-2.5-flash"
