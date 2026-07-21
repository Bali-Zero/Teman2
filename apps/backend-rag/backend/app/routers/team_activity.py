"""
Team Activity API Router
Endpoints for team timesheet and activity tracking
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field

from backend.app.dependencies import get_current_user
from backend.app.utils.crm_utils import is_crm_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/team", tags=["team-activity"])


# ============================================================================
# Pydantic Models
# ============================================================================


class ClockInRequest(BaseModel):
    """Clock-in request"""

    user_id: str = Field(..., description="User identifier")
    email: EmailStr = Field(..., description="User email")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")


class ClockOutRequest(BaseModel):
    """Clock-out request"""

    user_id: str = Field(..., description="User identifier")
    email: EmailStr = Field(..., description="User email")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")


class ClockResponse(BaseModel):
    """Clock-in/out response"""

    success: bool
    action: str | None = None
    timestamp: str | None = None
    bali_time: str | None = None
    message: str
    error: str | None = None
    hours_worked: float | None = None


class UserStatusResponse(BaseModel):
    """User work status response"""

    user_id: str
    is_online: bool
    last_action: str | None
    last_action_type: str | None
    today_hours: float
    week_hours: float
    week_days: int


class TeamMemberStatus(BaseModel):
    """Team member status"""

    user_id: str
    email: str
    is_online: bool
    last_action: str
    last_action_type: str


class DailyHours(BaseModel):
    """Daily work hours.

    date / clock_in / clock_out are Optional because get_daily_hours() emits
    None for members still clocked in (no clock_out yet) or edge-case rows with
    a NULL work_date/clock_in. The service guards those NULLs (returning None);
    the model must accept them or DailyHours(**row) raises ValidationError ->
    HTTP 400 on GET /api/team/hours (observed live 2026-07-09).
    """

    user_id: str
    email: str
    date: str | None = None
    clock_in: str | None = None
    clock_out: str | None = None
    hours_worked: float = 0.0


class WeeklySummary(BaseModel):
    """Weekly work summary"""

    user_id: str
    email: str
    week_start: str
    days_worked: int
    total_hours: float
    avg_hours_per_day: float


class MonthlySummary(BaseModel):
    """Monthly work summary"""

    user_id: str
    email: str
    month_start: str
    days_worked: int
    total_hours: float
    avg_hours_per_day: float


# ============================================================================
# Admin Authorization
# ============================================================================


def verify_admin(user: dict) -> bool:
    """Check if user is admin"""
    return is_crm_admin(user)


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency to verify admin user
    """
    if verify_admin(current_user):
        return current_user

    raise HTTPException(status_code=403, detail="Admin access required")


def _resolve_actor_identity(
    current_user: dict,
    requested_user_id: str,
    requested_email: str,
) -> tuple[str, str]:
    """
    Resolve the (user_id, email) pair a team-member endpoint acts on
    (tourniquet, 2026-07-21 — round 2, Codex red-team on the round-1 diff).

    Round 1 only compared `request.email` against the token. That missed
    that `team_timesheet_service` keys every row — the INSERT and the
    "already clocked in" lookup — on `user_id`, which round 1 still took
    verbatim from the body. A non-admin could send their own (token-
    matching) email with a VICTIM's user_id and clock the victim in/out
    under their own attendance record.

    Fix: for non-admin callers, identity is ALWAYS the authenticated
    principal's own (user_id, email) — the caller-supplied values are
    ignored outright, not validated-then-trusted, so there is no mismatch
    check left to defeat. Admins keep acting on behalf of another team
    member (existing `is_crm_admin` precedent).

    `current_user["user_id"]` comes from `get_current_user()`, which for
    the live kita cookie-auth path resolves to `HybridAuthMiddleware`'s
    `request.state.user["id"]` = the JWT `sub` claim = `str(user["id"])` —
    verified to equal the same value the kita frontend independently sends
    as `userProfile.id` in the request body, so this never breaks a
    legitimate caller's own clock-in/out/status.
    """
    if verify_admin(current_user):
        return requested_user_id, requested_email

    own_user_id = str(current_user.get("user_id") or current_user.get("email") or "")
    own_email = str(current_user.get("email") or "")
    if requested_user_id != own_user_id or requested_email.strip().lower() != own_email.strip().lower():
        logger.warning(
            "team_activity identity override: non-admin %s requested identity (user_id=%s, "
            "email=%s) — using own principal identity instead",
            own_email,
            requested_user_id,
            requested_email,
        )
    return own_user_id, own_email


# ============================================================================
# Team Member Endpoints (All team members can use)
# ============================================================================


@router.post("/clock-in", response_model=ClockResponse)
async def clock_in(
    request: ClockInRequest,
    current_user: dict = Depends(get_current_user),
) -> ClockResponse:
    """
    Clock in for work day

    Team members use this to start their work day.
    One clock-in per day allowed.

    SECURITY (tourniquet, 2026-07-21 — see memory
    `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`):
    this endpoint previously had no `Depends`, trusting user_id/email from
    the request body — anyone could clock any team member in/out with a
    bare unauthenticated POST. Now requires a valid session (401 if
    missing/invalid). Non-admin callers ALWAYS clock themselves in — the
    body's identity is ignored, not merely validated, per
    `_resolve_actor_identity` (round 2: round 1's email-only check still
    let user_id through unverified). Admins keep the ability to act on
    behalf of another team member (existing `is_crm_admin` precedent, see
    `get_admin_user` above) — the only live caller (kita app) always sends
    the logged-in user's own profile, so this does not change that path.
    """
    actor_user_id, actor_email = _resolve_actor_identity(
        current_user, request.user_id, request.email
    )

    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        result = await service.clock_in(
            user_id=actor_user_id,
            email=actor_email,
            metadata=request.metadata,
        )
        return ClockResponse(**result)
    except Exception as e:
        logger.error("❌ Clock-in failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/clock-out", response_model=ClockResponse)
