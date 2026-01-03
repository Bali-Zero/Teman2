"""
Unit tests for team_analytics router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.dependencies import get_database_pool
from app.routers.team_analytics import get_team_analytics_service, router
from services.analytics.team_analytics_service import TeamAnalyticsService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return MagicMock()


@pytest.fixture
def mock_team_analytics_service():
    """Mock TeamAnalyticsService"""
    service = MagicMock(spec=TeamAnalyticsService)
    service.analyze_work_patterns = AsyncMock(return_value={"patterns": []})
    service.calculate_productivity_scores = AsyncMock(return_value={"scores": []})
    service.detect_burnout_signals = AsyncMock(return_value={"signals": []})
    service.analyze_performance_trends = AsyncMock(return_value={"trends": []})
    service.analyze_workload_balance = AsyncMock(return_value={"balance": []})
    return service


@pytest.fixture
def app(mock_db_pool, mock_team_analytics_service):
    """Create FastAPI app with router and dependency overrides"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    app.dependency_overrides[get_team_analytics_service] = lambda: mock_team_analytics_service
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestTeamAnalyticsRouter:
    """Tests for team_analytics router"""

    def test_get_work_patterns(self, client, mock_team_analytics_service):
        """Test getting work patterns"""
        response = client.get("/api/team-analytics/patterns")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        mock_team_analytics_service.analyze_work_patterns.assert_called_once()

    def test_get_work_patterns_with_email(self, client, mock_team_analytics_service):
        """Test getting work patterns with email filter"""
        response = client.get("/api/team-analytics/patterns?user_email=test@example.com")
        assert response.status_code == 200
        mock_team_analytics_service.analyze_work_patterns.assert_called_with("test@example.com", 30)

    def test_get_work_patterns_with_days(self, client, mock_team_analytics_service):
        """Test getting work patterns with custom days"""
        response = client.get("/api/team-analytics/patterns?days=60")
        assert response.status_code == 200
        mock_team_analytics_service.analyze_work_patterns.assert_called_with(None, 60)

    def test_get_work_patterns_error(self, client, mock_team_analytics_service):
        """Test getting work patterns with error"""
        mock_team_analytics_service.analyze_work_patterns = AsyncMock(side_effect=Exception("Error"))
        response = client.get("/api/team-analytics/patterns")
        assert response.status_code == 500

    def test_get_productivity_scores(self, client, mock_team_analytics_service):
        """Test getting productivity scores"""
        response = client.get("/api/team-analytics/productivity")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "scores" in data
        mock_team_analytics_service.calculate_productivity_scores.assert_called_once_with(7)

    def test_get_productivity_scores_with_days(self, client, mock_team_analytics_service):
        """Test getting productivity scores with custom days"""
        response = client.get("/api/team-analytics/productivity?days=14")
        assert response.status_code == 200
        mock_team_analytics_service.calculate_productivity_scores.assert_called_with(14)

    def test_get_productivity_scores_error(self, client, mock_team_analytics_service):
        """Test getting productivity scores with error"""
        mock_team_analytics_service.calculate_productivity_scores = AsyncMock(side_effect=Exception("Error"))
        response = client.get("/api/team-analytics/productivity")
        assert response.status_code == 500

    def test_get_burnout_signals(self, client, mock_team_analytics_service):
        """Test getting burnout signals"""
        response = client.get("/api/team-analytics/burnout")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "signals" in data
        mock_team_analytics_service.detect_burnout_signals.assert_called_once_with(None)

    def test_get_burnout_signals_with_email(self, client, mock_team_analytics_service):
        """Test getting burnout signals with email filter"""
        response = client.get("/api/team-analytics/burnout?user_email=test@example.com")
        assert response.status_code == 200
        mock_team_analytics_service.detect_burnout_signals.assert_called_with("test@example.com")

    def test_get_burnout_signals_error(self, client, mock_team_analytics_service):
        """Test getting burnout signals with error"""
        mock_team_analytics_service.detect_burnout_signals = AsyncMock(side_effect=Exception("Error"))
        response = client.get("/api/team-analytics/burnout")
        assert response.status_code == 500

    def test_get_performance_trends(self, client, mock_team_analytics_service):
        """Test getting performance trends"""
        response = client.get("/api/team-analytics/trends/test@example.com")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "trends" in data
        mock_team_analytics_service.analyze_performance_trends.assert_called_once_with("test@example.com", 4)

    def test_get_performance_trends_with_weeks(self, client, mock_team_analytics_service):
        """Test getting performance trends with custom weeks"""
        response = client.get("/api/team-analytics/trends/test@example.com?weeks=8")
        assert response.status_code == 200
        mock_team_analytics_service.analyze_performance_trends.assert_called_with("test@example.com", 8)

    def test_get_performance_trends_error(self, client, mock_team_analytics_service):
        """Test getting performance trends with error"""
        mock_team_analytics_service.analyze_performance_trends = AsyncMock(side_effect=Exception("Error"))
        response = client.get("/api/team-analytics/trends/test@example.com")
        assert response.status_code == 500

    def test_get_workload_balance(self, client, mock_team_analytics_service):
        """Test getting workload balance"""
        response = client.get("/api/team-analytics/workload-balance")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "balance" in data
        mock_team_analytics_service.analyze_workload_balance.assert_called_once_with(7)

    def test_get_workload_balance_with_days(self, client, mock_team_analytics_service):
        """Test getting workload balance with custom days"""
        response = client.get("/api/team-analytics/workload-balance?days=14")
        assert response.status_code == 200
        mock_team_analytics_service.analyze_workload_balance.assert_called_with(14)

    def test_get_workload_balance_error(self, client, mock_team_analytics_service):
        """Test getting workload balance with error"""
        mock_team_analytics_service.analyze_workload_balance = AsyncMock(side_effect=Exception("Error"))
        response = client.get("/api/team-analytics/workload-balance")
        assert response.status_code == 500





