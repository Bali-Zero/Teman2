"""Admin Email Health Router

Dashboard endpoint for the email-delivery audit trail written by
``backend/services/notifications/email_audit.py`` and retried by
``backend/services/notifications/email_health_monitor.py``.

Admin-only. Returns:
- 7-day rollup (counts per email_type × status)
- pending failures (status IN ('failed','escalated')) with full details
- 7-day failure rate per provider (brevo vs zoho)
"""

from __future__ import annotations

from typing import Any

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.notifications.email_health_monitor import EmailHealthMonitor

router = APIRouter(prefix="/api/admin/email-health", tags=["admin-email-health"])


async def _verify_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_crm_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("")
async def get_email_health(
    db_pool: Pool = Depends(get_database_pool),
    _admin: dict = Depends(_verify_admin),
) -> dict[str, Any]:
    """Return a snapshot of the email delivery health."""
    monitor = EmailHealthMonitor(db_pool)
    return {
        "rollup_7d": await monitor.dashboard_rollup_7d(),
        "pending_failures": await monitor.dashboard_pending_failures(),
        "provider_failure_rate_7d": await monitor.dashboard_provider_failure_rate_7d(),
    }
