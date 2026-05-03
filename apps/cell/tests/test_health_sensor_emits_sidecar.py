"""Sprint 1.B 2026-05-02: HealthSensor must emit sidecar liveness file post-poll.

Spec ref: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
"""
from datetime import datetime, timezone
from unittest.mock import patch

from cell.sensors import health_sensor as hs


def test_bridge_emits_ok_sidecar_on_200():
    """Reachable + status=200 → emit ok with metadata (http_status + latency_ms)."""
    fake_reading = hs.HealthReading(
        timestamp=datetime.now(tz=timezone.utc),
        reachable=True,
        status_code=200,
        response_time_seconds=0.047,
    )

    captured: list[tuple[str, str, dict]] = []

    def fake_emit(organ_id, status, metadata=None, **kwargs):
        captured.append((organ_id, status, dict(metadata or {})))
        return True

    with patch.object(hs, "emit_organ_last_seen", side_effect=fake_emit):
        hs.bridge_reading_to_sidecar(fake_reading)

    assert len(captured) == 1
    organ_id, status, metadata = captured[0]
    assert organ_id == "backend.api"
    assert status == "ok"
    assert metadata["http_status"] == 200
    assert metadata["latency_ms"] == 47.0  # 0.047s * 1000 = 47 ms


def test_bridge_emits_degraded_sidecar_on_non_200():
    """Reachable + non-200 → degraded."""
    fake_reading = hs.HealthReading(
        timestamp=datetime.now(tz=timezone.utc),
        reachable=True,
        status_code=503,
        response_time_seconds=0.012,
    )

    captured: list[tuple[str, str, dict]] = []

    def fake_emit(organ_id, status, metadata=None, **kwargs):
        captured.append((organ_id, status, dict(metadata or {})))
        return True

    with patch.object(hs, "emit_organ_last_seen", side_effect=fake_emit):
        hs.bridge_reading_to_sidecar(fake_reading)

    assert captured[0][:2] == ("backend.api", "degraded")
    assert captured[0][2]["http_status"] == 503


def test_bridge_emits_fail_sidecar_on_unreachable():
    """Unreachable → fail with error metadata."""
    fake_reading = hs.HealthReading(
        timestamp=datetime.now(tz=timezone.utc),
        reachable=False,
        status_code=0,
        error="connection timeout after 10s",
    )

    captured: list[tuple[str, str, dict]] = []

    def fake_emit(organ_id, status, metadata=None, **kwargs):
        captured.append((organ_id, status, dict(metadata or {})))
        return True

    with patch.object(hs, "emit_organ_last_seen", side_effect=fake_emit):
        hs.bridge_reading_to_sidecar(fake_reading)

    assert captured[0][:2] == ("backend.api", "fail")
    assert "error" in captured[0][2]
    assert "connection timeout" in captured[0][2]["error"]
