"""Unit tests for the RAG trace ledger.

Coverage target: 90%+ on :mod:`backend.services.observability.rag_trace`.
These tests exercise the public surface via ``rag_span`` plus the internal
``_summarise`` / ``_TraceState`` plumbing that stats_aggregator depends on.
The DB flush is always stubbed — the integration test covers the real DB
path separately.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest

from backend.services.observability import rag_trace
from backend.services.observability.rag_trace import (
    CURRENT_SPAN_ID,
    CURRENT_TRACE_ID,
    RagSpan,
    _summarise,
    current_trace_id,
    rag_span,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CaptureFlush:
    """Replaces the module-default flush so tests assert against a list."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, state) -> None:  # noqa: ANN001
        self.calls.append(_summarise(state))


@pytest.fixture
def capture_flush(monkeypatch):
    cap = _CaptureFlush()

    async def _patched(state):
        await cap(state)

    monkeypatch.setattr(rag_trace, "_default_flush", _patched)
    return cap


@pytest.fixture(autouse=True)
def _enable_flag(monkeypatch):
    monkeypatch.setenv("RAG_TRACE_ENABLED", "true")
    monkeypatch.setenv("RAG_TRACE_SAMPLE_RATE", "1.0")


# ---------------------------------------------------------------------------
# 1. Basic context manager lifecycle
# ---------------------------------------------------------------------------


async def test_root_span_creates_trace_and_flushes(capture_flush):
    async with rag_span("retrieval", domain="visa") as span:
        span.set(cache_hit=False, metadata={"docs": 7})
    # Flush is scheduled via create_task; yield once to let it run.
    await asyncio.sleep(0)
    assert len(capture_flush.calls) == 1
    payload = capture_flush.calls[0]
    assert payload["domain"] == "visa"
    assert payload["root_span"]["spans"][0]["stage"] == "retrieval"
    assert payload["root_span"]["spans"][0]["cache_hit"] is False
    assert payload["root_span"]["spans"][0]["metadata"]["docs"] == 7


async def test_nested_spans_share_trace_id(capture_flush):
    async with rag_span("root") as outer:
        outer_id = outer.trace_id
        async with rag_span("child") as inner:
            assert inner.trace_id == outer_id
    await asyncio.sleep(0)
    assert len(capture_flush.calls) == 1
    spans = capture_flush.calls[0]["root_span"]["spans"]
    assert {s["stage"] for s in spans} == {"root", "child"}
    child = next(s for s in spans if s["stage"] == "child")
    parent = next(s for s in spans if s["stage"] == "root")
    assert child["parent_span_id"] == parent["span_id"]


async def test_current_trace_id_is_none_outside_span():
    assert current_trace_id() is None
    async with rag_span("retrieval"):
        assert current_trace_id() is not None
    assert current_trace_id() is None


async def test_sequential_traces_are_independent(capture_flush):
    async with rag_span("stage1"):
        pass
    async with rag_span("stage2"):
        pass
    await asyncio.sleep(0)
    assert len(capture_flush.calls) == 2
    ids = {c["trace_id"] for c in capture_flush.calls}
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# 2. Feature flag + sampling
# ---------------------------------------------------------------------------


async def test_feature_flag_off_records_nothing(monkeypatch, capture_flush):
    monkeypatch.setenv("RAG_TRACE_ENABLED", "false")
    async with rag_span("retrieval") as span:
        assert span.trace_id is None  # noop handle
        span.set(cache_hit=True)
    await asyncio.sleep(0)
    assert capture_flush.calls == []


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off", ""])
async def test_flag_off_accepts_multiple_false_spellings(monkeypatch, capture_flush, raw):
    monkeypatch.setenv("RAG_TRACE_ENABLED", raw)
    async with rag_span("retrieval"):
        pass
    await asyncio.sleep(0)
    assert capture_flush.calls == []


async def test_sample_rate_zero_suppresses_flush(monkeypatch, capture_flush):
    monkeypatch.setenv("RAG_TRACE_SAMPLE_RATE", "0.0")
    async with rag_span("retrieval"):
        pass
    await asyncio.sleep(0)
    assert capture_flush.calls == []


async def test_sample_rate_invalid_defaults_to_full(monkeypatch, capture_flush):
    monkeypatch.setenv("RAG_TRACE_SAMPLE_RATE", "not-a-number")
    async with rag_span("retrieval"):
        pass
    await asyncio.sleep(0)
    assert len(capture_flush.calls) == 1


async def test_sample_rate_clamped_high(monkeypatch, capture_flush):
    monkeypatch.setenv("RAG_TRACE_SAMPLE_RATE", "42")  # > 1.0
    async with rag_span("retrieval"):
        pass
    await asyncio.sleep(0)
    assert len(capture_flush.calls) == 1


# ---------------------------------------------------------------------------
# 3. Contextvar propagation across await
# ---------------------------------------------------------------------------


