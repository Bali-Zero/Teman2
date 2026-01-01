"""
Unit tests for TeamInsightsService
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

from services.analytics.team_insights import TeamInsightsService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def team_insights(mock_db_pool):
    """Create TeamInsightsService instance"""
    return TeamInsightsService(db_pool=mock_db_pool)


class TestTeamInsightsService:
    """Tests for TeamInsightsService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = TeamInsightsService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_generate_team_insights_no_sessions(self, team_insights, mock_db_pool):
        """Test generating team insights with no sessions"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await team_insights.generate_team_insights()
        assert isinstance(results, dict)
        assert "error" in results

    @pytest.mark.asyncio
    async def test_generate_team_insights_with_sessions(self, team_insights, mock_db_pool):
        """Test generating team insights with sessions"""
        from unittest.mock import MagicMock
        session = MagicMock()
        session.__getitem__ = lambda self, key: {
            "user_name": "User 1",
            "user_email": "user1@example.com",
            "session_start": datetime.now(),
            "session_end": datetime.now() + timedelta(hours=4),
            "duration_minutes": 240,
            "conversations_count": 20,
            "activities_count": 50,
            "start_hour": 9.0,
            "day_of_week": 1
        }.get(key)
        sessions = [session]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await team_insights.generate_team_insights()
        assert isinstance(results, dict)
        assert "team_summary" in results

    @pytest.mark.asyncio
    async def test_generate_team_insights_custom_days(self, team_insights, mock_db_pool):
        """Test generating team insights with custom days"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await team_insights.generate_team_insights(days=14)
        assert isinstance(results, dict)

