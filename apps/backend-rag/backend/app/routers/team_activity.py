"""
Team Activity API Router
Endpoints for team timesheet and activity tracking
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

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
    """Daily work hours"""

    user_id: str
    email: str
    date: str
    clock_in: str
    clock_out: str
    hours_worked: float


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

ADMIN_EMAILS = ["zero@balizero.com", "admin@zantara.io", "admin@balizero.com"]


def verify_admin(email: str) -> bool:
    """Check if user is admin"""
    return email.lower() in ADMIN_EMAILS


async def get_admin_email(
    _authorization: str | None = Header(None), x_user_email: str | None = Header(None)
) -> str:
    """
    Extract and verify admin email from headers

    Accepts either:
    - X-User-Email header (for demo/mock auth)
    - Authorization header (for future JWT implementation)
    """
    # Try X-User-Email header first (demo mode)
    if x_user_email:
        email = x_user_email.lower()
        if verify_admin(email):
            return email
        raise HTTPException(status_code=403, detail="Admin access required")

    # JWT authentication is handled by middleware
    #     token = authorization[7:]
    #     email = decode_jwt_token(token)
    #     if verify_admin(email):
    #         return email

    raise HTTPException(
        status_code=401, detail="Authentication required. Provide X-User-Email header."
    )


# ============================================================================
# Team Member Endpoints (All team members can use)
# ============================================================================


@router.post("/clock-in", response_model=ClockResponse)
async def clock_in(request: ClockInRequest):
    """
    Clock in for work day

    Team members use this to start their work day.
    One clock-in per day allowed.
    """
    from services.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        result = await service.clock_in(
            user_id=request.user_id, email=request.email, metadata=request.metadata
        )
        return ClockResponse(**result)
    except Exception as e:
        logger.error(f"❌ Clock-in failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/clock-out", response_model=ClockResponse)
async def clock_out(request: ClockOutRequest):
    """
    Clock out for work day

    Team members use this to end their work day.
    Must be clocked in first.
    """
    from services.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        result = await service.clock_out(
            user_id=request.user_id, email=request.email, metadata=request.metadata
        )
        return ClockResponse(**result)
    except Exception as e:
        logger.error(f"❌ Clock-out failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/my-status", response_model=UserStatusResponse)
async def get_my_status(user_id: str = Query(..., description="User ID")):
    """
    Get my current work status

    Returns:
    - Current online/offline status
    - Today's hours worked
    - This week's summary
    """
    from services.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        status = await service.get_my_status(user_id)
        return UserStatusResponse(**status)
    except Exception as e:
        logger.error(f"❌ Get status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Admin-Only Endpoints
# ============================================================================


@router.get("/status", response_model=list[TeamMemberStatus])
async def get_team_status(_admin_email: str = Depends(get_admin_email)):
    """
    Get current online status of all team members (ADMIN ONLY)

    Shows who is currently clocked in and who is offline.
    """
    from services.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()
    if not service:
        raise HTTPException(status_code=503, detail="Timesheet service unavailable")

    try:
        statuses = await service.get_team_online_status()
        return [TeamMemberStatus(**s) for s in statuses]
    except Exception as e:
        logger.error(f"❌ Get team status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/hours", response_model=list[DailyHours])
async def get_daily_hours(
    date: str | None = Query(None, description="Date (YYYY-MM-DD, defaults to today)"),
    _admin_email: str = Depends(get_admin_email),
):
    """
    Get work hours for a specific date (ADMIN ONLY)

    Returns all team members' work hours for the specified date.
    """
    from services.team_timesheet_service import get_timesheet_service

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
        logger.error(f"❌ Get daily hours failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/activity/weekly", response_model=list[WeeklySummary])
async def get_weekly_summary(
    week_start: str | None = Query(None, description="Week start date (YYYY-MM-DD)"),
    _admin_email: str = Depends(get_admin_email),
):
    """
    Get weekly work summary (ADMIN ONLY)

    Returns total hours, days worked, and averages for each team member.
    """
    from services.team_timesheet_service import get_timesheet_service

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
        logger.error(f"❌ Get weekly summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/activity/monthly", response_model=list[MonthlySummary])
async def get_monthly_summary(
    month_start: str | None = Query(None, description="Month start date (YYYY-MM-DD)"),
    _admin_email: str = Depends(get_admin_email),
):
    """
    Get monthly work summary (ADMIN ONLY)

    Returns total hours, days worked, and averages for each team member.
    """
    from services.team_timesheet_service import get_timesheet_service

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
        logger.error(f"❌ Get monthly summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/export")
async def export_timesheet(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    format: str = Query("csv", description="Export format (csv only for now)"),
    _admin_email: str = Depends(get_admin_email),
):
    """
    Export timesheet data (ADMIN ONLY)

    Returns CSV file with all work hours in the specified date range.
    """
    from fastapi.responses import Response

    from services.team_timesheet_service import get_timesheet_service

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
                "Content-Disposition": f"attachment; filename=timesheet_{start_date}_to_{end_date}.csv"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}") from e
    except Exception as e:
        logger.error(f"❌ Export timesheet failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def health_check():
    """Health check for team activity service"""
    from services.team_timesheet_service import get_timesheet_service

    service = get_timesheet_service()

    return {
        "service": "team-activity",
        "status": "healthy" if service else "unavailable",
        "auto_logout_enabled": service.running if service else False,
    }
