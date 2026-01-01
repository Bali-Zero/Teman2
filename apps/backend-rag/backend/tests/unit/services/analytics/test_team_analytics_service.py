"""
Unit tests for TeamAnalyticsService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.analytics.team_analytics_service import TeamAnalyticsService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def team_analytics(mock_db_pool):
    """Create TeamAnalyticsService instance"""
    return TeamAnalyticsService(db_pool=mock_db_pool)


class TestTeamAnalyticsService:
    """Tests for TeamAnalyticsService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = TeamAnalyticsService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool
        assert service.pattern_analyzer is not None
        assert service.productivity_scorer is not None
        assert service.burnout_detector is not None

    @pytest.mark.asyncio
    async def test_analyze_work_patterns(self, team_analytics):
        """Test analyzing work patterns"""
        team_analytics.pattern_analyzer.analyze_work_patterns = AsyncMock(return_value={"patterns": {}})
        results = await team_analytics.analyze_work_patterns()
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores(self, team_analytics):
        """Test calculating productivity scores"""
        team_analytics.productivity_scorer.calculate_productivity_scores = AsyncMock(return_value=[])
        results = await team_analytics.calculate_productivity_scores()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_detect_burnout_signals(self, team_analytics):
        """Test detecting burnout signals"""
        team_analytics.burnout_detector.detect_burnout_signals = AsyncMock(return_value=[])
        results = await team_analytics.detect_burnout_signals()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_analyze_performance_trends(self, team_analytics):
        """Test analyzing performance trends"""
        team_analytics.performance_trend.analyze_performance_trends = AsyncMock(return_value={"trend": {}})
        results = await team_analytics.analyze_performance_trends("test@example.com")
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_analyze_workload_balance(self, team_analytics):
        """Test analyzing workload balance"""
        team_analytics.workload_balance.analyze_workload_balance = AsyncMock(return_value={"balance": {}})
        results = await team_analytics.analyze_workload_balance()
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_identify_optimal_hours(self, team_analytics):
        """Test identifying optimal hours"""
        team_analytics.optimal_hours.identify_optimal_hours = AsyncMock(return_value={"optimal_windows": []})
        results = await team_analytics.identify_optimal_hours()
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_generate_team_insights(self, team_analytics):
        """Test generating team insights"""
        team_analytics.team_insights.generate_team_insights = AsyncMock(return_value={"team_summary": {}})
        results = await team_analytics.generate_team_insights()
        assert isinstance(results, dict)

