"""
Unit Tests for Team Analytics Router - 95% Coverage Target
Tests all endpoints in backend/app/routers/team_analytics.py directly
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test get_team_analytics_service dependency
# ============================================================================


class TestGetTeamAnalyticsService:
    """Test suite for get_team_analytics_service dependency"""

    def test_get_team_analytics_service_creates_new_instance(self):
        """Test that service creates a new instance when none exists"""
        import app.routers.team_analytics as analytics_module

        # Reset global service
        analytics_module._team_analytics_service = None

        with patch("app.routers.team_analytics.TeamAnalyticsService") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_db_pool = MagicMock()

            result = analytics_module.get_team_analytics_service(db_pool=mock_db_pool)

            mock_cls.assert_called_once_with(mock_db_pool)
            assert result == mock_instance

    def test_get_team_analytics_service_returns_existing_instance(self):
        """Test that service returns existing instance"""
        import app.routers.team_analytics as analytics_module

        mock_existing = MagicMock()
        analytics_module._team_analytics_service = mock_existing

        result = analytics_module.get_team_analytics_service(db_pool=MagicMock())

        assert result == mock_existing

        # Cleanup
        analytics_module._team_analytics_service = None


# ============================================================================
# Test Get Work Patterns Endpoint
# ============================================================================


class TestGetWorkPatterns:
    """Test suite for GET /api/team-analytics/patterns"""

    @pytest.mark.asyncio
    async def test_get_work_patterns_success(self):
        """Test successful work patterns retrieval"""
        mock_service = MagicMock()
        mock_service.analyze_work_patterns = AsyncMock(
            return_value={
                "peak_hours": [9, 10, 11, 14, 15],
                "average_session_length": 2.5,
                "most_active_day": "Tuesday",
            }
        )

        from app.routers.team_analytics import get_work_patterns

        result = await get_work_patterns(user_email=None, days=30, service=mock_service)

        assert result["success"] is True
        assert "data" in result
        assert result["data"]["most_active_day"] == "Tuesday"
        mock_service.analyze_work_patterns.assert_called_once_with(None, 30)

    @pytest.mark.asyncio
    async def test_get_work_patterns_with_user_filter(self):
        """Test work patterns with user email filter"""
        mock_service = MagicMock()
        mock_service.analyze_work_patterns = AsyncMock(
            return_value={"peak_hours": [10, 11], "average_session_length": 3.0}
        )

        from app.routers.team_analytics import get_work_patterns

        result = await get_work_patterns(
            user_email="test@example.com", days=14, service=mock_service
        )

        assert result["success"] is True
        mock_service.analyze_work_patterns.assert_called_once_with("test@example.com", 14)

    @pytest.mark.asyncio
    async def test_get_work_patterns_error(self):
        """Test work patterns error handling"""
        mock_service = MagicMock()
        mock_service.analyze_work_patterns = AsyncMock(side_effect=Exception("Database error"))

        from fastapi import HTTPException

        from app.routers.team_analytics import get_work_patterns

        with pytest.raises(HTTPException) as exc_info:
            await get_work_patterns(user_email=None, days=30, service=mock_service)

        assert exc_info.value.status_code == 500
        assert "Database error" in str(exc_info.value.detail)


# ============================================================================
# Test Get Productivity Scores Endpoint
# ============================================================================


class TestGetProductivityScores:
    """Test suite for GET /api/team-analytics/productivity"""

    @pytest.mark.asyncio
    async def test_get_productivity_scores_success(self):
        """Test successful productivity scores retrieval"""
        mock_service = MagicMock()
        mock_service.calculate_productivity_scores = AsyncMock(
            return_value=[
                {"email": "user1@example.com", "score": 85, "rank": 1},
                {"email": "user2@example.com", "score": 78, "rank": 2},
            ]
        )

        from app.routers.team_analytics import get_productivity_scores

        result = await get_productivity_scores(days=7, service=mock_service)

        assert result["success"] is True
        assert "scores" in result
        assert len(result["scores"]) == 2
        mock_service.calculate_productivity_scores.assert_called_once_with(7)

    @pytest.mark.asyncio
    async def test_get_productivity_scores_empty(self):
        """Test productivity scores with no data"""
        mock_service = MagicMock()
        mock_service.calculate_productivity_scores = AsyncMock(return_value=[])

        from app.routers.team_analytics import get_productivity_scores

        result = await get_productivity_scores(days=7, service=mock_service)

        assert result["success"] is True
        assert result["scores"] == []

    @pytest.mark.asyncio
    async def test_get_productivity_scores_error(self):
        """Test productivity scores error handling"""
        mock_service = MagicMock()
        mock_service.calculate_productivity_scores = AsyncMock(
            side_effect=Exception("Calculation error")
        )

        from fastapi import HTTPException

        from app.routers.team_analytics import get_productivity_scores

        with pytest.raises(HTTPException) as exc_info:
            await get_productivity_scores(days=7, service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Get Burnout Signals Endpoint
# ============================================================================


class TestGetBurnoutSignals:
    """Test suite for GET /api/team-analytics/burnout"""

    @pytest.mark.asyncio
    async def test_get_burnout_signals_success(self):
        """Test successful burnout signals detection"""
        mock_service = MagicMock()
        mock_service.detect_burnout_signals = AsyncMock(
            return_value=[
                {
                    "email": "user1@example.com",
                    "risk_level": "high",
                    "indicators": ["long_hours", "weekend_work"],
                }
            ]
        )

        from app.routers.team_analytics import get_burnout_signals

        result = await get_burnout_signals(user_email=None, service=mock_service)

        assert result["success"] is True
        assert "signals" in result
        assert result["signals"][0]["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_get_burnout_signals_with_user_filter(self):
        """Test burnout signals with user email filter"""
        mock_service = MagicMock()
        mock_service.detect_burnout_signals = AsyncMock(
            return_value={"risk_level": "low", "indicators": []}
        )

        from app.routers.team_analytics import get_burnout_signals

        result = await get_burnout_signals(user_email="test@example.com", service=mock_service)

        assert result["success"] is True
        mock_service.detect_burnout_signals.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_get_burnout_signals_no_risk(self):
        """Test burnout signals with no risk detected"""
        mock_service = MagicMock()
        mock_service.detect_burnout_signals = AsyncMock(return_value=[])

        from app.routers.team_analytics import get_burnout_signals

        result = await get_burnout_signals(user_email=None, service=mock_service)

        assert result["success"] is True
        assert result["signals"] == []

    @pytest.mark.asyncio
    async def test_get_burnout_signals_error(self):
        """Test burnout signals error handling"""
        mock_service = MagicMock()
        mock_service.detect_burnout_signals = AsyncMock(side_effect=Exception("Detection error"))

        from fastapi import HTTPException

        from app.routers.team_analytics import get_burnout_signals

        with pytest.raises(HTTPException) as exc_info:
            await get_burnout_signals(user_email=None, service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Get Performance Trends Endpoint
# ============================================================================


class TestGetPerformanceTrends:
    """Test suite for GET /api/team-analytics/trends/{user_email}"""

    @pytest.mark.asyncio
    async def test_get_performance_trends_success(self):
        """Test successful performance trends retrieval"""
        mock_service = MagicMock()
        mock_service.analyze_performance_trends = AsyncMock(
            return_value={
                "weekly_scores": [80, 82, 85, 78],
                "trend": "improving",
                "avg_score": 81.25,
            }
        )

        from app.routers.team_analytics import get_performance_trends

        result = await get_performance_trends(
            user_email="test@example.com", weeks=4, service=mock_service
        )

        assert result["success"] is True
        assert result["trends"]["trend"] == "improving"
        mock_service.analyze_performance_trends.assert_called_once_with("test@example.com", 4)

    @pytest.mark.asyncio
    async def test_get_performance_trends_custom_weeks(self):
        """Test performance trends with custom weeks parameter"""
        mock_service = MagicMock()
        mock_service.analyze_performance_trends = AsyncMock(
            return_value={"weekly_scores": [70, 75, 80], "trend": "up"}
        )

        from app.routers.team_analytics import get_performance_trends

        result = await get_performance_trends(
            user_email="user@test.com", weeks=12, service=mock_service
        )

        assert result["success"] is True
        mock_service.analyze_performance_trends.assert_called_once_with("user@test.com", 12)

    @pytest.mark.asyncio
    async def test_get_performance_trends_error(self):
        """Test performance trends error handling"""
        mock_service = MagicMock()
        mock_service.analyze_performance_trends = AsyncMock(side_effect=Exception("Analysis error"))

        from fastapi import HTTPException

        from app.routers.team_analytics import get_performance_trends

        with pytest.raises(HTTPException) as exc_info:
            await get_performance_trends(
                user_email="test@example.com", weeks=4, service=mock_service
            )

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Get Workload Balance Endpoint
# ============================================================================


class TestGetWorkloadBalance:
    """Test suite for GET /api/team-analytics/workload-balance"""

    @pytest.mark.asyncio
    async def test_get_workload_balance_success(self):
        """Test successful workload balance retrieval"""
        mock_service = MagicMock()
        mock_service.analyze_workload_balance = AsyncMock(
            return_value={
                "distribution": {"user1": 30, "user2": 40, "user3": 30},
                "balance_score": 0.85,
                "overloaded": [],
                "underutilized": [],
            }
        )

        from app.routers.team_analytics import get_workload_balance

        result = await get_workload_balance(days=7, service=mock_service)

        assert result["success"] is True
        assert "balance" in result
        assert result["balance"]["balance_score"] == 0.85
        mock_service.analyze_workload_balance.assert_called_once_with(7)

    @pytest.mark.asyncio
    async def test_get_workload_balance_imbalanced(self):
        """Test workload balance with imbalanced team"""
        mock_service = MagicMock()
        mock_service.analyze_workload_balance = AsyncMock(
            return_value={
                "distribution": {"user1": 60, "user2": 30, "user3": 10},
                "balance_score": 0.45,
                "overloaded": ["user1"],
                "underutilized": ["user3"],
            }
        )

        from app.routers.team_analytics import get_workload_balance

        result = await get_workload_balance(days=14, service=mock_service)

        assert result["success"] is True
        assert result["balance"]["overloaded"] == ["user1"]

    @pytest.mark.asyncio
    async def test_get_workload_balance_error(self):
        """Test workload balance error handling"""
        mock_service = MagicMock()
        mock_service.analyze_workload_balance = AsyncMock(side_effect=Exception("Balance error"))

        from fastapi import HTTPException

        from app.routers.team_analytics import get_workload_balance

        with pytest.raises(HTTPException) as exc_info:
            await get_workload_balance(days=7, service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Get Optimal Hours Endpoint
# ============================================================================


class TestGetOptimalHours:
    """Test suite for GET /api/team-analytics/optimal-hours"""

    @pytest.mark.asyncio
    async def test_get_optimal_hours_success(self):
        """Test successful optimal hours identification"""
        mock_service = MagicMock()
        mock_service.identify_optimal_hours = AsyncMock(
            return_value={
                "best_hours": [9, 10, 11, 14, 15],
                "productivity_by_hour": {9: 0.9, 10: 0.95, 11: 0.92},
                "recommendation": "Focus deep work between 9-11 AM",
            }
        )

        from app.routers.team_analytics import get_optimal_hours

        result = await get_optimal_hours(user_email=None, days=30, service=mock_service)

        assert result["success"] is True
        assert "optimal_hours" in result
        assert 10 in result["optimal_hours"]["best_hours"]

    @pytest.mark.asyncio
    async def test_get_optimal_hours_with_user_filter(self):
        """Test optimal hours with user email filter"""
        mock_service = MagicMock()
        mock_service.identify_optimal_hours = AsyncMock(
            return_value={"best_hours": [14, 15, 16], "is_afternoon_person": True}
        )

        from app.routers.team_analytics import get_optimal_hours

        result = await get_optimal_hours(
            user_email="test@example.com", days=60, service=mock_service
        )

        assert result["success"] is True
        mock_service.identify_optimal_hours.assert_called_once_with("test@example.com", 60)

    @pytest.mark.asyncio
    async def test_get_optimal_hours_error(self):
        """Test optimal hours error handling"""
        mock_service = MagicMock()
        mock_service.identify_optimal_hours = AsyncMock(side_effect=Exception("Hours error"))

        from fastapi import HTTPException

        from app.routers.team_analytics import get_optimal_hours

        with pytest.raises(HTTPException) as exc_info:
            await get_optimal_hours(user_email=None, days=30, service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Get Team Insights Endpoint
# ============================================================================


class TestGetTeamInsights:
    """Test suite for GET /api/team-analytics/team-insights"""

    @pytest.mark.asyncio
    async def test_get_team_insights_success(self):
        """Test successful team insights generation"""
        mock_service = MagicMock()
        mock_service.generate_team_insights = AsyncMock(
            return_value={
                "collaboration_score": 0.85,
                "top_performers": ["user1", "user2"],
                "improvement_areas": ["communication", "meeting efficiency"],
                "highlights": ["Team productivity up 10%", "Response time improved"],
            }
        )

        from app.routers.team_analytics import get_team_insights

        result = await get_team_insights(days=7, service=mock_service)

        assert result["success"] is True
        assert "insights" in result
        assert result["insights"]["collaboration_score"] == 0.85
        mock_service.generate_team_insights.assert_called_once_with(7)

    @pytest.mark.asyncio
    async def test_get_team_insights_custom_days(self):
        """Test team insights with custom days parameter"""
        mock_service = MagicMock()
        mock_service.generate_team_insights = AsyncMock(return_value={"summary": "30-day analysis"})

        from app.routers.team_analytics import get_team_insights

        result = await get_team_insights(days=30, service=mock_service)

        assert result["success"] is True
        mock_service.generate_team_insights.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_team_insights_error(self):
        """Test team insights error handling"""
        mock_service = MagicMock()
        mock_service.generate_team_insights = AsyncMock(side_effect=Exception("Insights error"))

        from fastapi import HTTPException

        from app.routers.team_analytics import get_team_insights

        with pytest.raises(HTTPException) as exc_info:
            await get_team_insights(days=7, service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Router Configuration
# ============================================================================


class TestRouterConfiguration:
    """Test router prefix and tags configuration"""

    def test_router_prefix(self):
        """Test that router has correct prefix"""
        from app.routers.team_analytics import router

        assert router.prefix == "/api/team-analytics"

    def test_router_tags(self):
        """Test that router has correct tags"""
        from app.routers.team_analytics import router

        assert "team-analytics" in router.tags
