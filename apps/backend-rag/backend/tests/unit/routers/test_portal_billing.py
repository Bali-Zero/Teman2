"""Tests for portal billing via PortalService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import portal_billing
from backend.services.portal.portal_service import PortalService


def _make_invoice_service(row: dict[str, object] | None) -> tuple[PortalService, AsyncMock]:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = row

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    return PortalService(mock_pool), mock_conn


def test_get_portal_service_returns_portal_service() -> None:
    """_get_portal_service wires the request pool into PortalService."""
    mock_pool = MagicMock()

    service = portal_billing._get_portal_service(mock_pool)

    assert isinstance(service, PortalService)
    assert service.pool is mock_pool


@pytest.mark.asyncio
async def test_get_billing_returns_invoices():
    """get_billing returns invoices with summary."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 1, "invoice_number": "INV-202602-00010", "amount_idr": 20000000.0,
            "invoice_source": "local_pdf", "drive_file_id": "abc", "drive_web_link": "https://drive.google.com/abc",
            "email_sent_to_client": True, "generated_at": None, "created_at": None,
            "practice_id": 10, "practice_name": "KITAS B211A", "practice_category": "visa",
            "payment_status": "pending", "quoted_price": 20000000.0,
        },
        {
            "id": 2, "invoice_number": "INV-202603-00015", "amount_idr": 35000000.0,
            "invoice_source": "local_pdf", "drive_file_id": "def", "drive_web_link": "https://drive.google.com/def",
            "email_sent_to_client": True, "generated_at": None, "created_at": None,
            "practice_id": 15, "practice_name": "PT PMA Setup", "practice_category": "company",
            "payment_status": "paid", "quoted_price": 35000000.0,
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_billing(
        client_id=1, current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert len(result["invoices"]) == 2
    assert result["summary"]["total_invoiced"] == 55000000.0
    assert result["summary"]["total_paid"] == 35000000.0
    assert result["summary"]["total_pending"] == 20000000.0
    assert result["summary"]["count"] == 2
    assert all(invoice["drive_web_link"] is None for invoice in result["invoices"])


@pytest.mark.asyncio
async def test_get_billing_empty():
    """get_billing returns empty list when no invoices."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_billing(
        client_id=999, current_user={"client_id": 999, "email": "c999@example.com"},
    )

    assert len(result["invoices"]) == 0
    assert result["summary"]["total_invoiced"] == 0
    assert result["summary"]["total_pending"] == 0


@pytest.mark.asyncio
async def test_get_billing_fallback_on_missing_table():
    """get_billing returns empty when invoices table doesn't exist."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = Exception("relation 'invoices' does not exist")

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_billing(
        client_id=1, current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert len(result["invoices"]) == 0
    assert result["summary"]["count"] == 0


@pytest.mark.asyncio
async def test_get_billing_route_wraps_service_result() -> None:
    """Billing route returns the service payload behind the success envelope."""
    client = {"client_id": 7, "email": "c7@example.com"}
    expected = {"invoices": [], "summary": {"count": 0}}
    service = AsyncMock()
    service.get_billing.return_value = expected

    result = await portal_billing.get_billing(client=client, portal_service=service)

    assert result == {"success": True, "data": expected}
    service.get_billing.assert_awaited_once_with(7, current_user=client)


@pytest.mark.asyncio
async def test_get_billing_route_hides_service_errors() -> None:
    """Billing route logs backend errors without leaking details to clients."""
    service = AsyncMock()
    service.get_billing.side_effect = RuntimeError("database unavailable")

    with pytest.raises(portal_billing.HTTPException) as exc:
        await portal_billing.get_billing(
            client={"client_id": 7, "email": "c7@example.com"},
            portal_service=service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to load billing data"


@pytest.mark.asyncio
async def test_get_invoice_pdf_url():
    """get_invoice_pdf_url returns a portal proxy URL, not Drive details."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"drive_web_link": "https://drive.google.com/abc", "drive_file_id": "abc123"}

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_invoice_pdf_url(
        client_id=1,
        invoice_id=1,
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is not None
    assert result == {"download_url": "/api/portal/billing/1/pdf"}


@pytest.mark.asyncio
async def test_download_invoice_pdf_streams_owned_invoice_drive_file():
    """download_invoice_pdf streams an invoice PDF through the portal proxy."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "invoice_number": "INV-202602-00010",
        "drive_web_link": "https://drive.google.com/file/d/invoice_drive_123/view",
        "drive_file_id": "invoice_drive_123",
    }

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    meta_response = MagicMock(status_code=200)
    meta_response.json.return_value = {
        "name": "invoice.pdf",
        "mimeType": "application/pdf",
    }
    download_response = MagicMock(status_code=200, content=b"PDF_INVOICE")

    async_http = MagicMock()
    async_http.get = AsyncMock(side_effect=[meta_response, download_response])

    service = PortalService(mock_pool)
    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("httpx.AsyncClient") as client_cls,
    ):
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value="access-token")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=async_http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.download_invoice_pdf(
            client_id=1,
            invoice_id=1,
            current_user={"client_id": 1, "email": "c1@example.com"},
        )

    assert result == {
        "content": b"PDF_INVOICE",
        "file_name": "invoice.pdf",
        "mime_type": "application/pdf",
    }


def test_download_invoice_pdf_route_streams_proxy_response():
    """Billing PDF route returns file bytes without exposing Drive details."""
    app = FastAPI()
    app.include_router(portal_billing.router)

    service = AsyncMock()
    service.download_invoice_pdf.return_value = {
        "content": b"PDF_INVOICE",
        "file_name": "invoice.pdf",
        "mime_type": "application/pdf",
    }

    app.dependency_overrides[portal_billing.get_current_client] = lambda: {
        "client_id": 1,
        "email": "c1@example.com",
    }
    app.dependency_overrides[portal_billing._get_portal_service] = lambda: service

    response = TestClient(app).get("/api/portal/billing/1/pdf")

    assert response.status_code == 200
    assert response.content == b"PDF_INVOICE"
    assert response.headers["content-type"] == "application/pdf"
    assert "invoice.pdf" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_get_invoice_pdf_url_not_found():
    """get_invoice_pdf_url returns None for non-existent invoice."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_invoice_pdf_url(
        client_id=1,
        invoice_id=999,
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_invoice_pdf_url_returns_none_on_db_error() -> None:
    """get_invoice_pdf_url degrades to None when the invoice lookup fails."""
    service, mock_conn = _make_invoice_service(row=None)
    mock_conn.fetchrow.side_effect = ConnectionError("database unavailable")

    result = await service.get_invoice_pdf_url(
        client_id=1,
        invoice_id=999,
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_download_invoice_pdf_returns_none_for_missing_invoice() -> None:
    """download_invoice_pdf returns None when the invoice is absent."""
    service, _mock_conn = _make_invoice_service(row=None)

    result = await service.download_invoice_pdf(
        client_id=1,
        invoice_id=999,
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_download_invoice_pdf_returns_none_for_unextractable_drive_link() -> None:
    """download_invoice_pdf refuses invoice rows without a usable Drive file id."""
    service, _mock_conn = _make_invoice_service({
        "invoice_number": "INV-202602-00010",
        "drive_web_link": "https://example.com/not-google-drive",
        "drive_file_id": None,
    })

    result = await service.download_invoice_pdf(
        client_id=1,
        invoice_id=1,
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_download_invoice_pdf_raises_when_drive_not_connected() -> None:
    """download_invoice_pdf reports missing Google Drive token as a backend failure."""
    service, _mock_conn = _make_invoice_service({
        "invoice_number": "INV-202602-00010",
        "drive_web_link": None,
        "drive_file_id": "invoice_drive_123",
    })

    with patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls:
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="Google Drive is not connected"):
            await service.download_invoice_pdf(
                client_id=1,
                invoice_id=1,
                current_user={"client_id": 1, "email": "c1@example.com"},
            )


@pytest.mark.asyncio
async def test_download_invoice_pdf_returns_none_when_metadata_is_404() -> None:
    """download_invoice_pdf returns None when Drive metadata lookup is 404."""
    service, _mock_conn = _make_invoice_service({
        "invoice_number": "INV-202602-00010",
        "drive_web_link": None,
        "drive_file_id": "invoice_drive_123",
    })
    meta_response = MagicMock(status_code=404)
    async_http = MagicMock()
    async_http.get = AsyncMock(return_value=meta_response)

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("httpx.AsyncClient") as client_cls,
    ):
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value="access-token")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=async_http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.download_invoice_pdf(
            client_id=1,
            invoice_id=1,
            current_user={"client_id": 1, "email": "c1@example.com"},
        )

    assert result is None


@pytest.mark.asyncio
async def test_download_invoice_pdf_raises_when_metadata_fetch_fails() -> None:
    """download_invoice_pdf raises on non-200 Drive metadata errors."""
    service, _mock_conn = _make_invoice_service({
        "invoice_number": "INV-202602-00010",
        "drive_web_link": None,
        "drive_file_id": "invoice_drive_123",
    })
    meta_response = MagicMock(status_code=503)
    async_http = MagicMock()
    async_http.get = AsyncMock(return_value=meta_response)

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("httpx.AsyncClient") as client_cls,
    ):
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value="access-token")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=async_http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="Failed to fetch invoice metadata"):
            await service.download_invoice_pdf(
                client_id=1,
                invoice_id=1,
                current_user={"client_id": 1, "email": "c1@example.com"},
            )


@pytest.mark.asyncio
async def test_download_invoice_pdf_returns_none_when_download_is_404() -> None:
    """download_invoice_pdf returns None when Drive media download is 404."""
    service, _mock_conn = _make_invoice_service({
        "invoice_number": "INV-202602-00010",
        "drive_web_link": None,
        "drive_file_id": "invoice_drive_123",
    })
    meta_response = MagicMock(status_code=200)
    meta_response.json.return_value = {"name": "invoice.pdf", "mimeType": "application/pdf"}
    download_response = MagicMock(status_code=404)
    async_http = MagicMock()
    async_http.get = AsyncMock(side_effect=[meta_response, download_response])

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("httpx.AsyncClient") as client_cls,
    ):
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value="access-token")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=async_http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.download_invoice_pdf(
            client_id=1,
            invoice_id=1,
            current_user={"client_id": 1, "email": "c1@example.com"},
        )

    assert result is None


@pytest.mark.asyncio
async def test_download_invoice_pdf_raises_when_download_fails() -> None:
    """download_invoice_pdf raises on non-200 Drive download errors."""
    service, _mock_conn = _make_invoice_service({
        "invoice_number": "INV-202602-00010",
        "drive_web_link": None,
        "drive_file_id": "invoice_drive_123",
    })
    meta_response = MagicMock(status_code=200)
    meta_response.json.return_value = {"name": "invoice.pdf", "mimeType": "application/pdf"}
    download_response = MagicMock(status_code=500)
    async_http = MagicMock()
    async_http.get = AsyncMock(side_effect=[meta_response, download_response])

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("httpx.AsyncClient") as client_cls,
    ):
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value="access-token")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=async_http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="Failed to download invoice"):
            await service.download_invoice_pdf(
                client_id=1,
                invoice_id=1,
                current_user={"client_id": 1, "email": "c1@example.com"},
            )

@pytest.mark.asyncio
async def test_get_invoice_pdf_url_route_returns_proxy_url() -> None:
    """PDF URL route returns the portal proxy URL from the service."""
    client = {"client_id": 7, "email": "c7@example.com"}
    expected = {"download_url": "/api/portal/billing/13/pdf"}
    service = AsyncMock()
    service.get_invoice_pdf_url.return_value = expected

    result = await portal_billing.get_invoice_pdf_url(
        invoice_id=13,
        client=client,
        portal_service=service,
    )

    assert result == {"success": True, "data": expected}
    service.get_invoice_pdf_url.assert_awaited_once_with(7, 13, current_user=client)


@pytest.mark.asyncio
async def test_get_invoice_pdf_url_route_returns_404_when_missing() -> None:
    """PDF URL route returns 404 when the invoice has no downloadable PDF."""
    service = AsyncMock()
    service.get_invoice_pdf_url.return_value = None

    with pytest.raises(portal_billing.HTTPException) as exc:
        await portal_billing.get_invoice_pdf_url(
            invoice_id=13,
            client={"client_id": 7, "email": "c7@example.com"},
            portal_service=service,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice not found or PDF not available"


@pytest.mark.asyncio
async def test_download_invoice_pdf_route_returns_404_when_missing() -> None:
    """Billing PDF route returns 404 when the service cannot stream a PDF."""
    service = AsyncMock()
    service.download_invoice_pdf.return_value = None

    with pytest.raises(portal_billing.HTTPException) as exc:
        await portal_billing.download_invoice_pdf(
            invoice_id=13,
            client={"client_id": 7, "email": "c7@example.com"},
            portal_service=service,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice not found or PDF not available"


@pytest.mark.asyncio
async def test_download_invoice_pdf_route_hides_service_errors() -> None:
    """Billing PDF route converts unexpected service failures to a 500."""
    service = AsyncMock()
    service.download_invoice_pdf.side_effect = RuntimeError("drive unavailable")

    with pytest.raises(portal_billing.HTTPException) as exc:
        await portal_billing.download_invoice_pdf(
            invoice_id=13,
            client={"client_id": 7, "email": "c7@example.com"},
            portal_service=service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to download invoice PDF"
