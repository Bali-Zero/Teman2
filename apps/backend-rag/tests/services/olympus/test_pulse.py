"""Tests for Pulse — periodic maintenance actions."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse, _SAFE_VACUUM_TABLES


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


def _make_rules(thresholds: dict[str, object] | None = None) -> MagicMock:
    """Return a mock RulesEngine with get_threshold behaviour."""
    rules = MagicMock()
    _thresholds = thresholds or {}

    def _get_threshold(name: str, default: object = None) -> object:
        return _thresholds.get(name, default)

    rules.get_threshold = MagicMock(side_effect=_get_threshold)
    return rules


# ---------------------------------------------------------------------------
# Tests — vacuum_bloated_tables
# ---------------------------------------------------------------------------


class TestVacuumBloatedTables:
    """vacuum_bloated_tables should VACUUM only safe-listed tables above threshold."""

    async def test_vacuums_bloated_safe_table(self) -> None:
        mock_conn = AsyncMock()
        # pg_stat_user_tables returns one bloated safe-listed table
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "relname": "activity_log",
                "n_live_tup": 900,
                "n_dead_tup": 100,
                "dead_pct": 10.0,
            },
        ])
        mock_conn.execute = AsyncMock()

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules({"vacuum_dead_pct_threshold": 5})
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.vacuum_bloated_tables()

        assert len(actions) == 1
        assert actions[0].action_type == "vacuum"
        assert actions[0].target == "activity_log"
        assert actions[0].outcome == "ok"
        assert actions[0].duration_ms is not None

        # Verify VACUUM ANALYZE was executed (second acquire call)
        calls = mock_conn.execute.call_args_list
        vacuum_calls = [c for c in calls if "VACUUM ANALYZE" in str(c)]
        assert len(vacuum_calls) == 1
        assert "activity_log" in str(vacuum_calls[0])

    async def test_skips_table_not_in_safe_list(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "relname": "dangerous_table",
                "n_live_tup": 50,
                "n_dead_tup": 50,
                "dead_pct": 50.0,
            },
        ])
        mock_conn.execute = AsyncMock()

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules({"vacuum_dead_pct_threshold": 5})
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.vacuum_bloated_tables()

        assert len(actions) == 1
        assert actions[0].outcome == "skipped"
        assert actions[0].target == "dangerous_table"
        # No VACUUM should have been executed
        execute_calls = mock_conn.execute.call_args_list
        vacuum_calls = [c for c in execute_calls if "VACUUM" in str(c)]
        assert len(vacuum_calls) == 0

    async def test_ignores_table_below_threshold(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "relname": "activity_log",
                "n_live_tup": 999,
                "n_dead_tup": 1,
                "dead_pct": 0.1,
            },
        ])

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules({"vacuum_dead_pct_threshold": 5})
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.vacuum_bloated_tables()

        assert len(actions) == 0

    async def test_uses_default_threshold_when_rule_missing(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "relname": "conversations",
                "n_live_tup": 90,
                "n_dead_tup": 10,
                "dead_pct": 10.0,
            },
        ])
        mock_conn.execute = AsyncMock()

        mock_pool, _ = _make_pool(mock_conn)
        # No threshold configured — should fall back to default=5
        rules = _make_rules({})
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.vacuum_bloated_tables()

        assert len(actions) == 1
        assert actions[0].outcome == "ok"


# ---------------------------------------------------------------------------
# Tests — cleanup_audit_trail
# ---------------------------------------------------------------------------


class TestCleanupAuditTrail:
    """cleanup_audit_trail should DELETE old rows using retention days from rules."""

    async def test_deletes_with_retention_from_rules(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 42")

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules({"audit_retention_days": 60})
        pulse = Pulse(mock_pool, rules)

        action = await pulse.cleanup_audit_trail()

        assert action.action_type == "cleanup_audit_trail"
        assert action.target == "api_audit_trail"
        assert action.outcome == "ok"
        assert action.detail["retention_days"] == 60
        assert action.detail["rows_deleted"] == 42

        # Verify SQL contains correct interval
        sql_arg = mock_conn.execute.call_args[0][0]
        assert "DELETE FROM api_audit_trail" in sql_arg
        assert "60 days" in sql_arg

    async def test_uses_default_retention(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 0")

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules({})
        pulse = Pulse(mock_pool, rules)

        action = await pulse.cleanup_audit_trail()

        sql_arg = mock_conn.execute.call_args[0][0]
        assert "90 days" in sql_arg
        assert action.detail["retention_days"] == 90


# ---------------------------------------------------------------------------
# Tests — repair_sequences
# ---------------------------------------------------------------------------


class TestRepairSequences:
    """repair_sequences should fix broken sequences or return empty list."""

    async def test_returns_empty_when_no_sequences(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.repair_sequences()

        assert actions == []

    async def test_returns_empty_when_sequences_are_healthy(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "table_name": "clients",
                "column_name": "id",
                "seq": "clients_id_seq",
            },
        ])
        # max(id) = 100, last_value = 100 — healthy
        mock_conn.fetchval = AsyncMock(side_effect=[100, 100])

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.repair_sequences()

        assert actions == []

    async def test_repairs_broken_sequence(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "table_name": "clients",
                "column_name": "id",
                "seq": "clients_id_seq",
            },
        ])
        # max(id) = 200, last_value = 100 — broken
        mock_conn.fetchval = AsyncMock(side_effect=[200, 100])
        mock_conn.execute = AsyncMock()

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.repair_sequences()

        assert len(actions) == 1
        assert actions[0].action_type == "repair_sequence"
        assert actions[0].target == "clients_id_seq"
        assert actions[0].outcome == "ok"
        assert actions[0].detail["old_last_value"] == 100
        assert actions[0].detail["new_last_value"] == 200

        # Verify setval was called
        exec_calls = mock_conn.execute.call_args_list
        setval_calls = [c for c in exec_calls if "setval" in str(c)]
        assert len(setval_calls) == 1


# ---------------------------------------------------------------------------
# Tests — refresh_materialized_views
# ---------------------------------------------------------------------------


class TestRefreshMaterializedViews:
    """refresh_materialized_views should refresh all views from pg_matviews."""

    async def test_refreshes_all_views_concurrently(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"matviewname": "mv_bloat_stats"},
            {"matviewname": "mv_table_activity"},
        ])
        mock_conn.execute = AsyncMock()

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.refresh_materialized_views()

        assert len(actions) == 2
        assert all(a.action_type == "refresh_matview" for a in actions)
        assert all(a.outcome == "ok" for a in actions)
        targets = {a.target for a in actions}
        assert targets == {"mv_bloat_stats", "mv_table_activity"}
        # Both should report concurrent=True
        assert all(a.detail["concurrent"] is True for a in actions)

    async def test_falls_back_to_non_concurrent(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"matviewname": "mv_no_unique_idx"},
        ])
        # First call (CONCURRENTLY) fails, second (non-concurrent) succeeds
        mock_conn.execute = AsyncMock(
            side_effect=[Exception("no unique index"), None],
        )

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.refresh_materialized_views()

        assert len(actions) == 1
        assert actions[0].outcome == "ok"
        assert actions[0].detail["concurrent"] is False
        assert actions[0].reflection is not None

    async def test_returns_empty_when_no_matviews(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.refresh_materialized_views()

        assert actions == []


# ---------------------------------------------------------------------------
# Tests — cleanup_expired_sessions
# ---------------------------------------------------------------------------


class TestCleanupExpiredSessions:
    """cleanup_expired_sessions should DELETE old persistent_sessions rows."""

    async def test_deletes_expired_sessions(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 15")

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        action = await pulse.cleanup_expired_sessions()

        assert action.action_type == "cleanup_expired_sessions"
        assert action.target == "persistent_sessions"
        assert action.outcome == "ok"
        assert action.detail["rows_deleted"] == 15

        sql_arg = mock_conn.execute.call_args[0][0]
        assert "DELETE FROM persistent_sessions" in sql_arg
        assert "30 days" in sql_arg


# ---------------------------------------------------------------------------
# Tests — ensure_next_partition
# ---------------------------------------------------------------------------


class TestEnsureNextPartition:
    """ensure_next_partition should create partition or return None if exists."""

    async def test_returns_none_when_partition_exists(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "start": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "stop": datetime(2026, 6, 1, tzinfo=timezone.utc),
        })
        mock_conn.fetchval = AsyncMock(return_value=1)  # exists

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        result = await pulse.ensure_next_partition()

        assert result is None

    async def test_creates_partition_when_missing(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "start": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "stop": datetime(2026, 6, 1, tzinfo=timezone.utc),
        })
        mock_conn.fetchval = AsyncMock(return_value=None)  # does not exist
        mock_conn.execute = AsyncMock()

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules()
        pulse = Pulse(mock_pool, rules)

        action = await pulse.ensure_next_partition()

        assert action is not None
        assert action.action_type == "ensure_partition"
        assert action.target == "olympus_heartbeats_2026_05"
        assert action.outcome == "ok"

        # Verify CREATE TABLE was called
        exec_calls = mock_conn.execute.call_args_list
        create_calls = [c for c in exec_calls if "CREATE TABLE" in str(c)]
        assert len(create_calls) == 1


# ---------------------------------------------------------------------------
# Tests — run_full_pulse
# ---------------------------------------------------------------------------


class TestRunFullPulse:
    """run_full_pulse should call all sub-methods and aggregate actions."""

    async def test_aggregates_all_actions(self) -> None:
        mock_conn = AsyncMock()
        # vacuum: no bloated tables
        # audit: DELETE 0
        # sequences: no sequences
        # indexes: no invalid
        # matviews: no views
        # sessions: DELETE 0
        # partition: already exists
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="DELETE 0")
        mock_conn.fetchrow = AsyncMock(return_value={
            "start": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "stop": datetime(2026, 6, 1, tzinfo=timezone.utc),
        })
        mock_conn.fetchval = AsyncMock(return_value=1)  # partition exists

        mock_pool, _ = _make_pool(mock_conn)
        rules = _make_rules({"audit_retention_days": 90})
        pulse = Pulse(mock_pool, rules)

        actions = await pulse.run_full_pulse()

        # Should have at least the audit + sessions cleanup actions
        assert isinstance(actions, list)
        action_types = [a.action_type for a in actions]
        assert "cleanup_audit_trail" in action_types
        assert "cleanup_expired_sessions" in action_types


# ---------------------------------------------------------------------------
# Tests — _SAFE_VACUUM_TABLES
# ---------------------------------------------------------------------------


class TestSafeVacuumTables:
    """Verify the safe-list contains expected tables."""

    def test_contains_expected_tables(self) -> None:
        expected = {
            "api_audit_trail", "kg_edges", "kg_nodes",
            "conversations", "olympus_heartbeats", "olympus_actions",
        }
        assert expected.issubset(_SAFE_VACUUM_TABLES)

    def test_is_a_set(self) -> None:
        assert isinstance(_SAFE_VACUUM_TABLES, set)
