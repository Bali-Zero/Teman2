"""Portal Tax API endpoints."""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import Counter, Histogram

from backend.app.dependencies import get_current_portal_client, get_database_pool
from backend.schemas.portal import TaxSummary
from backend.services.portal.tax_service import TaxService

router = APIRouter(prefix="/api/portal/taxes", tags=["Portal - Taxes"])

# Metrics
tax_requests = Counter("portal_tax_requests_total", "Tax endpoint requests", ["endpoint", "status"])
tax_latency = Histogram("portal_tax_latency_seconds", "Tax endpoint latency")


@router.get("/", response_model=dict)
async def get_taxes(
    include_completed: bool = False,
    current_client=Depends(get_current_portal_client),
    db_pool=Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get all tax obligations for the authenticated client.

    Returns:
        - summary: TaxSummary (total_due, next_deadline, status)
        - obligations: List[TaxObligation]
    """
    start = time.time()
    try:
        service = TaxService(db_pool)
        obligations = await service.get_client_taxes(current_client["id"], include_completed)
        summary = await service.get_tax_summary(current_client["id"])

        tax_requests.labels(endpoint="get_taxes", status="success").inc()
        tax_latency.observe(time.time() - start)

        return {
            "summary": summary.model_dump(),
            "obligations": [o.model_dump() for o in obligations],
        }
    except Exception as e:
        tax_requests.labels(endpoint="get_taxes", status="error").inc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/summary", response_model=TaxSummary)
async def get_tax_summary(
    current_client=Depends(get_current_portal_client), db_pool=Depends(get_database_pool),
) -> Any:
    """Get tax summary for dashboard card."""
    service = TaxService(db_pool)
    return await service.get_tax_summary(current_client["id"])
