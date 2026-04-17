"""Chain observability — minimum-invasive Prometheus-shaped metrics.

MCP runs over stdio, not HTTP, so we cannot host a ``/metrics`` endpoint the
way a FastAPI process would. Instead we accumulate metrics in-process using
``prometheus_client`` (the exact library Grafana expects) and periodically
dump the registry to a shared JSON file at ``$NUZANTARA_MCP_METRICS_PATH``
(default ``~/.nuzantara/metrics/chains.prom``). A Grafana Agent or
``node_exporter --collector.textfile`` sidecar scrapes that path; no network
exposure from the MCP process itself.

Three series are emitted per chain run (all chain metadata is cardinality-
bounded: eight chains, ~15 step names per chain, four outcome labels):

    chain_runs_total{chain, status}
    chain_duration_seconds{chain, status}
    chain_step_errors_total{chain, step, error_type}
    chain_steps_total{chain, status}

Usage from chains.py:

    from nuzantara_mcp.workflows.metrics import get_metrics

    metrics = get_metrics()
    async with metrics.track_chain("daily_ops_autopilot") as tracker:
        # ... chain body, populates log ...
        tracker.set_log(log, outcome)

The tracker reads ``log`` at exit, derives per-step error counts from the
``{step, status, detail}`` entries every chain already appends, and bumps the
counters. If the chain raises before ``set_log`` is called, the run is still
counted with ``status="exception"``.

The observability is additive: chains that have not adopted ``track_chain``
yet still run exactly as before. No metric emission falls back to a no-op
if ``prometheus_client`` is not installed (Legge 4: graceful degradation).
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger("nuzantara-mcp.chains.metrics")

try:
    from prometheus_client import (  # type: ignore[import-not-found]
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest,
        write_to_textfile,
    )

    _PROM_AVAILABLE = True
except ImportError:  # pragma: no cover — optional dependency
    logger.info("prometheus_client not installed; chain metrics are disabled (no-op)")
    _PROM_AVAILABLE = False

    class _NoopMetric:  # minimal shim so callers don't need to branch
        def labels(self, **_: str) -> "_NoopMetric":
            return self

        def inc(self, amount: float = 1.0) -> None:
            pass

        def observe(self, amount: float) -> None:
            pass


DEFAULT_METRICS_PATH = Path.home() / ".nuzantara" / "metrics" / "chains.prom"
_METRICS_PATH_ENV = "NUZANTARA_MCP_METRICS_PATH"

# Histogram buckets tuned for chain-level durations (cron-style, seconds).
# Matches expected range: trivial chains <1s, heavy ops-autopilot up to ~120s.
_DURATION_BUCKETS = (0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300)


class ChainMetrics:
    """Container for chain-related Prometheus metrics.

    Construct once via :func:`get_metrics` (module-level singleton). Holds its
    own registry so callers can dump metrics without polluting the default
    registry (important when the MCP server runs as a subprocess of OpenClaw
    and several agents share the same Python interpreter).
    """

    def __init__(self, registry: Optional[Any] = None) -> None:
        if not _PROM_AVAILABLE:
            self.registry = None
            self.runs = _NoopMetric()  # type: ignore[assignment]
            self.duration = _NoopMetric()  # type: ignore[assignment]
            self.step_errors = _NoopMetric()  # type: ignore[assignment]
            self.steps = _NoopMetric()  # type: ignore[assignment]
            return

        self.registry = registry or CollectorRegistry()
        self.runs = Counter(
            "chain_runs_total",
            "Completed chain runs, labelled by chain name and final outcome.",
            labelnames=("chain", "status"),
            registry=self.registry,
        )
        self.duration = Histogram(
            "chain_duration_seconds",
            "Wall-clock duration of a chain run.",
            labelnames=("chain", "status"),
            buckets=_DURATION_BUCKETS,
            registry=self.registry,
        )
        self.step_errors = Counter(
            "chain_step_errors_total",
            "Errors at step level within a chain, classified by detail prefix.",
            labelnames=("chain", "step", "error_type"),
            registry=self.registry,
        )
        self.steps = Counter(
            "chain_steps_total",
            "Step executions within a chain, labelled by step status.",
            labelnames=("chain", "status"),
            registry=self.registry,
        )

    # ------------------------------------------------------------------ public

    @contextlib.asynccontextmanager
    async def track_chain(self, chain: str) -> AsyncIterator["_ChainTracker"]:
        """Wrap a chain execution and emit metrics at exit.

        If the body raises, ``status="exception"`` is recorded and the
        exception re-raised. If the body calls :meth:`_ChainTracker.set_log`,
        the outcome passed to ``set_log`` wins over the default ``success``.
        """
        tracker = _ChainTracker(chain)
        start = time.perf_counter()
        try:
            yield tracker
        except Exception:
            duration_s = time.perf_counter() - start
            self._finalize(chain, "exception", duration_s, log=None)
            raise
        else:
            duration_s = time.perf_counter() - start
            self._finalize(chain, tracker.outcome, duration_s, log=tracker.log)

    # ------------------------------------------------------------------ emit

    def record_from_log(
        self,
        chain: str,
        outcome: str,
        log: Optional[list[dict[str, Any]]],
        duration_s: float = 0.0,
    ) -> None:
        """Record metrics for a chain that did not use :meth:`track_chain`.

        Thin alias to :meth:`_finalize` for callers that already have the
        ``(chain, outcome, log)`` triple — e.g. the post-hoc reflection hook in
        ``chains._reflect_and_save``. When ``duration_s=0``, the duration
        histogram still receives an observation in the ``0-0.1s`` bucket so
        run counts and duration observations stay aligned.
        """
        self._finalize(chain, outcome, duration_s, log)

    def _finalize(
        self,
        chain: str,
        outcome: str,
        duration_s: float,
        log: Optional[list[dict[str, Any]]],
    ) -> None:
        status = outcome or "unknown"
        try:
            self.runs.labels(chain=chain, status=status).inc()
            self.duration.labels(chain=chain, status=status).observe(duration_s)
        except Exception:  # pragma: no cover — prometheus_client is robust
            logger.debug("metrics emission failed (run/duration)", exc_info=True)

        if log:
            for entry in log:
                step = entry.get("step") or "unknown"
                step_status = entry.get("status") or "unknown"
                try:
                    self.steps.labels(chain=chain, status=step_status).inc()
                except Exception:  # pragma: no cover
                    logger.debug("metrics emission failed (step)", exc_info=True)
                if step_status == "error":
                    error_type = _classify_error(entry.get("detail") or "")
                    try:
                        self.step_errors.labels(
                            chain=chain, step=step, error_type=error_type
                        ).inc()
                    except Exception:  # pragma: no cover
                        logger.debug("metrics emission failed (step_error)", exc_info=True)

        self._maybe_dump()

    def _maybe_dump(self) -> None:
        if not _PROM_AVAILABLE or self.registry is None:
            return
        path_str = os.environ.get(_METRICS_PATH_ENV) or str(DEFAULT_METRICS_PATH)
        path = Path(path_str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # write_to_textfile writes atomically via a temp file + rename.
            write_to_textfile(str(path), self.registry)
        except OSError as exc:
            logger.debug("metrics textfile write failed (%s): %s", path, exc)

    def render(self) -> bytes:
        """Return the current registry as Prometheus text exposition bytes.

        Exposed for tests and for the optional HTTP adapter that external
        callers may set up around the MCP process.
        """
        if not _PROM_AVAILABLE or self.registry is None:
            return b""
        return generate_latest(self.registry)


class _ChainTracker:
    """Per-run handle yielded by :meth:`ChainMetrics.track_chain`."""

    def __init__(self, chain: str) -> None:
        self.chain = chain
        self.log: Optional[list[dict[str, Any]]] = None
        self.outcome: str = "success"

    def set_log(self, log: list[dict[str, Any]], outcome: str) -> None:
        """Record the final step log and outcome. Must be called before the
        context exits for step-level metrics to be emitted.
        """
        self.log = log
        self.outcome = outcome or "success"


def _classify_error(detail: str) -> str:
    """Map a raw error string to a bounded label value.

    Error details in chain logs are free-form (`str(exception)`), and a naive
    label would blow up Prometheus cardinality. We bucket into common shapes
    so the ``error_type`` label stays at O(10) values.
    """
    if not detail:
        return "unknown"
    lower = detail.lower()
    if "timeout" in lower:
        return "timeout"
    if "connection" in lower or "network" in lower or "dns" in lower:
        return "network"
    # Order matters: 404 is a dedicated bucket; general 4xx → auth.
    if "http 404" in lower or "not found" in lower:
        return "not_found"
    if "http 401" in lower or "http 403" in lower or "unauthorized" in lower or "forbidden" in lower:
        return "auth"
    if "http 5" in lower or "server error" in lower:
        return "server_error"
    if "validation" in lower or "invalid" in lower:
        return "validation"
    return "other"


_INSTANCE: Optional[ChainMetrics] = None


def get_metrics() -> ChainMetrics:
    """Module-level singleton access."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ChainMetrics()
    return _INSTANCE


def reset_metrics_for_tests() -> None:
    """Reset the singleton — tests only."""
    global _INSTANCE
    _INSTANCE = None


__all__ = [
    "ChainMetrics",
    "DEFAULT_METRICS_PATH",
    "get_metrics",
    "reset_metrics_for_tests",
]
