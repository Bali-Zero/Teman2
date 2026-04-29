"""
P0-0 — Cell pulse classifies on body.status, not just HTTP code.

Cicatrix STRUCTURAL 2026-04-29: pulse.py classified GREEN whenever
`reading.reachable AND reading.status_code == 200`. So when /health
mistakenly returned 200 with body `{"status":"startup_failed"}`, Cell's
own nervous system reported green and never escalated. This test pins
the new contract: Cell looks past the HTTP envelope into the semantic
status field.

Reference: docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-0_health_endpoint_classify.md
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cell.core.pulse import classify_http_status
from cell.fast.health_triage import HealthStatus
from cell.sensors.health_sensor import HealthReading


def _reading(status_code: int = 200, body: dict | None = None, reachable: bool = True) -> HealthReading:
    return HealthReading(
        timestamp=datetime.now(timezone.utc),
        reachable=reachable,
        status_code=status_code,
        response_time_seconds=0.05,
        body=body,
    )


def test_classify_red_when_body_status_startup_failed() -> None:
    """A 200 OK with body {'status': 'startup_failed'} must classify RED.

    This is the exact scenario behind the 2026-04-29 03:11Z incident:
    backend reported HTTP 200 while critical services had failed to init.
    """
    reading = _reading(status_code=200, body={"status": "startup_failed", "error": "X"})
    assert classify_http_status(reading) == HealthStatus.RED


def test_classify_yellow_when_body_status_initializing() -> None:
    """A 200 OK with body {'status': 'initializing'} is warm-up, classify YELLOW."""
    reading = _reading(status_code=200, body={"status": "initializing"})
    assert classify_http_status(reading) == HealthStatus.YELLOW


def test_classify_green_when_body_status_healthy() -> None:
    """A 200 OK with body {'status': 'healthy'} stays GREEN."""
    reading = _reading(status_code=200, body={"status": "healthy"})
    assert classify_http_status(reading) == HealthStatus.GREEN


def test_classify_falls_back_to_http_when_body_missing() -> None:
    """When body is None (legacy path), fall back to HTTP-based classification."""
    reading = _reading(status_code=200, body=None)
    assert classify_http_status(reading) == HealthStatus.GREEN

    reading_unreachable = _reading(reachable=False)
    assert classify_http_status(reading_unreachable) == HealthStatus.RED
