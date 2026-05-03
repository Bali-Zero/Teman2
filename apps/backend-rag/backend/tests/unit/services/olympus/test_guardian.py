"""Tests for backend.services.olympus.guardian — OlympusGuardian orchestrator."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.olympus.models import PulseAction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_pool() -> MagicMock:
    """Mock asyncpg.Pool with acquire() context manager."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


def _make_action(
    outcome: str = "success",
    rule_applied: str | None = None,
) -> PulseAction:
    return PulseAction(
        action_type="vacuum",
        target="public.clients",
        outcome=outcome,
        rule_applied=rule_applied,
        executed_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def pool() -> MagicMock:
    return _make_pool()


@pytest.fixture
def guardian(pool: MagicMock):
    from backend.services.olympus.guardian import OlympusGuardian
    return OlympusGuardian(db_pool=pool, alert_service=MagicMock())


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_initial_state(self, guardian) -> None:
        assert guardian._running is False
        assert guardian._tasks == []
        assert guardian.rules_engine is None
        assert guardian.heartbeat is None
        assert guardian.pulse is None


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

class TestInitialize:
    @pytest.mark.asyncio
    @patch("backend.services.olympus.guardian.RulesEngine")
    @patch("backend.services.olympus.guardian.Heartbeat")
    @patch("backend.services.olympus.guardian.Pulse")
    @patch("backend.services.olympus.guardian.InsightsCollector")
    async def test_initialize_wires_components(
        self,
        mock_insights_cls: MagicMock,
        mock_pulse_cls: MagicMock,
        mock_hb_cls: MagicMock,
        mock_rules_cls: MagicMock,
        guardian,
    ) -> None:
        mock_rules = MagicMock()
        mock_rules.load_rules = AsyncMock()
        mock_rules.rules = {"rule_1": MagicMock()}
        mock_rules_cls.return_value = mock_rules

        mock_hb = MagicMock()
        mock_hb.on_alert = MagicMock()
        mock_hb_cls.return_value = mock_hb

        mock_pulse_cls.return_value = MagicMock()

        mock_insights = MagicMock()
        mock_insights.set_alert_callback = MagicMock()
        mock_insights_cls.return_value = mock_insights

        await guardian.initialize()

        assert guardian.rules_engine is not None
        assert guardian.heartbeat is not None
        assert guardian.pulse is not None
        assert guardian.insights is not None
        mock_rules.load_rules.assert_awaited_once()
        mock_hb.on_alert.assert_called_once()
        mock_insights.set_alert_callback.assert_called_once()


# ---------------------------------------------------------------------------
# run_heartbeat_once
# ---------------------------------------------------------------------------

class TestRunHeartbeatOnce:
    @pytest.mark.asyncio
    async def test_calls_heartbeat_methods(self, guardian) -> None:
        hb = AsyncMock()
        snapshot = MagicMock()
        hb.collect_metrics = AsyncMock(return_value=snapshot)
        hb.check_alerts = AsyncMock()
        hb.persist = AsyncMock()
        guardian.heartbeat = hb

        await guardian.run_heartbeat_once()

        hb.collect_metrics.assert_awaited_once()
        hb.check_alerts.assert_awaited_once_with(snapshot)
        hb.persist.assert_awaited_once_with(snapshot)


# ---------------------------------------------------------------------------
# run_pulse_once
# ---------------------------------------------------------------------------

class TestRunPulseOnce:
    @pytest.mark.asyncio
    async def test_basic_pulse(self, guardian, pool) -> None:
        action = _make_action(outcome="success", rule_applied="vacuum_threshold")

        mock_pulse = AsyncMock()
        mock_pulse.run_full_pulse = AsyncMock(return_value=[action])
        guardian.pulse = mock_pulse

        mock_rules = MagicMock()
        mock_rules.record_applied = AsyncMock()
        mock_rules.lower_confidence = AsyncMock()
        guardian.rules_engine = mock_rules

        guardian.insights = None

        mock_alerts = AsyncMock()
        mock_alerts.send_pulse_summary = AsyncMock()
        guardian.alerts = mock_alerts

        actions = await guardian.run_pulse_once()

        assert len(actions) == 1
        mock_rules.record_applied.assert_awaited_once_with("vacuum_threshold")
        mock_rules.lower_confidence.assert_not_awaited()
        mock_alerts.send_pulse_summary.assert_awaited_once_with(1, 0)

    @pytest.mark.asyncio
    async def test_failure_lowers_confidence(self, guardian, pool) -> None:
        action = _make_action(outcome="failure", rule_applied="bloat_threshold")

        mock_pulse = AsyncMock()
        mock_pulse.run_full_pulse = AsyncMock(return_value=[action])
        guardian.pulse = mock_pulse

        mock_rules = MagicMock()
        mock_rules.record_applied = AsyncMock()
        mock_rules.lower_confidence = AsyncMock()
        guardian.rules_engine = mock_rules
        guardian.insights = None

        guardian.alerts = AsyncMock()
        guardian.alerts.send_pulse_summary = AsyncMock()

        actions = await guardian.run_pulse_once()

        mock_rules.lower_confidence.assert_awaited_once_with("bloat_threshold")
        mock_rules.record_applied.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_insights_collected(self, guardian, pool) -> None:
        mock_pulse = AsyncMock()
        mock_pulse.run_full_pulse = AsyncMock(return_value=[])
        guardian.pulse = mock_pulse

        mock_rules = MagicMock()
        mock_rules.record_applied = AsyncMock()
        mock_rules.lower_confidence = AsyncMock()
        guardian.rules_engine = mock_rules

        insight_action = _make_action(outcome="success")
        mock_insights = AsyncMock()
        mock_insights.collect_query_insights = AsyncMock(return_value=[insight_action])
        mock_insights.collect_bloat_insights = AsyncMock(return_value=[])
        guardian.insights = mock_insights

        guardian.alerts = AsyncMock()
        guardian.alerts.send_pulse_summary = AsyncMock()

        actions = await guardian.run_pulse_once()
        assert len(actions) == 1
        mock_insights.collect_query_insights.assert_awaited_once()
        mock_insights.collect_bloat_insights.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insights_error_does_not_crash(self, guardian, pool) -> None:
        mock_pulse = AsyncMock()
        mock_pulse.run_full_pulse = AsyncMock(return_value=[])
        guardian.pulse = mock_pulse

        mock_rules = MagicMock()
        mock_rules.record_applied = AsyncMock()
        mock_rules.lower_confidence = AsyncMock()
        guardian.rules_engine = mock_rules

        mock_insights = AsyncMock()
        mock_insights.collect_query_insights = AsyncMock(side_effect=RuntimeError("boom"))
        guardian.insights = mock_insights

        guardian.alerts = AsyncMock()
        guardian.alerts.send_pulse_summary = AsyncMock()

        # Should not raise
        actions = await guardian.run_pulse_once()
        assert actions == []


# ---------------------------------------------------------------------------
# _persist_action
# ---------------------------------------------------------------------------

class TestPersistAction:
    @pytest.mark.asyncio
    async def test_inserts_action(self, guardian, pool) -> None:
        action = _make_action()
        await guardian._persist_action(action)
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_awaited_once()
        # Verify the JSON serialization of detail
        call_args = conn.execute.call_args[0]
        assert '"{}' not in call_args[0]  # It's a parameterized query

    @pytest.mark.asyncio
    async def test_persist_error_logged_not_raised(self, guardian, pool) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute.side_effect = RuntimeError("DB error")
        action = _make_action()
        # Should not raise
        await guardian._persist_action(action)


# ---------------------------------------------------------------------------
# _check_v4_readiness
# ---------------------------------------------------------------------------

class TestCheckV4Readiness:
    @pytest.mark.asyncio
    async def test_below_threshold(self, guardian, pool) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetchval.return_value = 100
        # Should not raise, just log nothing special
        await guardian._check_v4_readiness()

    @pytest.mark.asyncio
    async def test_above_threshold(self, guardian, pool) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetchval.return_value = 600
        # Should log v4 readiness (no assertion needed, just no crash)
        await guardian._check_v4_readiness()

    @pytest.mark.asyncio
    async def test_db_error_swallowed(self, guardian, pool) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetchval.side_effect = RuntimeError("DB down")
        await guardian._check_v4_readiness()  # Should not raise


# ---------------------------------------------------------------------------
# get_health_summary
# ---------------------------------------------------------------------------

class TestGetHealthSummary:
    @pytest.mark.asyncio
    async def test_returns_alive_status(self, guardian, pool) -> None:
        summary = await guardian.get_health_summary()
        assert summary["status"] == "alive"
        assert summary["running"] is False
        assert summary["rules_count"] == 0

    @pytest.mark.asyncio
    async def test_with_heartbeat_data(self, guardian, pool) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        hb_row = MagicMock()
        hb_row.__iter__ = MagicMock(return_value=iter([("col", "val")]))
        hb_row.items = MagicMock(return_value=[("col", "val")])
        conn.fetchrow.return_value = {"recorded_at": "2026-01-01", "pool_size": 10}
        conn.fetch.return_value = []

        summary = await guardian.get_health_summary()
        assert summary["last_heartbeat"] is not None

    @pytest.mark.asyncio
    async def test_db_error_handled(self, guardian, pool) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow.side_effect = RuntimeError("DB error")
        summary = await guardian.get_health_summary()
        assert summary["status"] == "alive"
        assert summary["last_heartbeat"] is None


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------

class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_sets_running(self, guardian) -> None:
        guardian.heartbeat = AsyncMock()
        guardian.pulse = AsyncMock()
        guardian.rules_engine = MagicMock()

        # Patch the loops to avoid infinite looping
        with patch.object(guardian, "_heartbeat_loop", new_callable=AsyncMock):
            with patch.object(guardian, "_pulse_loop", new_callable=AsyncMock):
                await guardian.start()
                assert guardian._running is True
                assert len(guardian._tasks) == 2

                await guardian.stop()
                assert guardian._running is False
                assert guardian._tasks == []


# ---------------------------------------------------------------------------
# interval helpers
# ---------------------------------------------------------------------------

class TestIntervalHelpers:
    def test_heartbeat_interval_default(self, guardian) -> None:
        guardian.rules_engine = None
        assert guardian._get_heartbeat_interval() == 300

    def test_heartbeat_interval_from_rules(self, guardian) -> None:
        mock_rules = MagicMock()
        mock_rules.get_threshold.return_value = 120
        guardian.rules_engine = mock_rules
        assert guardian._get_heartbeat_interval() == 120

    def test_pulse_interval_default(self, guardian) -> None:
        guardian.rules_engine = None
        assert guardian._get_pulse_interval_hours() == 6

    def test_pulse_interval_from_rules(self, guardian) -> None:
        mock_rules = MagicMock()
        mock_rules.get_threshold.return_value = 12
        guardian.rules_engine = mock_rules
        assert guardian._get_pulse_interval_hours() == 12
