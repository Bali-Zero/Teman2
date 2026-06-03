"""Tests for the Olympus Safety Envelope (P0) + Consume (P1) — 2026-06-04.

Covers M1 timeouts, M3 pulse budget, M5 self-retention, M6 insight dedup,
M2 circuit breaker, M4 granular kill-switch. Mock-pool style mirrors
test_pulse.py (no live DB).
"""

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.services.olympus.guardian import OlympusGuardian
from backend.services.olympus.insights import InsightsCollector
from backend.services.olympus.models import InsightRecord
from backend.services.olympus.pulse import Pulse
from backend.services.olympus.safety import PulseBudget, action_timeouts


def _mock_pool_conn():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


# --------------------------------------------------------------------------- #
# M1 — action_timeouts
# --------------------------------------------------------------------------- #
class TestActionTimeouts:
    @pytest.mark.asyncio
    async def test_sets_statement_and_lock_timeout(self):
        pool, conn = _mock_pool_conn()
        async with action_timeouts(pool, 300, 5) as c:
            assert c is conn
        executed = [call.args[0] for call in conn.execute.call_args_list]
        assert "SET statement_timeout = '300s'" in executed
        assert "SET lock_timeout = '5s'" in executed

    @pytest.mark.asyncio
    async def test_negative_values_clamped_to_zero(self):
        pool, conn = _mock_pool_conn()
        async with action_timeouts(pool, -10, -1):
            pass
        executed = [call.args[0] for call in conn.execute.call_args_list]
        assert "SET statement_timeout = '0s'" in executed
        assert "SET lock_timeout = '0s'" in executed


# --------------------------------------------------------------------------- #
# M3 — PulseBudget
# --------------------------------------------------------------------------- #
class TestPulseBudget:
    def test_trips_on_action_count(self):
        b = PulseBudget(max_actions=3, max_runtime_s=600)
        assert not b.exceeded()
        b.record(3)
        assert b.exceeded()
        assert "max_actions_per_pulse" in b.reason()

    def test_count_accumulates(self):
        b = PulseBudget(50, 600)
        b.record(2)
        b.record(5)
        assert b.count == 7

    def test_floor_guards(self):
        # zero/negative config must not produce an always-tripped budget
        b = PulseBudget(0, 0)
        assert b.max_actions >= 1
        assert b.max_runtime_s >= 1.0


class TestRunFullPulseBudget:
    @pytest.mark.asyncio
    async def test_budget_trips_and_emits_budget_exceeded(self):
        rules = MagicMock()
        rules.get_threshold = MagicMock(
            side_effect=lambda name, default=None: {
                "max_actions_per_pulse": 1,
                "max_pulse_runtime_s": 600,
            }.get(name, default)
        )
        pool, _ = _mock_pool_conn()
        pulse = Pulse(pool, rules)

        # First group returns 2 actions → budget (max 1) trips before group 2.
        from backend.services.olympus.models import PulseAction

        pulse.vacuum_bloated_tables = AsyncMock(
            return_value=[
                PulseAction(action_type="vacuum", target="t1", outcome="success"),
                PulseAction(action_type="vacuum", target="t2", outcome="success"),
            ]
        )
        # remaining groups should NOT be called once budget trips
        pulse.cleanup_audit_trail = AsyncMock()
        pulse.repair_sequences = AsyncMock()
        pulse.rebuild_invalid_indexes = AsyncMock()
        pulse.refresh_materialized_views = AsyncMock()
        pulse.cleanup_expired_sessions = AsyncMock()
        pulse.ensure_next_partition = AsyncMock()
        pulse.cleanup_olympus_self = AsyncMock()
        pulse.autovacuum_advisor = AsyncMock()

        actions = await pulse.run_full_pulse()

        assert any(a.action_type == "budget_exceeded" for a in actions)
        pulse.cleanup_audit_trail.assert_not_called()
        pulse.autovacuum_advisor.assert_not_called()


# --------------------------------------------------------------------------- #
# M5 — cleanup_olympus_self
# --------------------------------------------------------------------------- #
class TestCleanupOlympusSelf:
    @pytest.mark.asyncio
    async def test_emits_valid_outcomes_for_three_targets(self):
        rules = MagicMock()
        rules.get_threshold = MagicMock(
            side_effect=lambda name, default=None: {
                "olympus_hb_retention_months": 6,
                "olympus_actions_retention_days": 90,
                "olympus_insights_retention_days": 90,
            }.get(name, default)
        )
        pool, conn = _mock_pool_conn()
        conn.fetch = AsyncMock(return_value=[])  # no old partitions
        conn.execute = AsyncMock(return_value="DELETE 5")
        pulse = Pulse(pool, rules)

        actions = await pulse.cleanup_olympus_self()
        targets = {a.target for a in actions}
        assert "olympus_heartbeats" in targets
        assert "olympus_actions" in targets
        assert "olympus_insights" in targets
        for a in actions:
            assert a.outcome in {"success", "failure", "skipped", "proposed"}


