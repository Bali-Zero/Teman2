"""Tests for Olympus v3 models."""
import pytest
from backend.services.olympus.models import HeartbeatSnapshot, PulseAction, OlympusRule, InsightRecord


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


class TestInsightRecord:
    def test_defaults(self):
        r = InsightRecord(
            insight_type="pattern",
            title="Top query",
            content="SELECT * FROM clients",
            evidence={"total_ms": 1234},
            source="query_intelligence",
        )
        assert r.confidence == 1.0
        assert r.applicable_to == []

    def test_all_types_accepted(self):
        for t in ("pattern", "anomaly", "recommendation"):
            r = InsightRecord(
                insight_type=t, title="t", content="c",
                evidence={}, source="test",
            )
            assert r.insight_type == t


class TestHeartbeatSnapshotV3:
    def test_v3_fields_default_none(self):
        s = HeartbeatSnapshot(
            pool_size=5, pool_idle=3, active_connections=2,
            max_connections=100, db_size_bytes=1000,
        )
        assert s.cache_hit_ratio is None
        assert s.top_tables_by_size == []
        assert s.idx_scan_ratio is None
        assert s.health_score is None

    def test_health_score_perfect(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
            cache_hit_ratio=99.0, idx_scan_ratio=95.0,
        )
        score = s.compute_health_score(dead_tuple_ratio=0.5)
        assert score == 100

    def test_health_score_degraded(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=1, active_connections=8,
            max_connections=100, db_size_bytes=1000,
            long_queries=3, lock_waits=1,
            cache_hit_ratio=85.0, idx_scan_ratio=40.0,
        )
        score = s.compute_health_score(dead_tuple_ratio=10.0)
        assert 0 <= score <= 100
        assert score < 60  # degraded (formula: cache 22 + pool 4 + dead 12 + idx 7 + lq 4 + lw 5 = ~55)

    def test_health_score_zero_floor(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=0, active_connections=10,
            max_connections=10, db_size_bytes=1000,
            long_queries=20, lock_waits=10,
            cache_hit_ratio=50.0, idx_scan_ratio=10.0,
        )
        score = s.compute_health_score(dead_tuple_ratio=50.0)
        assert score >= 0
