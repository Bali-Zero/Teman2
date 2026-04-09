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
