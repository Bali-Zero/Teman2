"""Unit tests for backend/services/olympus/pulse.py"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _AsyncCM:
    """Reusable async context manager that returns a fixed connection mock."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def mock_pool():
    """Mock asyncpg pool with context manager.

    pool.acquire() must return a *synchronous* object that implements
    ``__aenter__``/``__aexit__`` — NOT a coroutine.  Using ``AsyncMock``
    for acquire() would produce a coroutine, which breaks the
    ``async with pool.acquire() as conn:`` pattern used by asyncpg.
    """
    pool = MagicMock()
    conn = AsyncMock()

    pool.acquire.return_value = _AsyncCM(conn)

    return pool, conn


@pytest.fixture
def mock_rules():
    """Mock RulesEngine."""
    rules = MagicMock()
    rules.get_threshold.return_value = 5  # default for all thresholds
    return rules


@pytest.fixture
def pulse(mock_pool, mock_rules):
    pool, _ = mock_pool
    from backend.services.olympus.pulse import Pulse

    return Pulse(db_pool=pool, rules=mock_rules)


# ---------------------------------------------------------------------------
# vacuum_bloated_tables
# ---------------------------------------------------------------------------


class TestVacuumBloatedTables:
    @pytest.mark.asyncio
    async def test_no_dead_rows(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []

        actions = await pulse.vacuum_bloated_tables()
        assert actions == []

    @pytest.mark.asyncio
    async def test_below_threshold_skipped(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"relname": "clients", "n_live_tup": 1000, "n_dead_tup": 10, "dead_pct": 1.0}
        ]

        actions = await pulse.vacuum_bloated_tables()
        assert actions == []

    @pytest.mark.asyncio
    async def test_safe_table_vacuumed(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"relname": "clients", "n_live_tup": 1000, "n_dead_tup": 200, "dead_pct": 16.7}
        ]

        actions = await pulse.vacuum_bloated_tables()
        assert len(actions) == 1
        assert actions[0].action_type == "vacuum"
        assert actions[0].outcome == "success"

    @pytest.mark.asyncio
    async def test_unsafe_table_skipped(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"relname": "secret_table", "n_live_tup": 100, "n_dead_tup": 50, "dead_pct": 33.3}
        ]

        actions = await pulse.vacuum_bloated_tables()
        assert len(actions) == 1
        assert actions[0].outcome == "skipped"
        assert "Not in safe-list" in (actions[0].reflection or "")

    @pytest.mark.asyncio
    async def test_vacuum_failure(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"relname": "clients", "n_live_tup": 100, "n_dead_tup": 50, "dead_pct": 33.3}
        ]
        conn.execute.side_effect = Exception("lock timeout")

        actions = await pulse.vacuum_bloated_tables()
        assert len(actions) == 1
        assert actions[0].outcome == "failure"


# ---------------------------------------------------------------------------
# cleanup_audit_trail
# ---------------------------------------------------------------------------


