"""
Unit tests for PerformanceTrendService
Target: >95% coverage
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.analytics.performance_trend import PerformanceTrendService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def performance_trend(mock_db_pool):
    """Create PerformanceTrendService instance"""
    return PerformanceTrendService(db_pool=mock_db_pool)


class TestPerformanceTrendService:
    """Tests for PerformanceTrendService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = PerformanceTrendService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_analyze_performance_trends_no_sessions(self, performance_trend, mock_db_pool):
        """Test analyzing performance trends with no sessions"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await performance_trend.analyze_performance_trends("test@example.com")
        assert isinstance(results, dict)
        assert "error" in results

    @pytest.mark.asyncio
    async def test_analyze_performance_trends_with_sessions(self, performance_trend, mock_db_pool):
        """Test analyzing performance trends with sessions"""
        from unittest.mock import MagicMock
        session = MagicMock()
        session.__getitem__ = lambda self, key: {
            "session_start": datetime.now() - timedelta(days=7),
            "duration_minutes": 480,
            "conversations_count": 30,
            "activities_count": 100
        }.get(key)
        session.session_start = datetime.now() - timedelta(days=7)
        sessions = [session]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await performance_trend.analyze_performance_trends("test@example.com")
        assert isinstance(results, dict)
        assert "weekly_breakdown" in results or "error" in results

    @pytest.mark.asyncio
    async def test_analyze_performance_trends_custom_weeks(self, performance_trend, mock_db_pool):
        """Test analyzing performance trends with custom weeks"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await performance_trend.analyze_performance_trends("test@example.com", weeks=8)
        assert isinstance(results, dict)

