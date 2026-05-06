"""
Unit tests for backend/services/invoicing/invoice_service.py

Covers:
  - InvoiceAutomationService.trigger_on_sending_invoice (full flow)
  - _send_invoice_email_to_client
  - _send_accounting_notification
  - _fetch_practice_data
  - _fetch_client_data
  - _update_practice_with_invoice
  - regenerate_invoice
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.invoicing.invoice_service import (
    ACCOUNTING_EMAIL,
    InvoiceAutomationService,
)

# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_drive_service():
    svc = MagicMock()
    svc.upload_file_to_folder = AsyncMock(
        return_value={"id": "drive-file-id", "webViewLink": "https://drive.google.com/file/xyz"}
    )
    return svc


@pytest.fixture
def mock_invoice_generator():
    gen = MagicMock()
    gen.generate_invoice_number = MagicMock(return_value="INV-2026-001")
    gen.generate = MagicMock(return_value=b"%PDF-1.4 fake pdf bytes")
    return gen


@pytest.fixture
def service(mock_db_pool, mock_drive_service, mock_invoice_generator):
    with (
        patch(
            "backend.services.invoicing.invoice_service.ServiceAccountDriveService",
            return_value=mock_drive_service,
        ),
        patch(
            "backend.services.invoicing.invoice_service.InvoiceGenerator",
            return_value=mock_invoice_generator,
        ),
    ):
        svc = InvoiceAutomationService(mock_db_pool)
    return svc


def _practice_data(**overrides):
    data = {
        "id": 1,
        "client_id": 100,
        "practice_type_code": "KITAS",
        "notes": "KITAS processing",
        "quoted_price": 5_000_000,
        "client_drive_folder_id": "folder-123",
    }
    data.update(overrides)
    return data


def _client_data(**overrides):
    data = {
        "id": 100,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+628123456",
        "address": "Jl. Sunset Road 123, Bali",
        "nationality": "Australian",
    }
    data.update(overrides)
    return data


# ============================================================
# _fetch_practice_data
# ============================================================


class TestFetchPracticeData:
    @pytest.mark.asyncio
    async def test_found(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=_practice_data())
        result = await service._fetch_practice_data(1)
        assert result is not None
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_not_found(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=None)
        result = await service._fetch_practice_data(999)
        assert result is None


# ============================================================
# _fetch_client_data
# ============================================================


class TestFetchClientData:
    @pytest.mark.asyncio
    async def test_found(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=_client_data())
        result = await service._fetch_client_data(100)
        assert result is not None
        assert result["full_name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_not_found(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=None)
        result = await service._fetch_client_data(999)
        assert result is None


# ============================================================
# _send_invoice_email_to_client
# ============================================================


class TestSendInvoiceEmailToClient:
    @pytest.mark.asyncio
    async def test_sends_email(self, service):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service._send_invoice_email_to_client(
                client_email="john@example.com",
                client_name="John Doe",
                invoice_number="INV-2026-001",
                pdf_bytes=b"fake pdf",
                filename="Invoice_INV-2026-001.pdf",
                amount=5_000_000,
                triggered_by="zero@balizero.com",
            )
            assert result is True
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["to"] == "john@example.com"
            assert "INV-2026-001" in payload["subject"]

    @pytest.mark.asyncio
    async def test_cc_includes_triggered_by(self, service):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await service._send_invoice_email_to_client(
                client_email="john@example.com",
                client_name="John Doe",
                invoice_number="INV-2026-001",
                pdf_bytes=b"fake",
                filename="test.pdf",
                amount=1000,
                triggered_by="admin@balizero.com",
            )
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert "admin@balizero.com" in payload["cc"]

    @pytest.mark.asyncio
    async def test_cc_does_not_duplicate_existing(self, service):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # triggered_by is already in INVOICE_CC_EMAILS
            await service._send_invoice_email_to_client(
                client_email="john@example.com",
                client_name="John Doe",
                invoice_number="INV-2026-001",
                pdf_bytes=b"fake",
                filename="test.pdf",
                amount=1000,
                triggered_by="zero@balizero.com",
            )
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            cc_parts = payload["cc"].split(", ")
            # Should not have "zero@balizero.com" twice
            assert cc_parts.count("zero@balizero.com") == 1


# ============================================================
# _send_accounting_notification
# ============================================================


class TestSendAccountingNotification:
    @pytest.mark.asyncio
    async def test_sends_to_asya(self, service):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service._send_accounting_notification(
                client_data=_client_data(),
                practice_data=_practice_data(),
                invoice_number="INV-2026-001",
                pdf_bytes=b"fake pdf",
                filename="Invoice_INV-2026-001.pdf",
            )
            assert result is True
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["to"] == ACCOUNTING_EMAIL
            assert "[TEAM]" in payload["subject"]


# ============================================================
# _update_practice_with_invoice
# ============================================================


class TestUpdatePracticeWithInvoice:
    @pytest.mark.asyncio
    async def test_updates_documents_and_invoices(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"client_id": 100, "quoted_price": 5_000_000})
        conn.fetchval = AsyncMock(return_value=None)  # no existing documents
        conn.execute = AsyncMock()

        invoice_info = {
            "invoice_number": "INV-2026-001",
            "invoice_generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "invoice_drive_id": "drive-id",
            "invoice_drive_link": "https://drive.google.com/file/xyz",
            "email_sent": True,
            "accounting_notified": True,
            "source": "local_pdf",
        }

        await service._update_practice_with_invoice(
            practice_id=1,
            invoice_info=invoice_info,
            triggered_by="zero@balizero.com",
        )
        # Should call execute 3 times: UPDATE practices, INSERT invoices, INSERT activity_log
        assert conn.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_handles_existing_documents_str(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"client_id": 100, "quoted_price": 5_000_000})
        existing_docs = json.dumps({"passport": {"file_id": "abc"}})
        conn.fetchval = AsyncMock(return_value=existing_docs)
        conn.execute = AsyncMock()

        await service._update_practice_with_invoice(
            practice_id=1,
            invoice_info={"invoice_number": "INV-001", "source": "local_pdf"},
            triggered_by="admin@balizero.com",
        )
        # Verify the documents update includes the old data.
        # Service now passes dicts directly (asyncpg jsonb codec serialises);
        # tolerate both shapes so the test stays valid for codec-on and
        # codec-off call paths.
        update_call = conn.execute.call_args_list[0]
        docs_json = update_call[0][1]
        parsed = docs_json if isinstance(docs_json, dict) else json.loads(docs_json)
        assert "passport" in parsed
        assert "invoice" in parsed

    @pytest.mark.asyncio
    async def test_handles_existing_documents_dict(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"client_id": 100, "quoted_price": 5_000_000})
        conn.fetchval = AsyncMock(return_value={"passport": {"file_id": "abc"}})
        conn.execute = AsyncMock()

        await service._update_practice_with_invoice(
            practice_id=1,
            invoice_info={"invoice_number": "INV-002", "source": "local_pdf"},
            triggered_by="admin@balizero.com",
        )
        update_call = conn.execute.call_args_list[0]
        docs_json = update_call[0][1]
        parsed = docs_json if isinstance(docs_json, dict) else json.loads(docs_json)
        assert "passport" in parsed

    @pytest.mark.asyncio
    async def test_handles_double_encoded_json(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"client_id": 100, "quoted_price": 3_000_000})
        # Double-encoded JSON string
        inner = json.dumps({"old_key": "val"})
        conn.fetchval = AsyncMock(return_value=json.dumps(inner))
        conn.execute = AsyncMock()

        await service._update_practice_with_invoice(
            practice_id=1,
            invoice_info={"invoice_number": "INV-003", "source": "local_pdf"},
            triggered_by="admin@balizero.com",
        )
        # Should not raise

    @pytest.mark.asyncio
    async def test_handles_invalid_json_documents(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"client_id": 100, "quoted_price": 3_000_000})
        conn.fetchval = AsyncMock(return_value="not-valid-json{{{")
        conn.execute = AsyncMock()

        await service._update_practice_with_invoice(
            practice_id=1,
            invoice_info={"invoice_number": "INV-004", "source": "local_pdf"},
            triggered_by="admin@balizero.com",
        )
        # Should not raise; documents should still have invoice key

    @pytest.mark.asyncio
    async def test_no_practice_row_skips_invoices_insert(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=None)  # practice not found
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        await service._update_practice_with_invoice(
            practice_id=999,
            invoice_info={"invoice_number": "INV-005", "source": "local_pdf"},
            triggered_by="admin@balizero.com",
        )
        # Should call execute 2 times: UPDATE practices + INSERT activity_log (skip invoices insert)
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_generated_at_does_not_crash(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"client_id": 100, "quoted_price": 1000})
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        await service._update_practice_with_invoice(
            practice_id=1,
            invoice_info={
                "invoice_number": "INV-006",
                "invoice_generated_at": "not-a-date",
                "source": "local_pdf",
            },
            triggered_by="admin@balizero.com",
        )
        # Should not raise


# ============================================================
# trigger_on_sending_invoice (full flow)
# ============================================================


class TestTriggerOnSendingInvoice:
    @pytest.mark.asyncio
    async def test_full_success_flow(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        # _fetch_practice_data
        conn.fetchrow = AsyncMock(side_effect=[
            _practice_data(),  # fetch practice
            _client_data(),    # fetch client
            {"client_id": 100, "quoted_price": 5_000_000},  # update practice: fetchrow in _update
        ])
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service.trigger_on_sending_invoice(1, "zero@balizero.com")

        assert result["success"] is True
        assert result["invoice_number"] == "INV-2026-001"
        assert result["email_sent"] is True
        assert result["accounting_notified"] is True
        assert result["drive_file_id"] == "drive-file-id"

    @pytest.mark.asyncio
    async def test_practice_not_found(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=None)

        result = await service.trigger_on_sending_invoice(999, "admin@balizero.com")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_client_not_found(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[_practice_data(), None])

        result = await service.trigger_on_sending_invoice(1, "admin@balizero.com")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pdf_generation_failure(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[_practice_data(), _client_data()])
        service.invoice_generator.generate.side_effect = Exception("ReportLab error")

        result = await service.trigger_on_sending_invoice(1, "admin@balizero.com")
        assert result["success"] is False
        assert "PDF" in result["error"]

    @pytest.mark.asyncio
    async def test_client_no_email_skips_email(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        client_no_email = _client_data(email=None)
        conn.fetchrow = AsyncMock(side_effect=[
            _practice_data(),
            client_no_email,
            {"client_id": 100, "quoted_price": 5_000_000},
        ])
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service.trigger_on_sending_invoice(1, "zero@balizero.com")

        assert result["success"] is True
        assert result["email_sent"] is False

    @pytest.mark.asyncio
    async def test_email_failure_continues(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[
            _practice_data(),
            _client_data(),
            {"client_id": 100, "quoted_price": 5_000_000},
        ])
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            # First call (client email) fails, second (accounting) succeeds
            mock_resp_ok = MagicMock()
            mock_resp_ok.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(side_effect=[Exception("SMTP failed"), mock_resp_ok])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service.trigger_on_sending_invoice(1, "zero@balizero.com")

        assert result["success"] is True
        assert result["email_sent"] is False

    @pytest.mark.asyncio
    async def test_drive_failure_continues(self, service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[
            _practice_data(),
            _client_data(),
            {"client_id": 100, "quoted_price": 5_000_000},
        ])
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        service.drive_service.upload_file_to_folder = AsyncMock(
            side_effect=Exception("Drive upload failed")
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.invoicing.invoice_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service.trigger_on_sending_invoice(1, "zero@balizero.com")

        assert result["success"] is True
        assert result["drive_file_id"] is None


# ============================================================
# regenerate_invoice
# ============================================================


class TestRegenerateInvoice:
    @pytest.mark.asyncio
    async def test_delegates_to_trigger(self, service):
        service.trigger_on_sending_invoice = AsyncMock(
            return_value={"success": True, "invoice_number": "INV-REGEN-001"}
        )
        result = await service.regenerate_invoice(1, "admin@balizero.com")
        assert result["success"] is True
        service.trigger_on_sending_invoice.assert_called_once_with(1, "admin@balizero.com")
