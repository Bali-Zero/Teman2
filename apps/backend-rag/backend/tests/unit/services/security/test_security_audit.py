"""Tests for security audit trail service — S03 Sprint 2."""

from unittest.mock import AsyncMock

import pytest


class TestSecurityAuditService:
    """Test security event logging."""

    @pytest.mark.asyncio
    async def test_log_event_inserts_row(self):
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        svc = SecurityAuditService()
        await svc.log_event(
            conn=mock_conn,
            action="login",
            user_email="zero@balizero.com",
            ip_address="1.2.3.4",
            success=True,
            details={"method": "pin"},
        )
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        call_sql = call_args[0]
        assert "INSERT INTO security_audit_log" in call_sql
        assert call_args[9] == {"method": "pin"}
        assert not isinstance(call_args[9], str)

    @pytest.mark.asyncio
    async def test_log_event_with_resource(self):
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        svc = SecurityAuditService()
        await svc.log_event(
            conn=mock_conn,
            action="token_revoke",
            user_email="zero@balizero.com",
            resource_type="token",
            resource_id="jti-123",
            success=True,
        )
        call_args = mock_conn.execute.call_args[0]
        assert call_args[3] == "token_revoke"
        assert call_args[9] is None

    @pytest.mark.asyncio
    async def test_log_event_handles_db_error_gracefully(self):
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB down"))
        svc = SecurityAuditService()
        # Should NOT raise
        await svc.log_event(
            conn=mock_conn,
            action="login",
            user_email="zero@balizero.com",
            success=True,
        )
        assert mock_conn.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_log_rbac_violation(self):
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        svc = SecurityAuditService()
        await svc.log_event(
            conn=mock_conn,
            action="rbac_violation",
            user_email="team@balizero.com",
            resource_type="practice",
            resource_id="42",
            success=False,
            details={"attempted": "view", "required_role": "admin"},
        )
        call_args = mock_conn.execute.call_args[0]
        assert call_args[3] == "rbac_violation"
        assert call_args[8] is False