# --------------------------------------------------------------------------- #
# M6 — insight dedup / supersede
# --------------------------------------------------------------------------- #
class TestInsightDedup:
    @pytest.mark.asyncio
    async def test_same_evidence_touches_not_inserts(self):
        rules = MagicMock()
        pool, conn = _mock_pool_conn()
        # existing active row with IDENTICAL evidence
        conn.fetchrow = AsyncMock(
            return_value={"id": 1, "evidence": {"index": "idx_a", "size_bytes": 100}}
        )
        coll = InsightsCollector(pool, rules)
        rec = InsightRecord(
            insight_type="recommendation",
            title="Unused index: idx_a",
            content="...",
            evidence={"index": "idx_a", "size_bytes": 100},
            source="bloat_intelligence",
        )
        await coll._persist_insight(rec)
        # must UPDATE accessed_count, never INSERT a new row
        executed = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        assert "UPDATE olympus_insights" in executed
        assert "accessed_count = accessed_count + 1" in executed
        conn.fetchval.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_evidence_inserts_and_supersedes(self):
        rules = MagicMock()
        pool, conn = _mock_pool_conn()
        conn.fetchrow = AsyncMock(
            return_value={"id": 1, "evidence": {"index": "idx_a", "size_bytes": 100}}
        )
        conn.fetchval = AsyncMock(return_value=2)  # new id
        coll = InsightsCollector(pool, rules)
        rec = InsightRecord(
            insight_type="recommendation",
            title="Unused index: idx_a",
            content="...",
            evidence={"index": "idx_a", "size_bytes": 999},  # CHANGED
            source="bloat_intelligence",
        )
        await coll._persist_insight(rec)
        conn.fetchval.assert_called()  # new INSERT ... RETURNING id
        executed = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        assert "superseded_by = $1" in executed

    @pytest.mark.asyncio
    async def test_no_existing_plain_insert(self):
        rules = MagicMock()
        pool, conn = _mock_pool_conn()
        conn.fetchrow = AsyncMock(return_value=None)  # nothing active
        conn.fetchval = AsyncMock(return_value=7)
        coll = InsightsCollector(pool, rules)
        rec = InsightRecord(
            insight_type="recommendation",
            title="Missing index: clients",
            content="...",
            evidence={"table": "clients"},
            source="bloat_intelligence",
        )
        await coll._persist_insight(rec)
        conn.fetchval.assert_called_once()


# --------------------------------------------------------------------------- #
# M2 / M4 — circuit breaker + kill-switch on the guardian
# --------------------------------------------------------------------------- #
class TestGuardianSafety:
    def _guardian(self, flags: dict):
        pool, _ = _mock_pool_conn()
        g = OlympusGuardian(db_pool=pool, alert_service=None)
        g.rules_engine = MagicMock()
        g.rules_engine.get_threshold = MagicMock(
            side_effect=lambda name, default=None: flags.get(name, default)
        )
        return g

    def test_master_kill_switch_disables_all(self):
        g = self._guardian({"olympus_enabled": False})
        assert g._flag_enabled("olympus_pulse_enabled") is False
        assert g._flag_enabled("olympus_heartbeat_enabled") is False

    def test_granular_pulse_flag(self):
        g = self._guardian({"olympus_enabled": True, "olympus_pulse_enabled": False})
        assert g._flag_enabled("olympus_pulse_enabled") is False
        assert g._flag_enabled("olympus_heartbeat_enabled") is True

    def test_default_enabled(self):
        g = self._guardian({})
        assert g._flag_enabled("olympus_pulse_enabled") is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_pool_fatal(self):
        g = self._guardian({})

        async def boom():
            raise asyncpg.InterfaceError("connection lost")

        # threshold=3 → 3 fatal errors open the breaker
        for _ in range(3):
            await g._run_cycle_guarded("pulse", boom)
        assert g._breaker.is_open()

    @pytest.mark.asyncio
    async def test_non_fatal_error_does_not_open_breaker(self):
        g = self._guardian({})

        async def value_error():
            raise ValueError("a bad vacuum, not a pool problem")

        for _ in range(5):
            await g._run_cycle_guarded("pulse", value_error)
        assert not g._breaker.is_open()
