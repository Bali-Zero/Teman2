"""
HR/Payroll Router — API endpoints for employees, bonuses, payroll, leave.

RBAC:
- HR Admin (Zero, Asya): full access to all endpoints
- Team members: read-only access to own data + leave requests
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from backend.app.dependencies import get_current_user, get_database_pool
from backend.core.cache import invalidate_cache
from backend.app.services.hr.hr_leave_notifier import (
    notify_leave_request_pending,
    notify_leave_request_reviewed,
)
from backend.app.services.hr.hr_leave_routing import resolve_approver
from backend.app.services.hr.hr_service import HRService
from backend.app.utils.hr_utils import is_hr_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hr", tags=["hr-payroll"])


# ─── Pydantic Models ────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    team_member_id: str
    hire_date: date
    base_salary_idr: int = Field(ge=0)
    bank_name: str | None = None
    bank_account: str | None = None
    bank_account_holder: str | None = None
    npwp: str | None = None
    ptkp_status: str = "TK/0"
    bpjs_kesehatan_number: str | None = None
    bpjs_ketenagakerjaan_number: str | None = None
    notes: str | None = None


class BonusRateCreate(BaseModel):
    practice_type_code: str
    amount_idr: int = Field(ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool = True
    notes: str | None = None


class LeaveRequestCreate(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    total_days: int = Field(gt=0)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> LeaveRequestCreate:
        if self.start_date > self.end_date:
            msg = "start_date must be on or before end_date"
            raise ValueError(msg)
        return self


class LeaveReviewRequest(BaseModel):
    reason: str | None = None


class PayrollCalculateRequest(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)


# ─── Helpers ─────────────────────────────────────────────────────────────

def _get_hr_service(db_pool: asyncpg.Pool) -> HRService:
    return HRService(db_pool)


def _require_hr_admin(user: dict[str, Any]) -> None:
    if not is_hr_admin(user):
        raise HTTPException(status_code=403, detail="HR admin access required")


async def _require_can_review_leave(
    service: HRService,
    user: dict[str, Any],
    request_id: int,
) -> dict[str, Any]:
    """Return the leave request row if the user may approve/reject it.

    Policy:
    - HR admins (Zero, Asya, Ruslana, antonellosiano) can review anyone
      EXCEPT their own requests (self-approval is forbidden).
    - Delegated supervisors (resolved via hr_leave_routing.resolve_approver)
      can review their direct reports only.
    - Raises HTTPException 404 if the request does not exist.
    - Raises HTTPException 403 if the user lacks permission.
    """
    req = await service.get_leave_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")

    user_email = (user.get("email") or "").lower().strip()
    requester_email = (req.get("requester_email") or "").lower().strip()

    # Self-approval is forbidden even for HR admins.
    if user_email and user_email == requester_email:
        raise HTTPException(
            status_code=403,
            detail="You cannot approve or reject your own leave request",
        )

    if is_hr_admin(user):
        return req

    if resolve_approver(requester_email) == user_email:
        return req

    raise HTTPException(
        status_code=403,
        detail="You are not authorized to review this leave request",
    )


def _get_user_id(current_user: dict[str, Any]) -> str:
    """Extract and validate user ID from auth context. Raises 400 if missing.

    Reads `user_id` (the key populated by get_current_user) with `id` as a
    backward-compatible fallback.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID missing from auth token")
    return user_id


async def _get_my_employee_id(
    service: HRService, user: dict[str, Any],
) -> int:
    """Get the employee_id for the current user, or raise 404."""
    emp = await service.get_employee_by_email(user["email"])
    if not emp:
        raise HTTPException(status_code=404, detail="No HR employee record found for your account")
    return emp["id"]


# ─── EMPLOYEES (admin only) ─────────────────────────────────────────────

