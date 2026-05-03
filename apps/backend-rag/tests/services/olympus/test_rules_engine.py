"""Tests for RulesEngine — load, apply, and evolve operational rules."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.olympus.models import OlympusRule
from backend.services.olympus.rules_engine import RulesEngine


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


def _fake_row(
    *,
    id: int = 1,
    rule_name: str = "vacuum_dead_pct_threshold",
    category: str = "threshold",
    config: dict | None = None,
    source: str = "initial",
    confidence: float = 1.0,
    applied_count: int = 0,
    last_applied: datetime | None = None,
    superseded_by: int | None = None,
) -> dict:
    """Simulate an asyncpg Record as a dict-like object."""
    cfg = config or {"value": 5}
    row = {
        "id": id,
        "rule_name": rule_name,
        "category": category,
        "config": cfg,  # asyncpg decodes JSONB to Python dicts
        "source": source,
        "confidence": confidence,
        "applied_count": applied_count,
        "last_applied": last_applied,
        "superseded_by": superseded_by,
    }
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadRules:
    """load_rules should populate self.rules from DB rows."""

    @pytest.mark.asyncio
    async def test_load_rules_populates_dict(self) -> None:
        rows = [
            _fake_row(id=1, rule_name="vacuum_dead_pct_threshold", config={"value": 5}),
            _fake_row(id=2, rule_name="audit_retention_days", config={"value": 90}),
        ]
        mock_pool, mock_conn = _make_pool()
        mock_conn.fetch = AsyncMock(return_value=rows)

        engine = RulesEngine(mock_pool)
        await engine.load_rules()

        assert len(engine.rules) == 2
        assert "vacuum_dead_pct_threshold" in engine.rules
        assert "audit_retention_days" in engine.rules

    @pytest.mark.asyncio
    async def test_load_rules_parses_config(self) -> None:
        rows = [_fake_row(id=1, rule_name="heartbeat_interval_seconds", config={"value": 60})]
        mock_pool, mock_conn = _make_pool()
        mock_conn.fetch = AsyncMock(return_value=rows)

        engine = RulesEngine(mock_pool)
        await engine.load_rules()

        rule = engine.rules["heartbeat_interval_seconds"]
        assert rule.config == {"value": 60}
        assert rule.get_value() == 60

    @pytest.mark.asyncio
    async def test_load_rules_empty_table(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.fetch = AsyncMock(return_value=[])

        engine = RulesEngine(mock_pool)
        await engine.load_rules()

        assert engine.rules == {}


class TestGetThreshold:
    """get_threshold should return rule value or default."""

    def test_returns_value_for_existing_rule(self) -> None:
        mock_pool, _ = _make_pool()
        engine = RulesEngine(mock_pool)
        engine.rules["vacuum_dead_pct_threshold"] = OlympusRule(
            id=1,
            rule_name="vacuum_dead_pct_threshold",
            category="threshold",
            config={"value": 5},
            source="initial",
        )

        assert engine.get_threshold("vacuum_dead_pct_threshold") == 5

    def test_returns_default_for_missing_rule(self) -> None:
        mock_pool, _ = _make_pool()
        engine = RulesEngine(mock_pool)

        assert engine.get_threshold("nonexistent_rule") is None
        assert engine.get_threshold("nonexistent_rule", default=42) == 42

    def test_returns_none_when_config_key_missing(self) -> None:
        mock_pool, _ = _make_pool()
        engine = RulesEngine(mock_pool)
        engine.rules["odd_config"] = OlympusRule(
            id=99,
            rule_name="odd_config",
            category="policy",
            config={"other_key": "data"},
            source="manual",
        )

        assert engine.get_threshold("odd_config") is None


class TestRecordApplied:
    """record_applied should UPDATE the DB and bump in-memory counters."""

    @pytest.mark.asyncio
    async def test_calls_update_sql(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()

        engine = RulesEngine(mock_pool)
        engine.rules["vacuum_dead_pct_threshold"] = OlympusRule(
            id=1,
            rule_name="vacuum_dead_pct_threshold",
            category="threshold",
            config={"value": 5},
            source="initial",
            applied_count=3,
        )

        await engine.record_applied("vacuum_dead_pct_threshold")

        mock_conn.execute.assert_awaited_once()
        args = mock_conn.execute.call_args
        sql = args[0][0]
        assert "UPDATE olympus_rules" in sql
        assert "applied_count = applied_count + 1" in sql
        assert args[0][2] == "vacuum_dead_pct_threshold"

    @pytest.mark.asyncio
    async def test_bumps_in_memory_count(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()

        engine = RulesEngine(mock_pool)
        engine.rules["vacuum_dead_pct_threshold"] = OlympusRule(
            id=1,
            rule_name="vacuum_dead_pct_threshold",
            category="threshold",
            config={"value": 5},
            source="initial",
            applied_count=0,
        )

        await engine.record_applied("vacuum_dead_pct_threshold")

        rule = engine.rules["vacuum_dead_pct_threshold"]
        assert rule.applied_count == 1
        assert rule.last_applied is not None


class TestLowerConfidence:
    """lower_confidence should clamp to 0.0, update DB and memory."""

    @pytest.mark.asyncio
    async def test_decreases_confidence(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()

        engine = RulesEngine(mock_pool)
        engine.rules["test_rule"] = OlympusRule(
            id=1,
            rule_name="test_rule",
            category="threshold",
            config={"value": 10},
            source="initial",
            confidence=0.8,
        )

        await engine.lower_confidence("test_rule", delta=-0.3)

        assert engine.rules["test_rule"].confidence == pytest.approx(0.5)
        mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clamps_to_zero(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()

        engine = RulesEngine(mock_pool)
        engine.rules["fragile_rule"] = OlympusRule(
            id=2,
            rule_name="fragile_rule",
            category="policy",
            config={"value": True},
            source="initial",
            confidence=0.05,
        )

        await engine.lower_confidence("fragile_rule", delta=-0.2)

        assert engine.rules["fragile_rule"].confidence == 0.0

    @pytest.mark.asyncio
    async def test_noop_for_missing_rule(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()

        engine = RulesEngine(mock_pool)
        await engine.lower_confidence("ghost_rule")

        mock_conn.execute.assert_not_awaited()
