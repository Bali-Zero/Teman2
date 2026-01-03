"""
Unit tests for PortalService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.portal.portal_service import PortalService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    conn = AsyncMock()
    mock_client = MagicMock()
    mock_client.__getitem__ = lambda self, key: {"id": 1, "full_name": "Test Client", "email": "test@example.com"}.get(key)
    conn.fetchrow = AsyncMock(return_value=mock_client)
    conn.fetch = AsyncMock(return_value=[])
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=conn)
    return pool


@pytest.fixture
def portal_service(mock_db_pool):
    """Create PortalService instance"""
    return PortalService(pool=mock_db_pool)


class TestPortalService:
    """Tests for PortalService"""

    def test_init(self, portal_service):
        """Test initialization"""
        assert portal_service.pool is not None

    @pytest.mark.asyncio
    async def test_get_dashboard(self, portal_service, mock_db_pool):
        """Test getting dashboard"""
        mock_conn = AsyncMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {"id": 1, "full_name": "Test Client", "email": "test@example.com"}.get(key)
        mock_conn.fetchrow = AsyncMock(return_value=mock_client)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await portal_service.get_dashboard(1)
        assert isinstance(result, dict)
        assert "visa" in result
        assert "company" in result

    @pytest.mark.asyncio
    async def test_get_dashboard_client_not_found(self, portal_service, mock_db_pool):
        """Test getting dashboard for non-existent client"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        with pytest.raises(ValueError):
            await portal_service.get_dashboard(999)




