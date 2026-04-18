"""RAG trace v2 — async span ledger for stage timing + cost correlation.

The module provides a zero-dependency-at-module-import tracer that attaches
per-stage timing, token, and cost data to a single ``trace_id`` across the
retrieval → rerank → reasoning pipeline (and any GraphRAG sub-stages).

Design choices:

* **contextvar propagation.** ``CURRENT_TRACE_ID`` carries the root trace
  identifier across ``await`` boundaries without passing it as a parameter.
  ``CURRENT_SPAN_ID`` tracks the direct parent for nested spans.
* **Async context manager.** ``rag_span(stage, ...)`` is the only public
  entry point. Opening the root span starts a trace; re-entering when a
  parent is active creates a child. The root span auto-flushes to Postgres
  on exit.
* **No coupling to the ledger.** Unlike Prometheus counters or the
  ``llm_cost_recorder`` financial ledger, this writer is a single
  best-effort INSERT into ``rag_traces``. A DB failure logs a warning and
  never propagates to the user-facing call path.
* **Overhead budget.** Target < 2% P95 of query latency. The hot path is
  a ``time.perf_counter()`` delta plus a ``Span`` append. Flush is
  executed in an ``asyncio.create_task`` so it never blocks the response.
* **Feature flag.** ``RAG_TRACE_ENABLED=false`` short-circuits the context
  manager to a no-op — tests assert zero DB writes with the flag off.
* **Sampling.** ``RAG_TRACE_SAMPLE_RATE`` (0.0-1.0, default 1.0) drops a
  fraction of new root spans to keep volume manageable on Fly.

The schema persisted to ``rag_traces`` is intentionally denormalised — the
full nested tree of stages lives in a single JSONB ``root_span`` column so
percentile queries read one row per trace. Per-stage aggregates are
computed by ``stats_aggregator`` via ``jsonb_path_query``.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import random
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read lazily so tests can monkeypatch os.environ)
# ---------------------------------------------------------------------------


def _flag_enabled() -> bool:
    """Return True unless ``RAG_TRACE_ENABLED`` is set to a falsey value."""
    raw = os.environ.get("RAG_TRACE_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off", ""}


def _sample_rate() -> float:
    """Return the root-span sampling rate (0.0 — 1.0)."""
    try:
        rate = float(os.environ.get("RAG_TRACE_SAMPLE_RATE", "1.0"))
    except ValueError:
        return 1.0
    return max(0.0, min(1.0, rate))


# ---------------------------------------------------------------------------
# Context variables
# ---------------------------------------------------------------------------

# Propagated trace identifier. ``None`` outside any rag_span.
CURRENT_TRACE_ID: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "rag_trace_id",
    default=None,
)

# Directly surrounding span — used to build parent/child edges.
CURRENT_SPAN_ID: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "rag_span_id",
    default=None,
)

# Shared mutable list collecting every span in the current trace. Populated
# by the root context and appended to by every child; flushed on root exit.
# We keep it in a contextvar (not a global) so concurrent traces do not
# interfere under asyncio.
_ACTIVE_TRACE: contextvars.ContextVar[_TraceState | None] = contextvars.ContextVar(
    "rag_trace_state",
    default=None,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RagSpan:
    """A single stage in the RAG pipeline.

    ``metadata`` holds anything stage-specific (cache keys, document counts,
    model names) — schema-less on purpose: new stages add fields without a
    migration.
    """

    span_id: uuid.UUID
    parent_span_id: uuid.UUID | None
    stage: str
    started_at: datetime
    duration_ms: float = 0.0
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: Decimal | None = None
    cache_hit: bool | None = None
    domain: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        """Serialise for JSONB storage. Decimal → str, UUID → str."""
        return {
            "span_id": str(self.span_id),
            "parent_span_id": (
                str(self.parent_span_id) if self.parent_span_id else None
            ),
            "stage": self.stage,
            "started_at": self.started_at.isoformat(),
            "duration_ms": round(self.duration_ms, 3),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": (str(self.cost_usd) if self.cost_usd is not None else None),
            "cache_hit": self.cache_hit,
            "domain": self.domain,
            "metadata": self.metadata,
        }


@dataclass
class _TraceState:
    """Shared bookkeeping for a single trace.

    Holds every span collected since the root opened; the root's ``__aexit__``
    uses ``flush_callback`` to persist it. Children mutate ``spans``
    directly — no locking needed because a single asyncio task executes the
    closure of each span sequentially.
    """

    trace_id: uuid.UUID
    started_at_mono: float
    spans: list[RagSpan] = field(default_factory=list)
    domain: str | None = None
    # Override hook for tests; production leaves this None → uses the default
    # asyncpg pool via :func:`_default_flush`.
    flush_callback: Any = None
    # Set to False when the root sampled itself out — children become no-ops.
    record: bool = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def rag_span(
    stage: str,
    *,
    domain: str | None = None,
    tokens_in: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AsyncIterator[_SpanHandle]:
    """Open a stage span. Reentrant — nested opens create child spans.

    Usage::

        async with rag_span("retrieval", domain="visa") as span:
            docs = await search(query)
            span.set(cache_hit=cache_was_hit, metadata={"docs": len(docs)})

    Outside any enclosing span the first call starts a *root* trace and
    flushes it on exit. ``domain`` provided on the root seeds the trace
    attribution; children may still override their own.
    """
    if not _flag_enabled():
        # Feature flag off — yield a throwaway handle that records nothing.
        yield _SpanHandle(_NOOP_SPAN, _NOOP_STATE)
        return

    state = _ACTIVE_TRACE.get()
    trace_token: contextvars.Token[uuid.UUID | None] | None = None
    state_token: contextvars.Token[_TraceState | None] | None = None

    if state is None:
        # Root span: create trace bookkeeping, apply sampling.
        trace_id = uuid.uuid4()
        sampled = random.random() < _sample_rate()  # noqa: S311 — telemetry
        state = _TraceState(
            trace_id=trace_id,
            started_at_mono=time.perf_counter(),
            domain=domain,
            record=sampled,
        )
        state_token = _ACTIVE_TRACE.set(state)
        trace_token = CURRENT_TRACE_ID.set(trace_id)
    else:
        trace_id = state.trace_id

    parent_span_id = CURRENT_SPAN_ID.get()
    span = RagSpan(
        span_id=uuid.uuid4(),
        parent_span_id=parent_span_id,
        stage=stage,
        started_at=datetime.now(timezone.utc),
        domain=domain or state.domain,
        tokens_in=tokens_in,
        metadata=dict(metadata) if metadata else {},
    )
    span_token = CURRENT_SPAN_ID.set(span.span_id)

    started_mono = time.perf_counter()
    handle = _SpanHandle(span, state)
    is_root = state_token is not None
    try:
        yield handle
    finally:
        span.duration_ms = (time.perf_counter() - started_mono) * 1000.0
        if state.record:
            state.spans.append(span)
        CURRENT_SPAN_ID.reset(span_token)

        if is_root:
            # Flush is fire-and-forget so the user request is not blocked.
            if state.record and state.spans:
                try:
                    flush = state.flush_callback or _default_flush
                    coro = flush(state)
                    # Flushers may be sync (e.g. in tests); awaitables are
                    # scheduled, plain values are silently ignored.
                    if asyncio.iscoroutine(coro):
                        asyncio.create_task(coro)  # noqa: RUF006 — fire & forget
                except Exception as exc:  # pragma: no cover — defensive
                    logger.warning("rag_trace flush dispatch failed: %s", exc)
            if state_token is not None:
                _ACTIVE_TRACE.reset(state_token)
            if trace_token is not None:
                CURRENT_TRACE_ID.reset(trace_token)


class _SpanHandle:
    """Lightweight handle passed to the ``async with`` caller.

    Exposes ``set()`` for post-hoc attribute updates (the duration is
    measured by the context manager itself) and ``trace_id`` for cross-ledger
    correlation (e.g. feeding the ``llm_cost_recorder``).
    """

    __slots__ = ("_span", "_state")

    def __init__(self, span: RagSpan, state: _TraceState) -> None:
        self._span = span
        self._state = state

    @property
    def trace_id(self) -> uuid.UUID | None:
        return self._state.trace_id if self._state is not _NOOP_STATE else None

    @property
    def span_id(self) -> uuid.UUID | None:
        return self._span.span_id if self._span is not _NOOP_SPAN else None

    @property
    def stage(self) -> str:
        return self._span.stage

    def set(
        self,
        *,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cost_usd: Decimal | float | None = None,
        cache_hit: bool | None = None,
        domain: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Attach or update stage attributes. Called from inside the block."""
        if self._span is _NOOP_SPAN:
            return
        if tokens_in is not None:
            self._span.tokens_in = tokens_in
        if tokens_out is not None:
            self._span.tokens_out = tokens_out
        if cost_usd is not None:
            self._span.cost_usd = (
                cost_usd if isinstance(cost_usd, Decimal) else Decimal(str(cost_usd))
            )
        if cache_hit is not None:
            self._span.cache_hit = cache_hit
        if domain is not None:
            self._span.domain = domain
        if metadata:
            self._span.metadata.update(metadata)


