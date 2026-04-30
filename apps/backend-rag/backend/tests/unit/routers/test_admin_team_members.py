"""
Unit tests for backend/app/routers/admin_team_members.py

Covers: verify_admin, SetPinRequest validation, set_pin success/404/audit-on-failure.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.routers.admin_team_members import (
    SetPinRequest,
    SetPinResponse,
    set_pin,
    verify_admin,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def admin_user():
    return {"email": "zero@balizero.com", "role": "admin"}


@pytest.fixture
def non_admin_user():
    return {"email": "subhi@balizero.com", "role": "member"}


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()

    # Pool acquire context manager
    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)

    # Connection transaction context manager
    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=None)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_request(mock_db_pool):
    request = MagicMock()
    request.app.state.db_pool = mock_db_pool
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"user-agent": "pytest"}
    return request


# ============================================================================
# SetPinRequest validation
# ============================================================================


class TestSetPinRequest:
    def test_valid_6_digit_pin(self):
        req = SetPinRequest(new_pin="123456")
        assert req.new_pin == "123456"

    def test_pin_too_short(self):
        with pytest.raises(ValidationError):
            SetPinRequest(new_pin="12345")

    def test_pin_too_long(self):
        with pytest.raises(ValidationError):
            SetPinRequest(new_pin="1234567")

    def test_pin_non_numeric_letters(self):
        with pytest.raises(ValidationError) as exc_info:
            SetPinRequest(new_pin="abcdef")
        assert "6 digits" in str(exc_info.value)

    def test_pin_non_numeric_mixed(self):
        with pytest.raises(ValidationError):
            SetPinRequest(new_pin="12345a")

    def test_pin_with_space(self):
        with pytest.raises(ValidationError):
            SetPinRequest(new_pin="123 56")


# ============================================================================
# verify_admin
# ============================================================================


class TestVerifyAdmin:
    @pytest.mark.asyncio
    @patch("backend.app.routers.admin_team_members.is_crm_admin", return_value=True)
    async def test_admin_allowed(self, _mock, admin_user):
        result = await verify_admin(current_user=admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    @patch("backend.app.routers.admin_team_members.is_crm_admin", return_value=False)
    async def test_non_admin_rejected(self, _mock, non_admin_user):
        with pytest.raises(HTTPException) as exc_info:
            await verify_admin(current_user=non_admin_user)
        assert exc_info.value.status_code == 403


# ============================================================================
# set_pin endpoint
# ============================================================================


class TestSetPin:
    @pytest.mark.asyncio
    @patch("backend.app.routers.admin_team_members.get_database_pool")
    @patch("backend.app.routers.admin_team_members.SecurityAuditService")
    async def test_set_pin_success(
        self, mock_audit_cls, mock_get_pool, mock_db_pool, mock_request, admin_user,
    ):
        mock_get_pool.return_value = mock_db_pool
        mock_audit = MagicMock()
        mock_audit.log_event = AsyncMock()
        mock_audit_cls.return_value = mock_audit

        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"id": "uid-123", "email": "subhi@balizero.com"})
        conn.execute = AsyncMock(return_value="UPDATE 1")

        req = SetPinRequest(new_pin="987654")
        resp = await set_pin(
            user_id="uid-123",
            req=req,
            request=mock_request,
            admin=admin_user,
        )

        assert isinstance(resp, SetPinResponse)
        assert resp.status == "ok"
        assert resp.user_id == "uid-123"
        assert resp.email == "subhi@balizero.com"

        # Verify the UPDATE statement received a real bcrypt hash (60-char $2b$ format)
        call_args = conn.execute.call_args
        # First positional arg is the SQL query, second is the bcrypt hash
        bcrypt_hash = call_args[0][1]
        assert bcrypt_hash.startswith("$2b$")
        # Roundtrip check: the stored hash verifies the original PIN
        assert bcrypt.checkpw(b"987654", bcrypt_hash.encode())

        # Audit log called once with success=True
        mock_audit.log_event.assert_called_once()
        kwargs = mock_audit.log_event.call_args.kwargs
        assert kwargs["action"] == "permission_change"
        assert kwargs["resource_type"] == "team_member.pin"
        assert kwargs["resource_id"] == "uid-123"
        assert kwargs["success"] is True
        assert kwargs["details"]["target_email"] == "subhi@balizero.com"

    @pytest.mark.asyncio
    @patch("backend.app.routers.admin_team_members.get_database_pool")
    @patch("backend.app.routers.admin_team_members.SecurityAuditService")
    async def test_set_pin_user_not_found_audits_then_404(
        self, mock_audit_cls, mock_get_pool, mock_db_pool, mock_request, admin_user,
    ):
        mock_get_pool.return_value = mock_db_pool
        mock_audit = MagicMock()
        mock_audit.log_event = AsyncMock()
        mock_audit_cls.return_value = mock_audit

        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        req = SetPinRequest(new_pin="111222")

        with pytest.raises(HTTPException) as exc_info:
            await set_pin(
                user_id="missing-id",
                req=req,
                request=mock_request,
                admin=admin_user,
            )

        assert exc_info.value.status_code == 404

        # Verify audit log fired with success=False BEFORE the 404
        mock_audit.log_event.assert_called_once()
        kwargs = mock_audit.log_event.call_args.kwargs
        assert kwargs["success"] is False
        assert kwargs["details"]["reason"] == "user_not_found"
        assert kwargs["resource_id"] == "missing-id"

        # Crucially: the UPDATE was NEVER executed
        conn.execute.assert_not_called()


# ============================================================================
# Router manifest registration
# ============================================================================


class TestRouterManifest:
    def test_admin_team_members_registered(self):
        """Ensure admin_team_members is in router_manifest with _API process group."""
        from backend.app.setup.router_manifest import ROUTER_MANIFEST

        entries = [e for e in ROUTER_MANIFEST if e.name == "admin_team_members"]
        assert len(entries) == 1, "admin_team_members must be registered exactly once"
        entry = entries[0]
        assert "admin" in entry.tags
        assert "team" in entry.tags
