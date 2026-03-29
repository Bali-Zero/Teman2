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
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
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
        result = await service.approve_bonus(bonus_id, current_user.get("id", ""))
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
        data.month, data.year, current_user.get("id", ""),
    )
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
        result = await service.approve_payroll(period_id, current_user.get("id", ""))
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
        return {"success": True, "period": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── LEAVE ───────────────────────────────────────────────────────────────

@router.post("/leave/request")
async def request_leave(
    data: LeaveRequestCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Create a leave request."""
    service = _get_hr_service(db_pool)
    my_id = await _get_my_employee_id(service, current_user)
    try:
        result = await service.request_leave({
            "employee_id": my_id,
            **data.model_dump(),
        })
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.post("/leave/{request_id}/approve")
async def approve_leave(
    request_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a leave request."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    try:
        result = await service.approve_leave(request_id, current_user.get("id", ""))
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/leave/{request_id}/reject")
async def reject_leave(
    request_id: int,
    data: LeaveReviewRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Reject a leave request."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    try:
        result = await service.reject_leave(
            request_id, current_user.get("id", ""), data.reason or "",
        )
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
