"""
Unit tests for CRM automation services.

Tests ProcessAutomationService, CompletedProcessService,
WaitingDocumentsService and shared helpers.
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


# ---------------------------------------------------------------------------
# Shared helper tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFetchPracticeData:
    async def test_returns_dict_when_found(self):
        from backend.services.crm.automation import _fetch_practice_data
        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": 1, "practice_type_code": "KITAS", "practice_type_name": "KITAS"}
        pool, _ = _make_pool(conn)
        result = await _fetch_practice_data(pool, 1)
        assert result["id"] == 1

    async def test_returns_none_when_not_found(self):
        from backend.services.crm.automation import _fetch_practice_data
        conn = AsyncMock()
        conn.fetchrow.return_value = None
        pool, _ = _make_pool(conn)
        result = await _fetch_practice_data(pool, 999)
        assert result is None


@pytest.mark.asyncio
class TestFetchClientData:
    async def test_basic_columns(self):
        from backend.services.crm.automation import _fetch_client_data
        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": 10, "full_name": "John", "email": "j@x.com", "phone": "+62123", "address": "Bali", "nationality": "US"}
        pool, _ = _make_pool(conn)
        result = await _fetch_client_data(pool, 10)
        assert result["full_name"] == "John"

    async def test_include_drive_columns(self):
        from backend.services.crm.automation import _fetch_client_data
        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": 10, "full_name": "John", "email": "j@x.com", "phone": "+62123", "drive_folder_id": "df1", "drive_folder_url": "http://...", "drive_documents_folder_id": "dd1", "drive_final_folder_id": "dfin"}
        pool, _ = _make_pool(conn)
        result = await _fetch_client_data(pool, 10, include_drive=True)
        assert result["drive_folder_id"] == "df1"


@pytest.mark.asyncio
class TestFetchPracticeWithClient:
    async def test_returns_both_when_found(self):
        from backend.services.crm.automation import _fetch_practice_with_client
        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": 1, "status": "on_process", "practice_type_code": "KITAS", "practice_type_name": "KITAS", "client_db_id": 10, "full_name": "John", "email": "j@x.com", "phone": "+62123", "address": "Bali", "nationality": "US"}
        pool, _ = _make_pool(conn)
        practice, client = await _fetch_practice_with_client(pool, 1)
        assert practice["id"] == 1
        assert client["id"] == 10

    async def test_returns_none_none_when_not_found(self):
        from backend.services.crm.automation import _fetch_practice_with_client
        conn = AsyncMock()
        conn.fetchrow.return_value = None
        pool, _ = _make_pool(conn)
        practice, client = await _fetch_practice_with_client(pool, 999)
        assert practice is None and client is None


@pytest.mark.asyncio
class TestSendWithBrevoFallback:
    async def test_sends_via_brevo(self):
        from backend.services.crm.automation import _send_with_brevo_fallback
        mock_zoho = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        with patch("backend.services.crm.automation.httpx.AsyncClient") as mock_cls:
            mock_c = AsyncMock()
            mock_c.__aenter__.return_value = mock_c
            mock_c.__aexit__.return_value = False
            mock_c.post.return_value = mock_response
            mock_cls.return_value = mock_c
            await _send_with_brevo_fallback(mock_zoho, "to@x.com", "Sub", "Body")
        mock_zoho.send_email.assert_not_awaited()

    async def test_falls_back_to_zoho(self):
        from backend.services.crm.automation import _send_with_brevo_fallback
        mock_zoho = AsyncMock()
        with patch("backend.services.crm.automation.httpx.AsyncClient") as mock_cls:
            mock_c = AsyncMock()
            mock_c.__aenter__.return_value = mock_c
            mock_c.__aexit__.return_value = False
            mock_c.post.side_effect = Exception("Brevo down")
            mock_cls.return_value = mock_c
            await _send_with_brevo_fallback(mock_zoho, "to@x.com", "Sub", "Body")
        mock_zoho.send_email.assert_awaited_once()


@pytest.mark.asyncio
class TestLogActivity:
    async def test_inserts_activity(self):
        from backend.services.crm.automation import _log_activity
        pool, conn = _make_pool()
        await _log_activity(pool, 1, "user@x.com", "action", "desc")
        conn.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# ProcessAutomationService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProcessAutomationService:
    def _make_service(self):
        pool, conn = _make_pool()
        with patch("backend.services.integrations.zoho_email_service.ZohoEmailService"):
            from backend.services.crm.automation import ProcessAutomationService
            svc = ProcessAutomationService(pool)
        svc.zoho_email_service = AsyncMock()
        return svc, pool, conn

    async def test_trigger_practice_not_found(self):
        svc, _, _ = self._make_service()
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m:
            m.return_value = (None, None)
            result = await svc.trigger_on_process_start(999, "user@x.com")
        assert result["success"] is False

    async def test_trigger_client_not_found(self):
        svc, _, _ = self._make_service()
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m:
            m.return_value = ({"id": 1}, None)
            result = await svc.trigger_on_process_start(1, "user@x.com")
        assert result["success"] is False

    async def test_trigger_success_with_notifications(self):
        svc, _, _ = self._make_service()
        practice = {"id": 1, "practice_type_name": "KITAS", "assigned_to": "lead@x.com", "created_by": "admin@x.com"}
        client = {"id": 10, "full_name": "John", "email": "john@x.com"}
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m_fetch, \
             patch("backend.services.crm.automation._send_with_brevo_fallback", new_callable=AsyncMock) as m_send, \
             patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock):
            m_fetch.return_value = (practice, client)
            result = await svc.trigger_on_process_start(1, "user@x.com")
        assert result["success"] is True
        assert result["client_notified"] is True
        assert m_send.await_count == 2

    async def test_trigger_no_client_email(self):
        svc, _, _ = self._make_service()
        practice = {"id": 1, "practice_type_name": "KITAS", "assigned_to": "lead@x.com"}
        client = {"id": 10, "full_name": "John", "email": None}
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m, \
             patch("backend.services.crm.automation._send_with_brevo_fallback", new_callable=AsyncMock), \
             patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock):
            m.return_value = (practice, client)
            result = await svc.trigger_on_process_start(1, "user@x.com")
        assert result["client_notified"] is False


# ---------------------------------------------------------------------------
# CompletedProcessService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCompletedProcessService:
    def _make_service(self):
        pool, conn = _make_pool()
        with patch("backend.services.integrations.zoho_email_service.ZohoEmailService"), \
             patch("backend.services.integrations.drive_folder_service.DriveFolderService"):
            from backend.services.crm.automation import CompletedProcessService
            svc = CompletedProcessService(pool)
        svc.zoho_email_service = AsyncMock()
        svc.drive_service = AsyncMock()
        return svc, pool, conn

    async def test_trigger_practice_not_found(self):
        svc, _, _ = self._make_service()
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m:
            m.return_value = (None, None)
            result = await svc.trigger_on_completed(999, "user@x.com")
        assert result["success"] is False

    async def test_trigger_completed_success(self):
        svc, _, _ = self._make_service()
        practice = {"id": 1, "practice_type_name": "KITAS", "assigned_to": "lead@x.com"}
        client = {"id": 10, "full_name": "John", "email": "john@x.com"}
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m, \
             patch("backend.services.crm.automation._send_with_brevo_fallback", new_callable=AsyncMock), \
             patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock):
            m.return_value = (practice, client)
            result = await svc.trigger_on_completed(1, "user@x.com")
        assert result["success"] is True
        assert result["client_notified"] is True

    async def test_upload_final_documents_no_folder(self):
        svc, _, _ = self._make_service()
        result = await svc._upload_final_documents(
            client_data={"id": 10, "drive_final_folder_id": None},
            documents=[{"content": b"pdf", "filename": "doc.pdf"}],
        )
        assert result == []

    async def test_save_final_document_record(self):
        svc, pool, conn = self._make_service()
        await svc._save_final_document_record(10, "doc.pdf", "gd-123", "https://...")
        conn.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# WaitingDocumentsService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWaitingDocumentsService:
    def _make_service(self):
        pool, conn = _make_pool()
        with patch("backend.services.integrations.zoho_email_service.ZohoEmailService"):
            from backend.services.crm.automation import WaitingDocumentsService
            svc = WaitingDocumentsService(pool)
        svc.zoho_email_service = AsyncMock()
        return svc, pool, conn

    async def test_trigger_not_found(self):
        svc, _, _ = self._make_service()
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m:
            m.return_value = (None, None)
            result = await svc.trigger_on_waiting_documents(999, "user@x.com")
        assert result["success"] is False

    async def test_trigger_success(self):
        svc, _, _ = self._make_service()
        practice = {"id": 1, "practice_type_name": "KITAS", "practice_type_code": "kitas", "assigned_to": "lead@x.com"}
        client = {"id": 10, "full_name": "John", "email": "john@x.com"}
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m, \
             patch("backend.services.crm.automation._send_with_brevo_fallback", new_callable=AsyncMock) as ms, \
             patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock):
            m.return_value = (practice, client)
            result = await svc.trigger_on_waiting_documents(1, "user@x.com")
        assert result["success"] is True
        assert result["team_leader_notified"] is True
        assert result["client_notified"] is True
        assert ms.await_count == 2

    async def test_exception_handling(self):
        svc, _, _ = self._make_service()
        with patch("backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("DB error")
            result = await svc.trigger_on_waiting_documents(1, "user@x.com")
        assert result["success"] is False
        assert "DB error" in result["error"]
