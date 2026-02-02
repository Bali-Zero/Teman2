"""Portal Tax API endpoints."""
import time

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from prometheus_client import Counter, Histogram

from backend.app.dependencies import get_database_pool
from backend.schemas.portal import TaxSummary
from backend.services.portal.tax_service import TaxService

router = APIRouter(prefix="/api/portal/taxes", tags=["Portal - Taxes"])

# Metrics
tax_requests = Counter(
    "portal_tax_requests_total", "Tax endpoint requests", ["endpoint", "status"]
)
tax_latency = Histogram("portal_tax_latency_seconds", "Tax endpoint latency")


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
async def get_taxes(
    include_completed: bool = False,
    current_client=Depends(get_current_portal_client),
    db_pool=Depends(get_database_pool),
):
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=TaxSummary)
async def get_tax_summary(
    current_client=Depends(get_current_portal_client), db_pool=Depends(get_database_pool)
):
    """Get tax summary for dashboard card."""
    service = TaxService(db_pool)
    return await service.get_tax_summary(current_client["id"])
