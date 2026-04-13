"""Tests for GeminiJakselService and GeminiService wrapper.

Covers: initialization, generate_response, generate_response_stream,
circuit breaker behavior, OpenRouter fallback, and the GeminiService
compatibility wrapper.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core.exceptions import GoogleAPIError, ResourceExhausted, ServiceUnavailable

from backend.services.llm_clients.gemini_service import GeminiJakselService, GeminiService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_persona() -> Any:
    """Patch the persona imports so tests don't depend on prompt files."""
    with (
        patch(
            "backend.services.llm_clients.gemini_service.SYSTEM_INSTRUCTION",
            "You are a test assistant.",
        ),
        patch(
            "backend.services.llm_clients.gemini_service.FEW_SHOT_EXAMPLES",
            [
                {"role": "user", "content": "Hello"},
                {"role": "model", "content": "Hi there!"},
            ],
        ),
    ):
        yield


@pytest.fixture
def mock_genai_client() -> MagicMock:
    """Create a mock GenAI client that reports is_available=True."""
    client = MagicMock()
    client.is_available = True
    client._auth_method = "api_key"

    # create_chat returns a mock ChatSession
    chat = MagicMock()
    client.create_chat.return_value = chat
    return client


@pytest.fixture
def service(_patch_persona: Any, mock_genai_client: MagicMock) -> GeminiJakselService:
    """Build a GeminiJakselService with the GenAI client pre-injected."""
    svc = GeminiJakselService(model_name="gemini-test-model")
    # Inject mock client directly (bypass lazy loader)
    svc._genai_client = mock_genai_client
    return svc


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitialization:
    """Verify construction and lazy-load wiring."""

    def test_model_name_strips_prefix(self, _patch_persona: Any) -> None:
        svc = GeminiJakselService(model_name="models/gemini-3-flash-preview")
        assert svc.model_name == "gemini-3-flash-preview"

    def test_default_model_name(self, _patch_persona: Any) -> None:
        svc = GeminiJakselService()
        assert svc.model_name == "gemini-3-flash-preview"

    def test_few_shot_history_populated(self, _patch_persona: Any) -> None:
        svc = GeminiJakselService()
        assert len(svc.few_shot_history) == 2
        assert svc.few_shot_history[0]["role"] == "user"

    def test_genai_client_initially_none(self, _patch_persona: Any) -> None:
        svc = GeminiJakselService()
        assert svc._genai_client is None

    def test_circuit_breaker_created(self, _patch_persona: Any) -> None:
        svc = GeminiJakselService()
        assert svc._gemini_circuit is not None
        assert svc._gemini_circuit.name == "gemini-jaksel"
        assert svc._gemini_circuit.failure_threshold == 5


# ---------------------------------------------------------------------------
# Lazy client loading
# ---------------------------------------------------------------------------


