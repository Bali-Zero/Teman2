"""
Federation Tracing — Dual-export observability (local + LangSmith).

Provides tracing context managers for the federation orchestrator pipeline:
  - trace_dispatch(): traces a single agent dispatch (A2A or CLI)
  - trace_pipeline(): traces the full federation pipeline
  - get_agent_metrics(): returns accumulated per-agent statistics

Export targets (both active simultaneously):
  1. Local: rolling JSONL file in ai-dispatch-output/metrics/
  2. LangSmith: OTLP HTTP when LANGSMITH_API_KEY is set

Metrics always collected in-memory regardless of export configuration.

Usage:
    from apps.federation.tracing import init_tracing, trace_dispatch, trace_pipeline

    init_tracing()

    with trace_pipeline("add tax calculation") as ctx:
        with trace_dispatch("gemini-search") as dispatch_ctx:
            result = await do_work()
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger("federation.tracing")

# ═══════════════════════════════════════════════════════
# Local file export
# ═══════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRICS_DIR = PROJECT_ROOT / "ai-dispatch-output" / "metrics"
_local_export_lock = threading.Lock()


def _ensure_metrics_dir() -> None:
    """Create metrics directory if it doesn't exist."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def _local_export_event(event: dict[str, Any]) -> None:
    """Append a trace event to the daily JSONL file."""
    try:
        _ensure_metrics_dir()
        today = datetime.now().strftime("%Y-%m-%d")
        filepath = METRICS_DIR / f"federation-{today}.jsonl"
        line = json.dumps(event, ensure_ascii=False, default=str) + "\n"
        with _local_export_lock:
            with open(filepath, "a") as f:
                f.write(line)
    except Exception as e:
        logger.debug("Local metrics export failed: %s", e)

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


def _record_dispatch(
    agent_id: str,
    duration_s: float,
    *,
    failed: bool = False,
    dispatch_mode: str = "unknown",
    output_length: int = 0,
) -> None:
    """Record a dispatch execution into the metrics accumulator + local file."""
    with _metrics_lock:
        if agent_id not in _agent_metrics:
            _agent_metrics[agent_id] = {"count": 0, "total_time": 0.0, "failures": 0}
        entry = _agent_metrics[agent_id]
        entry["count"] += 1
        entry["total_time"] += duration_s
        if failed:
            entry["failures"] += 1

    # Local file export
    _local_export_event({
        "type": "dispatch",
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "duration_s": round(duration_s, 3),
        "status": "failed" if failed else "completed",
        "dispatch_mode": dispatch_mode,
        "output_length": output_length,
    })


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
                    agent_id, duration,
                    failed=(status == "failed"),
                    dispatch_mode=dispatch_mode,
                    output_length=len(output_text) if output_text else 0,
                )
    else:
        # No-op path: still collect metrics + local export
        failed = False
        try:
            yield result
        except Exception:
            failed = True
            raise
        finally:
            duration = time.monotonic() - start
            status = "failed" if failed or result.get("error") else "completed"
            output_text = result.get("output", "")
            _record_dispatch(
                agent_id, duration,
                failed=(status == "failed"),
                dispatch_mode=dispatch_mode,
                output_length=len(output_text) if output_text else 0,
            )


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

                # Also export locally
                _local_export_event({
                    "type": "pipeline",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "task": task[:500],
                    "total_duration_s": round(duration, 3),
                    "total_agents": pipeline_ctx.get("total_agents", 0),
                    "status": "failed" if failed else "completed",
                    "classification": classification,
                })
    else:
        # No-op path
        failed = False
        try:
            yield pipeline_ctx
        except Exception:
            failed = True
            raise
        finally:
            duration = time.monotonic() - start
            _local_export_event({
                "type": "pipeline",
                "ts": datetime.now(timezone.utc).isoformat(),
                "task": task[:500],
                "total_duration_s": round(duration, 3),
                "total_agents": pipeline_ctx.get("total_agents", 0),
                "status": "failed" if failed else "completed",
                "classification": pipeline_ctx.get("classification", {}),
            })


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
# Local file metrics reader
# ═══════════════════════════════════════════════════════
def read_local_metrics(days: int = 7) -> dict[str, Any]:
    """Read metrics from local JSONL files for the last N days.

    Returns aggregated stats from file-based trace history,
    complementing the in-memory get_agent_metrics() which only
    covers the current process.
    """
    from datetime import timedelta

    _ensure_metrics_dir()
    all_events: list[dict] = []

    today = datetime.now()
    for i in range(days):
        day = today - timedelta(days=i)
        filepath = METRICS_DIR / f"federation-{day.strftime('%Y-%m-%d')}.jsonl"
        if filepath.exists():
            with open(filepath) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            all_events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

    # Aggregate dispatch events
    agent_stats: dict[str, dict[str, Any]] = {}
    pipeline_count = 0
    pipeline_total_time = 0.0

    for evt in all_events:
        if evt.get("type") == "dispatch":
            aid = evt.get("agent_id", "unknown")
            if aid not in agent_stats:
                agent_stats[aid] = {"count": 0, "total_time": 0.0, "failures": 0}
            agent_stats[aid]["count"] += 1
            agent_stats[aid]["total_time"] += evt.get("duration_s", 0)
            if evt.get("status") == "failed":
                agent_stats[aid]["failures"] += 1
        elif evt.get("type") == "pipeline":
            pipeline_count += 1
            pipeline_total_time += evt.get("total_duration_s", 0)

    # Format output
    agents_formatted = {}
    for aid, stats in agent_stats.items():
        c = stats["count"]
        agents_formatted[aid] = {
            "count": c,
            "total_time_s": round(stats["total_time"], 3),
            "avg_duration_s": round(stats["total_time"] / c, 3) if c > 0 else 0.0,
            "failures": stats["failures"],
            "success_rate": round((c - stats["failures"]) / c, 3) if c > 0 else 0.0,
        }

    return {
        "source": "local_files",
        "days": days,
        "events_total": len(all_events),
        "pipelines": pipeline_count,
        "pipeline_avg_time_s": round(pipeline_total_time / pipeline_count, 3) if pipeline_count > 0 else 0.0,
        "agents": agents_formatted,
    }


# ═══════════════════════════════════════════════════════
# CLI entrypoint
# ═══════════════════════════════════════════════════════
def main() -> None:
    """Print current + historical tracing metrics."""
    init_tracing()

    print("═══ In-Memory Metrics (current process) ═══")
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

    print(f"\n═══ Local File Metrics (last 7 days) ═══")
    local = read_local_metrics(days=7)
    print(json.dumps(local, indent=2))
    if local["events_total"] == 0:
        print("\nNo local trace files found.")
    else:
        print(f"\n{local['events_total']} events, {local['pipelines']} pipelines")
        print(f"Metrics dir: {METRICS_DIR}")


if __name__ == "__main__":
    main()
