"""Observability — per-node timing, structured logs, optional OpenTelemetry.

Usage in graph nodes:
    from nuzantara_graph.observability import trace_node

    @trace_node("understand")
    async def understand_node(state: GraphState) -> dict:
        ...

Or manually:
    from nuzantara_graph.observability import NodeTimer
    async with NodeTimer("retrieve") as t:
        result = await do_work()
    # t.duration_ms is available after the block

Fly.io integration:
  - All timing is emitted as structlog events → picked up by Fly.io log drain
  - JSON format: {"event": "node_complete", "node": "...", "duration_ms": 42, ...}
  - No external dependency required (structlog already in use)

OpenTelemetry (optional):
  - Set NUZANTARA_OTEL_ENDPOINT env var to enable OTLP export
  - If otel_endpoint is empty, falls back to structured logs only
"""

from __future__ import annotations

import functools
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable

import structlog

logger = structlog.get_logger()


class NodeTimer:
    """Async context manager that measures node execution time.

    Emits a structured log event on exit with:
      - node name
      - duration_ms
      - success/failure
      - key state fields (intent, correction_count, grade score if applicable)
    """

    def __init__(self, node_name: str, state: Any = None) -> None:
        self.node_name = node_name
        self.state = state
        self.duration_ms: float = 0.0
        self._start: float = 0.0

    async def __aenter__(self) -> NodeTimer:
        self._start = time.monotonic()
        logger.debug("node_start", node=self.node_name)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.duration_ms = (time.monotonic() - self._start) * 1000

        # Extract useful context from state if available
        ctx: dict[str, Any] = {
            "node": self.node_name,
            "duration_ms": round(self.duration_ms, 1),
            "success": exc_type is None,
        }

        if self.state is not None:
            if hasattr(self.state, "run_id"):
                ctx["run_id"] = self.state.run_id
            if hasattr(self.state, "intent") and self.state.intent:
                ctx["intent"] = str(self.state.intent)
            if hasattr(self.state, "correction_count"):
                ctx["correction_count"] = self.state.correction_count
            if hasattr(self.state, "grades") and self.state.grades:
                last = self.state.grades[-1]
                if hasattr(last, "score"):
                    ctx["last_grade_score"] = round(last.score, 3)
                if hasattr(last, "decision"):
                    ctx["last_grade_decision"] = str(last.decision)

        if exc_type is not None:
            ctx["error"] = str(exc_val)
            logger.error("node_failed", **ctx)
        else:
            logger.info("node_complete", **ctx)


def trace_node(node_name: str) -> Callable:
    """Decorator that wraps an async graph node function with NodeTimer.

    Usage:
        @trace_node("understand")
        async def understand_node(state: GraphState) -> dict:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
            async with NodeTimer(node_name, state=state):
                return await fn(state, *args, **kwargs)
        return wrapper
    return decorator


class GraphMetrics:
    """Accumulates per-run timing metrics across all nodes.

    Attach to GraphState.metadata or pass around explicitly.
    Emits a final summary log at the end of the graph run.

    Usage:
        metrics = GraphMetrics(run_id)
        metrics.record("understand", duration_ms=42.1)
        metrics.record("retrieve", duration_ms=310.5)
        metrics.summary()  # logs the full breakdown
    """

    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id
        self._timings: dict[str, float] = {}
        self._wall_start = time.monotonic()

    def record(self, node: str, duration_ms: float) -> None:
        """Record timing for a node (accumulates on retry)."""
        self._timings[node] = self._timings.get(node, 0.0) + duration_ms

    def summary(self) -> dict[str, Any]:
        """Log and return the full timing breakdown."""
        total_ms = (time.monotonic() - self._wall_start) * 1000
        breakdown = {k: round(v, 1) for k, v in sorted(self._timings.items())}

        summary = {
            "run_id": self.run_id,
            "total_ms": round(total_ms, 1),
            "node_timings_ms": breakdown,
            "slowest_node": max(breakdown, key=breakdown.get) if breakdown else None,
        }

        logger.info("graph_run_complete", **summary)
        return summary


def setup_structlog(log_level: str = "INFO") -> None:
    """Configure structlog for JSON output — Fly.io log drain compatible.

    Call once at application startup in main.py.
    Produces lines like:
      {"event": "node_complete", "node": "retrieve", "duration_ms": 142.3, ...}

    Uses stdlib LoggerFactory so structlog's ``add_logger_name`` processor
    can resolve ``logger.name`` — ``PrintLoggerFactory`` omits ``.name`` and
    crashes any ``logger.error(...)`` call with ``AttributeError``.
    """
    import logging
    import sys

    # Configure stdlib logging as the underlying sink. JSON formatting is
    # done by structlog's JSONRenderer, so the stdlib formatter just has
    # to pass the message through unchanged.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
