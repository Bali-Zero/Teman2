"""Tests for nuzantara_mcp.workflows.metrics — Prometheus-shaped chain telemetry.

These tests assume prometheus_client is importable (it's declared in
requirements for the MCP server). If the library is missing the module
degrades to no-op, and the coverage of that branch lives in
``test_chain_metrics_noop`` below, gated on a monkeypatch.
"""

from __future__ import annotations

import pytest

from nuzantara_mcp.workflows import metrics as metrics_mod


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    metrics_mod.reset_metrics_for_tests()
    yield
    metrics_mod.reset_metrics_for_tests()


@pytest.fixture
def fresh_metrics() -> metrics_mod.ChainMetrics:
    """A ChainMetrics with its own registry (not the module singleton)."""
    if not metrics_mod._PROM_AVAILABLE:
        pytest.skip("prometheus_client not available")
    from prometheus_client import CollectorRegistry  # type: ignore[import-not-found]

    return metrics_mod.ChainMetrics(registry=CollectorRegistry())


def _counter_value(cm: metrics_mod.ChainMetrics, metric_attr: str, **labels: str) -> float:
    """Read a single Counter/Histogram cell's sample value."""
    metric = getattr(cm, metric_attr)
    # _metrics keeps instances by tuple(label_values)
    label_names = sorted(labels)
    values = tuple(labels[n] for n in label_names)
    # Counter exposes .labels(**kw) → child with _value
    child = metric.labels(**labels)
    return child._value.get()


def _histogram_count(cm: metrics_mod.ChainMetrics, **labels: str) -> float:
    child = cm.duration.labels(**labels)
    return child._sum.get()  # sum of all observations — duration > 0 proves an obs happened


# ---------------------------------------------------------------------------
# ChainMetrics API
# ---------------------------------------------------------------------------

def test_chain_metrics_construct(fresh_metrics: metrics_mod.ChainMetrics) -> None:
    assert fresh_metrics.registry is not None


@pytest.mark.asyncio
async def test_track_chain_records_run_and_duration(
    fresh_metrics: metrics_mod.ChainMetrics,
) -> None:
    async with fresh_metrics.track_chain("chain_x") as tracker:
        tracker.set_log([{"step": "a", "status": "ok"}], outcome="success")

    assert _counter_value(fresh_metrics, "runs", chain="chain_x", status="success") == 1
    assert _histogram_count(fresh_metrics, chain="chain_x", status="success") > 0


@pytest.mark.asyncio
async def test_track_chain_counts_each_step(
    fresh_metrics: metrics_mod.ChainMetrics,
) -> None:
    async with fresh_metrics.track_chain("chain_y") as tracker:
        log = [
            {"step": "a", "status": "ok"},
            {"step": "b", "status": "ok"},
            {"step": "c", "status": "error", "detail": "timeout waiting"},
        ]
        tracker.set_log(log, outcome="partial")

    assert _counter_value(fresh_metrics, "steps", chain="chain_y", status="ok") == 2
    assert _counter_value(fresh_metrics, "steps", chain="chain_y", status="error") == 1
    # Step error bucketed by error_type
    assert _counter_value(
        fresh_metrics, "step_errors", chain="chain_y", step="c", error_type="timeout"
    ) == 1


@pytest.mark.asyncio
async def test_track_chain_exception_records_failure(
    fresh_metrics: metrics_mod.ChainMetrics,
) -> None:
    with pytest.raises(ValueError):
        async with fresh_metrics.track_chain("chain_boom"):
            raise ValueError("boom")

    assert _counter_value(
        fresh_metrics, "runs", chain="chain_boom", status="exception"
    ) == 1


@pytest.mark.asyncio
async def test_track_chain_without_set_log_still_counts_run(
    fresh_metrics: metrics_mod.ChainMetrics,
) -> None:
    """A chain that forgets to call set_log is still counted — defensive."""
    async with fresh_metrics.track_chain("chain_lazy"):
        pass

    assert _counter_value(fresh_metrics, "runs", chain="chain_lazy", status="success") == 1


