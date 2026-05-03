"""Tests for Heartbeat — metrics collection, alert evaluation, persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.olympus.heartbeat import Heartbeat
from backend.services.olympus.models import HeartbeatSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(
    mock_conn: AsyncMock | None = None,
    *,
    pool_size: int = 10,
    pool_idle: int = 8,
) -> tuple[MagicMock, AsyncMock]:
    """Return (mock_pool, mock_conn) with async-context-manager acquire."""
    if mock_conn is None:
        mock_conn = AsyncMock()
    mock_pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = cm
    mock_pool.get_size.return_value = pool_size
    mock_pool.get_idle_size.return_value = pool_idle
    return mock_pool, mock_conn


def _make_rules(overrides: dict[str, object] | None = None) -> MagicMock:
    """Return a mock RulesEngine whose get_threshold honours *overrides*."""
    defaults: dict[str, object] = {
        "long_query_seconds": 30,
        "pool_alert_pct": 80,
        "connection_alert_pct": 80,
    }
    if overrides:
        defaults.update(overrides)
    rules = MagicMock()
    rules.get_threshold.side_effect = lambda name, default=None: defaults.get(name, default)
    return rules


def _setup_conn_for_collect(
    mock_conn: AsyncMock,
    *,
    active: int = 5,
    max_conn: int = 100,
    db_size: int = 1_000_000,
    bloat_rows: list[dict] | None = None,
    long_queries: int = 0,
    lock_waits: int = 0,
) -> None:
    """Configure mock_conn.fetchrow / fetch to return predictable data."""
    if bloat_rows is None:
        bloat_rows = []

    # fetchrow is called for: active connections, max_connections, db_size,
    # long_queries, lock_waits  (in that order)
    mock_conn.fetchrow = AsyncMock(side_effect=[
        {"cnt": active},                 # _count_active_connections
        {"max_connections": str(max_conn)},  # _get_max_connections (SHOW returns str)
        {"size": db_size},               # _get_db_size
        {"cnt": long_queries},           # _count_long_queries
        {"cnt": lock_waits},             # _count_lock_waits
    ])
    mock_conn.fetch = AsyncMock(return_value=bloat_rows)  # _get_bloat_top3


# ---------------------------------------------------------------------------
# Tests — collect_metrics
# ---------------------------------------------------------------------------


class TestCollectMetrics:
    """collect_metrics should build a HeartbeatSnapshot from DB queries."""

    @pytest.mark.asyncio
    async def test_returns_correct_snapshot(self) -> None:
        mock_pool, mock_conn = _make_pool(pool_size=10, pool_idle=6)
        rules = _make_rules()

        bloat = [
            {"relname": "big_table", "n_dead_tup": 5000, "n_live_tup": 100_000},
        ]
        _setup_conn_for_collect(
            mock_conn,
            active=12,
            max_conn=200,
            db_size=2_000_000,
            bloat_rows=bloat,
            long_queries=2,
            lock_waits=1,
        )

        hb = Heartbeat(mock_pool, rules)
        snapshot = await hb.collect_metrics()

        assert isinstance(snapshot, HeartbeatSnapshot)
        assert snapshot.pool_size == 10
        assert snapshot.pool_idle == 6
        assert snapshot.active_connections == 12
        assert snapshot.max_connections == 200
        assert snapshot.db_size_bytes == 2_000_000
        assert len(snapshot.bloat_top3) == 1
        assert snapshot.bloat_top3[0]["table"] == "big_table"
        assert snapshot.long_queries == 2
        assert snapshot.lock_waits == 1
        # pool_utilization = 1 - 6/10 = 0.4
        assert snapshot.pool_utilization == pytest.approx(0.4)

    @pytest.mark.asyncio
    async def test_empty_bloat_and_zero_issues(self) -> None:
        mock_pool, mock_conn = _make_pool(pool_size=5, pool_idle=5)
        rules = _make_rules()
        _setup_conn_for_collect(
            mock_conn,
            active=1,
            max_conn=100,
            db_size=500_000,
            bloat_rows=[],
            long_queries=0,
            lock_waits=0,
        )

        hb = Heartbeat(mock_pool, rules)
        snapshot = await hb.collect_metrics()

        assert snapshot.bloat_top3 == []
        assert snapshot.long_queries == 0
        assert snapshot.lock_waits == 0
        # pool_utilization = 1 - 5/5 = 0.0
        assert snapshot.pool_utilization == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_uses_long_query_threshold_from_rules(self) -> None:
        mock_pool, mock_conn = _make_pool()
        rules = _make_rules({"long_query_seconds": 60})
        _setup_conn_for_collect(mock_conn)

        hb = Heartbeat(mock_pool, rules)
        await hb.collect_metrics()

        # The fourth fetchrow call is _count_long_queries — verify threshold param
        call_args = mock_conn.fetchrow.call_args_list[3]
        assert call_args[0][1] == 60  # second positional arg = threshold


# ---------------------------------------------------------------------------
# Tests — check_alerts
# ---------------------------------------------------------------------------


class TestCheckAlerts:
    """check_alerts should fire callbacks when thresholds are breached."""

    @pytest.mark.asyncio
    async def test_pool_utilization_alert_fires(self) -> None:
        mock_pool, _ = _make_pool()
        rules = _make_rules({"pool_alert_pct": 80})

        hb = Heartbeat(mock_pool, rules)
        alert_log: list[str] = []
        hb.on_alert(AsyncMock(side_effect=lambda msg: alert_log.append(msg)))

        # pool_utilization = 1 - 1/10 = 0.9  (> 0.80)
        snapshot = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=1,
            active_connections=5,
            max_connections=100,
            db_size_bytes=1_000,
        )

        messages = await hb.check_alerts(snapshot)

        assert len(messages) == 1
        assert "Pool utilization" in messages[0]
        assert "90%" in messages[0]
        assert snapshot.alerts_sent == 1
        assert len(alert_log) == 1

    @pytest.mark.asyncio
    async def test_no_alert_when_below_threshold(self) -> None:
        mock_pool, _ = _make_pool()
        rules = _make_rules({"pool_alert_pct": 80, "connection_alert_pct": 80})

        hb = Heartbeat(mock_pool, rules)
        callback = AsyncMock()
        hb.on_alert(callback)

        # pool_utilization = 1 - 8/10 = 0.2  (well below 80%)
        snapshot = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=8,
            active_connections=5,
            max_connections=100,
            db_size_bytes=1_000,
        )

        messages = await hb.check_alerts(snapshot)

        assert messages == []
        assert snapshot.alerts_sent == 0
        callback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_connection_ratio_alert_fires(self) -> None:
        mock_pool, _ = _make_pool()
        rules = _make_rules({"connection_alert_pct": 80})

        hb = Heartbeat(mock_pool, rules)
        callback = AsyncMock()
        hb.on_alert(callback)

        # connection ratio = 90/100 = 0.90 (> 0.80)
        snapshot = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=10,
            active_connections=90,
            max_connections=100,
            db_size_bytes=1_000,
        )

        messages = await hb.check_alerts(snapshot)

        assert any("Connection ratio" in m for m in messages)

    @pytest.mark.asyncio
    async def test_long_queries_alert_fires(self) -> None:
        mock_pool, _ = _make_pool()
        rules = _make_rules()

        hb = Heartbeat(mock_pool, rules)
        callback = AsyncMock()
        hb.on_alert(callback)

        snapshot = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=10,
            active_connections=5,
            max_connections=100,
            db_size_bytes=1_000,
            long_queries=3,
        )

        messages = await hb.check_alerts(snapshot)

        assert any("long-running" in m for m in messages)
        assert snapshot.alerts_sent >= 1

    @pytest.mark.asyncio
    async def test_multiple_alerts_accumulate(self) -> None:
        mock_pool, _ = _make_pool()
        rules = _make_rules({"pool_alert_pct": 80, "connection_alert_pct": 80})

        hb = Heartbeat(mock_pool, rules)
        hb.on_alert(AsyncMock())

        # pool_util = 0.9, conn_ratio = 0.85, long_queries = 1 → 3 alerts
        snapshot = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=1,
            active_connections=85,
            max_connections=100,
            db_size_bytes=1_000,
            long_queries=1,
        )

        messages = await hb.check_alerts(snapshot)

        assert len(messages) == 3
        assert snapshot.alerts_sent == 3


# ---------------------------------------------------------------------------
# Tests — persist
# ---------------------------------------------------------------------------


class TestPersist:
    """persist should INSERT the snapshot into olympus_heartbeats."""

    @pytest.mark.asyncio
    async def test_persist_calls_insert(self) -> None:
        mock_pool, mock_conn = _make_pool()
        mock_conn.execute = AsyncMock()
        rules = _make_rules()

        hb = Heartbeat(mock_pool, rules)

        snapshot = HeartbeatSnapshot(
            pool_size=10,
            pool_idle=8,
            active_connections=5,
            max_connections=100,
            db_size_bytes=2_000_000,
            bloat_top3=[{"table": "t", "dead_tuples": 2000, "live_tuples": 50000}],
            long_queries=0,
            lock_waits=0,
            alerts_sent=1,
        )

        await hb.persist(snapshot)

        mock_conn.execute.assert_awaited_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO olympus_heartbeats" in sql
        # Verify positional parameters match snapshot fields
        args = mock_conn.execute.call_args[0]
        assert args[1] == 10          # pool_size
        assert args[2] == 8           # pool_idle
        assert args[3] == 5           # active_connections
        assert args[4] == 100         # max_connections
        assert args[5] == 2_000_000   # db_size_bytes


# ---------------------------------------------------------------------------
# Tests — on_alert / alert
# ---------------------------------------------------------------------------


class TestAlertCallbacks:
    """on_alert registers callbacks; alert invokes them."""

    @pytest.mark.asyncio
    async def test_on_alert_registers_callback(self) -> None:
        mock_pool, _ = _make_pool()
        rules = _make_rules()
        hb = Heartbeat(mock_pool, rules)

        cb1 = AsyncMock()
        cb2 = AsyncMock()
        hb.on_alert(cb1)
        hb.on_alert(cb2)

        await hb.alert("test message")

        cb1.assert_awaited_once_with("test message")
        cb2.assert_awaited_once_with("test message")
