"""Tests for Olympus v2 Pulse — outcome values match DB CHECK constraint."""
import pytest
from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse
from unittest.mock import AsyncMock, MagicMock

VALID_OUTCOMES = {"success", "failure", "skipped", "proposed"}


class TestPulseOutcomes:
    def test_no_ok_or_error_in_code(self):
        """BUG-1 fix: pulse must never emit 'ok' or 'error' as outcome."""
        import inspect
        source = inspect.getsource(Pulse)
        assert 'outcome="ok"' not in source, "Found 'ok' outcome — must be 'success'"
        assert 'outcome="error"' not in source, "Found 'error' outcome — must be 'failure'"

    def test_all_outcomes_in_valid_set(self):
        """Every outcome literal in pulse.py must match the DB CHECK constraint."""
        import inspect, re
        source = inspect.getsource(Pulse)
        outcomes = re.findall(r'outcome="(\w+)"', source)
        for o in outcomes:
            assert o in VALID_OUTCOMES, f"Invalid outcome '{o}' — must be one of {VALID_OUTCOMES}"


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
        "vacuum_dead_pct_threshold": 5,
        "audit_retention_days": 90,
    }.get(name, default))
    return rules


class TestAutovacuumAdvisor:
    @pytest.mark.asyncio
    async def test_proposes_tuning_for_untuned_table(self, mock_rules):
        pool = MagicMock()
        conn = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx
        conn.fetch.return_value = [
            {"relname": "big_table", "reloptions": None,
             "n_dead_tup": 50000, "n_tup_upd": 10000, "n_tup_ins": 5000},
        ]
        pulse = Pulse(pool, mock_rules)
        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 1
        assert actions[0].outcome == "proposed"
        assert actions[0].action_type == "autovacuum_tuning"

    @pytest.mark.asyncio
    async def test_skips_already_tuned_table(self, mock_rules):
        pool = MagicMock()
        conn = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx
        conn.fetch.return_value = [
            {"relname": "tuned_table",
             "reloptions": ["autovacuum_vacuum_scale_factor=0.02"],
             "n_dead_tup": 50000, "n_tup_upd": 10000, "n_tup_ins": 5000},
        ]
        pulse = Pulse(pool, mock_rules)
        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 0

    @pytest.mark.asyncio
    async def test_skips_low_dead_tuples(self, mock_rules):
        pool = MagicMock()
        conn = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx
        conn.fetch.return_value = []
        pulse = Pulse(pool, mock_rules)
        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 0


class TestPartitionAwareCleanup:
    @pytest.mark.asyncio
    async def test_delete_when_not_partitioned(self, mock_rules):
        pool = MagicMock()
        conn = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx
        conn.fetchval.return_value = "r"
        conn.execute.return_value = "DELETE 42"
        pulse = Pulse(pool, mock_rules)
        action = await pulse.cleanup_audit_trail()
        assert action.outcome == "success"
        assert action.detail.get("method") == "delete"

    @pytest.mark.asyncio
    async def test_detach_drop_when_partitioned(self, mock_rules):
        pool = MagicMock()
        conn = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx
        conn.fetchval.return_value = "p"
        conn.fetch.return_value = [
            {"child_name": "api_audit_trail_2026_01"},
        ]
        pulse = Pulse(pool, mock_rules)
        action = await pulse.cleanup_audit_trail()
        assert action.outcome == "success"
        assert action.detail.get("method") == "detach_drop"
