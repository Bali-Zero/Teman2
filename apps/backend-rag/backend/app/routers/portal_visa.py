"""Portal Visa API endpoints."""
import time

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from prometheus_client import Counter, Histogram

from backend.app.dependencies import get_database_pool
from backend.schemas.portal import VisaSummary
from backend.services.portal.visa_service import VisaService

router = APIRouter(prefix="/api/portal/visa", tags=["Portal - Visa"])

# Metrics
visa_requests = Counter(
    "portal_visa_requests_total", "Visa endpoint requests", ["endpoint", "status"]
)
visa_latency = Histogram("portal_visa_latency_seconds", "Visa endpoint latency")


async def get_current_portal_client(
    request: Request, db_pool: asyncpg.Pool = Depends(get_database_pool)
) -> dict:
    """
    Get current authenticated client from JWT token.

    Requires:
    - Valid JWT token (from middleware)
    - role = 'client'
    - linked_client_id set

    Returns:
        dict with: id, email, full_name
    """
    # Get user from middleware
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(
            status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"}
        )

    user = request.state.user

    # Check role is client
    if user.get("role") != "client":
        raise HTTPException(status_code=403, detail="This endpoint is only accessible to clients")

    # Get linked_client_id from user record
    async with db_pool.acquire() as conn:
        client_row = await conn.fetchrow(
            """
            SELECT c.id, c.email, c.full_name
            FROM clients c
            JOIN user_profiles up ON up.linked_client_id = c.id
            WHERE up.id = $1 AND up.role = 'client'
        """,
            user.get("user_id"),
        )

        if not client_row:
            raise HTTPException(status_code=404, detail="Client profile not found")

        return dict(client_row)


@router.get("/", response_model=dict)
async def get_visa_status(
    current_client=Depends(get_current_portal_client), db_pool=Depends(get_database_pool)
):
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=VisaSummary)
async def get_visa_summary(
    current_client=Depends(get_current_portal_client), db_pool=Depends(get_database_pool)
):
    """Get visa summary for dashboard card."""
    service = VisaService(db_pool)
    return await service.get_visa_summary(current_client["id"])
