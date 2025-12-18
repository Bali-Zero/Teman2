"""
Comprehensive tests for AuditService - 100% coverage target
Tests security logging and system audit trails
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAuditServiceInit:
    """Tests for AuditService initialization"""

    def test_init_with_url(self):
        """Test initialization with database URL"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            from services.audit_service import AuditService

            service = AuditService("postgresql://custom")

            assert service.database_url == "postgresql://custom"
            assert service.enabled is True
            assert service.pool is None

    def test_init_with_settings(self):
        """Test initialization with settings URL"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://settings"

            from services.audit_service import AuditService

            service = AuditService()

            assert service.database_url == "postgresql://settings"
            assert service.enabled is True

    def test_init_without_url(self):
        """Test initialization without database URL"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None

            from services.audit_service import AuditService

            service = AuditService()

            assert service.enabled is False


class TestConnect:
    """Tests for connect method"""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            with patch(
                "services.audit_service.asyncpg.create_pool", new_callable=AsyncMock
            ) as mock_pool:
                mock_pool.return_value = MagicMock()

                from services.audit_service import AuditService

                service = AuditService()
                await service.connect()

                assert service.pool is not None
                mock_pool.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_disabled(self):
        """Test connect when disabled"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None

            from services.audit_service import AuditService

            service = AuditService()
            await service.connect()

            assert service.pool is None

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://invalid"

            with patch(
                "services.audit_service.asyncpg.create_pool", new_callable=AsyncMock
            ) as mock_pool:
                mock_pool.side_effect = Exception("Connection failed")

                from services.audit_service import AuditService

                service = AuditService()
                await service.connect()

                assert service.enabled is False


class TestClose:
    """Tests for close method"""

    @pytest.mark.asyncio
    async def test_close_with_pool(self):
        """Test closing with pool"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            from services.audit_service import AuditService

            service = AuditService()
            service.pool = AsyncMock()

            await service.close()

            service.pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_pool(self):
        """Test closing without pool"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            from services.audit_service import AuditService

            service = AuditService()

            # Should not raise
            await service.close()


class TestLogAuthEvent:
    """Tests for log_auth_event method"""

    @pytest.fixture
    def service(self):
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            from services.audit_service import AuditService

            svc = AuditService()
            svc.pool = AsyncMock()
            svc.enabled = True
            return svc

    @pytest.mark.asyncio
    async def test_log_auth_event_success(self, service):
        """Test logging auth event"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        service.pool = AsyncMock()
        service.pool.acquire = MagicMock(return_value=mock_context_manager)
        service.enabled = True

        await service.log_auth_event(
            email="test@example.com",
            action="login",
            success=True,
            ip_address="127.0.0.1",
            user_agent="Test/1.0",
            user_id="user-123",
            metadata={"method": "password"},
        )

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_auth_event_failure_reason(self, service):
        """Test logging auth event with failure reason"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        service.pool = AsyncMock()
        service.pool.acquire = MagicMock(return_value=mock_context_manager)
        service.enabled = True

        await service.log_auth_event(
            email="test@example.com",
            action="failed_login",
            success=False,
            failure_reason="Invalid password",
        )

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_auth_event_disabled(self):
        """Test logging when disabled"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None

            from services.audit_service import AuditService

            service = AuditService()

            # Should not raise
            await service.log_auth_event(email="test@example.com", action="login", success=True)

    @pytest.mark.asyncio
    async def test_log_auth_event_no_pool(self, service):
        """Test logging without pool"""
        service.pool = None

        # Should not raise
        await service.log_auth_event(email="test@example.com", action="login", success=True)

    @pytest.mark.asyncio
    async def test_log_auth_event_error(self, service):
        """Test logging with database error"""
        from tests.conftest import create_async_cm_mock

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))
        service.pool.acquire = MagicMock(return_value=create_async_cm_mock(mock_conn))

        # Should not raise
        await service.log_auth_event(email="test@example.com", action="login", success=True)


class TestLogSystemEvent:
    """Tests for log_system_event method"""

    @pytest.fixture
    def service(self):
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            from services.audit_service import AuditService

            svc = AuditService()
            svc.pool = AsyncMock()
            svc.enabled = True
            return svc

    @pytest.mark.asyncio
    async def test_log_system_event_success(self, service):
        """Test logging system event"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        service.pool.acquire = MagicMock(return_value=mock_context_manager)

        await service.log_system_event(
            event_type="data_access",
            action="read",
            user_id="user-123",
            resource_id="doc-456",
            details={"collection": "visa_oracle"},
            ip_address="127.0.0.1",
            user_agent="Test/1.0",
        )

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_system_event_minimal(self, service):
        """Test logging system event with minimal args"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        service.pool.acquire = MagicMock(return_value=mock_context_manager)

        await service.log_system_event(event_type="security_alert", action="warning")

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_system_event_disabled(self):
        """Test logging when disabled"""
        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = None

            from services.audit_service import AuditService

            service = AuditService()

            # Should not raise and return early
            await service.log_system_event(event_type="data_access", action="read")

    @pytest.mark.asyncio
    async def test_log_system_event_no_pool(self, service):
        """Test logging without pool"""
        service.pool = None

        # Should not raise
        await service.log_system_event(event_type="data_access", action="read")

    @pytest.mark.asyncio
    async def test_log_system_event_error(self, service):
        """Test logging with database error"""
        from tests.conftest import create_async_cm_mock

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))
        service.pool.acquire = MagicMock(return_value=create_async_cm_mock(mock_conn))

        # Should not raise
        await service.log_system_event(event_type="data_access", action="read")


class TestGetAuditService:
    """Tests for get_audit_service function"""

    def test_get_audit_service_creates_instance(self):
        """Test get_audit_service creates instance"""
        from services import audit_service

        # Reset singleton
        audit_service._audit_service = None

        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            result = audit_service.get_audit_service()

            assert result is not None
            assert isinstance(result, audit_service.AuditService)

    def test_get_audit_service_returns_singleton(self):
        """Test get_audit_service returns singleton"""
        from services import audit_service

        # Reset singleton
        audit_service._audit_service = None

        with patch("services.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"

            svc1 = audit_service.get_audit_service()
            svc2 = audit_service.get_audit_service()

            assert svc1 is svc2
