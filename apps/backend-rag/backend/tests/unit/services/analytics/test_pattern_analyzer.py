"""
Unit tests for PatternAnalyzerService
Target: >95% coverage
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.analytics.pattern_analyzer import PatternAnalyzerService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def pattern_analyzer(mock_db_pool):
    """Create PatternAnalyzerService instance"""
    return PatternAnalyzerService(db_pool=mock_db_pool)


class TestPatternAnalyzerService:
    """Tests for PatternAnalyzerService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = PatternAnalyzerService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_no_sessions(self, pattern_analyzer, mock_db_pool):
        """Test analyzing work patterns with no sessions"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await pattern_analyzer.analyze_work_patterns()
        assert isinstance(results, dict)
        assert "error" in results

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_with_sessions(self, pattern_analyzer, mock_db_pool):
        """Test analyzing work patterns with sessions"""
        from unittest.mock import MagicMock
        session = MagicMock()
        session.__getitem__ = lambda self, key: {
            "session_start": datetime.now(),
            "duration_minutes": 60,
            "day_of_week": 1,
            "start_hour": 9.0
        }.get(key)
        sessions = [session]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await pattern_analyzer.analyze_work_patterns()
        assert isinstance(results, dict)
        assert "patterns" in results

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_with_user_email(self, pattern_analyzer, mock_db_pool):
        """Test analyzing work patterns for specific user"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await pattern_analyzer.analyze_work_patterns(user_email="test@example.com")
        assert isinstance(results, dict)
        mock_db_pool.fetch.assert_called_once()

