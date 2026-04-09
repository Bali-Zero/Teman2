"""Tests for Olympus v2 models."""
import pytest
from backend.services.olympus.models import HeartbeatSnapshot, PulseAction, OlympusRule


class TestHeartbeatSnapshot:
    def test_pool_utilization_computed(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=3, active_connections=5,
            max_connections=100, db_size_bytes=1000,
        )
        assert s.pool_utilization == 0.7

    def test_pool_utilization_zero_pool(self):
        s = HeartbeatSnapshot(
            pool_size=0, pool_idle=0, active_connections=0,
            max_connections=100, db_size_bytes=0,
        )
        assert s.pool_utilization == 0.0

    def test_defaults(self):
        s = HeartbeatSnapshot(
            pool_size=5, pool_idle=5, active_connections=0,
            max_connections=100, db_size_bytes=0,
        )
        assert s.long_queries == 0
        assert s.lock_waits == 0
        assert s.alerts_sent == 0
        assert s.bloat_top3 == []


class TestPulseAction:
    def test_outcome_values_match_db_constraint(self):
        for outcome in ("success", "failure", "skipped", "proposed"):
            a = PulseAction(action_type="test", outcome=outcome)
            assert a.outcome == outcome

    def test_defaults(self):
        a = PulseAction(action_type="vacuum")
        assert a.rhythm == "pulse"
        assert a.target is None
        assert a.outcome is None
        assert a.detail == {}


class TestOlympusRule:
    def test_config_parsed_from_json_string(self):
        r = OlympusRule(
            id=1, rule_name="test", category="threshold",
            config='{"value": 10, "unit": "percent"}', source="seed",
        )
        assert r.config == {"value": 10, "unit": "percent"}
        assert r.get_value() == 10

    def test_config_accepts_dict(self):
        r = OlympusRule(
            id=1, rule_name="test", category="threshold",
            config={"value": 42}, source="seed",
        )
        assert r.get_value() == 42

    def test_defaults(self):
        r = OlympusRule(
            id=1, rule_name="test", category="threshold",
            config={"value": 1}, source="seed",
        )
        assert r.confidence == 1.0
        assert r.applied_count == 0
        assert r.last_applied is None
        assert r.superseded_by is None
