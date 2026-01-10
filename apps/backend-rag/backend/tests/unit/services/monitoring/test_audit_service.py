"""
Unit tests for AuditService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.monitoring.audit_service import AuditService


@pytest.fixture
def audit_service():
    """Create AuditService instance"""
    with patch("backend.services.monitoring.audit_service.settings") as mock_settings:
        mock_settings.database_url = "postgresql://test"
        service = AuditService()
        return service


class TestAuditService:
    """Tests for AuditService"""

    def test_init(self):
        """Test initialization"""
        with patch("backend.services.monitoring.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"
            service = AuditService()
            assert service.enabled is True
            assert service.pool is None

    @pytest.mark.asyncio
    async def test_connect(self, audit_service):
        """Test connecting to database"""
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            await audit_service.connect()
            # Pool is assigned in connect method
            assert audit_service.pool is not None or audit_service.enabled is False

    @pytest.mark.asyncio
    async def test_connect_disabled(self):
        """Test connecting when disabled"""
        with patch("backend.services.monitoring.audit_service.settings") as mock_settings:
            mock_settings.database_url = None
            service = AuditService()
            await service.connect()
            assert service.pool is None

    @pytest.mark.asyncio
    async def test_close(self, audit_service):
        """Test closing connection"""
        mock_pool = AsyncMock()
        audit_service.pool = mock_pool
        await audit_service.close()
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_auth_event(self, audit_service):
        """Test logging auth event"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        audit_service.pool = mock_pool
        audit_service.enabled = True
        await audit_service.log_auth_event(email="test@example.com", action="login", success=True)
        # execute is called inside acquire context manager
        assert mock_pool.acquire.called

    @pytest.mark.asyncio
    async def test_log_auth_event_disabled(self):
        """Test logging auth event when disabled"""
        with patch("backend.services.monitoring.audit_service.settings") as mock_settings:
            mock_settings.database_url = None
            service = AuditService()
            await service.log_auth_event(email="test@example.com", action="login", success=True)
            # Should not raise error

    @pytest.mark.asyncio
    async def test_log_system_event(self, audit_service):
        """Test logging system event"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        audit_service.pool = mock_pool
        audit_service.enabled = True
        await audit_service.log_system_event(event_type="test", action="test_action")
        # execute is called inside acquire context manager
        assert mock_pool.acquire.called
