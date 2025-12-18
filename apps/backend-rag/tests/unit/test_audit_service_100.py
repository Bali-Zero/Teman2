"""
Complete 100% Coverage Tests for Audit Service

Tests all methods and edge cases in audit_service.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests"""
    with patch("services.audit_service.settings") as mock:
        mock.database_url = "postgresql://user:pass@localhost/db"
        yield mock


class TestAuditService:
    """Tests for AuditService class"""

    def test_init_with_database_url(self, mock_settings):
        """Test initialization with provided database URL"""
        from services.audit_service import AuditService

        service = AuditService(database_url="postgresql://custom@localhost/db")

        assert service.database_url == "postgresql://custom@localhost/db"
        assert service.enabled is True
        assert service.pool is None

    def test_init_from_settings(self, mock_settings):
        """Test initialization from settings"""
        from services.audit_service import AuditService

        service = AuditService()

        assert service.database_url == "postgresql://user:pass@localhost/db"
        assert service.enabled is True

    def test_init_no_database_url(self):
        """Test initialization without database URL"""
        from services.audit_service import AuditService

        with patch("services.audit_service.settings") as mock:
            mock.database_url = None
            service = AuditService()

            assert service.enabled is False

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_settings):
        """Test successful database connection"""
        from services.audit_service import AuditService

        service = AuditService()

        with patch(
            "services.audit_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create:
            mock_pool = AsyncMock()
            mock_create.return_value = mock_pool

            await service.connect()

            assert service.pool is mock_pool
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_disabled(self):
        """Test connect when service is disabled"""
        from services.audit_service import AuditService

        with patch("services.audit_service.settings") as mock:
            mock.database_url = None
            service = AuditService()

            await service.connect()

            assert service.pool is None

    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_settings):
        """Test connect handles connection failure"""
        from services.audit_service import AuditService

        service = AuditService()

        with patch("services.audit_service.asyncpg.create_pool") as mock_create:
            mock_create.side_effect = Exception("Connection failed")

            await service.connect()

            assert service.enabled is False
            assert service.pool is None

    @pytest.mark.asyncio
    async def test_close_with_pool(self, mock_settings):
        """Test close with active pool"""
        from services.audit_service import AuditService

        service = AuditService()
        mock_pool = AsyncMock()
        service.pool = mock_pool

        await service.close()

        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_pool(self, mock_settings):
        """Test close without pool"""
        from services.audit_service import AuditService

        service = AuditService()
        service.pool = None

        # Should not raise
        await service.close()

    @pytest.mark.asyncio
    async def test_log_auth_event_success(self, mock_settings):
        """Test successful auth event logging"""
        from services.audit_service import AuditService

        service = AuditService()
        service.enabled = True

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_context_manager)
        service.pool = mock_pool
        service.enabled = True

        await service.log_auth_event(
            email="user@example.com",
            action="login",
            success=True,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            user_id="user-123",
            failure_reason=None,
            metadata={"device": "mobile"},
        )

        mock_conn.execute.assert_called_once()
        # Verify INSERT query was called
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO auth_audit_log" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_log_auth_event_disabled(self):
        """Test auth event logging when disabled"""
        from services.audit_service import AuditService

        with patch("services.audit_service.settings") as mock:
            mock.database_url = None
            service = AuditService()

            # Should not raise
            await service.log_auth_event(email="user@example.com", action="login", success=True)

    @pytest.mark.asyncio
    async def test_log_auth_event_no_pool(self, mock_settings):
        """Test auth event logging without pool"""
        from services.audit_service import AuditService

        service = AuditService()
        service.pool = None

        # Should not raise
        await service.log_auth_event(email="user@example.com", action="login", success=True)

    @pytest.mark.asyncio
    async def test_log_auth_event_failure(self, mock_settings):
        """Test auth event logging handles database error"""
        from services.audit_service import AuditService

        service = AuditService()

        mock_pool = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_pool.acquire = MagicMock(return_value=mock_context_manager)
        service.pool = mock_pool

        # Should not raise
        await service.log_auth_event(email="user@example.com", action="login", success=True)

    @pytest.mark.asyncio
    async def test_log_auth_event_minimal(self, mock_settings):
        """Test auth event logging with minimal params"""
        from services.audit_service import AuditService

        service = AuditService()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_context_manager)
        service.pool = mock_pool
        service.enabled = True

        await service.log_auth_event(email="user@example.com", action="logout", success=True)

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_system_event_success(self, mock_settings):
        """Test successful system event logging"""
        from services.audit_service import AuditService

        service = AuditService()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_context_manager)
        service.pool = mock_pool
        service.enabled = True

        await service.log_system_event(
            event_type="data_access",
            action="read",
            user_id="user-123",
            resource_id="resource-456",
            details={"file": "document.pdf"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO audit_events" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_log_system_event_disabled(self):
        """Test system event logging when disabled"""
        from services.audit_service import AuditService

        with patch("services.audit_service.settings") as mock:
            mock.database_url = None
            service = AuditService()

            # Should not raise
            await service.log_system_event(event_type="data_access", action="read")

    @pytest.mark.asyncio
    async def test_log_system_event_no_pool(self, mock_settings):
        """Test system event logging without pool"""
        from services.audit_service import AuditService

        service = AuditService()
        service.pool = None

        # Should not raise and return silently
        await service.log_system_event(event_type="security_alert", action="detect")

    @pytest.mark.asyncio
    async def test_log_system_event_failure(self, mock_settings):
        """Test system event logging handles database error"""
        from services.audit_service import AuditService

        service = AuditService()

        mock_pool = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_pool.acquire = MagicMock(return_value=mock_context_manager)
        service.pool = mock_pool

        # Should not raise
        await service.log_system_event(event_type="data_access", action="read")

    @pytest.mark.asyncio
    async def test_log_system_event_minimal(self, mock_settings):
        """Test system event logging with minimal params"""
        from services.audit_service import AuditService

        service = AuditService()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_context_manager)
        service.pool = mock_pool
        service.enabled = True

        await service.log_system_event(event_type="security_alert", action="detect")

        mock_conn.execute.assert_called_once()


class TestGetAuditService:
    """Tests for get_audit_service function"""

    def test_get_audit_service_creates_instance(self, mock_settings):
        """Test get_audit_service creates new instance"""
        import services.audit_service as module

        # Reset singleton
        module._audit_service = None

        service = module.get_audit_service()

        assert service is not None
        assert isinstance(service, module.AuditService)

    def test_get_audit_service_returns_singleton(self, mock_settings):
        """Test get_audit_service returns same instance"""
        import services.audit_service as module

        # Reset singleton
        module._audit_service = None

        service1 = module.get_audit_service()
        service2 = module.get_audit_service()

        assert service1 is service2