# Singletons used by the no-op path so handles returned with the flag off
# do not carry per-call allocations.
_NOOP_SPAN = RagSpan(
    span_id=uuid.UUID(int=0),
    parent_span_id=None,
    stage="noop",
    started_at=datetime.fromtimestamp(0, tz=timezone.utc),
)
_NOOP_STATE = _TraceState(
    trace_id=uuid.UUID(int=0),
    started_at_mono=0.0,
    record=False,
)


def current_trace_id() -> uuid.UUID | None:
    """Return the trace id of the enclosing ``rag_span``, if any.

    Consumers — e.g. cost recorders or structured loggers — use this to
    correlate their own rows with a specific trace without passing the id
    through every function signature.
    """
    return CURRENT_TRACE_ID.get()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _summarise(state: _TraceState) -> dict[str, Any]:
    """Compute totals + build the JSON payload written to ``rag_traces``.

    We keep the root JSON flat (trace-level) plus a nested ``children`` array
    so Grafana / ``stats_aggregator`` can cheaply drill into a single stage
    using ``jsonb_path_query``.
    """
    total_duration = (time.perf_counter() - state.started_at_mono) * 1000.0
    total_cost = Decimal("0")
    total_tokens_in = 0
    total_tokens_out = 0
    for span in state.spans:
        if span.cost_usd is not None:
            total_cost += span.cost_usd
        if span.tokens_in:
            total_tokens_in += span.tokens_in
        if span.tokens_out:
            total_tokens_out += span.tokens_out

    root_payload = {
        "trace_id": str(state.trace_id),
        "domain": state.domain,
        "spans": [s.to_json_dict() for s in state.spans],
    }
    return {
        "trace_id": state.trace_id,
        "root_span": root_payload,
        "total_duration_ms": int(round(total_duration)),
        "total_cost_usd": total_cost,
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "domain": state.domain,
    }


