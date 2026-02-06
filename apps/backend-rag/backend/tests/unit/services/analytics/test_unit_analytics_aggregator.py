"""
Unit tests for AnalyticsAggregator
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.analytics.analytics_aggregator import AnalyticsAggregator


@pytest.fixture
def mock_app_state():
    """Mock FastAPI app state"""
    app_state = MagicMock()
    app_state.boot_time = 1000.0
    return app_state


@pytest.fixture
def analytics_aggregator(mock_app_state):
    """Create AnalyticsAggregator instance"""
    return AnalyticsAggregator(app_state=mock_app_state)


class TestAnalyticsAggregator:
    """Tests for AnalyticsAggregator"""

    def test_init(self, mock_app_state):
        """Test initialization"""
        aggregator = AnalyticsAggregator(app_state=mock_app_state)
        assert aggregator.app_state == mock_app_state
        assert aggregator._boot_time == 1000.0

    @pytest.mark.asyncio
    async def test_get_overview_stats_no_pool(self, analytics_aggregator):
        """Test getting overview stats without database pool"""
        analytics_aggregator.app_state.db_pool = None
        analytics_aggregator.app_state.memory_service = None
        stats = await analytics_aggregator.get_overview_stats()
        assert stats is not None
        assert hasattr(stats, "uptime_seconds")

    @pytest.mark.asyncio
    async def test_get_overview_stats_with_pool(self, analytics_aggregator):
        """Test getting overview stats with database pool"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=10)
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        analytics_aggregator.app_state.db_pool = mock_pool
        stats = await analytics_aggregator.get_overview_stats()
        assert stats is not None

    @pytest.mark.asyncio
    async def test_get_rag_stats(self, analytics_aggregator):
        """Test getting RAG stats"""
        stats = await analytics_aggregator.get_rag_stats()
        # Returns RAGStats object, not dict
        assert stats is not None
        assert hasattr(stats, "avg_latency_ms") or isinstance(stats, dict)
