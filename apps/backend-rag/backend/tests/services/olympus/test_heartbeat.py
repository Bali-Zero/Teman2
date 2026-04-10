"""Tests for Olympus v2 Heartbeat."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.olympus.heartbeat import Heartbeat
from backend.services.olympus.models import HeartbeatSnapshot


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
        "long_query_threshold_seconds": 30,
        "pool_alert_pct": 80,
        "connection_alert_pct": 70,
    }.get(name, default))
    return rules


class TestHeartbeat:
    def test_rule_name_is_long_query_threshold_seconds(self, mock_rules):
        """BUG-3 fix: must use 'long_query_threshold_seconds', not 'long_query_seconds'."""
        import inspect
        source = inspect.getsource(Heartbeat.collect_metrics)
        assert "long_query_threshold_seconds" in source
        assert "long_query_seconds" not in source.replace("long_query_threshold_seconds", "")

    @pytest.mark.asyncio
    async def test_check_alerts_pool_over_threshold(self, mock_rules):
        hb = Heartbeat(AsyncMock(), mock_rules)
        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=1, active_connections=5,
            max_connections=100, db_size_bytes=1000,
        )
        alert_called = False
        async def on_alert(msg):
            nonlocal alert_called
            alert_called = True
        hb.on_alert(on_alert)
        msgs = await hb.check_alerts(snapshot)
        assert len(msgs) >= 1
        assert alert_called

    @pytest.mark.asyncio
    async def test_check_alerts_no_alerts_when_healthy(self, mock_rules):
        hb = Heartbeat(AsyncMock(), mock_rules)
        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
        )
        msgs = await hb.check_alerts(snapshot)
        assert len(msgs) == 0


class TestHeartbeatExtendedMetrics:
    @pytest.mark.asyncio
    async def test_health_score_alert_when_low(self, mock_rules):
        """Alert fires when health_score < threshold."""
        mock_rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
            "long_query_threshold_seconds": 30,
            "pool_alert_pct": 80,
            "connection_alert_pct": 70,
            "health_score_alert_threshold": 60,
        }.get(name, default))

        hb = Heartbeat(AsyncMock(), mock_rules)
        alert_msgs = []
        async def on_alert(msg):
            alert_msgs.append(msg)
        hb.on_alert(on_alert)

        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
            health_score=45,
        )
        await hb.check_alerts(snapshot)
        assert any("Health score" in m for m in alert_msgs)

    @pytest.mark.asyncio
    async def test_no_health_alert_when_healthy(self, mock_rules):
        mock_rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
            "long_query_threshold_seconds": 30,
            "pool_alert_pct": 80,
            "connection_alert_pct": 70,
            "health_score_alert_threshold": 60,
        }.get(name, default))

        hb = Heartbeat(AsyncMock(), mock_rules)
        alert_fired = False
        async def on_alert(msg):
            nonlocal alert_fired
            if "Health score" in msg:
                alert_fired = True
        hb.on_alert(on_alert)

        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
            health_score=85,
        )
        await hb.check_alerts(snapshot)
        assert not alert_fired

    @pytest.mark.asyncio
    async def test_persist_includes_v3_columns(self, mock_rules):
        """persist() sends v3 columns to DB."""
        from unittest.mock import MagicMock
        pool = MagicMock()
        conn = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx

        hb = Heartbeat(pool, mock_rules)
        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=5, active_connections=3,
            max_connections=100, db_size_bytes=5000,
            cache_hit_ratio=97.5,
            top_tables_by_size=[{"table": "clients", "bytes": 1000}],
            idx_scan_ratio=88.0,
            health_score=92,
        )
        await hb.persist(snapshot)

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        sql = call_args[0]
        assert "cache_hit_ratio" in sql
        assert "top_tables_by_size" in sql
        assert "idx_scan_ratio" in sql
        assert "health_score" in sql