async def clock_out(
    request: ClockOutRequest,
    current_user: dict = Depends(get_current_user),
) -> ClockResponse:
    """
    Clock out for work day

    Team members use this to end their work day.
    Must be clocked in first.

    SECURITY (tourniquet, 2026-07-21): same identity gate as `clock_in`
    above — see that docstring for the full rationale.
    """
    actor_user_id, actor_email = _resolve_actor_identity(
        current_user, request.user_id, request.email
    )

    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        result = await service.clock_out(
            user_id=actor_user_id,
            email=actor_email,
            metadata=request.metadata,
        )
        return ClockResponse(**result)
    except Exception as e:
        logger.error("❌ Clock-out failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/my-status", response_model=UserStatusResponse)
async def get_my_status(
    user_id: str = Query(..., description="User ID"),
    current_user: dict = Depends(get_current_user),
) -> UserStatusResponse:
    """
    Get my current work status

    Returns:
    - Current online/offline status
    - Today's hours worked
    - This week's summary

    SECURITY (tourniquet round-2, 2026-07-21 — class-audit sibling of
    clock-in/out, same PII exposure class): this endpoint previously took
    `user_id` from an unauthenticated query param — anyone could read
    anyone's online status / hours by enumerating user_id. Same identity
    rule as clock-in/out: non-admin always gets THEIR OWN status
    (`_resolve_actor_identity` ignores the query value); admin can still
    query anyone.
    """
    resolved_user_id, _ = _resolve_actor_identity(current_user, user_id, "")

    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        status = await service.get_my_status(resolved_user_id)
        return UserStatusResponse(**status)
    except Exception as e:
        logger.error("❌ Get status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Admin-Only Endpoints
# ============================================================================


@router.get("/status", response_model=list[TeamMemberStatus])
async def get_team_status(_admin: dict = Depends(get_admin_user)) -> list[Any]:
    """
    Get current online status of all team members (ADMIN ONLY)

    Shows who is currently clocked in and who is offline.
    """
    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        statuses = await service.get_team_online_status()
        return [TeamMemberStatus(**s) for s in statuses]
    except Exception as e:
        logger.error("❌ Get team status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/hours", response_model=list[DailyHours])
async def get_daily_hours(
    date: str | None = Query(None, description="Date (YYYY-MM-DD, defaults to today)"),
    _admin: dict = Depends(get_admin_user),
) -> list[Any]:
    """
    Get work hours for a specific date (ADMIN ONLY)

    Returns all team members' work hours for the specified date.
    """
    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        target_date = None
        if date:
            target_date = datetime.fromisoformat(date)

        hours = await service.get_daily_hours(target_date)
        return [DailyHours(**h) for h in hours]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}") from e
    except Exception as e:
        logger.error("❌ Get daily hours failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/activity/weekly", response_model=list[WeeklySummary])
async def get_weekly_summary(
    week_start: str | None = Query(None, description="Week start date (YYYY-MM-DD)"),
    _admin: dict = Depends(get_admin_user),
) -> list[Any]:
    """
    Get weekly work summary (ADMIN ONLY)

    Returns total hours, days worked, and averages for each team member.
    """
    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        target_week = None
        if week_start:
            target_week = datetime.fromisoformat(week_start)

        summary = await service.get_weekly_summary(target_week)
        return [WeeklySummary(**s) for s in summary]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}") from e
    except Exception as e:
        logger.error("❌ Get weekly summary failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/activity/monthly", response_model=list[MonthlySummary])
async def get_monthly_summary(
    month_start: str | None = Query(None, description="Month start date (YYYY-MM-DD)"),
    _admin: dict = Depends(get_admin_user),
) -> list[Any]:
    """
    Get monthly work summary (ADMIN ONLY)

    Returns total hours, days worked, and averages for each team member.
    """
    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        target_month = None
        if month_start:
            target_month = datetime.fromisoformat(month_start)

        summary = await service.get_monthly_summary(target_month)
        return [MonthlySummary(**s) for s in summary]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}") from e
    except Exception as e:
        logger.error("❌ Get monthly summary failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/export")
async def export_timesheet(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    format: str = Query("csv", description="Export format (csv only for now)"),
    _admin: dict = Depends(get_admin_user),
) -> Response:
    """
    Export timesheet data (ADMIN ONLY)

    Returns CSV file with all work hours in the specified date range.
    """
    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format supported")

    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        csv_data = await service.export_timesheet_csv(start, end)

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=timesheet_{start_date}_to_{end_date}.csv",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}") from e
    except Exception as e:
        logger.error("❌ Export timesheet failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check for team activity service"""
    from backend.services.analytics.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()

    return {
        "service": "team-activity",
        "status": "healthy" if service else "unavailable",
        "auto_logout_enabled": service.running if service else False,
    }