async def test_trace_id_propagates_across_await(capture_flush):
    captured: dict[str, uuid.UUID | None] = {}

    async def inner():
        await asyncio.sleep(0)
        captured["inside"] = current_trace_id()

    async with rag_span("root") as span:
        await inner()
        captured["outside"] = span.trace_id

    assert captured["inside"] == captured["outside"]


async def test_concurrent_tasks_do_not_leak_trace_id(capture_flush):
    seen: list[uuid.UUID | None] = []

    async def task(label: str):
        async with rag_span(label):
            await asyncio.sleep(0)
            seen.append(current_trace_id())

    await asyncio.gather(task("a"), task("b"), task("c"))
    await asyncio.sleep(0)
    # Three separate traces, three distinct IDs.
    assert len(set(seen)) == 3
    assert len(capture_flush.calls) == 3


# ---------------------------------------------------------------------------
# 4. Span payload + attributes
# ---------------------------------------------------------------------------


async def test_span_set_accumulates_attributes(capture_flush):
    async with rag_span("reasoning") as s:
        s.set(tokens_in=100, tokens_out=50, cost_usd=Decimal("0.0123"))
        s.set(domain="tax")
        s.set(metadata={"model": "gemini-flash"})
    await asyncio.sleep(0)
    span_dict = capture_flush.calls[0]["root_span"]["spans"][0]
    assert span_dict["tokens_in"] == 100
    assert span_dict["tokens_out"] == 50
    assert span_dict["cost_usd"] == "0.0123"
    assert span_dict["domain"] == "tax"
    assert span_dict["metadata"]["model"] == "gemini-flash"


async def test_span_set_coerces_float_to_decimal(capture_flush):
    async with rag_span("reasoning") as s:
        s.set(cost_usd=0.0099)
    await asyncio.sleep(0)
    span_dict = capture_flush.calls[0]["root_span"]["spans"][0]
    assert span_dict["cost_usd"] is not None
    # Decimal(str(0.0099)) is exact
    assert Decimal(span_dict["cost_usd"]) == Decimal("0.0099")


async def test_noop_handle_set_is_safe(monkeypatch, capture_flush):
    monkeypatch.setenv("RAG_TRACE_ENABLED", "false")
    async with rag_span("retrieval") as s:
        s.set(tokens_in=1, tokens_out=2, cost_usd=0.01, cache_hit=True,
              domain="visa", metadata={"x": 1})
        assert s.span_id is None


async def test_root_exception_still_resets_contextvars(capture_flush):
    with pytest.raises(ValueError):
        async with rag_span("retrieval"):
            raise ValueError("boom")
    assert current_trace_id() is None
    assert CURRENT_SPAN_ID.get() is None
    assert CURRENT_TRACE_ID.get() is None
    # No flush: recorded spans list was empty (we raised before any child
    # completed). The span that raised has duration_ms set and is flushed.
    await asyncio.sleep(0)
    assert len(capture_flush.calls) == 1


# ---------------------------------------------------------------------------
# 5. Summarisation totals
# ---------------------------------------------------------------------------


async def test_summarise_totals_token_and_cost(capture_flush):
    async with rag_span("retrieval") as s:
        s.set(tokens_in=10)
        async with rag_span("reasoning") as r:
            r.set(tokens_in=20, tokens_out=30, cost_usd=Decimal("0.5"))
            async with rag_span("rerank") as rr:
                rr.set(cost_usd=Decimal("0.1"))
    await asyncio.sleep(0)
    payload = capture_flush.calls[0]
    assert payload["total_tokens_in"] == 30
    assert payload["total_tokens_out"] == 30
    assert payload["total_cost_usd"] == Decimal("0.6")
    assert payload["total_duration_ms"] >= 0


async def test_ragspan_dataclass_to_json_dict_shape():
    span = RagSpan(
        span_id=uuid.UUID(int=1),
        parent_span_id=None,
        stage="retrieval",
        started_at=_now(),
        duration_ms=1.234,
        tokens_in=5,
        cost_usd=Decimal("0.01"),
        cache_hit=True,
        domain="visa",
        metadata={"k": "v"},
    )
    d = span.to_json_dict()
    assert d["stage"] == "retrieval"
    assert d["cost_usd"] == "0.01"
    assert d["cache_hit"] is True
    assert d["domain"] == "visa"
    assert d["metadata"] == {"k": "v"}
    assert d["duration_ms"] == 1.234


# ---------------------------------------------------------------------------
# 6. Flush dispatch resilience
# ---------------------------------------------------------------------------


async def test_flush_exception_does_not_leak_to_caller(monkeypatch):
    async def broken_flush(state):  # noqa: ANN001
        raise RuntimeError("db went away")

    monkeypatch.setattr(rag_trace, "_default_flush", broken_flush)
    # Must not raise even if the flush fails.
    async with rag_span("retrieval"):
        pass
    await asyncio.sleep(0)


async def test_configure_pool_registers_value():
    sentinel = object()
    rag_trace.configure_pool(sentinel)
    assert await rag_trace._acquire_pool() is sentinel
    rag_trace.configure_pool(None)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
