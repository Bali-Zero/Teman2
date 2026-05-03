"""
Unit tests for Streaming endpoints.
Covers: _parse_history, ChatStreamRequest model, bali_zero_chat_stream GET,
chat_stream_post POST, event_stream generation, error handling.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.app.streaming import (
    CHUNK_TIMEOUT_SECONDS,
    STREAM_TIMEOUT_SECONDS,
    ChatStreamRequest,
    _parse_history,
    bali_zero_chat_stream,
    chat_stream_post,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def mock_request() -> MagicMock:
    """Mock FastAPI request with full app state."""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"email": "test@example.com", "role": "member"}
    request.app.state = MagicMock()
    request.app.state.services_initialized = True
    request.app.state.intelligent_router = MagicMock()
    request.app.state.memory_service = None
    request.app.state.collaborator_service = None
    request.app.state.collective_memory_workflow = None
    request.headers = {"X-API-Key": "test-key"}
    return request


def _make_async_stream(chunks: list[Any]) -> AsyncMock:
    """Create a mock async iterator for stream_chat."""
    async def stream_chat(**kwargs: Any) -> Any:
        for chunk in chunks:
            yield chunk
    mock_router = MagicMock()
    mock_router.stream_chat = stream_chat
    return mock_router


# --------------------------------------------------------------------------- #
# _parse_history
# --------------------------------------------------------------------------- #

class TestParseHistory:
    def test_valid_json_list(self) -> None:
        history = '[{"role": "user", "content": "test"}]'
        result = _parse_history(history)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_invalid_json(self) -> None:
        assert _parse_history("invalid json") == []

    def test_none(self) -> None:
        assert _parse_history(None) == []

    def test_empty_string(self) -> None:
        assert _parse_history("") == []

    def test_not_a_list(self) -> None:
        assert _parse_history('{"not": "a list"}') == []

    def test_valid_empty_list(self) -> None:
        assert _parse_history("[]") == []

    def test_multiple_entries(self) -> None:
        history = '[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]'
        result = _parse_history(history)
        assert len(result) == 2


# --------------------------------------------------------------------------- #
# ChatStreamRequest model
# --------------------------------------------------------------------------- #

class TestChatStreamRequest:
    def test_basic_creation(self) -> None:
        req = ChatStreamRequest(message="test")
        assert req.message == "test"
        assert req.user_id is None
        assert req.conversation_history is None
        assert req.metadata is None
        assert req.zantara_context is None
        assert req.session_id is None

    def test_full_creation(self) -> None:
        req = ChatStreamRequest(
            message="hello",
            user_id="user@test.com",
            conversation_history=[{"role": "user", "content": "prev"}],
            metadata={"key": "val"},
            zantara_context={"session_id": "sess1"},
            session_id="sess2",
        )
        assert req.user_id == "user@test.com"
        assert len(req.conversation_history) == 1
        assert req.session_id == "sess2"


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

class TestConstants:
    def test_stream_timeout(self) -> None:
        assert STREAM_TIMEOUT_SECONDS == 120

    def test_chunk_timeout(self) -> None:
        assert CHUNK_TIMEOUT_SECONDS == 30


# --------------------------------------------------------------------------- #
# bali_zero_chat_stream (GET)
# --------------------------------------------------------------------------- #

class TestBaliZeroChatStream:
    @pytest.mark.asyncio
    async def test_empty_query_raises(self, mock_request: MagicMock) -> None:
        with pytest.raises(HTTPException) as exc:
            await bali_zero_chat_stream(
                request=mock_request, query="   ", background_tasks=MagicMock(),
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_no_auth_raises(self, mock_request: MagicMock) -> None:
        mock_request.state.user = None
        with patch("backend.app.streaming.get_request_state", return_value=None), \
             patch("backend.app.streaming.validate_auth_mixed", new_callable=AsyncMock, return_value=None):
            with pytest.raises(HTTPException) as exc:
                await bali_zero_chat_stream(
                    request=mock_request, query="test", background_tasks=MagicMock(),
                )
            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_services_not_initialized(self, mock_request: MagicMock) -> None:
        with patch("backend.app.streaming.get_request_state", return_value={"email": "test@test.com"}), \
             patch("backend.app.streaming.get_app_state", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await bali_zero_chat_stream(
                    request=mock_request, query="test", background_tasks=MagicMock(),
                )
            assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_no_router_raises(self, mock_request: MagicMock) -> None:
        mock_request.app.state.intelligent_router = None

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_request_state", return_value={"email": "t@t.com"}), \
             patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect):
            with pytest.raises(HTTPException) as exc:
                await bali_zero_chat_stream(
                    request=mock_request, query="test", background_tasks=MagicMock(),
                )
            assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_successful_stream_response(self, mock_request: MagicMock) -> None:
        mock_router = _make_async_stream([
            {"type": "token", "data": "Hello"},
            {"type": "done", "data": ""},
        ])
        mock_request.app.state.intelligent_router = mock_router

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            if key == "collaborator_service":
                return None
            if key == "collective_memory_workflow":
                return None
            return default

        with patch("backend.app.streaming.get_request_state", return_value={"email": "t@t.com", "role": "member"}), \
             patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await bali_zero_chat_stream(
                request=mock_request, query="test query",
                background_tasks=MagicMock(),
            )

            assert response.media_type == "text/event-stream"
            assert response.headers.get("Cache-Control") == "no-cache"

    @pytest.mark.asyncio
    async def test_auth_fallback(self, mock_request: MagicMock) -> None:
        """Test that fallback auth is called when middleware auth is None."""
        mock_router = _make_async_stream([{"type": "done", "data": ""}])
        mock_request.app.state.intelligent_router = mock_router

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_request_state", return_value=None), \
             patch("backend.app.streaming.validate_auth_mixed", new_callable=AsyncMock,
                   return_value={"email": "fallback@test.com", "role": "member"}), \
             patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await bali_zero_chat_stream(
                request=mock_request, query="test",
                background_tasks=MagicMock(),
            )
            assert response is not None


# --------------------------------------------------------------------------- #
# chat_stream_post (POST)
# --------------------------------------------------------------------------- #

class TestChatStreamPost:
    @pytest.mark.asyncio
    async def test_empty_message_raises(self, mock_request: MagicMock) -> None:
        body = ChatStreamRequest(message="   ")
        with pytest.raises(HTTPException) as exc:
            await chat_stream_post(
                request=mock_request, body=body, background_tasks=MagicMock(),
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_no_auth_raises(self, mock_request: MagicMock) -> None:
        mock_request.state.user = None
        body = ChatStreamRequest(message="hello")
        with patch("backend.app.streaming.validate_auth_mixed", new_callable=AsyncMock,
                    return_value=None):
            with pytest.raises(HTTPException) as exc:
                await chat_stream_post(
                    request=mock_request, body=body, background_tasks=MagicMock(),
                )
            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_services_not_initialized(self, mock_request: MagicMock) -> None:
        mock_request.state.user = {"email": "t@t.com"}
        body = ChatStreamRequest(message="hello")

        with patch("backend.app.streaming.get_app_state", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await chat_stream_post(
                    request=mock_request, body=body, background_tasks=MagicMock(),
                )
            assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_no_router_raises(self, mock_request: MagicMock) -> None:
        mock_request.state.user = {"email": "t@t.com"}
        mock_request.app.state.intelligent_router = None
        body = ChatStreamRequest(message="hello")

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect):
            with pytest.raises(HTTPException) as exc:
                await chat_stream_post(
                    request=mock_request, body=body, background_tasks=MagicMock(),
                )
            assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_successful_post_stream(self, mock_request: MagicMock) -> None:
        mock_router = _make_async_stream([
            {"type": "token", "data": "Hi"},
            {"type": "done", "data": ""},
        ])
        mock_request.app.state.intelligent_router = mock_router
        mock_request.state.user = {"email": "t@t.com", "role": "member"}
        mock_request.app.state.conversation_service = AsyncMock()
        mock_request.app.state.conversation_service.save_conversation = AsyncMock()

        body = ChatStreamRequest(
            message="hello world",
            session_id="sess1",
        )

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            if key == "collaborator_service":
                return None
            if key == "collective_memory_workflow":
                return None
            return default

        with patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await chat_stream_post(
                request=mock_request, body=body, background_tasks=MagicMock(),
            )

            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_session_id_from_zantara_context(self, mock_request: MagicMock) -> None:
        mock_router = _make_async_stream([{"type": "done", "data": ""}])
        mock_request.app.state.intelligent_router = mock_router
        mock_request.state.user = {"email": "t@t.com", "role": "member"}
        mock_request.app.state.conversation_service = AsyncMock()

        body = ChatStreamRequest(
            message="test",
            zantara_context={"session_id": "ctx-sess-123"},
        )

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await chat_stream_post(
                request=mock_request, body=body, background_tasks=MagicMock(),
            )
            assert response is not None

    @pytest.mark.asyncio
    async def test_auto_generated_session_id(self, mock_request: MagicMock) -> None:
        mock_router = _make_async_stream([{"type": "done", "data": ""}])
        mock_request.app.state.intelligent_router = mock_router
        mock_request.state.user = {"email": "t@t.com", "role": "member"}
        del mock_request.app.state.conversation_service

        body = ChatStreamRequest(message="test")

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await chat_stream_post(
                request=mock_request, body=body, background_tasks=MagicMock(),
            )
            assert response is not None


# --------------------------------------------------------------------------- #
# Event stream chunk processing
# --------------------------------------------------------------------------- #

class TestEventStreamChunks:
    """Test the internal event_stream generator behavior via collecting chunks."""

    @pytest.mark.asyncio
    async def test_string_chunk(self, mock_request: MagicMock) -> None:
        mock_router = _make_async_stream([
            "plain text token",
            {"type": "done", "data": ""},
        ])
        mock_request.app.state.intelligent_router = mock_router
        mock_request.state.user = {"email": "t@t.com", "role": "member"}

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await chat_stream_post(
                request=mock_request,
                body=ChatStreamRequest(message="test", session_id="s"),
                background_tasks=MagicMock(),
            )
            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_metadata_chunk_legacy(self, mock_request: MagicMock) -> None:
        mock_router = _make_async_stream([
            '[METADATA]{"model": "gemini"}',
            {"type": "done", "data": ""},
        ])
        mock_request.app.state.intelligent_router = mock_router
        mock_request.state.user = {"email": "t@t.com", "role": "member"}

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await chat_stream_post(
                request=mock_request,
                body=ChatStreamRequest(message="test", session_id="s"),
                background_tasks=MagicMock(),
            )
            assert response is not None

    @pytest.mark.asyncio
    async def test_various_chunk_types_get_endpoint(self, mock_request: MagicMock) -> None:
        mock_router = _make_async_stream([
            {"type": "metadata", "data": {"model": "gemini"}},
            {"type": "token", "data": "Hello"},
            {"type": "sources", "data": [{"title": "Doc"}]},
            {"type": "tool_start", "data": {"tool": "search"}},
            {"type": "tool_end", "data": {"result": "ok"}},
            {"type": "custom_event", "data": "custom"},
            {"type": "done", "data": ""},
        ])
        mock_request.app.state.intelligent_router = mock_router

        def get_app_state_side_effect(state: Any, key: str, default: Any = None) -> Any:
            if key == "services_initialized":
                return True
            return default

        with patch("backend.app.streaming.get_request_state", return_value={"email": "t@t.com", "role": "member"}), \
             patch("backend.app.streaming.get_app_state", side_effect=get_app_state_side_effect), \
             patch("backend.app.streaming.trace_span") as mock_trace:
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            response = await bali_zero_chat_stream(
                request=mock_request, query="test", background_tasks=MagicMock(),
            )
            assert response.media_type == "text/event-stream"
