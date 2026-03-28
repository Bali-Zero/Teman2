"""
HR/Payroll Service — Business logic for employees, bonuses, payroll, leave.

Pattern: asyncpg pool, same as CRM services.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any

import asyncpg

from backend.app.utils.hr_utils import (
    calculate_bpjs,
    calculate_pph21_monthly,
    calculate_thr,
)
import logging

logger = logging.getLogger(__name__)


class HRService:
    """HR/Payroll business logic service."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    # ─── EMPLOYEES ───────────────────────────────────────────────────

    async def list_employees(self) -> list[dict[str, Any]]:
        """List all HR employees with team member info."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT e.*, tm.full_name, tm.email, tm.role
                FROM hr_employees e
                JOIN team_members tm ON tm.id = e.team_member_id
                WHERE e.is_active = TRUE
                ORDER BY tm.full_name
            """)
            return [dict(r) for r in rows]

    async def get_employee(self, employee_id: int) -> dict[str, Any] | None:
        """Get employee by HR employee ID."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT e.*, tm.full_name, tm.email, tm.role
                FROM hr_employees e
                JOIN team_members tm ON tm.id = e.team_member_id
                WHERE e.id = $1
            """, employee_id)
            return dict(row) if row else None

    async def get_employee_by_email(self, email: str) -> dict[str, Any] | None:
        """Get employee by team member email."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT e.*, tm.full_name, tm.email, tm.role
                FROM hr_employees e
                JOIN team_members tm ON tm.id = e.team_member_id
                WHERE tm.email = $1
            """, email)
            return dict(row) if row else None

    async def upsert_employee(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update HR employee record."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO hr_employees (
                    team_member_id, hire_date, base_salary_idr,
                    bank_name, bank_account, bank_account_holder,
                    npwp, ptkp_status,
                    bpjs_kesehatan_number, bpjs_ketenagakerjaan_number,
                    notes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (team_member_id) DO UPDATE SET
                    hire_date = EXCLUDED.hire_date,
                    base_salary_idr = EXCLUDED.base_salary_idr,
                    bank_name = EXCLUDED.bank_name,
                    bank_account = EXCLUDED.bank_account,
                    bank_account_holder = EXCLUDED.bank_account_holder,
                    npwp = EXCLUDED.npwp,
                    ptkp_status = EXCLUDED.ptkp_status,
                    bpjs_kesehatan_number = EXCLUDED.bpjs_kesehatan_number,
                    bpjs_ketenagakerjaan_number = EXCLUDED.bpjs_ketenagakerjaan_number,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                RETURNING *
            """,
                data["team_member_id"],
                data["hire_date"],
                data["base_salary_idr"],
                data.get("bank_name"),
                data.get("bank_account"),
                data.get("bank_account_holder"),
                data.get("npwp"),
                data.get("ptkp_status", "TK/0"),
                data.get("bpjs_kesehatan_number"),
                data.get("bpjs_ketenagakerjaan_number"),
                data.get("notes"),
            )
            logger.info(f"HR employee upserted: team_member_id={data['team_member_id']}")
            return dict(row)

    # ─── BONUS RATES ─────────────────────────────────────────────────

    async def list_bonus_rates(self) -> list[dict[str, Any]]:
        """List all bonus rates."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT br.*, pt.name as practice_type_name
                FROM hr_bonus_rates br
                LEFT JOIN practice_types pt ON pt.code = br.practice_type_code
                ORDER BY br.practice_type_code
            """)
            return [dict(r) for r in rows]

    async def upsert_bonus_rate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update a bonus rate."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO hr_bonus_rates (
                    practice_type_code, amount_idr, effective_from,
                    effective_to, is_active, notes
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (practice_type_code) DO UPDATE SET
                    amount_idr = EXCLUDED.amount_idr,
                    effective_from = EXCLUDED.effective_from,
                    effective_to = EXCLUDED.effective_to,
                    is_active = EXCLUDED.is_active,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                RETURNING *
            """,
                data["practice_type_code"],
                data["amount_idr"],
                data.get("effective_from", date.today()),
                data.get("effective_to"),
                data.get("is_active", True),
                data.get("notes"),
            )
            logger.info(f"Bonus rate upserted: {data['practice_type_code']} = {data['amount_idr']} IDR")
            return dict(row)

    # ─── BONUSES ─────────────────────────────────────────────────────

    async def list_bonuses(
        self,
        employee_id: int | None = None,
        status: str | None = None,
        month: int | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """List bonus ledger entries with filters."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT bl.*, tm.full_name as employee_name, tm.email as employee_email,
                       p.status as practice_status, c.name as client_name
                FROM hr_bonus_ledger bl
                JOIN hr_employees e ON e.id = bl.employee_id
                JOIN team_members tm ON tm.id = e.team_member_id
                JOIN practices p ON p.id = bl.practice_id
                LEFT JOIN clients c ON c.id = p.client_id
                WHERE 1=1
            """
            params: list[Any] = []
            idx = 1

            if employee_id is not None:
                query += f" AND bl.employee_id = ${idx}"
                params.append(employee_id)
                idx += 1

            if status is not None:
                query += f" AND bl.status = ${idx}"
                params.append(status)
                idx += 1

            if month is not None and year is not None:
                query += f" AND EXTRACT(MONTH FROM bl.awarded_at) = ${idx}"
                params.append(month)
                idx += 1
                query += f" AND EXTRACT(YEAR FROM bl.awarded_at) = ${idx}"
                params.append(year)
                idx += 1

            query += " ORDER BY bl.awarded_at DESC"
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def approve_bonus(self, bonus_id: int, approved_by: str) -> dict[str, Any]:
        """Approve a pending bonus."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE hr_bonus_ledger
                SET status = 'approved', approved_by = $2, approved_at = NOW()
                WHERE id = $1 AND status = 'pending'
                RETURNING *
            """, bonus_id, approved_by)
            if not row:
                msg = f"Bonus {bonus_id} not found or not pending"
                raise ValueError(msg)
            logger.info(f"Bonus {bonus_id} approved by {approved_by}")
            return dict(row)

    async def get_bonus_summary(
        self, employee_id: int, month: int, year: int,
    ) -> dict[str, Any]:
        """Get bonus summary for an employee in a given month."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as bonus_count,
                    COALESCE(SUM(amount_idr) FILTER (WHERE status IN ('approved','paid')), 0) as approved_total,
                    COALESCE(SUM(amount_idr) FILTER (WHERE status = 'pending'), 0) as pending_total,
                    COALESCE(SUM(amount_idr), 0) as grand_total
                FROM hr_bonus_ledger
                WHERE employee_id = $1
                  AND EXTRACT(MONTH FROM awarded_at) = $2
                  AND EXTRACT(YEAR FROM awarded_at) = $3
            """, employee_id, month, year)
            return dict(row)

    # ─── PAYROLL ─────────────────────────────────────────────────────

    async def calculate_payroll(
        self, month: int, year: int, created_by: str,
    ) -> dict[str, Any]:
        """
        Calculate payroll for a given month.
        Creates period + payslips + deductions for all active employees.
        """
        period_start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        period_end = date(year, month, last_day)

        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Create or get period
                period = await conn.fetchrow("""
                    INSERT INTO hr_payroll_periods (
                        payroll_month, payroll_year, period_start, period_end,
                        status, created_by
                    ) VALUES ($1, $2, $3, $4, 'calculated', $5)
                    ON CONFLICT (payroll_month, payroll_year) DO UPDATE SET
                        status = 'calculated', updated_at = NOW()
                    RETURNING *
                """, month, year, period_start, period_end, created_by)
                period_id = period["id"]

                # Get all active employees
                employees = await conn.fetch("""
                    SELECT e.*, tm.full_name, tm.email
                    FROM hr_employees e
                    JOIN team_members tm ON tm.id = e.team_member_id
                    WHERE e.is_active = TRUE
                """)

                payslips = []
                for emp in employees:
                    salary = emp["base_salary_idr"]
                    emp_id = emp["id"]
                    ptkp = emp["ptkp_status"]

                    # Sum approved bonuses for this month
                    bonus_row = await conn.fetchrow("""
                        SELECT COALESCE(SUM(amount_idr), 0) as total
                        FROM hr_bonus_ledger
                        WHERE employee_id = $1
                          AND status IN ('approved', 'paid')
                          AND EXTRACT(MONTH FROM awarded_at) = $2
                          AND EXTRACT(YEAR FROM awarded_at) = $3
                    """, emp_id, month, year)
                    bonus_total = bonus_row["total"]

                    # Calculate BPJS
                    bpjs = calculate_bpjs(salary)

                    # Employee deductions
                    ded_kes = bpjs["kesehatan"]["employee"]
                    ded_jht = bpjs["jht"]["employee"]
                    ded_jp = bpjs["jp"]["employee"]
                    pph21 = calculate_pph21_monthly(salary + bonus_total, ptkp)
                    deduction_total = ded_kes + ded_jht + ded_jp + pph21

                    # Net salary
                    net = salary + bonus_total - deduction_total

                    # Delete existing payslip for recalculation
                    await conn.execute("""
                        DELETE FROM hr_deductions WHERE payslip_id IN (
                            SELECT id FROM hr_payslips
                            WHERE employee_id = $1 AND payroll_period_id = $2
                        )
                    """, emp_id, period_id)
                    await conn.execute("""
                        DELETE FROM hr_payslips
                        WHERE employee_id = $1 AND payroll_period_id = $2
                    """, emp_id, period_id)

                    # Insert payslip
                    payslip = await conn.fetchrow("""
                        INSERT INTO hr_payslips (
                            payroll_period_id, employee_id, base_salary_idr,
                            bonus_total_idr, deduction_total_idr, net_salary_idr
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING *
                    """, period_id, emp_id, salary, bonus_total, deduction_total, net)
                    payslip_id = payslip["id"]

                    # Insert deduction items
                    deduction_items = [
                        ("bpjs_kes_employee", "BPJS Kesehatan (1%)", ded_kes, False),
                        ("bpjs_kes_employer", "BPJS Kesehatan (4%)", bpjs["kesehatan"]["employer"], True),
                        ("bpjs_jht_employee", "BPJS JHT (2%)", ded_jht, False),
                        ("bpjs_jht_employer", "BPJS JHT (3.7%)", bpjs["jht"]["employer"], True),
                        ("bpjs_jkk", "BPJS JKK (0.24%)", bpjs["jkk"]["employer"], True),
                        ("bpjs_jkm", "BPJS JKM (0.30%)", bpjs["jkm"]["employer"], True),
                        ("bpjs_jp_employee", "BPJS JP (1%)", ded_jp, False),
                        ("bpjs_jp_employer", "BPJS JP (2%)", bpjs["jp"]["employer"], True),
                        ("pph21", "PPh21", pph21, False),
                    ]
                    for dtype, label, amount, is_employer in deduction_items:
                        if amount > 0:
                            await conn.execute("""
                                INSERT INTO hr_deductions (
                                    payslip_id, deduction_type, label, amount_idr, is_employer
                                ) VALUES ($1, $2, $3, $4, $5)
                            """, payslip_id, dtype, label, amount, is_employer)

                    payslips.append({
                        "employee_name": emp["full_name"],
                        "base_salary": salary,
                        "bonus_total": bonus_total,
                        "deduction_total": deduction_total,
                        "net_salary": net,
                    })

                logger.info(
                    f"Payroll calculated: {month}/{year}, {len(payslips)} employees"
                )
                return {
                    "period_id": period_id,
                    "month": month,
                    "year": year,
                    "employee_count": len(payslips),
                    "payslips": payslips,
                }

    async def list_payroll_periods(self) -> list[dict[str, Any]]:
        """List all payroll periods."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT pp.*,
                    COUNT(ps.id) as payslip_count,
                    COALESCE(SUM(ps.net_salary_idr), 0) as total_net
                FROM hr_payroll_periods pp
                LEFT JOIN hr_payslips ps ON ps.payroll_period_id = pp.id
                GROUP BY pp.id
                ORDER BY pp.payroll_year DESC, pp.payroll_month DESC
            """)
            return [dict(r) for r in rows]

    async def get_payslips(
        self,
        employee_id: int | None = None,
        period_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get payslips with filters."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT ps.*, tm.full_name as employee_name, tm.email as employee_email,
                       pp.payroll_month, pp.payroll_year, pp.status as period_status
                FROM hr_payslips ps
                JOIN hr_employees e ON e.id = ps.employee_id
                JOIN team_members tm ON tm.id = e.team_member_id
                JOIN hr_payroll_periods pp ON pp.id = ps.payroll_period_id
                WHERE 1=1
            """
            params: list[Any] = []
            idx = 1

            if employee_id is not None:
                query += f" AND ps.employee_id = ${idx}"
                params.append(employee_id)
                idx += 1
            if period_id is not None:
                query += f" AND ps.payroll_period_id = ${idx}"
                params.append(period_id)
                idx += 1

            query += " ORDER BY pp.payroll_year DESC, pp.payroll_month DESC"
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def get_payslip_detail(self, payslip_id: int) -> dict[str, Any] | None:
        """Get full payslip with deductions."""
        async with self.db_pool.acquire() as conn:
            payslip = await conn.fetchrow("""
                SELECT ps.*, tm.full_name, tm.email,
                       pp.payroll_month, pp.payroll_year
                FROM hr_payslips ps
                JOIN hr_employees e ON e.id = ps.employee_id
                JOIN team_members tm ON tm.id = e.team_member_id
                JOIN hr_payroll_periods pp ON pp.id = ps.payroll_period_id
                WHERE ps.id = $1
            """, payslip_id)
            if not payslip:
                return None

            deductions = await conn.fetch("""
                SELECT * FROM hr_deductions WHERE payslip_id = $1
                ORDER BY is_employer, deduction_type
            """, payslip_id)

            result = dict(payslip)
            result["deductions"] = [dict(d) for d in deductions]
            return result

    async def approve_payroll(self, period_id: int, approved_by: str) -> dict[str, Any]:
        """Approve a payroll period (locks it)."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE hr_payroll_periods
                SET status = 'approved', approved_by = $2
                WHERE id = $1 AND status = 'calculated'
                RETURNING *
            """, period_id, approved_by)
            if not row:
                msg = f"Period {period_id} not found or not in 'calculated' status"
                raise ValueError(msg)
            logger.info(f"Payroll period {period_id} approved by {approved_by}")
            return dict(row)

    async def mark_payroll_paid(self, period_id: int) -> dict[str, Any]:
        """Mark payroll as paid."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("""
                    UPDATE hr_payroll_periods
                    SET status = 'paid'
                    WHERE id = $1 AND status = 'approved'
                    RETURNING *
                """, period_id)
                if not row:
                    msg = f"Period {period_id} not found or not approved"
                    raise ValueError(msg)

                # Mark all bonuses in this period as paid
                await conn.execute("""
                    UPDATE hr_bonus_ledger
                    SET status = 'paid'
                    WHERE payroll_period_id = $1 AND status = 'approved'
                """, period_id)

                logger.info(f"Payroll period {period_id} marked as paid")
                return dict(row)

    # ─── LEAVE ───────────────────────────────────────────────────────

    async def request_leave(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a leave request."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Check balance
                balance = await conn.fetchrow("""
                    SELECT * FROM hr_leave_balances
                    WHERE employee_id = $1
                      AND leave_type_id = $2
                      AND balance_year = $3
                """, data["employee_id"], data["leave_type_id"],
                    data["start_date"].year)

                if balance:
                    available = (
                        balance["allocated_days"]
                        + balance["carried_over"]
                        - balance["used_days"]
                        - balance["pending_days"]
                    )
                    if data["total_days"] > available:
                        msg = f"Insufficient leave balance: {available} days available, {data['total_days']} requested"
                        raise ValueError(msg)

                    # Reserve pending days
                    await conn.execute("""
                        UPDATE hr_leave_balances
                        SET pending_days = pending_days + $1
                        WHERE id = $2
                    """, data["total_days"], balance["id"])

                row = await conn.fetchrow("""
                    INSERT INTO hr_leave_requests (
                        employee_id, leave_type_id, start_date, end_date,
                        total_days, reason
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING *
                """,
                    data["employee_id"],
                    data["leave_type_id"],
                    data["start_date"],
                    data["end_date"],
                    data["total_days"],
                    data.get("reason"),
                )
                logger.info(f"Leave request created: employee={data['employee_id']}, days={data['total_days']}")
                return dict(row)

    async def approve_leave(self, request_id: int, reviewed_by: str) -> dict[str, Any]:
        """Approve a leave request."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                req = await conn.fetchrow("""
                    UPDATE hr_leave_requests
                    SET status = 'approved', reviewed_by = $2, reviewed_at = NOW()
                    WHERE id = $1 AND status = 'pending'
                    RETURNING *
                """, request_id, reviewed_by)
                if not req:
                    msg = f"Leave request {request_id} not found or not pending"
                    raise ValueError(msg)

                # Move from pending to used
                await conn.execute("""
                    UPDATE hr_leave_balances
                    SET pending_days = pending_days - $1,
                        used_days = used_days + $1
                    WHERE employee_id = $2
                      AND leave_type_id = $3
                      AND balance_year = $4
                """, req["total_days"], req["employee_id"],
                    req["leave_type_id"], req["start_date"].year)

                logger.info(f"Leave request {request_id} approved by {reviewed_by}")
                return dict(req)

    async def reject_leave(
        self, request_id: int, reviewed_by: str, reason: str,
    ) -> dict[str, Any]:
        """Reject a leave request."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                req = await conn.fetchrow("""
                    UPDATE hr_leave_requests
                    SET status = 'rejected', reviewed_by = $2,
                        reviewed_at = NOW(), rejection_reason = $3
                    WHERE id = $1 AND status = 'pending'
                    RETURNING *
                """, request_id, reviewed_by, reason)
                if not req:
                    msg = f"Leave request {request_id} not found or not pending"
                    raise ValueError(msg)

                # Release pending days
                await conn.execute("""
                    UPDATE hr_leave_balances
                    SET pending_days = GREATEST(0, pending_days - $1)
                    WHERE employee_id = $2
                      AND leave_type_id = $3
                      AND balance_year = $4
                """, req["total_days"], req["employee_id"],
                    req["leave_type_id"], req["start_date"].year)

                logger.info(f"Leave request {request_id} rejected by {reviewed_by}")
                return dict(req)

    async def get_leave_balance(
        self, employee_id: int, year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get leave balances for an employee."""
        if year is None:
            year = date.today().year
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT lb.*, lt.code, lt.name as leave_type_name, lt.is_paid
                FROM hr_leave_balances lb
                JOIN hr_leave_types lt ON lt.id = lb.leave_type_id
                WHERE lb.employee_id = $1 AND lb.balance_year = $2
                ORDER BY lt.code
            """, employee_id, year)
            return [dict(r) for r in rows]

    async def list_leave_requests(
        self,
        employee_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List leave requests with filters."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT lr.*, tm.full_name as employee_name, tm.email as employee_email,
                       lt.name as leave_type_name
                FROM hr_leave_requests lr
                JOIN hr_employees e ON e.id = lr.employee_id
                JOIN team_members tm ON tm.id = e.team_member_id
                JOIN hr_leave_types lt ON lt.id = lr.leave_type_id
                WHERE 1=1
            """
            params: list[Any] = []
            idx = 1

            if employee_id is not None:
                query += f" AND lr.employee_id = ${idx}"
                params.append(employee_id)
                idx += 1
            if status is not None:
                query += f" AND lr.status = ${idx}"
                params.append(status)
                idx += 1

            query += " ORDER BY lr.requested_at DESC"
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    # ─── DASHBOARD ───────────────────────────────────────────────────

    async def get_admin_dashboard(self) -> dict[str, Any]:
        """Admin dashboard summary."""
        today = date.today()
        async with self.db_pool.acquire() as conn:
            emp_count = await conn.fetchval(
                "SELECT COUNT(*) FROM hr_employees WHERE is_active = TRUE"
            )
            pending_bonuses = await conn.fetchrow("""
                SELECT COUNT(*) as count, COALESCE(SUM(amount_idr), 0) as total
                FROM hr_bonus_ledger WHERE status = 'pending'
            """)
            pending_leave = await conn.fetchval(
                "SELECT COUNT(*) FROM hr_leave_requests WHERE status = 'pending'"
            )
            current_period = await conn.fetchrow("""
                SELECT * FROM hr_payroll_periods
                WHERE payroll_month = $1 AND payroll_year = $2
            """, today.month, today.year)

            return {
                "employee_count": emp_count,
                "pending_bonuses": dict(pending_bonuses),
                "pending_leave_requests": pending_leave,
                "current_period": dict(current_period) if current_period else None,
                "month": today.month,
                "year": today.year,
            }

    async def get_my_dashboard(self, employee_id: int) -> dict[str, Any]:
        """Personal dashboard for a team member."""
        today = date.today()
        async with self.db_pool.acquire() as conn:
            # Current month bonuses
            bonuses = await conn.fetchrow("""
                SELECT COUNT(*) as count, COALESCE(SUM(amount_idr), 0) as total
                FROM hr_bonus_ledger
                WHERE employee_id = $1
                  AND EXTRACT(MONTH FROM awarded_at) = $2
                  AND EXTRACT(YEAR FROM awarded_at) = $3
            """, employee_id, today.month, today.year)

            # Latest payslip
            latest_payslip = await conn.fetchrow("""
                SELECT ps.*, pp.payroll_month, pp.payroll_year
                FROM hr_payslips ps
                JOIN hr_payroll_periods pp ON pp.id = ps.payroll_period_id
                WHERE ps.employee_id = $1
                ORDER BY pp.payroll_year DESC, pp.payroll_month DESC
                LIMIT 1
            """, employee_id)

            # Leave balance
            leave_balance = await conn.fetch("""
                SELECT lb.*, lt.name
                FROM hr_leave_balances lb
                JOIN hr_leave_types lt ON lt.id = lb.leave_type_id
                WHERE lb.employee_id = $1 AND lb.balance_year = $2
            """, employee_id, today.year)

            return {
                "month_bonuses": dict(bonuses),
                "latest_payslip": dict(latest_payslip) if latest_payslip else None,
                "leave_balances": [dict(r) for r in leave_balance],
            }
