"""
Unit tests for WorkloadBalanceService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.analytics.workload_balance import WorkloadBalanceService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def workload_balance(mock_db_pool):
    """Create WorkloadBalanceService instance"""
    return WorkloadBalanceService(db_pool=mock_db_pool)


class TestWorkloadBalanceService:
    """Tests for WorkloadBalanceService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = WorkloadBalanceService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_analyze_workload_balance_no_sessions(self, workload_balance, mock_db_pool):
        """Test analyzing workload balance with no sessions"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await workload_balance.analyze_workload_balance()
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_analyze_workload_balance_with_sessions(self, workload_balance, mock_db_pool):
        """Test analyzing workload balance with sessions"""
        from unittest.mock import MagicMock
        session1 = MagicMock()
        session1.__getitem__ = lambda self, key: {
            "user_name": "User 1",
            "user_email": "user1@example.com",
            "total_minutes": 480,
            "total_conversations": 30,
            "session_count": 1
        }.get(key)
        session2 = MagicMock()
        session2.__getitem__ = lambda self, key: {
            "user_name": "User 2",
            "user_email": "user2@example.com",
            "total_minutes": 240,
            "total_conversations": 15,
            "session_count": 1
        }.get(key)
        sessions = [session1, session2]
        mock_db_pool.fetch = AsyncMock(return_value=sessions)
        results = await workload_balance.analyze_workload_balance()
        assert isinstance(results, dict)
        assert "team_distribution" in results or "balance_metrics" in results

    @pytest.mark.asyncio
    async def test_analyze_workload_balance_custom_days(self, workload_balance, mock_db_pool):
        """Test analyzing workload balance with custom days"""
        mock_db_pool.fetch = AsyncMock(return_value=[])
        results = await workload_balance.analyze_workload_balance(days=14)
        assert isinstance(results, dict)

