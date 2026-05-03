"""
Tests for AuditService - security logging and system audit trails.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm
    pool.close = AsyncMock()
    return pool, conn


class TestAuditService:
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """connect() should create a connection pool."""
        with patch("backend.services.monitoring.audit_service.asyncpg") as mock_asyncpg, \
             patch("backend.services.monitoring.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
            mock_asyncpg.create_pool = AsyncMock(return_value=MagicMock())

            from backend.services.monitoring.audit_service import AuditService
            svc = AuditService(database_url="postgresql://test:test@localhost:5432/test")
            await svc.connect()

            mock_asyncpg.create_pool.assert_awaited_once()
            assert svc.pool is not None

    @pytest.mark.asyncio
    async def test_log_auth_event_success(self, mock_pool):
        """log_auth_event should insert into auth_audit_log."""
        pool, conn = mock_pool
        with patch("backend.services.monitoring.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test@localhost/test"
            from backend.services.monitoring.audit_service import AuditService
            svc = AuditService(database_url="postgresql://test@localhost/test")
            svc.pool = pool
            svc.enabled = True

            await svc.log_auth_event(
                email="test@balizero.com",
                action="login",
                success=True,
                ip_address="127.0.0.1",
                user_agent="TestAgent/1.0",
            )
            conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_system_event_success(self, mock_pool):
        """log_system_event should insert into system_audit_log."""
        pool, conn = mock_pool
        with patch("backend.services.monitoring.audit_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test@localhost/test"
            from backend.services.monitoring.audit_service import AuditService
            svc = AuditService(database_url="postgresql://test@localhost/test")
            svc.pool = pool
            svc.enabled = True

            await svc.log_system_event(
                event_type="deployment",
                action="deploy",
                details={"message": "Deployment successful"},
            )
            conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_auth_event_disabled(self):
        """log_auth_event should skip when disabled."""
        with patch("backend.services.monitoring.audit_service.settings") as mock_settings:
            mock_settings.database_url = None
            from backend.services.monitoring.audit_service import AuditService
            svc = AuditService(database_url=None)
            svc.enabled = False
            # Should not raise
            await svc.log_auth_event("test@example.com", "login", True)
