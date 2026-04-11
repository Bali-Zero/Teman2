"""Tests for backend.services.analytics.analytics_aggregator"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.analytics.analytics_aggregator import (
    AnalyticsAggregator,
    CRMStats,
    OverviewStats,
    RAGStats,
    SystemStats,
    TeamStats,
)


def _make_pool(mock_conn):
    """Create a mock pool with proper async context manager for acquire()."""
    mock_pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = ctx
    return mock_pool


@pytest.fixture
def mock_app_state():
    state = MagicMock()
    state.boot_time = time.time() - 3600
    state.db_pool = None
    state.health_monitor = None
    state.memory_service = None
    return state


@pytest.fixture
def aggregator(mock_app_state):
    return AnalyticsAggregator(app_state=mock_app_state)


# ── Stats models ────────────────────────────────────────────────────────────


class TestStatsModels:
    def test_overview_defaults(self):
        stats = OverviewStats()
        assert stats.conversations_today == 0
        assert stats.revenue_pipeline == 0.0

    def test_rag_defaults(self):
        stats = RAGStats()
        assert stats.queries_today == 0
        assert stats.top_queries == []

    def test_crm_defaults(self):
        stats = CRMStats()
        assert stats.clients_total == 0
        assert stats.revenue_quoted == 0.0

    def test_team_defaults(self):
        stats = TeamStats()
        assert stats.hours_today == 0.0

    def test_system_defaults(self):
        stats = SystemStats()
        assert stats.cpu_percent == 0.0
        assert stats.services == []


# ── _get_db_pool ────────────────────────────────────────────────────────────


class TestGetDbPool:
    @pytest.mark.asyncio
    async def test_from_app_state(self, mock_app_state):
        mock_app_state.db_pool = MagicMock()
        agg = AnalyticsAggregator(app_state=mock_app_state)
        pool = await agg._get_db_pool()
        assert pool is mock_app_state.db_pool

    @pytest.mark.asyncio
    async def test_from_memory_service_fallback(self, mock_app_state):
        mock_app_state.db_pool = None
        mock_app_state.memory_service = MagicMock()
        mock_app_state.memory_service.pool = MagicMock()

        agg = AnalyticsAggregator(app_state=mock_app_state)
        pool = await agg._get_db_pool()
        assert pool is mock_app_state.memory_service.pool

    @pytest.mark.asyncio
    async def test_no_pool(self, aggregator):
        pool = await aggregator._get_db_pool()
        assert pool is None


# ── _get_client ─────────────────────────────────────────────────────────────


class TestGetClient:
    def test_creates_client(self, aggregator):
        client = aggregator._get_client()
        assert client is not None
        assert aggregator._client is client

    def test_reuses_client(self, aggregator):
        c1 = aggregator._get_client()
        c2 = aggregator._get_client()
        assert c1 is c2


# ── close ───────────────────────────────────────────────────────────────────


class TestClose:
    @pytest.mark.asyncio
    async def test_close_client(self, aggregator):
        mock_client = AsyncMock()
        mock_client.is_closed = False
        aggregator._client = mock_client
        await aggregator.close()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_no_client(self, aggregator):
        aggregator._client = None
        await aggregator.close()  # Should not raise


# ── get_overview_stats ──────────────────────────────────────────────────────


class TestGetOverviewStats:
    @pytest.mark.asyncio
    async def test_no_pool_returns_defaults(self, aggregator):
        result = await aggregator.get_overview_stats()
        assert isinstance(result, OverviewStats)
        assert result.conversations_today == 0
        assert result.uptime_seconds > 0

    @pytest.mark.asyncio
    async def test_with_pool(self, mock_app_state):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[10, 50, 5, 100000.0])
        pool = _make_pool(mock_conn)
        mock_app_state.db_pool = pool

        agg = AnalyticsAggregator(app_state=mock_app_state)
        result = await agg.get_overview_stats()
        assert result.conversations_today == 10
        assert result.conversations_week == 50


# ── get_rag_stats ───────────────────────────────────────────────────────────


class TestGetRagStats:
    @pytest.mark.asyncio
    async def test_no_pool(self, aggregator):
        result = await aggregator.get_rag_stats()
        assert isinstance(result, RAGStats)
        assert result.queries_today == 0


# ── get_crm_stats ───────────────────────────────────────────────────────────


class TestGetCrmStats:
    @pytest.mark.asyncio
    async def test_no_pool(self, aggregator):
        result = await aggregator.get_crm_stats()
        assert isinstance(result, CRMStats)
        assert result.clients_total == 0


# ── get_team_stats ──────────────────────────────────────────────────────────


class TestGetTeamStats:
    @pytest.mark.asyncio
    async def test_no_pool(self, aggregator):
        result = await aggregator.get_team_stats()
        assert isinstance(result, TeamStats)
        assert result.hours_today == 0.0


# ── get_system_stats ────────────────────────────────────────────────────────


class TestGetSystemStats:
    @pytest.mark.asyncio
    async def test_system_metrics(self, aggregator):
        with patch("backend.services.analytics.analytics_aggregator.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 25.5
            mock_memory = MagicMock()
            mock_memory.used = 500 * 1024 * 1024
            mock_memory.percent = 50.0
            mock_psutil.virtual_memory.return_value = mock_memory

            result = await aggregator.get_system_stats()
            assert isinstance(result, SystemStats)
            assert result.cpu_percent == 25.5
            assert result.memory_percent == 50.0

    @pytest.mark.asyncio
    async def test_with_pool_connections(self, mock_app_state):
        pool = MagicMock()
        pool.get_size.return_value = 10
        pool.get_idle_size.return_value = 7
        mock_app_state.db_pool = pool

        agg = AnalyticsAggregator(app_state=mock_app_state)
        with patch("backend.services.analytics.analytics_aggregator.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 10.0
            mock_memory = MagicMock()
            mock_memory.used = 100 * 1024 * 1024
            mock_memory.percent = 10.0
            mock_psutil.virtual_memory.return_value = mock_memory

            result = await agg.get_system_stats()
            assert result.db_connections_active == 3
            assert result.db_connections_idle == 7

    @pytest.mark.asyncio
    async def test_with_health_monitor(self, mock_app_state):
        mock_app_state.health_monitor = MagicMock()
        mock_app_state.health_monitor._service_states = {
            "db": {"healthy": True, "last_check": "2026-01-01", "error": ""},
        }

        agg = AnalyticsAggregator(app_state=mock_app_state)
        with patch("backend.services.analytics.analytics_aggregator.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 5.0
            mock_memory = MagicMock()
            mock_memory.used = 50 * 1024 * 1024
            mock_memory.percent = 5.0
            mock_psutil.virtual_memory.return_value = mock_memory

            result = await agg.get_system_stats()
            assert len(result.services) == 1
            assert result.services[0]["name"] == "db"
