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
UPDATED 2025-12-28:
- Fixed trace_span mocking to use nullcontext

Author: Nuzantara Team
Date: 2025-12-17
"""

from contextlib import nullcontext
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from services.rag.agentic.llm_gateway import (
    TIER_FALLBACK,
    TIER_FLASH,
    TIER_LITE,
    TIER_PRO,
    LLMGateway,
)


def create_mock_response(text="Test response", prompt_tokens=10, completion_tokens=20):
    """Create a properly mocked Gemini response with usage_metadata."""
    mock_response = MagicMock()
    mock_response.text = text
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = prompt_tokens
    mock_usage.candidates_token_count = completion_tokens
    mock_response.usage_metadata = mock_usage
    return mock_response


@pytest.fixture
def mock_settings():
    """Mock settings with fake API key."""
    mock = MagicMock()
    mock.google_api_key = "fake_google_api_key_for_testing"
    return mock


@pytest.fixture
def mock_genai_client():
    """Mock GenAIClient from llm.genai_client."""
    mock_client = MagicMock()
    mock_client.is_available = True

    # Mock the internal _client.aio.models.generate_content
    mock_response = create_mock_response("Test response")

    mock_aio = MagicMock()
    mock_aio.models = MagicMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)

    mock_client._client = MagicMock()
    mock_client._client.aio = mock_aio

    # Mock generate_content for health checks
    mock_client.generate_content = AsyncMock(return_value={"text": "pong"})

    # Mock create_chat and create_chat_session
    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(return_value={"text": "Chat response"})
    mock_client.create_chat = MagicMock(return_value=mock_chat)
    mock_client.create_chat_session = MagicMock(return_value=mock_chat)

    return mock_client


@pytest.fixture(autouse=True)
def mock_trace_span():
    """Mock trace_span to use nullcontext to avoid generator issues."""
    with patch(
        "services.rag.agentic.llm_gateway.trace_span",
        side_effect=lambda *args, **kwargs: nullcontext(),
    ):
        yield


@pytest.fixture
def llm_gateway(mock_settings, mock_genai_client):
    """Create LLMGateway instance with mocked dependencies."""
    with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
        # Patch get_genai_client which is called by LLMGateway.__init__
        with patch(
            "services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client
        ):
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

                # Verify model names are set (Gemini 3 Flash Preview primary)
                assert gateway.model_name_pro == "gemini-3-flash-preview"
                assert gateway.model_name_flash == "gemini-3-flash-preview"
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
        mock_response = create_mock_response("Flash response to your query")
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        # Send message with Flash tier
        text, model_name, response_obj, _ = await llm_gateway.send_message(
            chat=None,
            message="What is KITAS?",
            tier=TIER_FLASH,
        )

        # Assertions (Gemini 3 Flash Preview)
        assert text == "Flash response to your query"
        assert model_name == "gemini-3-flash-preview"
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_pro_tier_success(self, llm_gateway, mock_genai_client):
        """Test successful Pro model response."""
        mock_response = create_mock_response("Pro response with deep analysis")
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj, _ = await llm_gateway.send_message(
            chat=None,
            message="Analyze this complex legal document",
            tier=TIER_PRO,
        )

        assert text == "Pro response with deep analysis"
        assert model_name == "gemini-3-flash-preview"
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_lite_tier_success(self, llm_gateway, mock_genai_client):
        """Test successful Lite tier response (uses fallback model)."""
        mock_response = create_mock_response("Quick lite response")
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj, _ = await llm_gateway.send_message(
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
        llm_gateway.gemini_tools = [
            {
                "name": "test_tool",
                "description": "A test tool for testing",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"arg1": {"type": "STRING", "description": "First argument"}},
                    "required": ["arg1"],
                },
            }
        ]

        mock_response = create_mock_response("Response with tool call")
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
            if "3" in model or "2.5" in model:
                # First call (Flash 3) - raise quota error
                raise ResourceExhausted("Quota exceeded for Flash 3")
            else:
                # Second call (Fallback 2.0) - succeed
                return create_mock_response("Fallback 2.0 response")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        # Send message (should fallback to 2.0)
        text, model_name, response_obj, _ = await llm_gateway.send_message(
            chat=None,
            message="Test query",
            tier=TIER_FLASH,
        )

        # Assertions
        assert text == "Fallback 2.0 response"
        assert model_name == "gemini-2.0-flash"
        assert call_count[0] >= 2  # Flash 3 failed, then 2.0 succeeded

    @pytest.mark.asyncio
    async def test_fallback_pro_to_flash_on_service_unavailable(
        self, llm_gateway, mock_genai_client
    ):
        """Test fallback from Pro to Flash when service unavailable."""
        call_count = [0]

        async def mock_generate_content(model, contents, config=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ServiceUnavailable("Service temporarily unavailable")
            else:
                return create_mock_response("Flash fallback response")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        text, model_name, response_obj, _ = await llm_gateway.send_message(
            chat=None,
            message="Test query",
            tier=TIER_PRO,
        )

        assert text == "Flash fallback response"
        # Pro fails -> Flash (2.0 fallback) is tried next
        assert model_name == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_fallback_lite_raises_when_all_fail(self, llm_gateway, mock_genai_client):
        """Test that RuntimeError is raised when all Gemini models fail (no OpenRouter fallback)."""

        async def mock_generate_content(model, contents, config=None):
            raise ResourceExhausted("All models quota exceeded")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        # Should raise RuntimeError since OpenRouter is no longer automatic fallback
        with pytest.raises(RuntimeError, match="All LLM models failed"):
            await llm_gateway.send_message(
                chat=None,
                message="Test query",
                tier=TIER_LITE,
            )

    @pytest.mark.asyncio
    async def test_complete_cascade_flash_raises_when_all_fail(
        self, llm_gateway, mock_genai_client
    ):
        """Test complete cascade: Flash → Fallback → RuntimeError (no OpenRouter)."""

        async def mock_generate_content(model, contents, config=None):
            # All Gemini models fail
            raise ResourceExhausted("All Gemini models quota exceeded")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        with pytest.raises(RuntimeError, match="All LLM models failed"):
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
        """Test health check when Gemini models fail.

        Note: In current implementation, model_name_pro and model_name_flash
        both use 'gemini-3-flash-preview', so they will fail together.
        """

        async def mock_generate_content(*, contents, model, max_output_tokens=None):
            # Simulate connection failure for all Gemini models
            raise Exception("Connection error")

        # Assign to the actual _genai_client instance used by llm_gateway
        llm_gateway._genai_client.generate_content = mock_generate_content

        with patch.object(llm_gateway, "_get_openrouter_client", return_value=MagicMock()):
            status = await llm_gateway.health_check()

        # All Gemini models fail since they share the same model name
        assert status["gemini_flash"] is False
        assert status["gemini_pro"] is False
        assert status["gemini_flash_lite"] is False
        # OpenRouter should still be available
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
        mock_response = create_mock_response("")
        mock_response.text = None  # Simulate missing text

        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj, _ = await llm_gateway.send_message(
            chat=None,
            message="Test",
            tier=TIER_FLASH,
        )

        # Should return empty string when text attribute is None
        assert text == "" or text is None
        # TIER_FLASH uses gemini-3-flash-preview
        assert model_name == "gemini-3-flash-preview"

    @pytest.mark.asyncio
    async def test_fallback_tier_uses_gemini_2_0(self, llm_gateway, mock_genai_client):
        """Test that TIER_FALLBACK uses gemini-2.0-flash model."""
        mock_response = create_mock_response("Fallback response")

        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj, _ = await llm_gateway.send_message(
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
            if "3-flash" in model:
                raise ValueError("Some error")
            # Fallback to 2.0 succeeds
            return create_mock_response("Fallback 2.0 response")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        text, model_name, _, __ = await llm_gateway.send_message(
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
        mock_genai_client.create_chat_session.assert_called_once()

    def test_create_chat_with_history(self, llm_gateway, mock_genai_client):
        """Test creating chat with conversation history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        chat = llm_gateway.create_chat_with_history(history_to_use=history, model_tier=TIER_FLASH)

        assert chat is not None
        mock_genai_client.create_chat_session.assert_called_once()

    def test_create_chat_different_tiers(self, llm_gateway, mock_genai_client):
        """Test creating chat sessions with different tiers."""
        # Flash (default)
        llm_gateway.create_chat_with_history(model_tier=TIER_FLASH)
        call_args = mock_genai_client.create_chat_session.call_args
        assert call_args[1]["model"] == "gemini-3-flash-preview"

        # Pro
        llm_gateway.create_chat_with_history(model_tier=TIER_PRO)
        call_args = mock_genai_client.create_chat_session.call_args
        assert call_args[1]["model"] == "gemini-3-flash-preview"  # Both currently use same model

        # Lite
        llm_gateway.create_chat_with_history(model_tier=TIER_LITE)
        call_args = mock_genai_client.create_chat_session.call_args
        assert call_args[1]["model"] == "gemini-3-flash-preview"


