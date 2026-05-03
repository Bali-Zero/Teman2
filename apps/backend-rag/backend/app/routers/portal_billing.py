"""
Portal Billing Router.

Exposes invoice data to client portal via PortalService.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger
from backend.services.portal import PortalService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/billing", tags=["portal-billing"])


def _get_portal_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> PortalService:
    return PortalService(db_pool)


@router.get("")
async def get_billing(
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(_get_portal_service),
) -> dict[str, Any]:
    """Get all invoices and billing summary for the authenticated client."""
    try:
        result = await portal_service.get_billing(
            client["client_id"],
            current_user=client,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to get billing for client {client['client_id']}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load billing data")


@router.get("/{invoice_id}/pdf-url")
async def get_invoice_pdf_url(
    invoice_id: int,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(_get_portal_service),
) -> dict[str, Any]:
    """Get the Drive download URL for an invoice PDF."""
    result = await portal_service.get_invoice_pdf_url(
        client["client_id"],
        invoice_id,
        current_user=client,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Invoice not found or PDF not available")
    return {"success": True, "data": result}
