"""
Unit tests for CRM Assignment services.

Tests ClientIdentityResolver, normalize_phone, check_duplicates,
assign_lead, send_telegram_notification, and workflow creation.
"""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


def _make_pool(conn=None):
    pool = MagicMock()
    conn = conn or AsyncMock()

    class _Ctx:
        async def __aenter__(self): return conn
        async def __aexit__(self, *a): pass

    pool.acquire = MagicMock(return_value=_Ctx())
    pool._conn = conn
    return pool, conn


class TestNormalizePhone:
    def test_none_returns_none(self):
        from backend.services.crm.assignment import normalize_phone
        assert normalize_phone(None) is None

    def test_empty_returns_none(self):
        from backend.services.crm.assignment import normalize_phone
        assert normalize_phone("") is None

    def test_delegates_to_e164(self):
        from backend.services.crm.assignment import normalize_phone
        with patch("backend.services.crm.assignment.normalize_phone_e164", return_value="+6281234567890"):
            assert normalize_phone("+62 812 3456 7890") == "+6281234567890"


@pytest.mark.asyncio
class TestClientIdentityResolver:
    def _make_resolver(self, conn=None):
        pool, conn = _make_pool(conn)
        from backend.services.crm.assignment import ClientIdentityResolver
        return ClientIdentityResolver(pool), pool, conn

    async def test_find_by_telegram_found(self):
        conn = AsyncMock(); conn.fetchval.return_value = 42
        resolver, _, _ = self._make_resolver(conn)
        assert await resolver.find_client_by_telegram("12345") == 42

    async def test_find_by_telegram_not_found(self):
        conn = AsyncMock(); conn.fetchval.return_value = None
        resolver, _, _ = self._make_resolver(conn)
        assert await resolver.find_client_by_telegram("99999") is None

    async def test_find_by_whatsapp_messaging_users(self):
        conn = AsyncMock(); conn.fetchval.side_effect = [42]
        resolver, _, _ = self._make_resolver(conn)
        with patch("backend.services.crm.assignment.normalize_phone_e164", return_value="+62123"):
            assert await resolver.find_client_by_whatsapp("+62 123") == 42

    async def test_find_by_whatsapp_clients_fallback(self):
        conn = AsyncMock(); conn.fetchval.side_effect = [None, 55]
        resolver, _, _ = self._make_resolver(conn)
        with patch("backend.services.crm.assignment.normalize_phone_e164", return_value="+62123"):
            assert await resolver.find_client_by_whatsapp("+62 123") == 55

    async def test_find_by_whatsapp_invalid_phone(self):
        resolver, _, _ = self._make_resolver()
        with patch("backend.services.crm.assignment.normalize_phone_e164", return_value=None):
            assert await resolver.find_client_by_whatsapp("invalid") is None

    async def test_find_by_email_found(self):
        conn = AsyncMock(); conn.fetchval.return_value = 10
        resolver, _, _ = self._make_resolver(conn)
        assert await resolver.find_client_by_email("john@x.com") == 10

    async def test_find_by_email_empty(self):
        resolver, _, _ = self._make_resolver()
        assert await resolver.find_client_by_email("") is None

    async def test_link_telegram(self):
        conn = AsyncMock(); conn.execute.return_value = "UPDATE 1"
        resolver, _, _ = self._make_resolver(conn)
        assert await resolver.link_messaging_user_to_client("telegram", "12345", 42) is True

    async def test_link_whatsapp(self):
        conn = AsyncMock(); conn.execute.return_value = "UPDATE 1"
        resolver, _, _ = self._make_resolver(conn)
        with patch("backend.services.crm.assignment.normalize_phone", return_value="+62123"):
            assert await resolver.link_messaging_user_to_client("whatsapp", "+62123", 42) is True

    async def test_link_unknown_channel(self):
        resolver, _, _ = self._make_resolver()
        assert await resolver.link_messaging_user_to_client("sms", "123", 42) is False

    async def test_link_no_rows_affected(self):
        conn = AsyncMock(); conn.execute.return_value = "UPDATE 0"
        resolver, _, _ = self._make_resolver(conn)
        assert await resolver.link_messaging_user_to_client("telegram", "12345", 42) is False

    async def test_resolve_finds_existing(self):
        resolver, _, _ = self._make_resolver()
        resolver.find_client_by_email = AsyncMock(return_value=42)
        client_id, is_new = await resolver.resolve_or_create_client("email", "j@x.com")
        assert client_id == 42 and is_new is False

    async def test_resolve_creates_new(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": 100}
        resolver, _, _ = self._make_resolver(conn)
        resolver.find_client_by_email = AsyncMock(return_value=None)
        resolver.link_messaging_user_to_client = AsyncMock(return_value=True)
        client_id, is_new = await resolver.resolve_or_create_client("email", "new@x.com", client_data={"full_name": "New"})
        assert client_id == 100 and is_new is True

    async def test_resolve_no_data_no_create(self):
        resolver, _, _ = self._make_resolver()
        resolver.find_client_by_email = AsyncMock(return_value=None)
        client_id, is_new = await resolver.resolve_or_create_client("email", "x@x.com")
        assert client_id is None and is_new is False

    async def test_get_client_channels(self):
        conn = AsyncMock()
        conn.fetch.return_value = [{"channel": "telegram", "identifier": "123", "active": True, "created_at": None, "last_message_at": None}]
        resolver, _, _ = self._make_resolver(conn)
        result = await resolver.get_client_channels(42)
        assert len(result) == 1 and result[0]["channel"] == "telegram"


@pytest.mark.asyncio
class TestCheckDuplicates:
    def _make_state(self, **kw):
        state = {"client_id": 1, "client_data": {"email": "j@x.com", "phone": "+62123"}, "is_duplicate": False, "matched_client_id": None, "assigned_lead": None, "assigned_lead_name": None, "assignment_reason": "", "telegram_chat_id": None, "notification_sent": False, "success": True, "errors": []}
        state.update(kw)
        return state

    async def test_email_duplicate(self):
        from backend.services.crm.assignment import check_duplicates
        conn = AsyncMock(); conn.fetchrow.return_value = {"id": 99, "assigned_to": "lead@x.com"}
        pool, _ = _make_pool(conn)
        result = await check_duplicates(self._make_state(), pool)
        assert result["is_duplicate"] is True

    async def test_no_duplicate(self):
        from backend.services.crm.assignment import check_duplicates
        conn = AsyncMock(); conn.fetchrow.return_value = None
        pool, _ = _make_pool(conn)
        result = await check_duplicates(self._make_state(client_data={"email": None, "phone": None}), pool)
        assert result["is_duplicate"] is False


@pytest.mark.asyncio
class TestAssignLead:
    def _make_state(self, **kw):
        state = {"client_id": 1, "client_data": {"practice_type_code": "kitas"}, "is_duplicate": False, "matched_client_id": None, "assigned_lead": None, "assigned_lead_name": None, "assignment_reason": "", "telegram_chat_id": None, "notification_sent": False, "success": True, "errors": []}
        state.update(kw)
        return state

    async def test_duplicate_uses_existing(self):
        from backend.services.crm.assignment import assign_lead
        state = self._make_state(is_duplicate=True, matched_client_id=99, assigned_lead="existing@x.com")
        result = await assign_lead(state, AsyncMock())
        assert result["assigned_lead"] == "existing@x.com"
        assert "Duplicate" in result["assignment_reason"]

    async def test_department_match(self):
        from backend.services.crm.assignment import assign_lead
        conn = AsyncMock()
        conn.fetchrow.return_value = {"email": "lead@x.com", "full_name": "Lead", "department": "setup", "active_practices": 3}
        pool, _ = _make_pool(conn)
        result = await assign_lead(self._make_state(), pool)
        assert result["assigned_lead"] == "lead@x.com"

    async def test_no_available_team_members(self):
        from backend.services.crm.assignment import assign_lead
        conn = AsyncMock(); conn.fetchrow.return_value = None
        pool, _ = _make_pool(conn)
        result = await assign_lead(self._make_state(), pool)
        assert result["assigned_lead"] is None and len(result["errors"]) > 0


@pytest.mark.asyncio
class TestSendTelegramNotification:
    def _make_state(self, **kw):
        state = {"client_id": 1, "client_data": {"full_name": "John", "email": "j@x.com", "phone": "+62123", "practice_type_code": "kitas"}, "is_duplicate": False, "matched_client_id": None, "assigned_lead": "lead@x.com", "assigned_lead_name": "Lead", "assignment_reason": "Dept match", "telegram_chat_id": None, "notification_sent": False, "success": True, "errors": []}
        state.update(kw)
        return state

    async def test_no_lead_assigned(self):
        from backend.services.crm.assignment import send_telegram_notification
        result = await send_telegram_notification(self._make_state(assigned_lead=None), AsyncMock(), AsyncMock())
        assert result["notification_sent"] is False

    async def test_no_telegram_chat_id(self):
        from backend.services.crm.assignment import send_telegram_notification
        conn = AsyncMock(); conn.fetchrow.return_value = {"telegram_chat_id": None, "full_name": "Lead"}
        pool, _ = _make_pool(conn)
        result = await send_telegram_notification(self._make_state(), pool, AsyncMock())
        assert result["notification_sent"] is False

    async def test_sends_notification(self):
        from backend.services.crm.assignment import send_telegram_notification
        conn = AsyncMock(); conn.fetchrow.return_value = {"telegram_chat_id": 12345, "full_name": "Lead"}
        pool, _ = _make_pool(conn)
        mock_tg = AsyncMock()
        result = await send_telegram_notification(self._make_state(), pool, mock_tg)
        assert result["notification_sent"] is True
        mock_tg.send_message.assert_awaited_once()

    async def test_telegram_send_failure(self):
        from backend.services.crm.assignment import send_telegram_notification
        conn = AsyncMock(); conn.fetchrow.return_value = {"telegram_chat_id": 12345, "full_name": "Lead"}
        pool, _ = _make_pool(conn)
        mock_tg = AsyncMock(); mock_tg.send_message.side_effect = RuntimeError("API error")
        result = await send_telegram_notification(self._make_state(), pool, mock_tg)
        assert result["notification_sent"] is False


class TestWorkflowConstants:
    def test_assignable_roles(self):
        from backend.services.crm.assignment import ASSIGNABLE_ROLES
        assert "Supervisor" in ASSIGNABLE_ROLES

    def test_department_map(self):
        from backend.services.crm.assignment import PRACTICE_DEPARTMENT_MAP
        assert PRACTICE_DEPARTMENT_MAP["kitas"] == "setup"
        assert PRACTICE_DEPARTMENT_MAP["tax"] == "tax"


@pytest.mark.asyncio
class TestTriggerLeadAssignment:
    async def test_trigger_success(self):
        from backend.services.crm.assignment import trigger_lead_assignment
        with patch("backend.services.crm.assignment.create_lead_assignment_workflow") as m:
            mock_wf = AsyncMock()
            mock_wf.ainvoke.return_value = {"client_id": 1, "assigned_lead": "l@x.com", "notification_sent": True, "errors": []}
            m.return_value = mock_wf
            result = await trigger_lead_assignment(1, {"full_name": "John"}, AsyncMock(), AsyncMock())
        assert result["success"] is True

    async def test_trigger_failure(self):
        from backend.services.crm.assignment import trigger_lead_assignment
        with patch("backend.services.crm.assignment.create_lead_assignment_workflow") as m:
            mock_wf = AsyncMock(); mock_wf.ainvoke.side_effect = RuntimeError("Graph error")
            m.return_value = mock_wf
            result = await trigger_lead_assignment(1, {"full_name": "John"}, AsyncMock(), AsyncMock())
        assert result["success"] is False
