"""Tests for Olympus v3 InsightsCollector."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.olympus.insights import InsightsCollector


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_threshold = MagicMock(return_value=None)
    rules.record_applied = AsyncMock()
    return rules


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


class TestQueryIntelligence:
    @pytest.mark.asyncio
    async def test_skip_when_pgss_not_available(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetchval.return_value = None
        collector = InsightsCollector(pool, mock_rules)
        actions = await collector.collect_query_insights()
        assert len(actions) == 1
        assert actions[0].outcome == "skipped"
        assert "not available" in actions[0].reflection

    @pytest.mark.asyncio
    async def test_collects_top_queries(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [{"queryid": 123, "query": "SELECT * FROM clients", "calls": 100,
              "total_exec_time": 5000.0, "mean_exec_time": 50.0, "rows": 1000}],
            [],  # no previous insights
        ]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_query_insights()
        assert any(a.action_type == "query_intelligence" and a.outcome == "success" for a in actions)
        collector._persist_insight.assert_called()

    @pytest.mark.asyncio
    async def test_detects_regression(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [{"queryid": 123, "query": "SELECT * FROM clients", "calls": 100,
              "total_exec_time": 10000.0, "mean_exec_time": 100.0, "rows": 1000}],
            [{"evidence": '{"mean_exec_time": 50.0, "queryid": 123}'}],
        ]
        alert_msgs = []
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        collector._alert = AsyncMock(side_effect=lambda m: alert_msgs.append(m))
        actions = await collector.collect_query_insights()
        assert any(a.action_type == "query_regression" for a in actions)
        assert len(alert_msgs) > 0


class TestBloatIntelligence:
    @pytest.mark.asyncio
    async def test_detects_unused_indexes(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetch.side_effect = [
            [{"indexrelname": "idx_old_unused", "relname": "clients",
              "idx_scan": 0, "idx_size": 2000000}],
            [],
        ]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_bloat_insights()
        assert any(a.action_type == "unused_index" for a in actions)

    @pytest.mark.asyncio
    async def test_detects_missing_indexes(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetch.side_effect = [
            [],
            [{"relname": "big_table", "seq_scan": 1000, "idx_scan": 100,
              "table_size": 50000000, "idx_ratio": 9.1}],
        ]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_bloat_insights()
        assert any(a.action_type == "missing_index" for a in actions)

    @pytest.mark.asyncio
    async def test_no_insights_when_healthy(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetch.side_effect = [[], []]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_bloat_insights()
        assert len(actions) == 0
