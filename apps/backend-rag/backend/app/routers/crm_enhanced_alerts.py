"""
CRM Enhanced - Expiry Alerts Endpoints

Split from crm_enhanced.py for maintainability.
Provides: expiry alerts listing and summary.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm", tags=["crm-enhanced-alerts"])

# ============================================
# EXPIRY ALERTS ENDPOINTS
# ============================================


@router.get("/expiry-alerts")
async def get_all_expiry_alerts(
    alert_color: str | None = Query(None, description="Filter by color: expired, red, yellow"),
    assigned_to: str | None = Query(None, description="Filter by team member email"),
    limit: int = Query(100, le=500),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> list[Any]:
    """
    Get all expiry alerts across all clients (for team dashboard).
    RBAC REMOVED: All authenticated users can view all expiry alerts.
    Optional filtering by assigned_to is available as a query parameter.
    """
    async with pool.acquire() as conn:
        query = """
            SELECT
                entity_type, entity_id, entity_name, client_id, client_name,
                document_type, expiry_date, days_until_expiry, alert_color, assigned_to
            FROM client_expiry_alerts_view
            WHERE 1=1
        """
        params = []
        param_num = 1

        # Optional filter by assigned_to (user choice, not RBAC enforcement)
        if assigned_to:
            query += f" AND assigned_to = ${param_num}"
            params.append(assigned_to)
            param_num += 1

        query += f"""
            ORDER BY
                CASE alert_color
                    WHEN 'expired' THEN 1
                    WHEN 'red' THEN 2
                    WHEN 'yellow' THEN 3
                END,
                expiry_date
            LIMIT ${param_num}
        """
        params.append(limit)

        alerts = await conn.fetch(query, *params)
        return [dict(a) for a in alerts]


@router.get("/expiry-alerts/summary")
async def get_expiry_alerts_summary(
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get summary counts of expiry alerts for dashboard."""
    async with pool.acquire() as conn:
        summary = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE alert_color = 'expired') as expired,
                COUNT(*) FILTER (WHERE alert_color = 'red') as red,
                COUNT(*) FILTER (WHERE alert_color = 'yellow') as yellow,
                COUNT(*) FILTER (WHERE alert_color = 'green') as green
            FROM client_expiry_alerts_view
            """,
        )

        # Get top 5 urgent alerts
        urgent = await conn.fetch(
            """
            SELECT
                client_name, entity_name, document_type,
                expiry_date, days_until_expiry, alert_color
            FROM client_expiry_alerts_view
            WHERE alert_color IN ('expired', 'red')
            ORDER BY expiry_date
            LIMIT 5
            """,
        )

        return {"counts": dict(summary), "urgent_alerts": [dict(a) for a in urgent]}


