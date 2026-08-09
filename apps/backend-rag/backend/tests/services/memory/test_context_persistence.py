"""
Tests for ConversationEngine context persistence (_load_context, _save_context).

Tests use mocked Redis (CacheService) and PostgreSQL (asyncpg.Pool) to verify
the load → cache → save pipeline without external dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.channels.base import ChannelMessage
from backend.conversation.engine import _SESSION_CONTEXT_TTL, ConversationEngine

# ── Helpers ──────────────────────────────────────────────────────


def _make_engine() -> ConversationEngine:
    """Create a ConversationEngine with a mocked orchestrator."""
    mock_orchestrator = MagicMock()
    engine = ConversationEngine(orchestrator=mock_orchestrator)
    return engine


# ═══════════════════════════════════════════════════════════════
# _load_context
# ═══════════════════════════════════════════════════════════════


class TestLoadContext:
    @pytest.mark.asyncio
    async def test_empty_session_id(self) -> None:
        engine = _make_engine()
        result = await engine._load_context("")
        assert result == {"history": [], "user_state": {}}

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        engine = _make_engine()
        cached_ctx = {
            "history": [{"role": "user", "content": "hello"}],
            "user_state": {"lang": "it"},
        }

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=cached_ctx)

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            result = await engine._load_context("sess-123")

        assert result == cached_ctx
        mock_cache.get.assert_called_once_with("zantara:session_ctx:sess-123")

    @pytest.mark.asyncio
    async def test_cache_miss_db_hit(self) -> None:
        engine = _make_engine()

        # Mock Redis returning None
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)

        # Mock DB pool returning rows
        mock_row_1 = {"direction": "inbound", "content": "What is KBLI?"}
        mock_row_2 = {"direction": "outbound", "content": "KBLI is..."}
        mock_pool = AsyncMock()
        mock_pool.fetch = AsyncMock(return_value=[mock_row_2, mock_row_1])  # DESC order
        engine._db_pool = mock_pool

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            result = await engine._load_context("sess-456")

        # Should be in chronological order (reversed from DESC)
        assert len(result["history"]) == 2
        assert result["history"][0]["role"] == "user"
        assert result["history"][0]["content"] == "What is KBLI?"
        assert result["history"][1]["role"] == "assistant"

        # Should warm cache
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert (
            call_args[1]["ttl"] == _SESSION_CONTEXT_TTL or call_args[0][2] == _SESSION_CONTEXT_TTL
        )

    @pytest.mark.asyncio
    async def test_cache_miss_db_miss(self) -> None:
        engine = _make_engine()

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_pool = AsyncMock()
        mock_pool.fetch = AsyncMock(return_value=[])
        engine._db_pool = mock_pool

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            result = await engine._load_context("sess-789")

        assert result == {"history": [], "user_state": {}}

    @pytest.mark.asyncio
    async def test_no_db_pool_no_cache(self) -> None:
        engine = _make_engine()

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            result = await engine._load_context("sess-abc")

        assert result == {"history": [], "user_state": {}}

    @pytest.mark.asyncio
    async def test_cache_error_graceful(self) -> None:
        """Cache errors should not crash — fall through to DB or empty."""
        engine = _make_engine()

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(side_effect=Exception("Redis down"))

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            result = await engine._load_context("sess-err")

        assert result == {"history": [], "user_state": {}}


# ═══════════════════════════════════════════════════════════════
# _save_context
# ═══════════════════════════════════════════════════════════════


class TestSaveContext:
    @pytest.mark.asyncio
    async def test_saves_to_cache(self) -> None:
        engine = _make_engine()
        context = {"history": [{"role": "user", "content": "hi"}], "user_state": {}}

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(return_value=True)

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            await engine._save_context("sess-save", context)

        mock_cache.set.assert_called_once()
        args = mock_cache.set.call_args
        assert "zantara:session_ctx:sess-save" in str(args)

    @pytest.mark.asyncio
    async def test_empty_session_noop(self) -> None:
        engine = _make_engine()
        mock_cache = AsyncMock()

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            await engine._save_context("", {"history": []})

        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_context_noop(self) -> None:
        engine = _make_engine()
        mock_cache = AsyncMock()

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            await engine._save_context("sess-x", {})

        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_error_graceful(self) -> None:
        engine = _make_engine()
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(side_effect=Exception("Redis exploded"))

        with patch("backend.core.cache.get_cache_service", return_value=mock_cache):
            # Should not raise
            await engine._save_context("sess-err", {"history": [{"role": "user", "content": "x"}]})


class TestTrustedWhatsAppProcessing:
    @pytest.mark.asyncio
    async def test_trusted_whatsapp_skips_context_and_forwards_l0_marker(self) -> None:
        class CapturingOrchestrator:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            async def stream_query(self, **kwargs):
                self.calls.append(kwargs)
                yield {"type": "answer", "data": {"text": "public answer"}}

        orchestrator = CapturingOrchestrator()
        engine = ConversationEngine(orchestrator=orchestrator)
        engine._load_context = AsyncMock(side_effect=AssertionError("context load reached"))
        engine._load_cross_channel_context = AsyncMock(
            side_effect=AssertionError("cross-channel context reached")
        )
        engine._save_context = AsyncMock(side_effect=AssertionError("context save reached"))
        message = ChannelMessage(
            user_id="whatsapp_USER_CANARY",
            session_id="wa_session_SESSION_CANARY",
            text="PUBLIC_QUERY_CANARY",
            channel="whatsapp",
            metadata={
                "thread_id": "THREAD_CANARY",
                "agent_mesh": True,
                "agent_email": "PRIVATE_EMAIL_CANARY",
            },
        )

        responses = [
            response
            async for response in engine.process_message(
                message,
                {},
                trusted_whatsapp_ingress=True,
            )
        ]

        assert [response.text for response in responses] == ["public answer"]
        engine._load_context.assert_not_awaited()
        engine._load_cross_channel_context.assert_not_awaited()
        engine._save_context.assert_not_awaited()
        assert orchestrator.calls == [
            {
                "query": "PUBLIC_QUERY_CANARY",
                "user_id": "whatsapp_USER_CANARY",
                "session_id": "wa_session_SESSION_CANARY",
                "conversation_history": [],
                "images": None,
                "channel": "whatsapp",
                "is_whatsapp": True,
            }
        ]

    @pytest.mark.asyncio
    async def test_trusted_whatsapp_engine_logs_and_error_event_are_generic(
        self,
        caplog,
    ) -> None:
        user_canary = "WHATSAPP_ENGINE_USER_CANARY"
        session_canary = "WHATSAPP_ENGINE_SESSION_CANARY"
        query_canary = "WHATSAPP_ENGINE_QUERY_CANARY"
        error_canary = "WHATSAPP_ENGINE_ERROR_CANARY"

        class ExplodingOrchestrator:
            async def stream_query(self, **_kwargs):
                raise RuntimeError(error_canary)
                yield  # pragma: no cover - preserve async-generator shape

        engine = ConversationEngine(orchestrator=ExplodingOrchestrator())
        message = ChannelMessage(
            user_id=user_canary,
            session_id=session_canary,
            text=query_canary,
            channel="whatsapp",
        )

        with caplog.at_level("INFO", logger="backend.conversation.engine"):
            responses = [
                response
                async for response in engine.process_message(
                    message,
                    {},
                    trusted_whatsapp_ingress=True,
                )
            ]

        assert len(responses) == 1
        assert responses[0].metadata == {
            "event_type": "error",
            "error": "processing_failed",
        }
        for canary in (user_canary, session_canary, query_canary, error_canary):
            assert canary not in caplog.text
            assert canary not in repr(responses[0])
        assert "error_type=RuntimeError" in caplog.text
        assert all(record.exc_info is None for record in caplog.records)

    @pytest.mark.asyncio
    async def test_non_whatsapp_keeps_context_pipeline(self) -> None:
        class CapturingOrchestrator:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            async def stream_query(self, **kwargs):
                self.calls.append(kwargs)
                yield {"type": "answer", "data": {"text": "answer"}}

        orchestrator = CapturingOrchestrator()
        engine = ConversationEngine(orchestrator=orchestrator)
        context = {
            "history": [{"role": "assistant", "content": "prior public answer"}],
            "user_state": {},
        }
        engine._load_context = AsyncMock(return_value=context)
        engine._save_context = AsyncMock()
        message = ChannelMessage(
            user_id="telegram-user",
            session_id="telegram-session",
            text="next question",
            channel="telegram",
        )

        _ = [response async for response in engine.process_message(message, {})]

        engine._load_context.assert_awaited_once_with("telegram-session")
        engine._save_context.assert_awaited_once_with("telegram-session", context)
        assert orchestrator.calls[0]["conversation_history"] == context["history"]
        assert orchestrator.calls[0]["is_whatsapp"] is False
