"""
Comprehensive tests for services/audit_service.py
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, patch

import pytest

from services.audit_service import AuditService


class TestAuditService:
    """Comprehensive test suite for AuditService"""

    @pytest.fixture
    def mock_pool(self):
        """Mock asyncpg pool"""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        pool.acquire.return_value.__aexit__.return_value = None
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock()
        return pool, conn

    @pytest.fixture
    def audit_service(self):
        """Create AuditService instance"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"
            return AuditService()

    def test_init_with_url(self):
        """Test AuditService initialization with URL"""
        service = AuditService(database_url="postgresql://test")
        assert service.database_url == "postgresql://test"
        assert service.enabled is True

    def test_init_without_url(self):
        """Test AuditService initialization without URL"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None
            service = AuditService()
            assert service.enabled is False

    @pytest.mark.asyncio
    async def test_connect_success(self, audit_service, mock_pool):
        """Test connect success"""
        pool, conn = mock_pool
        with patch("services.audit_service.asyncpg.create_pool", return_value=pool):
            await audit_service.connect()
            assert audit_service.pool == pool

    @pytest.mark.asyncio
    async def test_connect_error(self, audit_service):
        """Test connect error"""
        with patch("services.audit_service.asyncpg.create_pool", side_effect=Exception("Error")):
            await audit_service.connect()
            assert audit_service.enabled is False

    @pytest.mark.asyncio
    async def test_connect_disabled(self):
        """Test connect when disabled"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None
            service = AuditService()
            await service.connect()
            assert service.pool is None

    @pytest.mark.asyncio
    async def test_close(self, audit_service, mock_pool):
        """Test close"""
        pool, conn = mock_pool
        audit_service.pool = pool
        await audit_service.close()
        pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_auth_event_success(self, audit_service, mock_pool):
        """Test log_auth_event success"""
        pool, conn = mock_pool
        audit_service.pool = pool
        audit_service.enabled = True
        await audit_service.log_auth_event(
            email="test@example.com",
            action="login",
            success=True,
            ip_address="127.0.0.1",
        )
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_auth_event_disabled(self):
        """Test log_auth_event when disabled"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None
            service = AuditService()
            await service.log_auth_event(email="test@example.com", action="login", success=True)
            # Should not raise error

    @pytest.mark.asyncio
    async def test_log_auth_event_no_pool(self, audit_service):
        """Test log_auth_event without pool"""
        audit_service.pool = None
        await audit_service.log_auth_event(email="test@example.com", action="login", success=True)
        # Should not raise error

    @pytest.mark.asyncio
    async def test_log_auth_event_error(self, audit_service, mock_pool):
        """Test log_auth_event with error"""
        pool, conn = mock_pool
        conn.execute.side_effect = Exception("Error")
        audit_service.pool = pool
        await audit_service.log_auth_event(email="test@example.com", action="login", success=True)
        # Should not raise error

    @pytest.mark.asyncio
    async def test_log_system_event_success(self, audit_service, mock_pool):
        """Test log_system_event success"""
        pool, conn = mock_pool
        audit_service.pool = pool
        audit_service.enabled = True
        await audit_service.log_system_event(
            event_type="test", action="test_action", user_id="user123"
        )
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_system_event_disabled(self):
        """Test log_system_event when disabled"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None
            service = AuditService()
            await service.log_system_event(event_type="test", action="test_action")

    @pytest.mark.asyncio
    async def test_get_audit_service(self):
        """Test get_audit_service singleton"""
        from services.audit_service import get_audit_service

        service = get_audit_service()
        assert isinstance(service, AuditService)