async def _default_flush(state: _TraceState) -> None:
    """Best-effort write to ``rag_traces`` via the shared asyncpg pool.

    A failure here must never bubble into user-facing code paths, so every
    exception is caught and logged at WARNING.
    """
    try:
        row = _summarise(state)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("rag_trace summary failed: %s", exc)
        return

    try:
        pool = await _acquire_pool()
    except Exception as exc:  # pragma: no cover — environment dependent
        logger.debug("rag_trace pool unavailable, skipping flush: %s", exc)
        return
    if pool is None:
        return

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rag_traces (
                    trace_id, root_span, total_duration_ms,
                    total_cost_usd, total_tokens_in, total_tokens_out, domain
                )
                VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7)
                ON CONFLICT (trace_id) DO NOTHING
                """,
                row["trace_id"],
                json.dumps(row["root_span"]),
                row["total_duration_ms"],
                row["total_cost_usd"],
                row["total_tokens_in"],
                row["total_tokens_out"],
                row["domain"],
            )
    except Exception as exc:  # pragma: no cover — DB outage path
        logger.warning("rag_trace insert failed (swallowed): %s", exc)


# ---------------------------------------------------------------------------
# Pool registry (set at app startup)
# ---------------------------------------------------------------------------

_POOL_REGISTRY: dict[str, Any] = {"pool": None}


def configure_pool(pool: Any) -> None:
    """Register the asyncpg pool used by ``_default_flush``.

    Called once from the FastAPI lifespan after the app pool opens; the
    module then writes traces without needing a ``Request`` instance.
    """
    _POOL_REGISTRY["pool"] = pool


async def _acquire_pool() -> Any | None:
    return _POOL_REGISTRY.get("pool")


__all__ = [
    "RagSpan",
    "rag_span",
    "current_trace_id",
    "configure_pool",
    "CURRENT_TRACE_ID",
    "CURRENT_SPAN_ID",
]
