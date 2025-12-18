"""
API Tests for Team Analytics Router - Coverage 95% Target
Tests all team analytics endpoints and edge cases

Coverage:
- GET /api/team-analytics/patterns - Work patterns analysis
- GET /api/team-analytics/productivity - Productivity scores
- GET /api/team-analytics/burnout - Burnout detection
- GET /api/team-analytics/trends/{user_email} - Performance trends
- GET /api/team-analytics/workload-balance - Workload balance
- GET /api/team-analytics/optimal-hours - Optimal hours identification
- GET /api/team-analytics/team-insights - Team insights
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
# Test Work Patterns
# ============================================================================


class TestWorkPatterns:
    """Test suite for GET /api/team-analytics/patterns"""

    def test_get_work_patterns_success(self, authenticated_client):
        """Test successful work patterns analysis"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.analyze_work_patterns = AsyncMock(
                return_value={
                    "patterns": {
                        "avg_start_hour": 9.5,
                        "preferred_start_time": "09:30",
                        "avg_session_duration_hours": 4.5,
                    },
                    "consistency_score": 75.0,
                    "total_sessions_analyzed": 20,
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/patterns?days=30")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data

    def test_get_work_patterns_with_user(self, authenticated_client):
        """Test work patterns with user filter"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.analyze_work_patterns = AsyncMock(return_value={"patterns": {}})
            mock_get.return_value = mock_service

            response = authenticated_client.get(
                "/api/team-analytics/patterns?user_email=test@example.com&days=60"
            )

            assert response.status_code == 200
            mock_service.analyze_work_patterns.assert_called_once_with("test@example.com", 60)

    def test_get_work_patterns_no_sessions(self, authenticated_client):
        """Test work patterns with no sessions"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.analyze_work_patterns = AsyncMock(
                return_value={"error": "No sessions found"}
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/patterns")

            assert response.status_code == 200
            data = response.json()
            assert "error" in data["data"]


# ============================================================================
# Test Productivity Scores
# ============================================================================


class TestProductivityScores:
    """Test suite for GET /api/team-analytics/productivity"""

    def test_get_productivity_scores_success(self, authenticated_client):
        """Test successful productivity scores retrieval"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.calculate_productivity_scores = AsyncMock(
                return_value=[
                    {
                        "user": "User 1",
                        "email": "user1@example.com",
                        "productivity_score": 85.5,
                        "rating": "Excellent",
                    }
                ]
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/productivity?days=7")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "scores" in data
            assert len(data["scores"]) == 1

    def test_get_productivity_scores_empty(self, authenticated_client):
        """Test productivity scores with no data"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.calculate_productivity_scores = AsyncMock(return_value=[])
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/productivity")

            assert response.status_code == 200
            data = response.json()
            assert data["scores"] == []


# ============================================================================
# Test Burnout Signals
# ============================================================================


class TestBurnoutSignals:
    """Test suite for GET /api/team-analytics/burnout"""

    def test_get_burnout_signals_success(self, authenticated_client):
        """Test successful burnout detection"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.detect_burnout_signals = AsyncMock(
                return_value=[
                    {
                        "user": "User 1",
                        "email": "user1@example.com",
                        "burnout_risk_score": 65,
                        "risk_level": "High Risk",
                        "warning_signals": ["Warning 1", "Warning 2"],
                    }
                ]
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/burnout")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "signals" in data

    def test_get_burnout_signals_with_user(self, authenticated_client):
        """Test burnout detection with user filter"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.detect_burnout_signals = AsyncMock(return_value=[])
            mock_get.return_value = mock_service

            response = authenticated_client.get(
                "/api/team-analytics/burnout?user_email=test@example.com"
            )

            assert response.status_code == 200
            mock_service.detect_burnout_signals.assert_called_once_with("test@example.com")


# ============================================================================
# Test Performance Trends
# ============================================================================


class TestPerformanceTrends:
    """Test suite for GET /api/team-analytics/trends/{user_email}"""

    def test_get_performance_trends_success(self, authenticated_client):
        """Test successful performance trends retrieval"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.analyze_performance_trends = AsyncMock(
                return_value={
                    "weekly_breakdown": [{"week": "2024-W01", "hours": 40.0, "conversations": 100}],
                    "trend": {"direction": "Increasing"},
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get(
                "/api/team-analytics/trends/test@example.com?weeks=4"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "trends" in data

    def test_get_performance_trends_no_sessions(self, authenticated_client):
        """Test performance trends with no sessions"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.analyze_performance_trends = AsyncMock(
                return_value={"error": "No sessions found"}
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/trends/test@example.com")

            assert response.status_code == 200
            data = response.json()
            assert "error" in data["trends"]


# ============================================================================
# Test Workload Balance
# ============================================================================


class TestWorkloadBalance:
    """Test suite for GET /api/team-analytics/workload-balance"""

    def test_get_workload_balance_success(self, authenticated_client):
        """Test successful workload balance analysis"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.analyze_workload_balance = AsyncMock(
                return_value={
                    "team_distribution": [
                        {"user": "User 1", "hours": 40.0, "hours_share_percent": 50.0}
                    ],
                    "balance_metrics": {"balance_score": 85.0, "balance_rating": "Well Balanced"},
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/workload-balance?days=7")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "balance" in data

    def test_get_workload_balance_no_sessions(self, authenticated_client):
        """Test workload balance with no sessions"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.analyze_workload_balance = AsyncMock(
                return_value={"error": "No sessions found"}
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/workload-balance")

            assert response.status_code == 200
            data = response.json()
            assert "error" in data["balance"]


# ============================================================================
# Test Optimal Hours
# ============================================================================


class TestOptimalHours:
    """Test suite for GET /api/team-analytics/optimal-hours"""

    def test_get_optimal_hours_success(self, authenticated_client):
        """Test successful optimal hours identification"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.identify_optimal_hours = AsyncMock(
                return_value={
                    "optimal_windows": [{"hour": "09:00", "conversations_per_hour": 5.5}],
                    "recommendation": "Most productive: 09:00",
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/optimal-hours?days=30")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "optimal_hours" in data

    def test_get_optimal_hours_with_user(self, authenticated_client):
        """Test optimal hours with user filter"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.identify_optimal_hours = AsyncMock(return_value={"optimal_windows": []})
            mock_get.return_value = mock_service

            response = authenticated_client.get(
                "/api/team-analytics/optimal-hours?user_email=test@example.com"
            )

            assert response.status_code == 200
            mock_service.identify_optimal_hours.assert_called_once_with("test@example.com", 30)


# ============================================================================
# Test Team Insights
# ============================================================================


class TestTeamInsights:
    """Test suite for GET /api/team-analytics/team-insights"""

    def test_get_team_insights_success(self, authenticated_client):
        """Test successful team insights generation"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.generate_team_insights = AsyncMock(
                return_value={
                    "team_summary": {
                        "active_members": 5,
                        "total_hours_worked": 200.0,
                        "total_conversations": 500,
                    },
                    "team_health_score": 85.0,
                    "health_rating": "Excellent",
                    "collaboration_windows": [],
                    "insights": ["Insight 1", "Insight 2"],
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/team-insights?days=7")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "insights" in data

    def test_get_team_insights_no_sessions(self, authenticated_client):
        """Test team insights with no sessions"""
        with patch("app.routers.team_analytics.get_team_analytics_service") as mock_get:
            mock_service = MagicMock()
            mock_service.generate_team_insights = AsyncMock(
                return_value={"error": "No team sessions found"}
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/team-analytics/team-insights")

            assert response.status_code == 200
            data = response.json()
            assert "error" in data["insights"]
