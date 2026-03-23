"""
Federation Tracing — OpenTelemetry instrumentation with LangSmith OTLP export.

Provides tracing context managers for the federation orchestrator pipeline:
  - trace_dispatch(): traces a single agent dispatch (A2A or CLI)
  - trace_pipeline(): traces the full federation pipeline
  - get_agent_metrics(): returns accumulated per-agent statistics

Exports to LangSmith via OTLP HTTP when LANGSMITH_API_KEY is set.
Gracefully degrades to no-ops if opentelemetry packages are missing.

Usage:
    from apps.federation.tracing import init_tracing, trace_dispatch, trace_pipeline

    init_tracing()

    async with trace_pipeline("add tax calculation") as span:
        async with trace_dispatch("gemini-search") as dispatch_span:
            result = await do_work()
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger("federation.tracing")

# ═══════════════════════════════════════════════════════
# Graceful degradation flag
# ═══════════════════════════════════════════════════════
_TRACING_ENABLED = False

# ═══════════════════════════════════════════════════════
# Per-agent metrics accumulator (thread-safe)
# ═══════════════════════════════════════════════════════
_metrics_lock = threading.Lock()
_agent_metrics: dict[str, dict[str, float]] = {}
# Structure per agent_id:
#   {"count": N, "total_time": float, "failures": N}


def _record_dispatch(agent_id: str, duration_s: float, *, failed: bool = False) -> None:
    """Record a dispatch execution into the metrics accumulator."""
    with _metrics_lock:
        if agent_id not in _agent_metrics:
            _agent_metrics[agent_id] = {"count": 0, "total_time": 0.0, "failures": 0}
        entry = _agent_metrics[agent_id]
        entry["count"] += 1
        entry["total_time"] += duration_s
        if failed:
            entry["failures"] += 1


# ═══════════════════════════════════════════════════════
# Initialization
# ═══════════════════════════════════════════════════════
def init_tracing(service_name: str = "federation-v3") -> None:
    """Initialize OpenTelemetry tracing with LangSmith OTLP export.

    Requires:
      - opentelemetry-api
      - opentelemetry-sdk
      - opentelemetry-exporter-otlp-proto-http
      - LANGSMITH_API_KEY environment variable

    If any dependency is missing, tracing is disabled and all
    trace_dispatch / trace_pipeline calls become no-ops. Metrics
    collection via _agent_metrics still works regardless.
    """
    global _TRACING_ENABLED  # noqa: PLW0603

    langsmith_key = os.environ.get("LANGSMITH_API_KEY")
    if not langsmith_key:
        logger.warning(
            "LANGSMITH_API_KEY not set — tracing disabled (metrics still collected)"
        )
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning(
            "opentelemetry packages not installed (%s) — tracing disabled. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-http",
            exc,
        )
        return

    # Build resource with service metadata
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "3.0.0",
            "deployment.environment": os.environ.get("FLY_APP_NAME", "local"),
        }
    )

    # LangSmith OTLP endpoint
    exporter = OTLPSpanExporter(
        endpoint="https://api.smith.langchain.com/otel/v1/traces",
        headers={"x-api-key": langsmith_key},
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _TRACING_ENABLED = True
    logger.info(
        "OpenTelemetry tracing initialized — exporting to LangSmith (service=%s)",
        service_name,
    )


def _get_tracer() -> Any:
    """Return the federation tracer, or None if tracing is disabled."""
    if not _TRACING_ENABLED:
        return None
    try:
        from opentelemetry import trace

        return trace.get_tracer("federation.orchestrator", "3.0.0")
    except Exception:
        return None


# ═══════════════════════════════════════════════════════
# trace_dispatch — context manager for a single agent dispatch
# ═══════════════════════════════════════════════════════
@contextmanager
def trace_dispatch(
    agent_id: str,
    dispatch_mode: str = "a2a",
) -> Generator[dict[str, Any], None, None]:
    """Context manager that traces a single agent dispatch.

    Sets span attributes:
      - agent_id: the federation agent being dispatched
      - dispatch_mode: "a2a" or "cli"
      - start_time: ISO 8601 timestamp

    On exit sets:
      - duration_s: wall-clock seconds
      - status: "completed" or "failed"
      - output_length: length of output (set via result dict)

    Usage:
        with trace_dispatch("gemini-search", dispatch_mode="cli") as ctx:
            output = await do_search(task)
            ctx["output"] = output  # optional: sets output_length attribute

    Yields a mutable dict that callers can populate with 'output' and 'error'.
    """
    tracer = _get_tracer()
    result: dict[str, Any] = {"output": "", "error": None}
    start = time.monotonic()
    start_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    if tracer is not None:
        from opentelemetry.trace import StatusCode

        with tracer.start_as_current_span(f"dispatch/{agent_id}") as span:
            span.set_attribute("agent_id", agent_id)
            span.set_attribute("dispatch_mode", dispatch_mode)
            span.set_attribute("start_time", start_iso)

            failed = False
            try:
                yield result
            except Exception as exc:
                failed = True
                result["error"] = str(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
            finally:
                duration = time.monotonic() - start
                status = "failed" if failed or result.get("error") else "completed"
                output_text = result.get("output", "")

                span.set_attribute("duration_s", round(duration, 3))
                span.set_attribute("status", status)
                span.set_attribute(
                    "output_length", len(output_text) if output_text else 0
                )

                _record_dispatch(
                    agent_id, duration, failed=(status == "failed")
                )
    else:
        # No-op path: still collect metrics
        failed = False
        try:
            yield result
        except Exception:
            failed = True
            raise
        finally:
            duration = time.monotonic() - start
            status = "failed" if failed or result.get("error") else "completed"
            _record_dispatch(agent_id, duration, failed=(status == "failed"))


# ═══════════════════════════════════════════════════════
# trace_pipeline — context manager for the full pipeline
# ═══════════════════════════════════════════════════════
@contextmanager
def trace_pipeline(
    task: str,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for the full federation pipeline execution.

    Sets span attributes:
      - task: the task description (truncated to 500 chars)
      - classification: JSON string of the classification result
      - total_agents: number of agents dispatched
      - total_duration_s: wall-clock pipeline duration

    Usage:
        with trace_pipeline("add quarterly tax calculation") as ctx:
            classification = await classify_task(task)
            ctx["classification"] = classification
            ctx["total_agents"] = len(classification["dispatch"])
            results = await dispatch_agents(...)

    Yields a mutable dict that callers can populate with pipeline metadata.
    """
    tracer = _get_tracer()
    pipeline_ctx: dict[str, Any] = {
        "classification": {},
        "total_agents": 0,
    }
    start = time.monotonic()

    if tracer is not None:
        from opentelemetry.trace import StatusCode

        with tracer.start_as_current_span("federation/pipeline") as span:
            span.set_attribute("task", task[:500])

            failed = False
            try:
                yield pipeline_ctx
            except Exception as exc:
                failed = True
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
            finally:
                duration = time.monotonic() - start
                classification = pipeline_ctx.get("classification", {})

                span.set_attribute("total_duration_s", round(duration, 3))
                span.set_attribute("total_agents", pipeline_ctx.get("total_agents", 0))
                span.set_attribute(
                    "status", "failed" if failed else "completed"
                )

                # Serialize classification as JSON string for the span attribute
                import json

                try:
                    span.set_attribute(
                        "classification", json.dumps(classification, default=str)
                    )
                except Exception:
                    span.set_attribute("classification", str(classification))
    else:
        # No-op path
        try:
            yield pipeline_ctx
        except Exception:
            raise


