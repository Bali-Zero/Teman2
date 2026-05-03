"""Tests for Olympus Pydantic models."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.services.olympus.models import (
    HeartbeatSnapshot,
    Insight,
    OlympusRule,
    PulseAction,
    Skill,
)


# ---------------------------------------------------------------------------
# HeartbeatSnapshot
# ---------------------------------------------------------------------------

class TestHeartbeatSnapshot:
    """HeartbeatSnapshot defaults and computed fields."""

    def test_defaults_and_recorded_at(self) -> None:
        snap = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=3,
            active_connections=7,
            max_connections=100,
            db_size_bytes=1_000_000,
        )
        assert snap.long_queries == 0
        assert snap.lock_waits == 0
        assert snap.alerts_sent == 0
        assert snap.bloat_top3 == []
        assert snap.recorded_at.tzinfo is not None

    def test_pool_utilization_computed(self) -> None:
        snap = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=3,
            active_connections=7,
            max_connections=100,
            db_size_bytes=500_000,
        )
        # 1 - 3/10 = 0.7
        assert snap.pool_utilization == 0.7

    def test_pool_utilization_zero_pool_size(self) -> None:
        snap = HeartbeatSnapshot(
            pool_size=0,
            pool_idle=0,
            active_connections=0,
            max_connections=100,
            db_size_bytes=0,
        )
        assert snap.pool_utilization == 0.0

    def test_pool_utilization_all_idle(self) -> None:
        snap = HeartbeatSnapshot(
            pool_size=5,
            pool_idle=5,
            active_connections=0,
            max_connections=100,
            db_size_bytes=100,
        )
        assert snap.pool_utilization == 0.0


# ---------------------------------------------------------------------------
# PulseAction
# ---------------------------------------------------------------------------

class TestPulseAction:
    """PulseAction creation with defaults."""

    def test_valid_creation_defaults(self) -> None:
        action = PulseAction(action_type="vacuum")
        assert action.rhythm == "pulse"
        assert action.action_type == "vacuum"
        assert action.target is None
        assert action.detail == {}
        assert action.outcome is None
        assert action.duration_ms is None
        assert action.rule_applied is None
        assert action.reflection is None
        assert action.executed_at.tzinfo is not None

    def test_full_creation(self) -> None:
        ts = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
        action = PulseAction(
            rhythm="maintenance",
            action_type="reindex",
            target="olympus_heartbeats",
            detail={"pages": 42},
            outcome="success",
            duration_ms=350,
            rule_applied="auto_reindex",
            reflection="table was 30% bloated",
            executed_at=ts,
        )
        assert action.rhythm == "maintenance"
        assert action.detail == {"pages": 42}
        assert action.executed_at == ts


# ---------------------------------------------------------------------------
# OlympusRule
# ---------------------------------------------------------------------------

class TestOlympusRule:
    """OlympusRule defaults and get_value."""

    def test_get_value_default_key(self) -> None:
        rule = OlympusRule(
            id=1,
            rule_name="pool_max",
            category="connection",
            config={"value": 20},
            source="seed",
        )
        assert rule.get_value() == 20

    def test_get_value_custom_key(self) -> None:
        rule = OlympusRule(
            id=2,
            rule_name="bloat_threshold",
            category="maintenance",
            config={"value": 40, "unit": "percent"},
            source="learned",
        )
        assert rule.get_value("unit") == "percent"

    def test_get_value_missing_key_returns_none(self) -> None:
        rule = OlympusRule(
            id=3,
            rule_name="noop",
            category="test",
            config={},
            source="manual",
        )
        assert rule.get_value() is None

    def test_defaults(self) -> None:
        rule = OlympusRule(
            id=4,
            rule_name="r",
            category="c",
            config={},
            source="s",
        )
        assert rule.confidence == 1.0
        assert rule.applied_count == 0
        assert rule.last_applied is None
        assert rule.superseded_by is None


# ---------------------------------------------------------------------------
# Insight
# ---------------------------------------------------------------------------

class TestInsight:
    """Insight creation and defaults."""

    def test_defaults(self) -> None:
        ins = Insight(
            insight_type="anomaly",
            title="Pool spike",
            content="Pool utilization hit 95%",
        )
        assert ins.evidence == {}
        assert ins.source == ""
        assert ins.confidence == 0.8
        assert ins.applicable_to == []


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------

class TestSkill:
    """Skill creation and defaults."""

    def test_defaults(self) -> None:
        skill = Skill(
            skill_name="vacuum_table",
            description="VACUUM ANALYZE on a target table",
            sql_template="VACUUM ANALYZE {table};",
        )
        assert skill.parameters == {}
        assert skill.preconditions == []
        assert skill.success_criteria is None
        assert skill.learned_from is None
