import pytest

from backend.app.utils.crm_utils import (
    can_view_all_clients,
    is_active_tax_department_member,
    is_crm_admin,
)


class TestIsCrmAdmin:
    def test_admin_email_is_admin(self):
        user = {"email": "zero@balizero.com", "role": "admin"}
        assert is_crm_admin(user) is True

    def test_team_member_is_not_admin(self):
        user = {"email": "surya@balizero.com", "role": "user"}
        assert is_crm_admin(user) is False

    def test_client_is_not_admin(self):
        user = {"email": "client@example.com", "role": "client"}
        assert is_crm_admin(user) is False

    def test_asya_is_admin(self):
        user = {"email": "asya@balizero.com", "role": "user"}
        assert is_crm_admin(user) is True

    def test_founder_role_is_admin(self):
        user = {"email": "someone@balizero.com", "role": "founder"}
        assert is_crm_admin(user) is True

    def test_none_user_is_not_admin(self):
        assert is_crm_admin(None) is False


class TestCanViewAllClients:
    def test_admin_can_view_all(self):
        user = {"email": "zero@balizero.com", "role": "admin"}
        assert can_view_all_clients(user) is True

    def test_asya_can_view_all(self):
        user = {"email": "asya@balizero.com", "role": "user"}
        assert can_view_all_clients(user) is True

    def test_team_member_can_view_all(self):
        user = {"email": "surya@balizero.com", "role": "user"}
        assert can_view_all_clients(user) is True

    def test_founder_role_can_view_all(self):
        user = {"email": "someone@balizero.com", "role": "founder"}
        assert can_view_all_clients(user) is True

    def test_none_user_cannot_view_all(self):
        assert can_view_all_clients(None) is False


class _FakeConn:
    """Minimal async fetchrow stand-in — returns a fixed row (or None)."""

    def __init__(self, row: dict | None) -> None:
        self._row = row

    async def fetchrow(self, *_args, **_kwargs):
        return self._row


class TestIsActiveTaxDepartmentMember:
    """Guilt+innocence for the tax-department portal-invite widening
    (Zero, 2026-09-14). Judged on the `team_members.department` COLUMN, never
    on the email's shape — none of these cases carry a `.tax@` address."""

    @pytest.mark.asyncio
    async def test_active_tax_member_passes(self):
        user = {"email": "kadek.tax@balizero.com"}
        conn = _FakeConn({"department": "tax", "active": True})
        assert await is_active_tax_department_member(user, conn) is True

    @pytest.mark.asyncio
    async def test_inactive_tax_member_fails(self):
        user = {"email": "kadek.tax@balizero.com"}
        conn = _FakeConn({"department": "tax", "active": False})
        assert await is_active_tax_department_member(user, conn) is False

    @pytest.mark.asyncio
    async def test_department_spelled_differently_fails(self):
        """Exact-match on the normalised value, not a substring — "Tax Team"
        must not pass just because it contains "tax" (scar #3: guard the
        entity, never a substring of it)."""
        user = {"email": "someone@balizero.com"}
        conn = _FakeConn({"department": "Tax Team", "active": True})
        assert await is_active_tax_department_member(user, conn) is False

    @pytest.mark.asyncio
    async def test_department_case_and_whitespace_are_normalised(self):
        user = {"email": "dewaayu.tax@balizero.com"}
        conn = _FakeConn({"department": " TAX ", "active": True})
        assert await is_active_tax_department_member(user, conn) is True

    @pytest.mark.asyncio
    async def test_non_tax_department_fails(self):
        user = {"email": "surya@balizero.com"}
        conn = _FakeConn({"department": "marketing", "active": True})
        assert await is_active_tax_department_member(user, conn) is False

    @pytest.mark.asyncio
    async def test_no_team_members_row_fails(self):
        """A client role never resolves to a team_members row keyed on this
        email in practice, and a missing row must fail closed either way."""
        user = {"email": "client@example.com"}
        conn = _FakeConn(None)
        assert await is_active_tax_department_member(user, conn) is False

    @pytest.mark.asyncio
    async def test_no_email_fails(self):
        conn = _FakeConn({"department": "tax", "active": True})
        assert await is_active_tax_department_member({}, conn) is False

    @pytest.mark.asyncio
    async def test_none_user_fails(self):
        conn = _FakeConn({"department": "tax", "active": True})
        assert await is_active_tax_department_member(None, conn) is False
