"""Tests for Olympus v2 RulesEngine."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.olympus.rules_engine import RulesEngine


def _make_pool(conn):
    """Return a pool mock where acquire() is a sync call returning an async CM."""
    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


@pytest.fixture
def sample_rules_rows():
    return [
        {
            "id": 1,
            "rule_name": "vacuum_dead_pct_threshold",
            "category": "threshold",
            "config": '{"value": 10, "unit": "percent"}',
            "source": "initial",
            "confidence": 1.0,
            "applied_count": 0,
            "last_applied": None,
            "superseded_by": None,
        },
        {
            "id": 2,
            "rule_name": "audit_retention_days",
            "category": "policy",
            "config": '{"value": 90}',
            "source": "initial",
            "confidence": 0.8,
            "applied_count": 5,
            "last_applied": None,
            "superseded_by": None,
        },
    ]


class TestRulesEngine:
    @pytest.mark.asyncio
    async def test_load_rules(self, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        pool = _make_pool(conn)

        engine = RulesEngine(pool)
        await engine.load_rules()

        assert len(engine.rules) == 2
        assert "vacuum_dead_pct_threshold" in engine.rules
        assert engine.rules["vacuum_dead_pct_threshold"].config["value"] == 10

    @pytest.mark.asyncio
    async def test_get_threshold_exists(self, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        pool = _make_pool(conn)

        engine = RulesEngine(pool)
        await engine.load_rules()

        assert engine.get_threshold("vacuum_dead_pct_threshold") == 10

    def test_get_threshold_missing_returns_default(self):
        pool = MagicMock()
        engine = RulesEngine(pool)
        assert engine.get_threshold("nonexistent", default=42) == 42

    @pytest.mark.asyncio
    async def test_record_applied_increments(self, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        conn.execute = AsyncMock()
        pool = _make_pool(conn)

        engine = RulesEngine(pool)
        await engine.load_rules()

        old_count = engine.rules["vacuum_dead_pct_threshold"].applied_count
        await engine.record_applied("vacuum_dead_pct_threshold")
        assert engine.rules["vacuum_dead_pct_threshold"].applied_count == old_count + 1

    @pytest.mark.asyncio
    async def test_lower_confidence_clamps_to_zero(self, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        conn.execute = AsyncMock()
        pool = _make_pool(conn)

        engine = RulesEngine(pool)
        await engine.load_rules()

        await engine.lower_confidence("vacuum_dead_pct_threshold", delta=-5.0)
        assert engine.rules["vacuum_dead_pct_threshold"].confidence == 0.0

    @pytest.mark.asyncio
    async def test_lower_confidence_missing_rule_noop(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()
        pool = _make_pool(conn)

        engine = RulesEngine(pool)
        await engine.lower_confidence("nonexistent")
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_supersede_learned_rule_updates_and_audits(self):
        old_rule = {
            "id": 10,
            "rule_name": "learned_vacuum_dead_pct_threshold_v1",
            "category": "threshold",
            "config": '{"value": 10, "unit": "percent"}',
            "source": "learned",
            "confidence": 0.1,
            "superseded_by": None,
        }
        new_rule = {
            "id": 11,
            "rule_name": "learned_vacuum_dead_pct_threshold_v2",
            "category": "threshold",
            "config": '{"value": 5, "unit": "percent"}',
            "source": "learned",
            "confidence": 0.8,
            "superseded_by": None,
        }
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[old_rule, new_rule])
        conn.execute = AsyncMock(side_effect=["UPDATE 1", "INSERT 0 1"])
        pool = _make_pool(conn)

        engine = RulesEngine(pool)
        engine.rules[old_rule["rule_name"]] = MagicMock()

        result = await engine.supersede(old_rule["rule_name"], new_rule["id"], "better learned rule")

        assert result is True
        assert old_rule["rule_name"] not in engine.rules
        assert conn.execute.await_count == 2
        update_args = conn.execute.await_args_list[0].args
        audit_args = conn.execute.await_args_list[1].args
        assert update_args[1] == new_rule["id"]
        assert update_args[3] == old_rule["id"]
        assert audit_args[1] == "metacognition"
        assert audit_args[2] == "rule_superseded"
        assert audit_args[3] == old_rule["rule_name"]

    @pytest.mark.asyncio
    async def test_supersede_protects_initial_rule(self):
        old_rule = {
            "id": 10,
            "rule_name": "vacuum_dead_pct_threshold",
            "category": "threshold",
            "config": '{"value": 10, "unit": "percent"}',
            "source": "initial",
            "confidence": 0.1,
            "superseded_by": None,
        }
        new_rule = {
            "id": 11,
            "rule_name": "learned_vacuum_dead_pct_threshold_v2",
            "category": "threshold",
            "config": '{"value": 5, "unit": "percent"}',
            "source": "learned",
            "confidence": 0.8,
            "superseded_by": None,
        }
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[old_rule, new_rule])
        conn.execute = AsyncMock()
        pool = _make_pool(conn)

        engine = RulesEngine(pool)

        result = await engine.supersede(old_rule["rule_name"], new_rule["id"], "should not mutate base")

        assert result is False
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_propose_supersessions_shadow_writes_insight(self, monkeypatch):
        monkeypatch.delenv("OLYMPUS_RULE_SUPERSEDE_MODE", raising=False)
        now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
        old_rule = {
            "id": 10,
            "rule_name": "learned_vacuum_dead_pct_threshold_v1",
            "category": "threshold",
            "config": '{"value": 10, "unit": "percent"}',
            "source": "learned",
            "confidence": 0.1,
            "created_at": now - timedelta(days=2),
            "superseded_by": None,
        }
        new_rule = {
            "id": 11,
            "rule_name": "learned_vacuum_dead_pct_threshold_v2",
            "category": "threshold",
            "config": '{"value": 5, "unit": "percent"}',
            "source": "learned",
            "confidence": 0.8,
            "created_at": now - timedelta(days=1),
            "superseded_by": None,
        }
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[old_rule, new_rule])
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        pool = _make_pool(conn)

        engine = RulesEngine(pool)

        proposals = await engine.propose_supersessions(confidence_floor=0.2)

        assert len(proposals) == 1
        assert proposals[0]["mode"] == "shadow"
        assert proposals[0]["old_rule_name"] == old_rule["rule_name"]
        assert proposals[0]["new_rule_name"] == new_rule["rule_name"]
        conn.execute.assert_awaited_once()
        assert conn.execute.call_args.args[1] == "recommendation"
        assert conn.execute.call_args.args[5] == "rules_engine"

    @pytest.mark.asyncio
    async def test_propose_supersessions_enforce_supersedes(self, monkeypatch):
        monkeypatch.setenv("OLYMPUS_RULE_SUPERSEDE_MODE", "enforce")
        now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
        old_rule = {
            "id": 10,
            "rule_name": "learned_vacuum_dead_pct_threshold_v1",
            "category": "threshold",
            "config": '{"value": 10, "unit": "percent"}',
            "source": "learned",
            "confidence": 0.1,
            "created_at": now - timedelta(days=2),
            "superseded_by": None,
        }
        new_rule = {
            "id": 11,
            "rule_name": "learned_vacuum_dead_pct_threshold_v2",
            "category": "threshold",
            "config": '{"value": 5, "unit": "percent"}',
            "source": "learned",
            "confidence": 0.8,
            "created_at": now - timedelta(days=1),
            "superseded_by": None,
        }
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[old_rule, new_rule])
        conn.fetchrow = AsyncMock(side_effect=[old_rule, new_rule])
        conn.execute = AsyncMock(side_effect=["UPDATE 1", "INSERT 0 1"])
        pool = _make_pool(conn)

        engine = RulesEngine(pool)

        proposals = await engine.propose_supersessions(confidence_floor=0.2)

        assert len(proposals) == 1
        assert proposals[0]["mode"] == "enforce"
        assert conn.execute.await_count == 2
