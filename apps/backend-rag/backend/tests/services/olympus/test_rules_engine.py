"""Tests for Olympus v2 RulesEngine."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.olympus.rules_engine import RulesEngine
from backend.services.olympus.models import OlympusRule


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
            "id": 1, "rule_name": "vacuum_dead_pct_threshold",
            "category": "threshold", "config": '{"value": 10, "unit": "percent"}',
            "source": "initial", "confidence": 1.0, "applied_count": 0,
            "last_applied": None, "superseded_by": None,
        },
        {
            "id": 2, "rule_name": "audit_retention_days",
            "category": "policy", "config": '{"value": 90}',
            "source": "initial", "confidence": 0.8, "applied_count": 5,
            "last_applied": None, "superseded_by": None,
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
