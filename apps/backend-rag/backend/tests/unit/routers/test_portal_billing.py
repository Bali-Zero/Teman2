"""Tests for portal billing via PortalService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.portal.portal_service import PortalService


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
    result = await service.get_billing(client_id=1)

    assert len(result["invoices"]) == 2
    assert result["summary"]["total_invoiced"] == 55000000.0
    assert result["summary"]["total_paid"] == 35000000.0
    assert result["summary"]["total_pending"] == 20000000.0
    assert result["summary"]["count"] == 2


@pytest.mark.asyncio
async def test_get_billing_empty():
    """get_billing returns empty list when no invoices."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_billing(client_id=999)

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
    result = await service.get_billing(client_id=1)

    assert len(result["invoices"]) == 0
    assert result["summary"]["count"] == 0


@pytest.mark.asyncio
async def test_get_invoice_pdf_url():
    """get_invoice_pdf_url returns Drive link for valid invoice."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"drive_web_link": "https://drive.google.com/abc", "drive_file_id": "abc123"}

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_invoice_pdf_url(client_id=1, invoice_id=1)

    assert result is not None
    assert result["download_url"] == "https://drive.google.com/abc"


@pytest.mark.asyncio
async def test_get_invoice_pdf_url_not_found():
    """get_invoice_pdf_url returns None for non-existent invoice."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_invoice_pdf_url(client_id=1, invoice_id=999)

    assert result is None
