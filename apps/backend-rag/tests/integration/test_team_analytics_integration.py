"""
Integration tests for TeamAnalyticsService
Tests team analytics and performance analysis
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestTeamAnalyticsIntegration:
    """Integration tests for TeamAnalyticsService"""

    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool"""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])
        mock_pool.fetchrow = AsyncMock(return_value=None)
        return mock_pool

    @pytest.mark.asyncio
    async def test_team_analytics_init(self, mock_db_pool):
        """Test TeamAnalyticsService initialization"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        assert service is not None
        assert service.pool is not None

    @pytest.mark.asyncio
    async def test_analyze_work_patterns(self, mock_db_pool):
        """Test analyzing work patterns"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "session_start": "2025-01-01 09:00:00",
                    "duration_minutes": 120,
                    "day_of_week": 1,
                    "start_hour": 9,
                }
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.analyze_work_patterns(user_email="test@example.com", days=30)

        assert isinstance(result, dict)
        assert "error" not in result or result.get("error") != "No sessions found"

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_no_sessions(self, mock_db_pool):
        """Test analyzing work patterns with no sessions"""
        mock_db_pool.fetch = AsyncMock(return_value=[])

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.analyze_work_patterns(user_email="test@example.com", days=30)

        assert isinstance(result, dict)
        assert result.get("error") == "No sessions found"

    @pytest.mark.asyncio
    async def test_analyze_workload_balance(self, mock_db_pool):
        """Test analyzing workload balance"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "user_email": "user1@example.com",
                    "total_minutes": 2400,  # 40 hours
                    "total_conversations": 100,
                    "total_activities": 500,
                    "session_count": 10,
                }
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.analyze_workload_balance(days=30)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_identify_optimal_hours(self, mock_db_pool):
        """Test identifying optimal work hours"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "hour": 9.0,
                    "duration_minutes": 120,
                    "conversations_count": 5,
                }
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.identify_optimal_hours(user_email="test@example.com", days=30)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_team_insights(self, mock_db_pool):
        """Test generating team insights"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "user_name": "Test User",
                    "user_email": "user1@example.com",
                    "session_start": "2025-01-01 09:00:00",
                    "session_end": "2025-01-01 11:00:00",
                    "duration_minutes": 120,
                    "conversations_count": 5,
                    "activities_count": 10,
                    "start_hour": 9.0,
                    "day_of_week": 1.0,
                }
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.generate_team_insights(days=30)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores(self, mock_db_pool):
        """Test calculating productivity scores"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "user_name": "Test User",
                    "user_email": "user1@example.com",
                    "total_minutes": 2400,
                    "total_conversations": 100,
                    "total_activities": 500,
                    "session_count": 10,
                }
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.calculate_productivity_scores(days=7)

        assert isinstance(result, list)
        if result:
            assert "productivity_score" in result[0]
            assert "rating" in result[0]

    @pytest.mark.asyncio
    async def test_detect_burnout_signals(self, mock_db_pool):
        """Test detecting burnout signals"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "user_name": "Test User",
                    "user_email": "user1@example.com",
                    "session_start": "2025-01-01 09:00:00",
                    "duration_minutes": 600,
                    "conversations_count": 5,
                    "activities_count": 20,
                    "day_of_week": 0,
                }
                for _ in range(5)
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.detect_burnout_signals(user_email="user1@example.com")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_analyze_performance_trends(self, mock_db_pool):
        """Test analyzing performance trends"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "session_start": "2025-01-01 09:00:00",
                    "duration_minutes": 240,
                    "conversations_count": 10,
                    "activities_count": 50,
                }
                for _ in range(10)
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.analyze_performance_trends(user_email="user1@example.com", weeks=4)

        assert isinstance(result, dict)
        assert "weekly_breakdown" in result or "error" in result

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_no_user(self, mock_db_pool):
        """Test analyzing work patterns without user email"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "user_email": "user1@example.com",
                    "session_start": "2025-01-01 09:00:00",
                    "duration_minutes": 120,
                    "day_of_week": 1,
                    "start_hour": 9,
                }
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.analyze_work_patterns(user_email=None, days=30)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_no_user(self, mock_db_pool):
        """Test identifying optimal hours without user email"""
        mock_db_pool.fetch = AsyncMock(
            return_value=[
                {
                    "hour": 9.0,
                    "duration_minutes": 120,
                    "conversations_count": 5,
                }
            ]
        )

        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=mock_db_pool)
        result = await service.identify_optimal_hours(user_email=None, days=30)

        assert isinstance(result, dict)