class TestLazyClientLoading:
    """Test _get_genai_client and _available property."""

    def test_get_genai_client_returns_cached(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        result = service._get_genai_client()
        assert result is mock_genai_client

    @patch("backend.services.llm_clients.gemini_service.GENAI_AVAILABLE", True)
    @patch("backend.services.llm_clients.gemini_service.get_genai_client")
    def test_get_genai_client_lazy_loads(
        self, mock_get: MagicMock, _patch_persona: Any,
    ) -> None:
        client = MagicMock()
        client.is_available = True
        client._auth_method = "api_key"
        mock_get.return_value = client

        svc = GeminiJakselService()
        result = svc._get_genai_client()
        assert result is client
        mock_get.assert_called_once()

    @patch("backend.services.llm_clients.gemini_service.GENAI_AVAILABLE", False)
    def test_get_genai_client_returns_none_when_unavailable(
        self, _patch_persona: Any,
    ) -> None:
        svc = GeminiJakselService()
        assert svc._get_genai_client() is None

    def test_available_property_true(
        self, service: GeminiJakselService,
    ) -> None:
        assert service._available is True

    @patch("backend.services.llm_clients.gemini_service.GENAI_AVAILABLE", False)
    def test_available_property_false_when_no_sdk(
        self, _patch_persona: Any,
    ) -> None:
        svc = GeminiJakselService()
        assert svc._available is False


# ---------------------------------------------------------------------------
# generate_response_stream — success path
# ---------------------------------------------------------------------------


class TestGenerateResponseStream:
    """Test streaming generation with Gemini and fallback."""

    @pytest.mark.asyncio
    async def test_stream_success_yields_chunks(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """Gemini available, circuit closed -> yields chunks from chat stream."""
        chat = mock_genai_client.create_chat.return_value

        async def fake_stream(msg: str) -> AsyncGenerator[str, None]:
            for chunk in ["Hello ", "world!"]:
                yield chunk

        chat.send_message_stream = fake_stream

        chunks: list[str] = []
        async for chunk in service.generate_response_stream("test query"):
            chunks.append(chunk)

        assert chunks == ["Hello ", "world!"]
        mock_genai_client.create_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_with_context(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """Context string is prepended to the user message."""
        chat = mock_genai_client.create_chat.return_value
        captured_messages: list[str] = []

        async def capturing_stream(msg: str) -> AsyncGenerator[str, None]:
            captured_messages.append(msg)
            yield "response"

        chat.send_message_stream = capturing_stream

        chunks: list[str] = []
        async for chunk in service.generate_response_stream(
            "query", context="some context",
        ):
            chunks.append(chunk)

        assert len(captured_messages) == 1
        assert "CONTEXT" in captured_messages[0]
        assert "some context" in captured_messages[0]
        assert "query" in captured_messages[0]

    @pytest.mark.asyncio
    async def test_stream_with_history(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """Conversation history is passed through to the chat session."""
        chat = mock_genai_client.create_chat.return_value

        async def fake_stream(msg: str) -> AsyncGenerator[str, None]:
            yield "ok"

        chat.send_message_stream = fake_stream

        history = [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ]

        chunks: list[str] = []
        async for chunk in service.generate_response_stream("new query", history=history):
            chunks.append(chunk)

        assert chunks == ["ok"]
        # Verify history was included in create_chat call
        call_kwargs = mock_genai_client.create_chat.call_args
        passed_history = call_kwargs.kwargs.get("history") or call_kwargs[1].get("history", [])
        # History should include few-shot + conversation history
        assert len(passed_history) > 2  # 2 few-shot + 2 history entries

    @pytest.mark.asyncio
    async def test_stream_records_circuit_success(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """Successful stream records success on the circuit breaker."""
        chat = mock_genai_client.create_chat.return_value

        async def fake_stream(msg: str) -> AsyncGenerator[str, None]:
            yield "done"

        chat.send_message_stream = fake_stream

        service._gemini_circuit.record_success = MagicMock()

        chunks: list[str] = []
        async for chunk in service.generate_response_stream("test"):
            chunks.append(chunk)

        service._gemini_circuit.record_success.assert_called_once()


# ---------------------------------------------------------------------------
# generate_response_stream — error / fallback paths
# ---------------------------------------------------------------------------


class TestStreamFallbackBehavior:
    """Test fallback to OpenRouter on various Gemini errors."""

    @pytest.mark.asyncio
    async def test_resource_exhausted_triggers_fallback(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """ResourceExhausted (429) triggers OpenRouter fallback."""
        chat = mock_genai_client.create_chat.return_value

        async def failing_stream(msg: str) -> AsyncGenerator[str, None]:
            raise ResourceExhausted("Quota exceeded")
            yield  # noqa: unreachable — makes this an async generator

        chat.send_message_stream = failing_stream

        mock_or_client = MagicMock()

        async def fake_or_stream(messages: list, tier: Any = None) -> AsyncGenerator[str, None]:
            yield "fallback response"

        mock_or_client.complete_stream = fake_or_stream
        service._openrouter_client = mock_or_client

        chunks: list[str] = []
        async for chunk in service.generate_response_stream("test"):
            chunks.append(chunk)

        assert chunks == ["fallback response"]

    @pytest.mark.asyncio
    async def test_service_unavailable_triggers_fallback(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """ServiceUnavailable triggers OpenRouter fallback."""
        chat = mock_genai_client.create_chat.return_value

        async def failing_stream(msg: str) -> AsyncGenerator[str, None]:
            raise ServiceUnavailable("Service down")
            yield  # noqa: unreachable

        chat.send_message_stream = failing_stream

        mock_or_client = MagicMock()

        async def fake_or_stream(messages: list, tier: Any = None) -> AsyncGenerator[str, None]:
            yield "fallback"

        mock_or_client.complete_stream = fake_or_stream
        service._openrouter_client = mock_or_client

        chunks: list[str] = []
        async for chunk in service.generate_response_stream("test"):
            chunks.append(chunk)

        assert chunks == ["fallback"]

    @pytest.mark.asyncio
    async def test_rate_limit_google_api_error_triggers_fallback(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """GoogleAPIError containing '429' triggers fallback."""
        chat = mock_genai_client.create_chat.return_value

        async def failing_stream(msg: str) -> AsyncGenerator[str, None]:
            raise GoogleAPIError("429 Resource Exhausted")
            yield  # noqa: unreachable

        chat.send_message_stream = failing_stream

        mock_or_client = MagicMock()

        async def fake_or_stream(messages: list, tier: Any = None) -> AsyncGenerator[str, None]:
            yield "rate-limit fallback"

        mock_or_client.complete_stream = fake_or_stream
        service._openrouter_client = mock_or_client

        chunks: list[str] = []
        async for chunk in service.generate_response_stream("test"):
            chunks.append(chunk)

        assert chunks == ["rate-limit fallback"]

    @pytest.mark.asyncio
    async def test_non_rate_limit_google_api_error_raises(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """GoogleAPIError without rate-limit keyword raises directly."""
        chat = mock_genai_client.create_chat.return_value

        async def failing_stream(msg: str) -> AsyncGenerator[str, None]:
            raise GoogleAPIError("Internal server error")
            yield  # noqa: unreachable

        chat.send_message_stream = failing_stream

        with pytest.raises(GoogleAPIError, match="Internal server error"):
            async for _ in service.generate_response_stream("test"):
                pass


# ---------------------------------------------------------------------------
# Circuit breaker behavior
# ---------------------------------------------------------------------------


class TestCircuitBreakerBehavior:
    """Test that the circuit breaker skips Gemini when open."""

    @pytest.mark.asyncio
    async def test_open_circuit_skips_gemini(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """When circuit is open, Gemini is not called at all."""
        # Force circuit open
        for _ in range(5):
            service._gemini_circuit.record_failure()
        assert service._gemini_circuit.is_open() is True

        mock_or_client = MagicMock()

        async def fake_or_stream(messages: list, tier: Any = None) -> AsyncGenerator[str, None]:
            yield "circuit-bypass"

        mock_or_client.complete_stream = fake_or_stream
        service._openrouter_client = mock_or_client

        chunks: list[str] = []
        async for chunk in service.generate_response_stream("test"):
            chunks.append(chunk)

        assert chunks == ["circuit-bypass"]
        # Gemini create_chat should NOT have been called
        mock_genai_client.create_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_records_on_circuit(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """ResourceExhausted errors increment the circuit failure count."""
        chat = mock_genai_client.create_chat.return_value

        async def failing_stream(msg: str) -> AsyncGenerator[str, None]:
            raise ResourceExhausted("quota")
            yield  # noqa: unreachable

        chat.send_message_stream = failing_stream

        mock_or_client = MagicMock()

        async def fake_or_stream(messages: list, tier: Any = None) -> AsyncGenerator[str, None]:
            yield "ok"

        mock_or_client.complete_stream = fake_or_stream
        service._openrouter_client = mock_or_client

        initial_failures = service._gemini_circuit.failure_count
        async for _ in service.generate_response_stream("test"):
            pass

        assert service._gemini_circuit.failure_count > initial_failures


# ---------------------------------------------------------------------------
# generate_response (non-streaming)
# ---------------------------------------------------------------------------


class TestGenerateResponse:
    """Test the non-streaming generate_response method."""

    @pytest.mark.asyncio
    async def test_generate_response_concatenates_stream(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """generate_response collects all streaming chunks into a single string."""
        chat = mock_genai_client.create_chat.return_value

        async def fake_stream(msg: str) -> AsyncGenerator[str, None]:
            for part in ["Hello ", "from ", "Gemini!"]:
                yield part

        chat.send_message_stream = fake_stream

        result = await service.generate_response("test query")
        assert result == "Hello from Gemini!"

    @pytest.mark.asyncio
    async def test_generate_response_with_context(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """Context is passed through to streaming layer."""
        chat = mock_genai_client.create_chat.return_value
        captured: list[str] = []

        async def capturing_stream(msg: str) -> AsyncGenerator[str, None]:
            captured.append(msg)
            yield "response"

        chat.send_message_stream = capturing_stream

        result = await service.generate_response("query", context="ctx data")
        assert result == "response"
        assert "ctx data" in captured[0]

    @pytest.mark.asyncio
    async def test_generate_response_returns_empty_on_no_chunks(
        self, service: GeminiJakselService, mock_genai_client: MagicMock,
    ) -> None:
        """If the stream yields nothing, result is an empty string."""
        chat = mock_genai_client.create_chat.return_value

        async def empty_stream(msg: str) -> AsyncGenerator[str, None]:
            return
            yield  # noqa: unreachable — makes this an async generator

        chat.send_message_stream = empty_stream

        result = await service.generate_response("test")
        assert result == ""


# ---------------------------------------------------------------------------
# OpenRouter fallback (_fallback_to_openrouter)
# ---------------------------------------------------------------------------


class TestOpenRouterFallback:
    """Test the direct OpenRouter fallback method."""

    @pytest.mark.asyncio
    async def test_fallback_raises_when_no_client(
        self, service: GeminiJakselService,
    ) -> None:
        """RuntimeError if OpenRouter client cannot be loaded."""
        service._openrouter_client = None
        with patch.object(service, "_get_openrouter_client", return_value=None):
            with pytest.raises(RuntimeError, match="OpenRouter fallback not available"):
                await service._fallback_to_openrouter("msg", None, "")

    @pytest.mark.asyncio
    async def test_fallback_success(
        self, service: GeminiJakselService,
    ) -> None:
        """Successful OpenRouter fallback returns content."""
        mock_result = MagicMock()
        mock_result.content = "fallback answer"
        mock_result.model_name = "test-model"

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        service._openrouter_client = mock_client

        result = await service._fallback_to_openrouter("question", None, "context")
        assert result == "fallback answer"
        mock_client.complete.assert_awaited_once()


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------


class TestMessageConversion:
    """Test _convert_to_openai_messages utility."""

    def test_basic_conversion(self, service: GeminiJakselService) -> None:
        messages = service._convert_to_openai_messages("hello", None, "")
        # Should have: system + few-shot examples + user message
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "hello"

    def test_conversion_with_context(self, service: GeminiJakselService) -> None:
        messages = service._convert_to_openai_messages("query", None, "my context")
        user_msg = messages[-1]["content"]
        assert "CONTEXT" in user_msg
        assert "my context" in user_msg
        assert "query" in user_msg

    def test_conversion_with_history(self, service: GeminiJakselService) -> None:
        history = [
            {"role": "user", "content": "prev q"},
            {"role": "assistant", "content": "prev a"},
        ]
        messages = service._convert_to_openai_messages("new q", history, "")
        roles = [m["role"] for m in messages]
        # System + few-shot + history + new user message
        assert roles.count("user") >= 2  # few-shot user + history user + new
        assert "prev q" in [m["content"] for m in messages]
        assert "prev a" in [m["content"] for m in messages]

    def test_conversion_skips_empty_history_content(
        self, service: GeminiJakselService,
    ) -> None:
        history = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "real message"},
        ]
        messages = service._convert_to_openai_messages("query", history, "")
        contents = [m["content"] for m in messages]
        assert "" not in contents  # empty content should be filtered


# ---------------------------------------------------------------------------
# GeminiService wrapper (compatibility layer)
# ---------------------------------------------------------------------------


class TestGeminiServiceWrapper:
    """Test the GeminiService compatibility wrapper class."""

    @pytest.mark.asyncio
    async def test_wrapper_generate_response(self, _patch_persona: Any) -> None:
        """GeminiService.generate_response delegates to GeminiJakselService."""
        wrapper = GeminiService(api_key="test-key")
        mock_inner = AsyncMock(return_value="wrapper response")
        wrapper._service.generate_response = mock_inner

        result = await wrapper.generate_response("prompt text")
        assert result == "wrapper response"
        mock_inner.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wrapper_generate_response_with_context(
        self, _patch_persona: Any,
    ) -> None:
        """Context list is joined into a string before delegation."""
        wrapper = GeminiService()
        mock_inner = AsyncMock(return_value="ctx response")
        wrapper._service.generate_response = mock_inner

        result = await wrapper.generate_response(
            "prompt", context=["line1", "line2"],
        )
        assert result == "ctx response"
        # Verify context was joined
        call_kwargs = mock_inner.call_args
        assert call_kwargs.kwargs.get("context") == "line1\nline2"

    @pytest.mark.asyncio
    async def test_wrapper_stream_response(self, _patch_persona: Any) -> None:
        """GeminiService.stream_response delegates to generate_response_stream."""
        wrapper = GeminiService()

        async def fake_stream(prompt: str) -> AsyncGenerator[str, None]:
            for chunk in ["a", "b", "c"]:
                yield chunk

        wrapper._service.generate_response_stream = fake_stream

        chunks: list[str] = []
        async for chunk in wrapper.stream_response("test prompt"):
            chunks.append(chunk)

        assert chunks == ["a", "b", "c"]