class TestLLMGatewayCoverageImprovements:
    """Test suite to improve coverage for edge cases."""

    @pytest.mark.asyncio
    async def test_genai_client_not_available_init(self, mock_settings):
        """Test initialization when GenAI client is not available (lines 121-123)."""
        with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch("services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
                mock_client = MagicMock()
                mock_client.is_available = False  # Client exists but not available
                mock_get.return_value = mock_client

                gateway = LLMGateway(gemini_tools=[])
                assert gateway._available is False

    @pytest.mark.asyncio
    async def test_genai_client_init_exception(self, mock_settings):
        """Test initialization when get_genai_client raises exception (line 123)."""
        with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch("services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
                mock_get.side_effect = Exception("Initialization failed")

                gateway = LLMGateway(gemini_tools=[])
                assert gateway._genai_client is None or gateway._available is False

    def test_set_gemini_tools(self, llm_gateway):
        """Test set_gemini_tools method (lines 144-145)."""
        new_tools = [{"name": "test_tool", "description": "Test"}]
        llm_gateway.set_gemini_tools(new_tools)
        assert llm_gateway.gemini_tools == new_tools

        # Test with None
        llm_gateway.set_gemini_tools(None)
        assert llm_gateway.gemini_tools == []

    @pytest.mark.asyncio
    async def test_openrouter_initialization_failure(self, llm_gateway):
        """Test OpenRouter initialization failure paths (lines 165-167)."""
        import httpx

        # Reset the cached client
        llm_gateway._openrouter_client = None

        with patch("services.rag.agentic.llm_gateway.OpenRouterClient") as MockClient:
            MockClient.side_effect = httpx.HTTPError("Connection failed")

            result = llm_gateway._get_openrouter_client()
            assert result is None

    @pytest.mark.asyncio
    async def test_openrouter_value_error(self, llm_gateway):
        """Test OpenRouter initialization with ValueError."""
        llm_gateway._openrouter_client = None

        with patch("services.rag.agentic.llm_gateway.OpenRouterClient") as MockClient:
            MockClient.side_effect = ValueError("Invalid configuration")

            result = llm_gateway._get_openrouter_client()
            assert result is None

    @pytest.mark.asyncio
    async def test_send_message_genai_not_available(self, mock_settings):
        """Test send_message when GenAI client is not available (line 328, 454-455)."""
        with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch("services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
                mock_client = MagicMock()
                mock_client.is_available = False
                mock_get.return_value = mock_client

                gateway = LLMGateway(gemini_tools=[])

                with pytest.raises(RuntimeError, match="All LLM models failed"):
                    await gateway.send_message(
                        chat=None,
                        message="Test",
                        tier=TIER_FLASH,
                    )

    @pytest.mark.asyncio
    async def test_send_message_with_system_prompt(self, llm_gateway, mock_genai_client):
        """Test send_message with system_prompt (line 284)."""
        mock_response = create_mock_response("Response with system prompt")
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, _, __ = await llm_gateway.send_message(
            chat=None,
            message="Test",
            tier=TIER_FLASH,
            system_prompt="You are a helpful assistant.",
        )

        assert text == "Response with system prompt"

    @pytest.mark.asyncio
    async def test_pro_tier_value_error_fallback(self, llm_gateway, mock_genai_client):
        """Test PRO tier ValueError triggers fallback (lines 404-409)."""
        call_count = [0]

        async def mock_generate_content(model, contents, config=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Pro tier error")
            return create_mock_response("Fallback response")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        text, model_name, _, __ = await llm_gateway.send_message(
            chat=None,
            message="Test",
            tier=TIER_PRO,
        )

        # Should have fallen back to 2.0 after ValueError
        assert text == "Fallback response"
        assert model_name == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_fallback_value_error_raises(self, llm_gateway, mock_genai_client):
        """Test fallback tier ValueError raises RuntimeError (lines 448-452)."""

        async def mock_generate_content(model, contents, config=None):
            raise ValueError("Fallback tier error")

        mock_genai_client._client.aio.models.generate_content = mock_generate_content

        with pytest.raises(RuntimeError, match="All LLM models failed"):
            await llm_gateway.send_message(
                chat=None,
                message="Test",
                tier=TIER_FALLBACK,
            )

    def test_create_chat_client_not_available(self, mock_settings):
        """Test create_chat_with_history when client not available (lines 518-519)."""
        with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch("services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
                mock_client = MagicMock()
                mock_client.is_available = False
                mock_get.return_value = mock_client

                gateway = LLMGateway(gemini_tools=[])
                result = gateway.create_chat_with_history(model_tier=TIER_FLASH)
                assert result is None

    def test_create_chat_history_not_list(self, llm_gateway, mock_genai_client):
        """Test create_chat_with_history when history is not a list (lines 533-536)."""
        # Pass a string instead of a list
        llm_gateway.create_chat_with_history(
            history_to_use="not a list",  # type: ignore
            model_tier=TIER_FLASH,
        )

        # Should have been called with empty history
        call_args = mock_genai_client.create_chat_session.call_args
        assert call_args[1]["history"] == []

    def test_create_chat_non_dict_message(self, llm_gateway, mock_genai_client):
        """Test create_chat_with_history with non-dict message in history (lines 541-542)."""
        history = [
            {"role": "user", "content": "Valid message"},
            "not a dict",  # Invalid message
            {"role": "assistant", "content": "Response"},
        ]

        llm_gateway.create_chat_with_history(
            history_to_use=history,  # type: ignore
            model_tier=TIER_FLASH,
        )

        # Should filter out the invalid message
        call_args = mock_genai_client.create_chat_session.call_args
        assert len(call_args[1]["history"]) == 2

    @pytest.mark.asyncio
    async def test_health_check_genai_not_available(self, mock_settings):
        """Test health_check when GenAI client is not available (line 590)."""
        with patch("services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch("services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
                mock_client = MagicMock()
                mock_client.is_available = False
                mock_get.return_value = mock_client

                gateway = LLMGateway(gemini_tools=[])

                with patch.object(gateway, "_get_openrouter_client", return_value=None):
                    status = await gateway.health_check()

                # All should be False when client not available
                assert status["gemini_flash"] is False
                assert status["gemini_pro"] is False
                assert status["openrouter"] is False

    @pytest.mark.asyncio
    async def test_response_value_error_function_call(self, llm_gateway, mock_genai_client):
        """Test ValueError when accessing response.text (function call, lines 376-380)."""
        mock_response = MagicMock()
        # Simulate function call where .text raises ValueError
        type(mock_response).text = property(
            lambda self: (_ for _ in ()).throw(ValueError("No text"))
        )
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 10
        mock_usage.candidates_token_count = 20
        mock_response.usage_metadata = mock_usage

        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        text, model_name, response_obj, _ = await llm_gateway.send_message(
            chat=None,
            message="Test",
            tier=TIER_FLASH,
        )

        # Should return empty string for function call
        assert text == ""
        assert response_obj == mock_response

    @pytest.mark.asyncio
    async def test_tool_config_exception(self, llm_gateway, mock_genai_client):
        """Test tool_config exception handling (lines 319-320)."""
        mock_response = create_mock_response("Response with tools")
        mock_genai_client._client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        # Set tools to trigger tool config path
        llm_gateway.gemini_tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"arg": {"type": "STRING", "description": "An arg"}},
                    "required": ["arg"],
                },
            }
        ]

        # Mock types to raise exception on ToolConfig
        with patch("services.rag.agentic.llm_gateway.types") as mock_types:
            mock_types.GenerateContentConfig = MagicMock()
            mock_types.FunctionDeclaration = MagicMock()
            mock_types.Schema = MagicMock()
            mock_types.Tool = MagicMock()
            mock_types.ToolConfig.side_effect = AttributeError("ToolConfig not available")

            text, model_name, _, __ = await llm_gateway.send_message(
                chat=None,
                message="Test",
                tier=TIER_FLASH,
                enable_function_calling=True,
            )

            # Should still work despite tool_config failure
            assert model_name == "gemini-3-flash-preview"
