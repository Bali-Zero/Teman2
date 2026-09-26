"""
Unit tests for CRM automation services.

Tests ProcessAutomationService and its shared helpers. CompletedProcessService
and WaitingDocumentsService were removed from automation.py 2026-08-08 — dead
duplicates of the live backend.services.crm.completed_process_service /
waiting_documents_service modules (the only ones crm_practices.py actually
imports); this file's TestCompletedProcessService/TestWaitingDocumentsService
were testing the unreachable copy, not real behavior. No test coverage for
the live modules existed before or after this change — that gap is
pre-existing, not introduced here.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_pool(conn=None):
    pool = MagicMock()
    conn = conn or AsyncMock()

    class _Ctx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *a):
            pass

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
        conn.fetchrow.return_value = {
            "id": 1,
            "practice_type_code": "KITAS",
            "practice_type_name": "KITAS",
        }
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
        conn.fetchrow.return_value = {
            "id": 10,
            "full_name": "John",
            "email": "j@x.com",
            "phone": "+62123",
            "address": "Bali",
            "nationality": "US",
        }
        pool, _ = _make_pool(conn)
        result = await _fetch_client_data(pool, 10)
        assert result["full_name"] == "John"

    async def test_include_drive_columns(self):
        from backend.services.crm.automation import _fetch_client_data

        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "id": 10,
            "full_name": "John",
            "email": "j@x.com",
            "phone": "+62123",
            "drive_folder_id": "df1",
            "drive_folder_url": "http://...",
            "drive_documents_folder_id": "dd1",
            "drive_final_folder_id": "dfin",
        }
        pool, _ = _make_pool(conn)
        result = await _fetch_client_data(pool, 10, include_drive=True)
        assert result["drive_folder_id"] == "df1"


@pytest.mark.asyncio
class TestFetchPracticeWithClient:
    async def test_returns_both_when_found(self):
        from backend.services.crm.automation import _fetch_practice_with_client

        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "id": 1,
            "status": "on_process",
            "practice_type_code": "KITAS",
            "practice_type_name": "KITAS",
            "client_db_id": 10,
            "full_name": "John",
            "email": "j@x.com",
            "phone": "+62123",
            "address": "Bali",
            "nationality": "US",
        }
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
    """GUILT (2026-09-27): the old "Zoho fallback" here called
    ``zoho_email_service.send_email(to_email=..., subject=..., body=...)`` —
    kwargs that never matched ``ZohoEmailService.send_email``'s real
    signature (``user_id, to, subject, content, ...``) — and, unlike the
    sibling copies in completed_process_service.py/waiting_documents_service.py,
    did not even catch the resulting TypeError: a Brevo failure escaped this
    function with no Telegram page and no ``email_send_log`` row at all
    (the old ``test_falls_back_to_zoho`` used a bare ``AsyncMock()`` with no
    ``spec=ZohoEmailService``, so it accepted the wrong kwargs silently and
    never caught this). The fallback is removed; the fix adds the same
    ``email_send_log`` audit wiring the other two services already had.
    """

    async def test_sends_via_brevo_records_sent(self):
        from backend.services.crm.automation import _send_with_brevo_fallback

        pool, _conn = _make_pool()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        with (
            patch("backend.services.crm.automation.httpx.AsyncClient") as mock_cls,
            patch(
                "backend.services.crm.automation.log_email_attempt",
                AsyncMock(return_value=42),
            ),
            patch(
                "backend.services.crm.automation.record_email_result", AsyncMock()
            ) as mock_record,
            patch(
                "backend.services.crm.automation.notify_email_failure_critical", MagicMock()
            ) as mock_notify,
        ):
            mock_c = AsyncMock()
            mock_c.__aenter__.return_value = mock_c
            mock_c.__aexit__.return_value = False
            mock_c.post.return_value = mock_response
            mock_cls.return_value = mock_c
            await _send_with_brevo_fallback(
                pool, "to@x.com", "Sub", "Body", email_type="process_start_client"
            )
        mock_record.assert_awaited_once()
        assert mock_record.call_args.kwargs["status"] == "sent"
        assert mock_record.call_args.kwargs["provider"] == "brevo"
        mock_notify.assert_not_called()

    async def test_brevo_failure_records_failed_and_alerts_no_zoho_attempt(self):
        """GUILT: before the fix this exception would have propagated as a
        TypeError from the broken Zoho call, with no alert and no audit row."""
        from backend.services.crm.automation import _send_with_brevo_fallback

        pool, _conn = _make_pool()
        with (
            patch("backend.services.crm.automation.httpx.AsyncClient") as mock_cls,
            patch(
                "backend.services.crm.automation.log_email_attempt",
                AsyncMock(return_value=42),
            ),
            patch(
                "backend.services.crm.automation.record_email_result", AsyncMock()
            ) as mock_record,
            patch(
                "backend.services.crm.automation.notify_email_failure_critical", MagicMock()
            ) as mock_notify,
        ):
            mock_c = AsyncMock()
            mock_c.__aenter__.return_value = mock_c
            mock_c.__aexit__.return_value = False
            mock_c.post.side_effect = Exception("Brevo down")
            mock_cls.return_value = mock_c
            with pytest.raises(Exception, match="Brevo down"):
                await _send_with_brevo_fallback(
                    pool, "to@x.com", "Sub", "Body", email_type="process_start_client"
                )
        mock_record.assert_awaited_once()
        assert mock_record.call_args.kwargs["status"] == "failed"
        assert mock_record.call_args.kwargs["provider"] == "brevo"
        mock_notify.assert_called_once()
        assert mock_notify.call_args.kwargs["email_type"] == "process_start_client"


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
        from backend.services.crm.automation import ProcessAutomationService

        svc = ProcessAutomationService(pool)
        return svc, pool, conn

    async def test_trigger_practice_not_found(self):
        svc, _, _ = self._make_service()
        with patch(
            "backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock
        ) as m:
            m.return_value = (None, None)
            result = await svc.trigger_on_process_start(999, "user@x.com")
        assert result["success"] is False

    async def test_trigger_client_not_found(self):
        svc, _, _ = self._make_service()
        with patch(
            "backend.services.crm.automation._fetch_practice_with_client", new_callable=AsyncMock
        ) as m:
            m.return_value = ({"id": 1}, None)
            result = await svc.trigger_on_process_start(1, "user@x.com")
        assert result["success"] is False

    async def test_trigger_success_with_notifications(self):
        svc, _, _ = self._make_service()
        practice = {
            "id": 1,
            "practice_type_name": "KITAS",
            "assigned_to": "lead@x.com",
            "created_by": "admin@x.com",
        }
        client = {"id": 10, "full_name": "John", "email": "john@x.com"}
        with (
            patch(
                "backend.services.crm.automation._fetch_practice_with_client",
                new_callable=AsyncMock,
            ) as m_fetch,
            patch(
                "backend.services.crm.automation._send_with_brevo_fallback", new_callable=AsyncMock
            ) as m_send,
            patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        ):
            m_fetch.return_value = (practice, client)
            result = await svc.trigger_on_process_start(1, "user@x.com")
        assert result["success"] is True
        assert result["client_notified"] is True
        assert m_send.await_count == 2

    async def test_trigger_no_client_email(self):
        svc, _, _ = self._make_service()
        practice = {"id": 1, "practice_type_name": "KITAS", "assigned_to": "lead@x.com"}
        client = {"id": 10, "full_name": "John", "email": None}
        with (
            patch(
                "backend.services.crm.automation._fetch_practice_with_client",
                new_callable=AsyncMock,
            ) as m,
            patch(
                "backend.services.crm.automation._send_with_brevo_fallback", new_callable=AsyncMock
            ),
            patch("backend.services.crm.automation._log_activity", new_callable=AsyncMock),
        ):
            m.return_value = (practice, client)
            result = await svc.trigger_on_process_start(1, "user@x.com")
        assert result["client_notified"] is False

