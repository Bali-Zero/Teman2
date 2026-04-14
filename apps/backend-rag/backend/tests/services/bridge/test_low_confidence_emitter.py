"""Tests for low-confidence emitter (writes rag.low_confidence to bridge_outbox)."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.bridge.low_confidence_emitter import (
    LOW_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_DEDUP_S,
    _low_confidence_dedup,
    maybe_emit_low_confidence,
)


class _AcquireCM:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


def _build_pool():
    conn = MagicMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))
    return pool, conn


@pytest.fixture(autouse=True)
def clear_dedup():
    _low_confidence_dedup.clear()
    yield
    _low_confidence_dedup.clear()


def test_threshold_constants():
    """Threshold and dedup window match spec."""
    assert LOW_CONFIDENCE_THRESHOLD == 0.3
    assert LOW_CONFIDENCE_DEDUP_S == 24 * 3600


@pytest.mark.asyncio
async def test_low_confidence_writes_outbox(monkeypatch):
    """confidence < 0.3 → insert_outbox_event called with rag.low_confidence."""
    insert_mock = AsyncMock(return_value=99)
    monkeypatch.setattr(
        "backend.services.bridge.low_confidence_emitter.insert_outbox_event",
        insert_mock,
    )

    pool, _ = _build_pool()
    await maybe_emit_low_confidence(pool, "What is the visa price?", 0.2)

    insert_mock.assert_called_once()
    args = insert_mock.call_args
    assert args.kwargs["event_type"] == "rag.low_confidence"
    payload = args.kwargs["payload"]
    assert payload["query"] == "What is the visa price?"
    assert payload["confidence"] == 0.2
    assert "query_hash" in payload


@pytest.mark.asyncio
async def test_high_confidence_does_not_emit(monkeypatch):
    """confidence >= 0.3 → no emit."""
    insert_mock = AsyncMock(return_value=99)
    monkeypatch.setattr(
        "backend.services.bridge.low_confidence_emitter.insert_outbox_event",
        insert_mock,
    )

    pool, _ = _build_pool()
    await maybe_emit_low_confidence(pool, "test", 0.7)
    await maybe_emit_low_confidence(pool, "test2", 0.3)  # boundary: 0.3 NOT emitted
    insert_mock.assert_not_called()


@pytest.mark.asyncio
async def test_dedup_within_window(monkeypatch):
    """Same query within 24h window emits only once."""
    insert_mock = AsyncMock(return_value=99)
    monkeypatch.setattr(
        "backend.services.bridge.low_confidence_emitter.insert_outbox_event",
        insert_mock,
    )

    pool, _ = _build_pool()
    await maybe_emit_low_confidence(pool, "same query", 0.1)
    await maybe_emit_low_confidence(pool, "same query", 0.1)
    await maybe_emit_low_confidence(pool, "same query", 0.2)
    assert insert_mock.call_count == 1


@pytest.mark.asyncio
async def test_dedup_different_queries_each_emit(monkeypatch):
    """Different queries each emit independently."""
    insert_mock = AsyncMock(return_value=99)
    monkeypatch.setattr(
        "backend.services.bridge.low_confidence_emitter.insert_outbox_event",
        insert_mock,
    )

    pool, _ = _build_pool()
    await maybe_emit_low_confidence(pool, "query A", 0.1)
    await maybe_emit_low_confidence(pool, "query B", 0.1)
    await maybe_emit_low_confidence(pool, "query C", 0.1)
    assert insert_mock.call_count == 3


@pytest.mark.asyncio
async def test_query_truncated_to_500_chars(monkeypatch):
    """Long queries are truncated in payload."""
    insert_mock = AsyncMock(return_value=99)
    monkeypatch.setattr(
        "backend.services.bridge.low_confidence_emitter.insert_outbox_event",
        insert_mock,
    )

    pool, _ = _build_pool()
    long_query = "x" * 1000
    await maybe_emit_low_confidence(pool, long_query, 0.1)
    payload = insert_mock.call_args.kwargs["payload"]
    assert len(payload["query"]) <= 500


@pytest.mark.asyncio
async def test_outbox_failure_swallowed(monkeypatch, caplog):
    """If insert_outbox_event raises, maybe_emit must NOT propagate."""
    insert_mock = AsyncMock(side_effect=RuntimeError("DB exploded"))
    monkeypatch.setattr(
        "backend.services.bridge.low_confidence_emitter.insert_outbox_event",
        insert_mock,
    )

    pool, _ = _build_pool()
    # Must NOT raise
    await maybe_emit_low_confidence(pool, "test", 0.1)


@pytest.mark.asyncio
async def test_pool_none_no_emit(monkeypatch):
    """If pool is None (RAG running without DB), gracefully skip."""
    insert_mock = AsyncMock(return_value=99)
    monkeypatch.setattr(
        "backend.services.bridge.low_confidence_emitter.insert_outbox_event",
        insert_mock,
    )

    await maybe_emit_low_confidence(None, "test", 0.1)
    insert_mock.assert_not_called()
