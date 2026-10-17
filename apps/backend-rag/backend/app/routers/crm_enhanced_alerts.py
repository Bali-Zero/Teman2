"""
CRM Enhanced - Expiry Alerts Endpoints

Split from crm_enhanced.py for maintainability.
Provides: expiry alerts listing and summary.
"""

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.auth import require_team_member
from backend.app.deps.crm_access import get_practices_user_filter
from backend.app.utils.crm_utils import can_view_all_practices, is_crm_admin
from backend.app.utils.logging_utils import get_logger
from backend.services.crm.practice_state_machine import (
    LEGACY_STATE_MAP,
    VALID_TRANSITIONS,
    normalize_state,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm", tags=["crm-enhanced-alerts"])


class MemberObligation(BaseModel):
    kind: Literal["passport", "process"]
    client_id: int
    client_name: str
    practice_id: int | None
    practice_type_name: str | None
    status: str
    created_at: datetime | None
    age_days: int | None
    passport_expiry: date | None
    days_left: int | None
    assigned_to: str | None
    can_open_process: bool


class ObligationOwner(BaseModel):
    email: str | None
    name: str
    total: int


class MemberObligationsOut(BaseModel):
    scope: Literal["mine", "team"]
    can_view_team: bool
    can_view_register: bool
    total: int
    passport_count: int
    process_count: int
    limit: int
    offset: int
    owners: list[ObligationOwner]
    items: list[MemberObligation]


_ACTIVE_PRACTICE_STATES = [
    status
    for status in (*VALID_TRANSITIONS, *LEGACY_STATE_MAP)
    if normalize_state(status) not in {"completed", "cancelled"}
]

# Derived from the source records: there is deliberately no duty/acknowledgment
# table. The first two parameters describe existing practice-detail access;
# the third is the resolved visibility boundary, never a user-selected owner.
_MEMBER_OBLIGATIONS_CTE = """
WITH duties AS (
    SELECT 'passport'::text AS kind, c.id AS client_id,
           COALESCE(NULLIF(c.full_name, ''), 'Client ' || c.id) AS client_name,
           NULL::integer AS practice_id, NULL::text AS practice_type_name,
           CASE WHEN c.passport_expiry < CURRENT_DATE THEN 'expired'
                ELSE 'expiring' END AS status,
           NULL::timestamptz AS created_at, NULL::integer AS age_days,
           c.passport_expiry, (c.passport_expiry - CURRENT_DATE)::integer AS days_left,
           NULLIF(LOWER(c.assigned_to), '') AS assigned_to,
           FALSE AS can_open_process, c.passport_expiry AS due_date
      FROM clients c
     WHERE c.deleted_at IS NULL
       AND c.passport_expiry <= CURRENT_DATE + 90
    UNION ALL
    SELECT 'process', c.id, COALESCE(NULLIF(c.full_name, ''), 'Client ' || c.id),
           p.id, pt.name, p.status,
           p.created_at, EXTRACT(DAY FROM (CURRENT_TIMESTAMP - p.created_at))::integer,
           NULL::date, NULL::integer, NULLIF(LOWER(p.assigned_to), ''),
           COALESCE($2::boolean OR c.assigned_to = $1 OR p.created_by = $1
                    OR LOWER(p.assigned_to) = $1, FALSE),
           (p.created_at + INTERVAL '14 days')::date
      FROM practices p
      JOIN clients c ON c.id = p.client_id
      JOIN practice_types pt ON pt.id = p.practice_type_id
     WHERE c.deleted_at IS NULL AND p.status = ANY($5::text[])
       AND p.created_at < CURRENT_TIMESTAMP - INTERVAL '14 days'
), visible AS (
    SELECT * FROM duties WHERE ($3::text IS NULL OR assigned_to = $3)
), filtered AS (
    SELECT * FROM visible
     WHERE ($4::text IS NULL OR assigned_to = $4
            OR ($4 = '__unassigned__' AND assigned_to IS NULL))
)
"""


@router.get("/member-obligations", response_model=MemberObligationsOut)
async def get_member_obligations(
    scope: Literal["mine", "team"] = Query("mine"),
    assigned_to: str | None = Query(None, max_length=254),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(require_team_member),
) -> MemberObligationsOut:
    """Personal duties from CRM records; team overview is a separate read grant."""
    email = str(current_user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Authenticated team identity required")
    full_view = can_view_all_practices(current_user)
    can_view_team = full_view or email in settings.member_obligations_supervisor_emails_set
    owner = (assigned_to or "").strip().lower() or None
    if scope == "team" and not can_view_team:
        raise HTTPException(status_code=403, detail="Team overview access required")
    if scope == "mine" and owner and owner != email:
        raise HTTPException(
            status_code=403, detail="Personal obligations are limited to your assignments"
        )

    args = (email, full_view, None if scope == "team" else email, owner, _ACTIVE_PRACTICE_STATES)
    async with pool.acquire() as conn:
        counts = await conn.fetchrow(
            _MEMBER_OBLIGATIONS_CTE
            + "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE kind = 'passport') "
            "AS passport_count, COUNT(*) FILTER (WHERE kind = 'process') AS process_count "
            "FROM filtered",
            *args,
        )
        rows = await conn.fetch(
            _MEMBER_OBLIGATIONS_CTE
            + "SELECT * FROM filtered ORDER BY due_date, kind, client_id, practice_id "
            "LIMIT $6 OFFSET $7",
            *args,
            limit,
            offset,
        )
        owners = await conn.fetch(
            _MEMBER_OBLIGATIONS_CTE
            + """SELECT v.assigned_to AS email,
                       COALESCE((SELECT COALESCE(NULLIF(tm.full_name, ''), tm.name)
                                   FROM team_members tm
                                  WHERE LOWER(tm.email) = v.assigned_to
                                  ORDER BY tm.active DESC NULLS LAST, tm.id LIMIT 1),
                                v.assigned_to, 'Unassigned') AS name,
                       COUNT(*) AS total
                  FROM visible v GROUP BY v.assigned_to ORDER BY name""",
            *args,
        )
    return MemberObligationsOut(
        scope=scope,
        can_view_team=can_view_team,
        can_view_register=is_crm_admin(current_user),
        **dict(counts),
        limit=limit,
        offset=offset,
        owners=[ObligationOwner.model_validate(dict(row)) for row in owners],
        items=[MemberObligation.model_validate(dict(row)) for row in rows],
    )


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
    Non-admin users see only alerts for their assigned clients.
    """
    async with pool.acquire() as conn:
        # RBAC: non-admin users only see their own assigned alerts
        user_filter = get_practices_user_filter(current_user)
        if user_filter and not assigned_to:
            assigned_to = user_filter

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
    user_filter = get_practices_user_filter(current_user)

    async with pool.acquire() as conn:
        rbac_clause = ""
        params: list = []
        if user_filter:
            rbac_clause = "WHERE LOWER(assigned_to) = $1"
            params.append(user_filter)

        summary = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*) FILTER (WHERE alert_color = 'expired') as expired,
                COUNT(*) FILTER (WHERE alert_color = 'red') as red,
                COUNT(*) FILTER (WHERE alert_color = 'yellow') as yellow,
                COUNT(*) FILTER (WHERE alert_color = 'green') as green
            FROM client_expiry_alerts_view
            {rbac_clause}
            """,
            *params,
        )

        # Get top 5 urgent alerts
        urgent_where = "WHERE alert_color IN ('expired', 'red')"
        if user_filter:
            urgent_where += " AND LOWER(assigned_to) = $1"

        urgent = await conn.fetch(
            f"""
            SELECT
                client_name, entity_name, document_type,
                expiry_date, days_until_expiry, alert_color
            FROM client_expiry_alerts_view
            {urgent_where}
            ORDER BY expiry_date
            LIMIT 5
            """,
            *params,
        )

        return {"counts": dict(summary), "urgent_alerts": [dict(a) for a in urgent]}
