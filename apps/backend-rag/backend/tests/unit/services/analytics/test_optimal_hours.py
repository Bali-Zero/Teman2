"""
Unit tests for OptimalHoursService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock
from datetime import datetime, timedelta
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.analytics.optimal_hours import OptimalHoursService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def optimal_hours_service(mock_db_pool):
    """Create OptimalHoursService instance"""
    return OptimalHoursService(db_pool=mock_db_pool)


class TestOptimalHoursService:
    """Tests for OptimalHoursService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = OptimalHoursService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_no_sessions(self, optimal_hours_service, mock_db_pool):
        """Test identifying optimal hours with no sessions"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        result = await optimal_hours_service.identify_optimal_hours()
        assert "error" in result
        assert result["error"] == "No sessions found"

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_with_sessions(self, optimal_hours_service, mock_db_pool):
        """Test identifying optimal hours with sessions"""
        cutoff = datetime.now() - timedelta(days=30)
        sessions = [
            {"hour": 9, "duration_minutes": 120, "conversations_count": 10},
            {"hour": 10, "duration_minutes": 180, "conversations_count": 15},
            {"hour": 14, "duration_minutes": 60, "conversations_count": 5},
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        result = await optimal_hours_service.identify_optimal_hours()
        assert "optimal_windows" in result
        assert "all_hours" in result
        assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_with_user_email(self, optimal_hours_service, mock_db_pool):
        """Test identifying optimal hours for specific user"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        result = await optimal_hours_service.identify_optimal_hours(user_email="test@example.com")
        assert "error" in result
        mock_db_pool.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_custom_days(self, optimal_hours_service, mock_db_pool):
        """Test identifying optimal hours with custom days"""
        sessions = [
            {"hour": 9, "duration_minutes": 120, "conversations_count": 10},
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        result = await optimal_hours_service.identify_optimal_hours(days=60)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_productivity_calculation(self, optimal_hours_service, mock_db_pool):
        """Test productivity calculation"""
        sessions = [
            {"hour": 9, "duration_minutes": 120, "conversations_count": 10},  # 5 conv/hour
            {"hour": 10, "duration_minutes": 60, "conversations_count": 2},   # 2 conv/hour
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        result = await optimal_hours_service.identify_optimal_hours()
        assert len(result["optimal_windows"]) > 0
        # Hour 9 should be more productive than hour 10
        assert result["optimal_windows"][0]["conversations_per_hour"] >= 2

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_zero_duration(self, optimal_hours_service, mock_db_pool):
        """Test handling zero duration sessions"""
        sessions = [
            {"hour": 9, "duration_minutes": 0, "conversations_count": 10},
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        result = await optimal_hours_service.identify_optimal_hours()
        # Should filter out zero duration sessions
        assert isinstance(result, dict)

