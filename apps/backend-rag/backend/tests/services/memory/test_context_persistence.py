"""
Tests for ConversationEngine context persistence (_load_context, _save_context).

Tests use mocked Redis (CacheService) and PostgreSQL (asyncpg.Pool) to verify
the load → cache → save pipeline without external dependencies.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.conversation.engine import ConversationEngine, _MAX_HISTORY_ENTRIES, _SESSION_CONTEXT_TTL


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
        assert call_args[1]["ttl"] == _SESSION_CONTEXT_TTL or call_args[0][2] == _SESSION_CONTEXT_TTL

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
