"""Tests for Olympus v2 Guardian — feedback loop and shutdown."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.olympus.guardian import OlympusGuardian
from backend.services.olympus.models import PulseAction


class TestGuardianFeedbackLoop:
    @pytest.mark.asyncio
    async def test_pulse_records_applied_rules(self):
        """record_applied is called for every action with a rule_applied."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
            PulseAction(action_type="vacuum", target="t2", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
            PulseAction(action_type="cleanup", target="t3", outcome="success", rule_applied="audit_retention_days"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        actions = await guardian.run_pulse_once()

        assert guardian.rules_engine.record_applied.call_count == 2
        called_rules = {c.args[0] for c in guardian.rules_engine.record_applied.call_args_list}
        assert called_rules == {"vacuum_dead_pct_threshold", "audit_retention_days"}

    @pytest.mark.asyncio
    async def test_pulse_lowers_confidence_on_failure(self):
        """MISS-2 fix: lower_confidence called when action fails."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="failure", rule_applied="vacuum_dead_pct_threshold"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        await guardian.run_pulse_once()

        guardian.rules_engine.lower_confidence.assert_called_once_with("vacuum_dead_pct_threshold")

    @pytest.mark.asyncio
    async def test_pulse_no_lower_confidence_on_success(self):
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        await guardian.run_pulse_once()

        guardian.rules_engine.lower_confidence.assert_not_called()

    @pytest.mark.asyncio
    async def test_pulse_summary_counts_failures_correctly(self):
        """BUG-4 fix: count 'failure' not 'error'."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="a", outcome="success"),
            PulseAction(action_type="b", outcome="failure"),
            PulseAction(action_type="c", outcome="failure"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        await guardian.run_pulse_once()

        guardian.alerts.send_pulse_summary.assert_called_once_with(3, 2)


class TestGuardianV3Insights:
    @pytest.mark.asyncio
    async def test_pulse_runs_insights(self):
        """v3: pulse runs InsightsCollector and persists actions."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
        ])
        guardian.insights = MagicMock()
        guardian.insights.collect_query_insights = AsyncMock(return_value=[
            PulseAction(action_type="query_intelligence", target="pg_stat_statements", outcome="success"),
        ])
        guardian.insights.collect_bloat_insights = AsyncMock(return_value=[
            PulseAction(action_type="unused_index", target="idx_old", outcome="proposed"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        actions = await guardian.run_pulse_once()

        assert len(actions) == 3
        guardian.insights.collect_query_insights.assert_called_once()
        guardian.insights.collect_bloat_insights.assert_called_once()
        assert guardian._persist_action.call_count == 3