# ═══════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════
def get_agent_metrics() -> dict[str, Any]:
    """Return collected metrics: avg duration per agent, success rate, total dispatches.

    Returns:
        {
            "total_dispatches": int,
            "total_failures": int,
            "overall_success_rate": float (0.0 - 1.0),
            "agents": {
                "agent-id": {
                    "count": int,
                    "total_time_s": float,
                    "avg_duration_s": float,
                    "failures": int,
                    "success_rate": float,
                },
                ...
            },
            "tracing_enabled": bool,
        }
    """
    with _metrics_lock:
        snapshot = {k: dict(v) for k, v in _agent_metrics.items()}

    total_dispatches = 0
    total_failures = 0
    agents: dict[str, Any] = {}

    for agent_id, stats in snapshot.items():
        count = int(stats["count"])
        total_time = stats["total_time"]
        failures = int(stats["failures"])

        total_dispatches += count
        total_failures += failures

        agents[agent_id] = {
            "count": count,
            "total_time_s": round(total_time, 3),
            "avg_duration_s": round(total_time / count, 3) if count > 0 else 0.0,
            "failures": failures,
            "success_rate": round((count - failures) / count, 3) if count > 0 else 0.0,
        }

    overall_success = (
        round((total_dispatches - total_failures) / total_dispatches, 3)
        if total_dispatches > 0
        else 0.0
    )

    return {
        "total_dispatches": total_dispatches,
        "total_failures": total_failures,
        "overall_success_rate": overall_success,
        "agents": agents,
        "tracing_enabled": _TRACING_ENABLED,
    }


def reset_metrics() -> None:
    """Clear all accumulated metrics. Useful for testing."""
    with _metrics_lock:
        _agent_metrics.clear()


# ═══════════════════════════════════════════════════════
# CLI entrypoint
# ═══════════════════════════════════════════════════════
def main() -> None:
    """Print current tracing metrics when run directly."""
    import json

    init_tracing()
    metrics = get_agent_metrics()
    print(json.dumps(metrics, indent=2))

    if not metrics["agents"]:
        print("\nNo dispatches recorded yet in this process.")
    else:
        print(f"\nTotal dispatches: {metrics['total_dispatches']}")
        print(f"Overall success rate: {metrics['overall_success_rate']:.1%}")
        for agent_id, stats in metrics["agents"].items():
            print(
                f"  {agent_id}: {stats['count']} calls, "
                f"avg {stats['avg_duration_s']:.2f}s, "
                f"success {stats['success_rate']:.1%}"
            )


if __name__ == "__main__":
    main()
