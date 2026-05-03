"""
Tests for ContextWindowManager — trimming, memoization, and cache behavior.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.misc.context_window_manager import ContextWindowManager


@pytest.fixture
def manager() -> ContextWindowManager:
    with patch("backend.llm.zantara_ai_client.ZantaraAIClient"):
        return ContextWindowManager(max_messages=5, summary_threshold=8)


def _make_messages(n: int) -> list[dict]:
    return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(n)]


# ============================================================
# trim_conversation_history
# ============================================================


def test_trim_short_conversation(manager: ContextWindowManager):
    """Short conversations (<=max_messages) should be kept in full."""
    msgs = _make_messages(3)
    result = manager.trim_conversation_history(msgs)
    assert result["trimmed_messages"] == msgs
    assert result["needs_summarization"] is False


def test_trim_medium_conversation(manager: ContextWindowManager):
    """Medium conversations (max_messages < n <= threshold) should trim to recent."""
    msgs = _make_messages(7)
    result = manager.trim_conversation_history(msgs)
    assert len(result["trimmed_messages"]) == 5  # max_messages
    assert result["needs_summarization"] is False


def test_trim_long_conversation(manager: ContextWindowManager):
    """Long conversations (>threshold) should flag for summarization."""
    msgs = _make_messages(12)
    result = manager.trim_conversation_history(msgs)
    assert len(result["trimmed_messages"]) == 5
    assert result["needs_summarization"] is True
    assert len(result["messages_to_summarize"]) == 7


def test_trim_empty_conversation(manager: ContextWindowManager):
    """Empty conversation returns empty result."""
    result = manager.trim_conversation_history([])
    assert result["trimmed_messages"] == []
    assert result["needs_summarization"] is False


# ============================================================
# generate_summary — memoization
# ============================================================


@pytest.mark.asyncio
async def test_generate_summary_cache_hit(manager: ContextWindowManager):
    """Second call with identical messages should return cached summary."""
    manager.zantara_client = AsyncMock()
    manager.zantara_client.generate_text = AsyncMock(return_value="Summary of conversation")

    msgs = _make_messages(5)

    # First call — cache miss, calls LLM
    result1 = await manager.generate_summary(msgs)
    assert result1 == "Summary of conversation"
    assert manager.zantara_client.generate_text.call_count == 1

    # Second call — cache hit, NO LLM call
    result2 = await manager.generate_summary(msgs)
    assert result2 == "Summary of conversation"
    assert manager.zantara_client.generate_text.call_count == 1  # Still 1


@pytest.mark.asyncio
async def test_generate_summary_cache_miss_on_change(manager: ContextWindowManager):
    """Changed messages should cause a cache miss."""
    manager.zantara_client = AsyncMock()
    manager.zantara_client.generate_text = AsyncMock(return_value="Summary v1")

    msgs_v1 = _make_messages(5)
    await manager.generate_summary(msgs_v1)

    # Modify messages — should be a cache miss
    manager.zantara_client.generate_text = AsyncMock(return_value="Summary v2")
    msgs_v2 = msgs_v1 + [{"role": "user", "content": "new question"}]
    result = await manager.generate_summary(msgs_v2)
    assert result == "Summary v2"
    manager.zantara_client.generate_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_summary_lru_eviction(manager: ContextWindowManager):
    """Cache should evict oldest entry when exceeding max size."""
    manager.zantara_client = AsyncMock()
    manager.zantara_client.generate_text = AsyncMock(return_value="summary")

    # Reduce max for test
    manager._SUMMARY_CACHE_MAX = 3

    for i in range(5):
        await manager.generate_summary([{"role": "user", "content": f"unique {i}"}])

    # Cache should have at most 3 entries
    assert len(manager._summary_cache) == 3


@pytest.mark.asyncio
async def test_generate_summary_no_client(manager: ContextWindowManager):
    """Without LLM client, should return fallback text."""
    manager.zantara_client = None
    result = await manager.generate_summary(_make_messages(3))
    assert "Earlier conversation" in result


# ============================================================
# cache_key stability
# ============================================================


def test_cache_key_deterministic():
    """Same messages should always produce the same key."""
    msgs = _make_messages(3)
    key1 = ContextWindowManager._cache_key(msgs, None)
    key2 = ContextWindowManager._cache_key(msgs, None)
    assert key1 == key2


def test_cache_key_different_for_different_messages():
    """Different messages should produce different keys."""
    key1 = ContextWindowManager._cache_key(_make_messages(3), None)
    key2 = ContextWindowManager._cache_key(_make_messages(4), None)
    assert key1 != key2


def test_cache_key_includes_existing_summary():
    """Same messages with different existing summary should produce different keys."""
    msgs = _make_messages(3)
    key1 = ContextWindowManager._cache_key(msgs, "summary A")
    key2 = ContextWindowManager._cache_key(msgs, "summary B")
    assert key1 != key2


# ============================================================
# context_status
# ============================================================


def test_context_status_healthy(manager: ContextWindowManager):
    result = manager.get_context_status(_make_messages(3))
    assert result["status"] == "healthy"


def test_context_status_approaching(manager: ContextWindowManager):
    result = manager.get_context_status(_make_messages(6))
    assert result["status"] == "approaching_limit"


def test_context_status_needs_summarization(manager: ContextWindowManager):
    result = manager.get_context_status(_make_messages(12))
    assert result["status"] == "needs_summarization"