@router.get("/employees")
async def list_employees(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """List all HR employees."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    employees = await service.list_employees()
    return {"employees": employees, "count": len(employees)}


@router.get("/employees/{employee_id}")
async def get_employee(
    employee_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get employee detail."""
    service = _get_hr_service(db_pool)

    # Team member can view own, admin can view all
    if not is_hr_admin(current_user):
        my_id = await _get_my_employee_id(service, current_user)
        if my_id != employee_id:
            raise HTTPException(status_code=403, detail="Access denied")

    emp = await service.get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@router.post("/employees")
async def upsert_employee(
    data: EmployeeCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Create or update an HR employee record."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    result = await service.upsert_employee(data.model_dump())
    await invalidate_cache("zantara:hr_employees:*")
    return {"success": True, "employee": result}


# ─── BONUS RATES (admin only) ───────────────────────────────────────────

@router.get("/bonus-rates")
async def list_bonus_rates(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """List all bonus rates."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    rates = await service.list_bonus_rates()
    return {"rates": rates, "count": len(rates)}


@router.post("/bonus-rates")
async def upsert_bonus_rate(
    data: BonusRateCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Create or update a bonus rate."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    result = await service.upsert_bonus_rate(data.model_dump())
    await invalidate_cache("zantara:hr_bonuses:*")
    return {"success": True, "rate": result}


# ─── BONUSES ─────────────────────────────────────────────────────────────

@router.get("/bonuses")
async def list_bonuses(
    employee_id: int | None = Query(None),
    status: str | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """List bonuses. Team members see only their own."""
    service = _get_hr_service(db_pool)

    if not is_hr_admin(current_user):
        my_id = await _get_my_employee_id(service, current_user)
        employee_id = my_id  # Force filter to own bonuses

    bonuses = await service.list_bonuses(employee_id, status, month, year)
    return {"bonuses": bonuses, "count": len(bonuses)}


@router.post("/bonuses/{bonus_id}/approve")
async def approve_bonus(
    bonus_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a pending bonus."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    try:
        approver_id = _get_user_id(current_user)
        result = await service.approve_bonus(bonus_id, approver_id)
        await invalidate_cache("zantara:hr_bonuses:*")
        return {"success": True, "bonus": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── PAYROLL ─────────────────────────────────────────────────────────────

@router.post("/payroll/calculate")
async def calculate_payroll(
    data: PayrollCalculateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Calculate payroll for a month (admin only)."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    result = await service.calculate_payroll(
        data.month, data.year, _get_user_id(current_user),
    )
    await invalidate_cache("zantara:hr_payroll:*")
    return {"success": True, **result}


@router.get("/payroll/periods")
async def list_payroll_periods(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """List payroll periods."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    periods = await service.list_payroll_periods()
    return {"periods": periods, "count": len(periods)}


@router.get("/payslips")
async def list_payslips(
    employee_id: int | None = Query(None),
    period_id: int | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """List payslips. Team members see only their own."""
    service = _get_hr_service(db_pool)

    if not is_hr_admin(current_user):
        my_id = await _get_my_employee_id(service, current_user)
        employee_id = my_id

    payslips = await service.get_payslips(employee_id, period_id)
    return {"payslips": payslips, "count": len(payslips)}


@router.get("/payslips/{payslip_id}")
async def get_payslip_detail(
    payslip_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get payslip with deduction breakdown."""
    service = _get_hr_service(db_pool)
    detail = await service.get_payslip_detail(payslip_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Payslip not found")

    # Check access
    if not is_hr_admin(current_user):
        my_id = await _get_my_employee_id(service, current_user)
        if detail.get("employee_id") != my_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return detail


@router.post("/payroll/{period_id}/approve")
async def approve_payroll(
    period_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a payroll period (locks it)."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    try:
        approver_id = _get_user_id(current_user)
        result = await service.approve_payroll(period_id, approver_id)
        await invalidate_cache("zantara:hr_payroll:*")
        return {"success": True, "period": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payroll/{period_id}/mark-paid")
async def mark_payroll_paid(
    period_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Mark payroll period as paid."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    try:
        result = await service.mark_payroll_paid(period_id)
        await invalidate_cache("zantara:hr_payroll:*")
        return {"success": True, "period": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── LEAVE ───────────────────────────────────────────────────────────────

@router.get("/leave/types")
async def get_leave_types(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Return all active leave types for dropdown population."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, code, name, default_days, is_paid, requires_document "
            "FROM hr_leave_types WHERE is_active = TRUE ORDER BY id",
        )
        return {"leave_types": [dict(r) for r in rows]}


@router.post("/leave/request")
async def request_leave(
    data: LeaveRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Create a leave request.

    On success, schedules a fire-and-forget email notification to the
    supervisor (see hr_leave_routing.build_notification_recipients).
    Email failure does NOT fail the request; it is logged as a warning.
    """
    service = _get_hr_service(db_pool)
    my_id = await _get_my_employee_id(service, current_user)
    try:
        result = await service.request_leave({
            "employee_id": my_id,
            **data.model_dump(),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Schedule the supervisor notification email (fire-and-forget)
    leave_type_name = await service.get_leave_type_name(data.leave_type_id)
    background_tasks.add_task(
        notify_leave_request_pending,
        request_id=result["id"],
        requester_email=current_user.get("email", ""),
        requester_name=(
            current_user.get("full_name") or current_user.get("email", "")
        ),
        leave_type_name=leave_type_name,
        start_date=data.start_date,
        end_date=data.end_date,
        total_days=data.total_days,
        reason=data.reason,
    )

    await invalidate_cache("zantara:hr_leave:*")
    return {"success": True, "request": result}


@router.get("/leave/requests")
async def list_leave_requests(
    employee_id: int | None = Query(None),
    status: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """List leave requests."""
    service = _get_hr_service(db_pool)

    if not is_hr_admin(current_user):
        my_id = await _get_my_employee_id(service, current_user)
        employee_id = my_id

    requests = await service.list_leave_requests(employee_id, status)
    return {"requests": requests, "count": len(requests)}


@router.get("/leave/balance")
async def get_leave_balance(
    year: int | None = Query(None),
    employee_id: int | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get leave balance."""
    service = _get_hr_service(db_pool)

    if not is_hr_admin(current_user) or employee_id is None:
        eid = await _get_my_employee_id(service, current_user)
    else:
        eid = employee_id

    balances = await service.get_leave_balance(eid, year)
    return {"balances": balances}


@router.get("/leave/team-summary")
async def get_team_leave_summary(
    year: int | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get leave balance summary for all team members. Admin only."""
    if not is_hr_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin only")
    service = _get_hr_service(db_pool)
    summary = await service.get_team_leave_summary(year)
    return {"summary": summary}


@router.post("/leave/{request_id}/approve")
async def approve_leave(
    request_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a leave request.

    Permission: HR admins (except self) OR the delegated supervisor of
    the requester. Self-approval is forbidden for everyone.

    On success, schedules a fire-and-forget email notification to the
    requester (with Zero/Asya in CC, dedup'd against the reviewer).
    """
    service = _get_hr_service(db_pool)
    req = await _require_can_review_leave(service, current_user, request_id)
    try:
        await service.approve_leave(
            request_id, _get_user_id(current_user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(
        notify_leave_request_reviewed,
        request_id=request_id,
        requester_email=req.get("requester_email", ""),
        requester_name=req.get("requester_name") or req.get("requester_email", ""),
        reviewer_email=current_user.get("email", ""),
        reviewer_name=(
            current_user.get("name") or current_user.get("email", "")
        ),
        leave_type_name=req.get("leave_type_name") or "Leave",
        start_date=req["start_date"],
        end_date=req["end_date"],
        total_days=req["total_days"],
        action="approved",
        rejection_reason=None,
    )

    await invalidate_cache("zantara:hr_leave:*")
    return {
        "success": True,
        "request": {**req, "status": "approved"},
    }


@router.post("/leave/{request_id}/reject")
async def reject_leave(
    request_id: int,
    data: LeaveReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Reject a leave request.

    Permission: HR admins (except self) OR the delegated supervisor of
    the requester. Self-rejection is forbidden for everyone.

    On success, schedules a fire-and-forget email notification to the
    requester (with Zero/Asya in CC, dedup'd against the reviewer).
    """
    service = _get_hr_service(db_pool)
    req = await _require_can_review_leave(service, current_user, request_id)
    try:
        await service.reject_leave(
            request_id, _get_user_id(current_user), data.reason or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(
        notify_leave_request_reviewed,
        request_id=request_id,
        requester_email=req.get("requester_email", ""),
        requester_name=req.get("requester_name") or req.get("requester_email", ""),
        reviewer_email=current_user.get("email", ""),
        reviewer_name=(
            current_user.get("name") or current_user.get("email", "")
        ),
        leave_type_name=req.get("leave_type_name") or "Leave",
        start_date=req["start_date"],
        end_date=req["end_date"],
        total_days=req["total_days"],
        action="rejected",
        rejection_reason=data.reason or None,
    )

    await invalidate_cache("zantara:hr_leave:*")
    return {
        "success": True,
        "request": {
            **req,
            "status": "rejected",
            "rejection_reason": data.reason or None,
        },
    }


# ─── DASHBOARD ───────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Admin HR dashboard."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    return await service.get_admin_dashboard()


@router.get("/my-dashboard")
async def get_my_dashboard(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Personal dashboard for team member."""
    service = _get_hr_service(db_pool)
    my_id = await _get_my_employee_id(service, current_user)
    return await service.get_my_dashboard(my_id)
