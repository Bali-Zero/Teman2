"""Tests for OlympusGuardian — orchestrator with heartbeat and pulse loops."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.olympus.guardian import OlympusGuardian
from backend.services.olympus.models import PulseAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(mock_conn: AsyncMock | None = None) -> tuple[MagicMock, AsyncMock]:
    """Return (mock_pool, mock_conn) with async-context-manager acquire."""
    if mock_conn is None:
        mock_conn = AsyncMock()
    mock_pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = cm
    return mock_pool, mock_conn


def _make_alert_service() -> MagicMock:
    """Return a mock AlertService with async send_alert."""
    svc = MagicMock()
    svc.send_alert = AsyncMock(return_value={"telegram": True})
    return svc


# ---------------------------------------------------------------------------
# Tests — initialize
# ---------------------------------------------------------------------------


class TestGuardianInitialize:
    """initialize() should set up rules_engine, heartbeat, and pulse."""

    @pytest.mark.asyncio
    async def test_guardian_initialize(self) -> None:
        mock_pool, mock_conn = _make_pool()
        alert_svc = _make_alert_service()

        # RulesEngine.load_rules queries the DB — mock the fetch
        mock_conn.fetch = AsyncMock(return_value=[])

        guardian = OlympusGuardian(mock_pool, alert_svc)

        assert guardian.rules_engine is None
        assert guardian.heartbeat is None
        assert guardian.pulse is None

        await guardian.initialize()

        assert guardian.rules_engine is not None
        assert guardian.heartbeat is not None
        assert guardian.pulse is not None
        assert len(guardian.rules_engine.rules) == 0

    @pytest.mark.asyncio
    async def test_guardian_initialize_with_rules(self) -> None:
        mock_pool, mock_conn = _make_pool()
        alert_svc = _make_alert_service()

        # Simulate one rule in the DB
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "id": 1,
                "rule_name": "heartbeat_interval_seconds",
                "category": "rhythm",
                "config": {"value": 120},
                "source": "seed",
                "confidence": 1.0,
                "applied_count": 0,
                "last_applied": None,
                "superseded_by": None,
            },
        ])

        guardian = OlympusGuardian(mock_pool, alert_svc)
        await guardian.initialize()

        assert len(guardian.rules_engine.rules) == 1
        assert "heartbeat_interval_seconds" in guardian.rules_engine.rules


# ---------------------------------------------------------------------------
# Tests — run_heartbeat_once
# ---------------------------------------------------------------------------


class TestGuardianSingleHeartbeat:
    """run_heartbeat_once should collect, check, and persist."""

    @pytest.mark.asyncio
    async def test_guardian_single_heartbeat(self) -> None:
        mock_pool, _ = _make_pool()
        alert_svc = _make_alert_service()

        guardian = OlympusGuardian(mock_pool, alert_svc)

        # Mock heartbeat sub-component directly
        mock_heartbeat = MagicMock()
        mock_snapshot = MagicMock()
        mock_heartbeat.collect_metrics = AsyncMock(return_value=mock_snapshot)
        mock_heartbeat.check_alerts = AsyncMock(return_value=[])
        mock_heartbeat.persist = AsyncMock()

        guardian.heartbeat = mock_heartbeat

        await guardian.run_heartbeat_once()

        mock_heartbeat.collect_metrics.assert_awaited_once()
        mock_heartbeat.check_alerts.assert_awaited_once_with(mock_snapshot)
        mock_heartbeat.persist.assert_awaited_once_with(mock_snapshot)


# ---------------------------------------------------------------------------
# Tests — run_pulse_once
# ---------------------------------------------------------------------------


class TestGuardianSinglePulse:
    """run_pulse_once should run pulse, persist, record rules, send summary."""

    @pytest.mark.asyncio
    async def test_guardian_single_pulse_success(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()
        alert_svc = _make_alert_service()

        guardian = OlympusGuardian(mock_pool, alert_svc)

        # Mock pulse to return two OK actions
        mock_pulse = MagicMock()
        actions = [
            PulseAction(
                action_type="vacuum",
                target="activity_log",
                outcome="ok",
                duration_ms=50,
                rule_applied="vacuum_dead_pct_threshold",
            ),
            PulseAction(
                action_type="cleanup_audit_trail",
                target="api_audit_trail",
                outcome="ok",
                duration_ms=30,
                rule_applied="audit_retention_days",
            ),
        ]
        mock_pulse.run_full_pulse = AsyncMock(return_value=actions)
        guardian.pulse = mock_pulse

        # Mock rules_engine for record_applied
        mock_rules = MagicMock()
        mock_rules.record_applied = AsyncMock()
        guardian.rules_engine = mock_rules

        result = await guardian.run_pulse_once()

        assert len(result) == 2
        mock_pulse.run_full_pulse.assert_awaited_once()
        # record_applied should be called for each unique rule
        assert mock_rules.record_applied.await_count == 2
        # Alert should be sent (pulse summary with 0 failures)
        alert_svc.send_alert.assert_awaited()

    @pytest.mark.asyncio
    async def test_guardian_single_pulse_with_failures(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()
        alert_svc = _make_alert_service()

        guardian = OlympusGuardian(mock_pool, alert_svc)

        # One success, one failure
        mock_pulse = MagicMock()
        actions = [
            PulseAction(
                action_type="vacuum",
                target="activity_log",
                outcome="ok",
                duration_ms=50,
            ),
            PulseAction(
                action_type="reindex",
                target="broken_idx",
                outcome="error",
                duration_ms=100,
                reflection="REINDEX failed",
            ),
        ]
        mock_pulse.run_full_pulse = AsyncMock(return_value=actions)
        guardian.pulse = mock_pulse

        mock_rules = MagicMock()
        mock_rules.record_applied = AsyncMock()
        guardian.rules_engine = mock_rules

        result = await guardian.run_pulse_once()

        assert len(result) == 2
        # Summary alert should include 1 failure
        alert_svc.send_alert.assert_awaited()
        # Verify the WARNING level was used (failures > 0)
        last_call = alert_svc.send_alert.call_args_list[-1]
        sent_message = last_call.kwargs.get("message", last_call[0][1] if len(last_call[0]) > 1 else "")
        assert "1 fallimenti" in sent_message


# ---------------------------------------------------------------------------
# Tests — get_health_summary
# ---------------------------------------------------------------------------


class TestGuardianHealthSummary:
    """get_health_summary should return structured status dict."""

    @pytest.mark.asyncio
    async def test_health_summary_alive(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.fetchrow = AsyncMock(return_value={"pool_size": 10, "recorded_at": "2026-04-10"})
        mock_conn.fetch = AsyncMock(return_value=[])
        alert_svc = _make_alert_service()

        guardian = OlympusGuardian(mock_pool, alert_svc)
        # Simulate initialized rules_engine
        mock_rules = MagicMock()
        mock_rules.rules = {"r1": MagicMock(), "r2": MagicMock()}
        guardian.rules_engine = mock_rules

        summary = await guardian.get_health_summary()

        assert summary["status"] == "alive"
        assert summary["rules_count"] == 2
        assert summary["last_heartbeat"] is not None
        assert isinstance(summary["recent_actions"], list)

    @pytest.mark.asyncio
    async def test_health_summary_no_data(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        alert_svc = _make_alert_service()

        guardian = OlympusGuardian(mock_pool, alert_svc)

        summary = await guardian.get_health_summary()

        assert summary["status"] == "alive"
        assert summary["running"] is False
        assert summary["rules_count"] == 0
        assert summary["last_heartbeat"] is None
        assert summary["recent_actions"] == []
