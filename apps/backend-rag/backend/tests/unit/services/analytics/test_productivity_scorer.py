"""
Unit tests for ProductivityScorerService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.analytics.productivity_scorer import ProductivityScorerService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def productivity_scorer(mock_db_pool):
    """Create ProductivityScorerService instance"""
    return ProductivityScorerService(db_pool=mock_db_pool)


class TestProductivityScorerService:
    """Tests for ProductivityScorerService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = ProductivityScorerService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_no_sessions(self, productivity_scorer, mock_db_pool):
        """Test calculating productivity scores with no sessions"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await productivity_scorer.calculate_productivity_scores()
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_excellent(self, productivity_scorer, mock_db_pool):
        """Test calculating productivity scores for excellent performer"""
        sessions = [
            {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "total_minutes": 480,  # 8 hours
                "total_conversations": 30,  # 3.75 per hour
                "total_activities": 200,  # 25 per hour
                "session_count": 1
            }
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await productivity_scorer.calculate_productivity_scores()
        assert len(results) == 1
        assert results[0]["productivity_score"] >= 60  # Should be good or excellent

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_fair(self, productivity_scorer, mock_db_pool):
        """Test calculating productivity scores for fair performer"""
        sessions = [
            {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "total_minutes": 240,  # 4 hours
                "total_conversations": 4,  # 1 per hour
                "total_activities": 20,  # 5 per hour
                "session_count": 1
            }
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await productivity_scorer.calculate_productivity_scores()
        assert len(results) == 1
        assert "productivity_score" in results[0]
        assert "rating" in results[0]

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_zero_hours(self, productivity_scorer, mock_db_pool):
        """Test calculating productivity scores with zero hours"""
        sessions = [
            {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "total_minutes": 0,
                "total_conversations": 0,
                "total_activities": 0,
                "session_count": 1
            }
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await productivity_scorer.calculate_productivity_scores()
        # Should skip zero hours sessions
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_multiple_users(self, productivity_scorer, mock_db_pool):
        """Test calculating productivity scores for multiple users"""
        sessions = [
            {
                "user_name": "User 1",
                "user_email": "user1@example.com",
                "total_minutes": 480,
                "total_conversations": 30,
                "total_activities": 200,
                "session_count": 1
            },
            {
                "user_name": "User 2",
                "user_email": "user2@example.com",
                "total_minutes": 240,
                "total_conversations": 10,
                "total_activities": 50,
                "session_count": 1
            }
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await productivity_scorer.calculate_productivity_scores()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_custom_days(self, productivity_scorer, mock_db_pool):
        """Test calculating productivity scores with custom days"""
        sessions = [
            {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "total_minutes": 480,
                "total_conversations": 30,
                "total_activities": 200,
                "session_count": 1
            }
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await productivity_scorer.calculate_productivity_scores(days=14)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_metrics(self, productivity_scorer, mock_db_pool):
        """Test that metrics are included in results"""
        sessions = [
            {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "total_minutes": 480,
                "total_conversations": 30,
                "total_activities": 200,
                "session_count": 1
            }
        ]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await productivity_scorer.calculate_productivity_scores()
        assert "metrics" in results[0]
        assert "conversations_per_hour" in results[0]["metrics"]
        assert "activities_per_hour" in results[0]["metrics"]
        assert "avg_session_hours" in results[0]["metrics"]

