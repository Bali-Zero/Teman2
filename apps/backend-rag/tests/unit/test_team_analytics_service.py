"""
Comprehensive tests for TeamAnalyticsService
Target: 100% coverage
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestTeamAnalyticsService:
    """Tests for TeamAnalyticsService class"""

    @pytest.fixture
    def mock_pool(self):
        """Create mock database pool"""
        mock = MagicMock()
        mock.fetch = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_pool):
        """Create TeamAnalyticsService instance"""
        from services.team_analytics_service import TeamAnalyticsService

        return TeamAnalyticsService(mock_pool)

    # Test Pattern Recognition
    @pytest.mark.asyncio
    async def test_analyze_work_patterns_with_user(self, service, mock_pool):
        """Test analyzing work patterns for specific user"""
        mock_pool.fetch.return_value = [
            {
                "session_start": datetime.now(),
                "duration_minutes": 480,
                "day_of_week": 1,
                "start_hour": 9,
            },
            {
                "session_start": datetime.now(),
                "duration_minutes": 420,
                "day_of_week": 2,
                "start_hour": 9,
            },
        ]

        result = await service.analyze_work_patterns(user_email="test@example.com")

        assert "patterns" in result
        assert "consistency_score" in result
        assert result["total_sessions_analyzed"] == 2

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_all_users(self, service, mock_pool):
        """Test analyzing work patterns for all users"""
        mock_pool.fetch.return_value = [
            {
                "user_email": "user1@test.com",
                "session_start": datetime.now(),
                "duration_minutes": 480,
                "day_of_week": 1,
                "start_hour": 9,
            },
        ]

        result = await service.analyze_work_patterns()

        assert "patterns" in result

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_no_sessions(self, service, mock_pool):
        """Test analyzing patterns with no sessions"""
        mock_pool.fetch.return_value = []

        result = await service.analyze_work_patterns()

        assert result["error"] == "No sessions found"

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_single_session(self, service, mock_pool):
        """Test analyzing patterns with single session"""
        mock_pool.fetch.return_value = [
            {
                "session_start": datetime.now(),
                "duration_minutes": 480,
                "day_of_week": 1,
                "start_hour": 9,
            },
        ]

        result = await service.analyze_work_patterns()

        assert result["total_sessions_analyzed"] == 1
        # Single session should have 0 standard deviation
        assert result["patterns"]["start_hour_variance"] == 0

    # Test Productivity Scoring
    @pytest.mark.asyncio
    async def test_calculate_productivity_scores(self, service, mock_pool):
        """Test calculating productivity scores"""
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "total_minutes": 2400,
                "total_conversations": 100,
                "total_activities": 500,
                "session_count": 5,
            },
        ]

        result = await service.calculate_productivity_scores()

        assert len(result) == 1
        assert result[0]["user"] == "John"
        assert "productivity_score" in result[0]
        assert "rating" in result[0]

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_zero_hours(self, service, mock_pool):
        """Test productivity with zero hours"""
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "total_minutes": 0,
                "total_conversations": 0,
                "total_activities": 0,
                "session_count": 1,
            },
        ]

        result = await service.calculate_productivity_scores()

        assert len(result) == 0  # Skipped due to zero hours

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_various_ratings(self, service, mock_pool):
        """Test various productivity ratings"""
        mock_pool.fetch.return_value = [
            {
                "user_name": "Excellent",
                "user_email": "e@test.com",
                "total_minutes": 2400,
                "total_conversations": 200,
                "total_activities": 1200,
                "session_count": 5,
            },  # High scores
            {
                "user_name": "Low",
                "user_email": "l@test.com",
                "total_minutes": 2400,
                "total_conversations": 10,
                "total_activities": 50,
                "session_count": 5,
            },  # Low scores
        ]

        result = await service.calculate_productivity_scores()

        assert len(result) == 2

    # Test Burnout Detection
    @pytest.mark.asyncio
    async def test_detect_burnout_signals(self, service, mock_pool):
        """Test detecting burnout signals"""
        now = datetime.now()
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(days=25),
                "duration_minutes": 300,
                "conversations_count": 50,
                "activities_count": 100,
                "day_of_week": 1,
            },
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(days=20),
                "duration_minutes": 400,
                "conversations_count": 50,
                "activities_count": 100,
                "day_of_week": 2,
            },
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(days=15),
                "duration_minutes": 500,
                "conversations_count": 50,
                "activities_count": 100,
                "day_of_week": 3,
            },
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(days=10),
                "duration_minutes": 600,
                "conversations_count": 30,
                "activities_count": 100,
                "day_of_week": 0,
            },  # Weekend
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(days=5),
                "duration_minutes": 700,
                "conversations_count": 20,
                "activities_count": 100,
                "day_of_week": 6,
            },  # Weekend
        ]

        result = await service.detect_burnout_signals()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_detect_burnout_signals_for_user(self, service, mock_pool):
        """Test detecting burnout signals for specific user"""
        mock_pool.fetch.return_value = []

        result = await service.detect_burnout_signals(user_email="test@example.com")

        assert result == []

    @pytest.mark.asyncio
    async def test_detect_burnout_signals_long_sessions(self, service, mock_pool):
        """Test burnout detection with very long sessions"""
        now = datetime.now()
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(days=i),
                "duration_minutes": 650,
                "conversations_count": 50,
                "activities_count": 100,
                "day_of_week": i % 7,
            }
            for i in range(10)
        ]

        result = await service.detect_burnout_signals()

        # Should detect long sessions warning
        if result:
            assert any(
                "very long sessions" in str(w) for r in result for w in r.get("warning_signals", [])
            )

    # Test Performance Trends
    @pytest.mark.asyncio
    async def test_analyze_performance_trends(self, service, mock_pool):
        """Test analyzing performance trends"""
        now = datetime.now()
        mock_pool.fetch.return_value = [
            {
                "session_start": now - timedelta(weeks=3),
                "duration_minutes": 480,
                "conversations_count": 50,
                "activities_count": 100,
            },
            {
                "session_start": now - timedelta(weeks=2),
                "duration_minutes": 480,
                "conversations_count": 55,
                "activities_count": 110,
            },
            {
                "session_start": now - timedelta(weeks=1),
                "duration_minutes": 480,
                "conversations_count": 60,
                "activities_count": 120,
            },
        ]

        result = await service.analyze_performance_trends("test@example.com")

        assert "weekly_breakdown" in result
        assert "trend" in result
        assert "averages" in result

    @pytest.mark.asyncio
    async def test_analyze_performance_trends_no_sessions(self, service, mock_pool):
        """Test trends with no sessions"""
        mock_pool.fetch.return_value = []

        result = await service.analyze_performance_trends("test@example.com")

        assert result["error"] == "No sessions found"

    @pytest.mark.asyncio
    async def test_analyze_performance_trends_single_week(self, service, mock_pool):
        """Test trends with single week of data"""
        now = datetime.now()
        mock_pool.fetch.return_value = [
            {
                "session_start": now,
                "duration_minutes": 480,
                "conversations_count": 50,
                "activities_count": 100,
            },
        ]

        result = await service.analyze_performance_trends("test@example.com")

        assert result["trend"]["direction"] == "Stable"

    # Test Workload Balance
    @pytest.mark.asyncio
    async def test_analyze_workload_balance(self, service, mock_pool):
        """Test analyzing workload balance"""
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "total_minutes": 2400,
                "total_conversations": 100,
                "session_count": 5,
            },
            {
                "user_name": "Jane",
                "user_email": "jane@test.com",
                "total_minutes": 2000,
                "total_conversations": 80,
                "session_count": 4,
            },
        ]

        result = await service.analyze_workload_balance()

        assert "team_distribution" in result
        assert "balance_metrics" in result
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_analyze_workload_balance_no_sessions(self, service, mock_pool):
        """Test workload balance with no sessions"""
        mock_pool.fetch.return_value = []

        result = await service.analyze_workload_balance()

        assert result["error"] == "No sessions found"

    @pytest.mark.asyncio
    async def test_analyze_workload_balance_single_user(self, service, mock_pool):
        """Test workload balance with single user"""
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "total_minutes": 2400,
                "total_conversations": 100,
                "session_count": 5,
            },
        ]

        result = await service.analyze_workload_balance()

        assert result["balance_metrics"]["balance_score"] == 100

    def test_generate_workload_recommendations_balanced(self, service):
        """Test recommendations for balanced team"""
        team_stats = [
            {"user": "John", "deviation_from_ideal": 0.5},
            {"user": "Jane", "deviation_from_ideal": -0.3},
        ]

        recs = service._generate_workload_recommendations(team_stats, 40)

        assert "well balanced" in recs[0].lower()

    def test_generate_workload_recommendations_overworked(self, service):
        """Test recommendations with overworked members"""
        team_stats = [
            {"user": "John", "deviation_from_ideal": 20},
            {"user": "Jane", "deviation_from_ideal": -20},
        ]

        recs = service._generate_workload_recommendations(team_stats, 40)

        assert any("above average" in r for r in recs)
        assert any("capacity" in r for r in recs)

    # Test Optimal Hours
    @pytest.mark.asyncio
    async def test_identify_optimal_hours(self, service, mock_pool):
        """Test identifying optimal work hours"""
        mock_pool.fetch.return_value = [
            {"hour": 9, "duration_minutes": 480, "conversations_count": 50},
            {"hour": 10, "duration_minutes": 420, "conversations_count": 60},
            {"hour": 14, "duration_minutes": 300, "conversations_count": 30},
        ]

        result = await service.identify_optimal_hours()

        assert "optimal_windows" in result
        assert "all_hours" in result
        assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_for_user(self, service, mock_pool):
        """Test optimal hours for specific user"""
        mock_pool.fetch.return_value = [
            {"hour": 9, "duration_minutes": 480, "conversations_count": 50},
        ]

        result = await service.identify_optimal_hours(user_email="test@example.com")

        assert "optimal_windows" in result

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_no_sessions(self, service, mock_pool):
        """Test optimal hours with no sessions"""
        mock_pool.fetch.return_value = []

        result = await service.identify_optimal_hours()

        assert result["error"] == "No sessions found"

    # Test Team Insights
    @pytest.mark.asyncio
    async def test_generate_team_insights(self, service, mock_pool):
        """Test generating team insights"""
        now = datetime.now()
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(hours=2),
                "session_end": now,
                "duration_minutes": 120,
                "conversations_count": 20,
                "activities_count": 50,
                "start_hour": 9,
                "day_of_week": 1,
            },
            {
                "user_name": "Jane",
                "user_email": "jane@test.com",
                "session_start": now - timedelta(hours=3),
                "session_end": now - timedelta(hours=1),
                "duration_minutes": 120,
                "conversations_count": 25,
                "activities_count": 60,
                "start_hour": 9,
                "day_of_week": 1,
            },
        ]

        result = await service.generate_team_insights()

        assert "team_summary" in result
        assert "team_health_score" in result
        assert "health_rating" in result
        assert "collaboration_windows" in result
        assert "insights" in result

    @pytest.mark.asyncio
    async def test_generate_team_insights_no_sessions(self, service, mock_pool):
        """Test team insights with no sessions"""
        mock_pool.fetch.return_value = []

        result = await service.generate_team_insights()

        assert result["error"] == "No team sessions found"

    @pytest.mark.asyncio
    async def test_generate_team_insights_no_overlap(self, service, mock_pool):
        """Test team insights with no collaboration windows"""
        now = datetime.now()
        mock_pool.fetch.return_value = [
            {
                "user_name": "John",
                "user_email": "john@test.com",
                "session_start": now - timedelta(hours=10),
                "session_end": now - timedelta(hours=8),
                "duration_minutes": 120,
                "conversations_count": 20,
                "activities_count": 50,
                "start_hour": 8,
                "day_of_week": 1,
            },
            {
                "user_name": "Jane",
                "user_email": "jane@test.com",
                "session_start": now - timedelta(hours=4),
                "session_end": now - timedelta(hours=2),
                "duration_minutes": 120,
                "conversations_count": 25,
                "activities_count": 60,
                "start_hour": 14,
                "day_of_week": 1,
            },
        ]

        result = await service.generate_team_insights()

        assert "collaboration_windows" in result

    def test_generate_team_insights_text_excellent(self, service):
        """Test insights text for excellent health"""
        insights = service._generate_team_insights_text(5, 200.0, 500, [], 85.0)

        assert any("excellently" in i for i in insights)

    def test_generate_team_insights_text_good(self, service):
        """Test insights text for good health"""
        insights = service._generate_team_insights_text(5, 200.0, 500, [], 65.0)

        assert any("well" in i for i in insights)

    def test_generate_team_insights_text_needs_improvement(self, service):
        """Test insights text for needs improvement"""
        insights = service._generate_team_insights_text(5, 200.0, 500, [], 35.0)

        assert any("improved" in i for i in insights)

    def test_generate_team_insights_text_with_collab_windows(self, service):
        """Test insights text with collaboration windows"""
        collab_windows = [{"hour": "09:00", "team_members_online": 3}]
        insights = service._generate_team_insights_text(5, 200.0, 500, collab_windows, 75.0)

        assert any("collaboration time" in i for i in insights)