class TestCleanupAuditTrail:
    @pytest.mark.asyncio
    async def test_partitioned_table(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetchval.return_value = "p"  # partitioned
        conn.fetch.return_value = [{"child_name": "api_audit_trail_2025_01"}]

        action = await pulse.cleanup_audit_trail()
        assert action.outcome == "success"
        assert action.detail["method"] == "detach_drop"

    @pytest.mark.asyncio
    async def test_regular_table(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetchval.return_value = "r"  # regular table
        conn.execute.return_value = "DELETE 42"

        action = await pulse.cleanup_audit_trail()
        assert action.outcome == "success"
        assert action.detail["method"] == "delete"
        assert action.detail["rows_deleted"] == 42

    @pytest.mark.asyncio
    async def test_cleanup_failure(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetchval.side_effect = Exception("permission denied")

        action = await pulse.cleanup_audit_trail()
        assert action.outcome == "failure"


# ---------------------------------------------------------------------------
# autovacuum_advisor
# ---------------------------------------------------------------------------


class TestAutovacuumAdvisor:
    @pytest.mark.asyncio
    async def test_no_tables(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []

        actions = await pulse.autovacuum_advisor()
        assert actions == []

    @pytest.mark.asyncio
    async def test_table_with_custom_autovacuum_skipped(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {
                "relname": "big_table",
                "reloptions": ["autovacuum_vacuum_scale_factor=0.01"],
                "n_dead_tup": 50000,
                "n_tup_upd": 100,
                "n_tup_ins": 100,
            }
        ]

        actions = await pulse.autovacuum_advisor()
        assert actions == []

    @pytest.mark.asyncio
    async def test_table_needs_tuning(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {
                "relname": "large_table",
                "reloptions": None,
                "n_dead_tup": 50000,
                "n_tup_upd": 100,
                "n_tup_ins": 1000,
            }
        ]

        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 1
        assert actions[0].action_type == "autovacuum_tuning"
        assert actions[0].outcome == "proposed"

    @pytest.mark.asyncio
    async def test_high_update_ratio_suggests_fillfactor(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {
                "relname": "hot_table",
                "reloptions": None,
                "n_dead_tup": 20000,
                "n_tup_upd": 800,
                "n_tup_ins": 200,
            }
        ]

        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 1
        assert "fillfactor_suggestion" in actions[0].detail


# ---------------------------------------------------------------------------
# repair_sequences
# ---------------------------------------------------------------------------


class TestRepairSequences:
    @pytest.mark.asyncio
    async def test_no_sequences(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []

        actions = await pulse.repair_sequences()
        assert actions == []

    @pytest.mark.asyncio
    async def test_sequence_behind_repaired(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"table_name": "clients", "column_name": "id", "seq": "clients_id_seq"}
        ]
        # max_val=100, last_val=50 -> needs repair
        conn.fetchval.side_effect = [100, 50]

        actions = await pulse.repair_sequences()
        assert len(actions) == 1
        assert actions[0].outcome == "success"
        assert actions[0].detail["old"] == 50
        assert actions[0].detail["new"] == 100

    @pytest.mark.asyncio
    async def test_sequence_ahead_no_action(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"table_name": "clients", "column_name": "id", "seq": "clients_id_seq"}
        ]
        # max_val=50, last_val=100 -> no repair needed
        conn.fetchval.side_effect = [50, 100]

        actions = await pulse.repair_sequences()
        assert actions == []

    @pytest.mark.asyncio
    async def test_sequence_repair_failure(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"table_name": "clients", "column_name": "id", "seq": "clients_id_seq"}
        ]
        conn.fetchval.side_effect = [100, 50]
        conn.execute.side_effect = Exception("setval failed")

        actions = await pulse.repair_sequences()
        assert len(actions) == 1
        assert actions[0].outcome == "failure"


# ---------------------------------------------------------------------------
# rebuild_invalid_indexes
# ---------------------------------------------------------------------------


class TestRebuildInvalidIndexes:
    @pytest.mark.asyncio
    async def test_no_invalid_indexes(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []

        actions = await pulse.rebuild_invalid_indexes()
        assert actions == []

    @pytest.mark.asyncio
    async def test_reindex_success(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"index_name": "idx_broken", "table_name": "clients"}
        ]

        actions = await pulse.rebuild_invalid_indexes()
        assert len(actions) == 1
        assert actions[0].outcome == "success"
        assert actions[0].action_type == "reindex"

    @pytest.mark.asyncio
    async def test_reindex_failure(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [
            {"index_name": "idx_broken", "table_name": "clients"}
        ]
        conn.execute.side_effect = Exception("reindex failed")

        actions = await pulse.rebuild_invalid_indexes()
        assert len(actions) == 1
        assert actions[0].outcome == "failure"


# ---------------------------------------------------------------------------
# refresh_materialized_views
# ---------------------------------------------------------------------------


class TestRefreshMaterializedViews:
    @pytest.mark.asyncio
    async def test_no_views(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []

        actions = await pulse.refresh_materialized_views()
        assert actions == []

    @pytest.mark.asyncio
    async def test_concurrent_refresh_success(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [{"matviewname": "mv_stats"}]

        actions = await pulse.refresh_materialized_views()
        assert len(actions) == 1
        assert actions[0].outcome == "success"
        assert actions[0].detail["concurrent"] is True

    @pytest.mark.asyncio
    async def test_fallback_to_non_concurrent(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [{"matviewname": "mv_stats"}]

        call_count = 0

        async def mock_execute(sql, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "CONCURRENTLY" in sql:
                raise Exception("unique index required")
            return None

        conn.execute = mock_execute

        actions = await pulse.refresh_materialized_views()
        assert len(actions) == 1
        assert actions[0].outcome == "success"
        assert actions[0].detail["concurrent"] is False

    @pytest.mark.asyncio
    async def test_both_methods_fail(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [{"matviewname": "mv_stats"}]
        conn.execute.side_effect = Exception("always fail")

        actions = await pulse.refresh_materialized_views()
        assert len(actions) == 1
        assert actions[0].outcome == "failure"


# ---------------------------------------------------------------------------
# cleanup_expired_sessions
# ---------------------------------------------------------------------------


class TestCleanupExpiredSessions:
    @pytest.mark.asyncio
    async def test_cleanup_success(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.execute.return_value = "DELETE 15"

        action = await pulse.cleanup_expired_sessions()
        assert action.outcome == "success"
        assert action.detail["rows_deleted"] == 15

    @pytest.mark.asyncio
    async def test_cleanup_failure(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.execute.side_effect = Exception("table not found")

        action = await pulse.cleanup_expired_sessions()
        assert action.outcome == "failure"


# ---------------------------------------------------------------------------
# ensure_next_partition
# ---------------------------------------------------------------------------


class TestEnsureNextPartition:
    @pytest.mark.asyncio
    async def test_partition_already_exists(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = {
            "start": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "stop": datetime(2026, 7, 1, tzinfo=timezone.utc),
        }
        conn.fetchval.return_value = True  # partition exists

        action = await pulse.ensure_next_partition()
        assert action is None  # Nothing to do

    @pytest.mark.asyncio
    async def test_partition_created(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = {
            "start": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "stop": datetime(2026, 7, 1, tzinfo=timezone.utc),
        }
        conn.fetchval.return_value = None  # does not exist

        action = await pulse.ensure_next_partition()
        assert action is not None
        assert action.outcome == "success"
        assert action.action_type == "ensure_partition"

    @pytest.mark.asyncio
    async def test_partition_creation_failure(self, pulse, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = {
            "start": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "stop": datetime(2026, 7, 1, tzinfo=timezone.utc),
        }
        conn.fetchval.return_value = None
        conn.execute.side_effect = Exception("already exists")

        action = await pulse.ensure_next_partition()
        assert action is not None
        assert action.outcome == "failure"


# ---------------------------------------------------------------------------
# run_full_pulse
# ---------------------------------------------------------------------------


class TestRunFullPulse:
    @pytest.mark.asyncio
    async def test_aggregates_all_actions(self, pulse):
        with patch.object(pulse, "vacuum_bloated_tables", new_callable=AsyncMock) as v, \
             patch.object(pulse, "cleanup_audit_trail", new_callable=AsyncMock) as c, \
             patch.object(pulse, "repair_sequences", new_callable=AsyncMock) as r, \
             patch.object(pulse, "rebuild_invalid_indexes", new_callable=AsyncMock) as i, \
             patch.object(pulse, "refresh_materialized_views", new_callable=AsyncMock) as m, \
             patch.object(pulse, "cleanup_expired_sessions", new_callable=AsyncMock) as s, \
             patch.object(pulse, "ensure_next_partition", new_callable=AsyncMock) as p, \
             patch.object(pulse, "autovacuum_advisor", new_callable=AsyncMock) as a:

            from backend.services.olympus.models import PulseAction

            v.return_value = [PulseAction(action_type="vacuum", outcome="success")]
            c.return_value = PulseAction(action_type="cleanup_audit_trail", outcome="success")
            r.return_value = []
            i.return_value = []
            m.return_value = []
            s.return_value = PulseAction(action_type="cleanup_expired_sessions", outcome="success")
            p.return_value = None
            a.return_value = []

            actions = await pulse.run_full_pulse()

        assert len(actions) == 3  # vacuum + audit cleanup + sessions
