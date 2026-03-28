"""Portal Visa API endpoints."""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import Counter, Histogram

from backend.app.dependencies import get_current_portal_client, get_database_pool
from backend.schemas.portal import VisaSummary
from backend.services.portal.visa_service import VisaService

router = APIRouter(prefix="/api/portal/visa", tags=["Portal - Visa"])

# Metrics
visa_requests = Counter(
    "portal_visa_requests_total", "Visa endpoint requests", ["endpoint", "status"]
)
visa_latency = Histogram("portal_visa_latency_seconds", "Visa endpoint latency")


@router.get("/", response_model=dict)
async def get_visa_status(
    current_client=Depends(get_current_portal_client), db_pool=Depends(get_database_pool)
) -> dict[str, Any]:
    """
    Get immigration status for authenticated client.

    Returns:
        - summary: VisaSummary
        - current_visa: VisaRecord or null
        - history: List[VisaRecord]
    """
    start = time.time()
    try:
        service = VisaService(db_pool)
        current_visa = await service.get_active_visa(current_client["id"])
        history = await service.get_visa_history(current_client["id"])
        summary = await service.get_visa_summary(current_client["id"])

        visa_requests.labels(endpoint="get_visa", status="success").inc()
        visa_latency.observe(time.time() - start)

        return {
            "summary": summary.model_dump(),
            "current_visa": current_visa.model_dump() if current_visa else None,
            "history": [v.model_dump() for v in history],
        }
    except Exception as e:
        visa_requests.labels(endpoint="get_visa", status="error").inc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/summary", response_model=VisaSummary)
async def get_visa_summary(
    current_client=Depends(get_current_portal_client), db_pool=Depends(get_database_pool)
) -> Any:
    """Get visa summary for dashboard card."""
    service = VisaService(db_pool)
    return await service.get_visa_summary(current_client["id"])