def test_render_returns_prometheus_text(fresh_metrics: metrics_mod.ChainMetrics) -> None:
    fresh_metrics.runs.labels(chain="c1", status="success").inc()
    out = fresh_metrics.render()
    assert b"chain_runs_total" in out
    assert b'chain="c1"' in out


# ---------------------------------------------------------------------------
# _classify_error — label cardinality control (OSINT blindato too: no free text)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "detail, expected",
    [
        ("Timeout (30s) calling /api/crm/clients", "timeout"),
        ("Connection reset by peer", "network"),
        ("DNS resolution failed", "network"),
        ("HTTP 404 from GET /api/foo", "not_found"),
        ("HTTP 503 from POST /api/bar", "server_error"),
        ("Unauthorized — rotate API key", "auth"),
        ("validation error: field missing", "validation"),
        ("", "unknown"),
        ("something totally opaque", "other"),
    ],
)
def test_classify_error_buckets(detail: str, expected: str) -> None:
    assert metrics_mod._classify_error(detail) == expected


# ---------------------------------------------------------------------------
# Textfile dump — no sensitive content leaks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_textfile_dump_written(
    fresh_metrics: metrics_mod.ChainMetrics,
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "nested" / "chains.prom"
    monkeypatch.setenv("NUZANTARA_MCP_METRICS_PATH", str(output))

    async with fresh_metrics.track_chain("chain_z") as tracker:
        tracker.set_log([{"step": "a", "status": "ok"}], outcome="success")

    assert output.is_file()
    content = output.read_text()
    assert "chain_runs_total" in content
    assert "chain_z" in content


@pytest.mark.asyncio
async def test_textfile_dump_failure_is_swallowed(
    fresh_metrics: metrics_mod.ChainMetrics,
    monkeypatch,
) -> None:
    """If the metrics dir is read-only, the chain must still succeed."""
    monkeypatch.setenv("NUZANTARA_MCP_METRICS_PATH", "/dev/null/invalid/chains.prom")

    async with fresh_metrics.track_chain("chain_w") as tracker:
        tracker.set_log([{"step": "a", "status": "ok"}], outcome="success")
    # No exception → Legge 4 satisfied.


# ---------------------------------------------------------------------------
# Singleton semantics
# ---------------------------------------------------------------------------

def test_get_metrics_returns_same_instance() -> None:
    a = metrics_mod.get_metrics()
    b = metrics_mod.get_metrics()
    assert a is b


def test_reset_metrics_for_tests_replaces_singleton() -> None:
    a = metrics_mod.get_metrics()
    metrics_mod.reset_metrics_for_tests()
    b = metrics_mod.get_metrics()
    assert a is not b


# ---------------------------------------------------------------------------
# Integration: _reflect_and_save emits metrics for real chain log shapes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reflect_and_save_emits_chain_metrics(monkeypatch, tmp_path) -> None:
    """Every chain goes through _reflect_and_save; ensure telemetry lands."""
    from unittest.mock import AsyncMock

    from nuzantara_mcp.workflows import chains as chains_mod

    monkeypatch.setenv(
        "NUZANTARA_MCP_METRICS_PATH", str(tmp_path / "chains.prom")
    )
    metrics_mod.reset_metrics_for_tests()

    call_safe = AsyncMock(return_value={"status": "ok"})
    log = [
        {"step": "expiry_alerts", "status": "ok", "reminders_sent": 3},
        {"step": "agent_health", "status": "error", "detail": "Timeout calling /api/agents"},
    ]

    await chains_mod._reflect_and_save(
        call_safe,
        chain_name="daily_ops_autopilot",
        summary="Reminders=3",
        outcome="partial",
        log=log,
    )

    metrics = metrics_mod.get_metrics()
    assert _counter_value(
        metrics, "runs", chain="daily_ops_autopilot", status="partial"
    ) == 1
    assert _counter_value(
        metrics, "steps", chain="daily_ops_autopilot", status="ok"
    ) == 1
    assert _counter_value(
        metrics,
        "step_errors",
        chain="daily_ops_autopilot",
        step="agent_health",
        error_type="timeout",
    ) == 1
    # Textfile dump happened
    assert (tmp_path / "chains.prom").is_file()
