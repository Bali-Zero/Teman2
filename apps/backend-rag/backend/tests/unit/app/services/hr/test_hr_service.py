"""
Unit tests for backend/app/services/hr/hr_service.py

Covers: HRService init, list_employees, get_employee, get_employee_by_email,
        upsert_employee, list_bonus_rates, upsert_bonus_rate, list_bonuses,
        approve_bonus, get_bonus_summary, calculate_payroll,
        list_payroll_periods, get_payslips, get_payslip_detail,
        approve_payroll, mark_payroll_paid, request_leave, approve_leave,
        reject_leave, get_leave_request, get_leave_type_name,
        get_leave_balance, get_team_leave_summary, list_leave_requests,
        get_admin_dashboard, get_my_dashboard.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.hr.hr_service import HRService


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()

    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=None)
    tx_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_cm)

    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def hr_service(mock_db_pool):
    return HRService(db_pool=mock_db_pool)


def _make_row(data: dict):
    """Create a mock asyncpg Row."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    row.__iter__ = MagicMock(return_value=iter(data.items()))
    row.keys = MagicMock(return_value=data.keys())
    # Make dict(row) work
    row.__class__ = dict
    return data  # asyncpg rows behave like dicts in practice


# ============================================================================
# Employees
# ============================================================================


class TestListEmployees:
    @pytest.mark.asyncio
    async def test_list_employees(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "full_name": "Alice", "email": "alice@test.com", "role": "agent"},
        ])
        result = await hr_service.list_employees()
        assert len(result) == 1
        assert result[0]["full_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_list_employees_empty(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await hr_service.list_employees()
        assert result == []


class TestGetEmployee:
    @pytest.mark.asyncio
    async def test_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "Alice"})
        result = await hr_service.get_employee(1)
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await hr_service.get_employee(999)
        assert result is None


class TestGetEmployeeByEmail:
    @pytest.mark.asyncio
    async def test_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "email": "a@t.com"})
        result = await hr_service.get_employee_by_email("a@t.com")
        assert result["email"] == "a@t.com"

    @pytest.mark.asyncio
    async def test_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await hr_service.get_employee_by_email("x@y.com")
        assert result is None


class TestUpsertEmployee:
    @pytest.mark.asyncio
    async def test_upsert(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={
            "id": 1, "team_member_id": 10, "base_salary_idr": 5000000,
        })
        data = {
            "team_member_id": 10, "hire_date": date(2024, 1, 1),
            "base_salary_idr": 5000000, "ptkp_status": "TK/0",
        }
        result = await hr_service.upsert_employee(data)
        assert result["team_member_id"] == 10


# ============================================================================
# Bonus Rates
# ============================================================================


class TestBonusRates:
    @pytest.mark.asyncio
    async def test_list(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "practice_type_code": "visa", "amount_idr": 100000},
        ])
        result = await hr_service.list_bonus_rates()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_upsert(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={
            "id": 1, "practice_type_code": "visa", "amount_idr": 150000,
        })
        data = {"practice_type_code": "visa", "amount_idr": 150000}
        result = await hr_service.upsert_bonus_rate(data)
        assert result["amount_idr"] == 150000


# ============================================================================
# Bonuses
# ============================================================================


class TestBonuses:
    @pytest.mark.asyncio
    async def test_list_bonuses_no_filter(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "employee_id": 1, "amount_idr": 100000, "status": "pending"},
        ])
        result = await hr_service.list_bonuses()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_bonuses_with_filters(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await hr_service.list_bonuses(employee_id=1, status="pending", month=4, year=2026)
        assert result == []

    @pytest.mark.asyncio
    async def test_approve_bonus(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={
            "id": 1, "status": "approved", "approved_by": "admin@test.com",
        })
        result = await hr_service.approve_bonus(1, "admin@test.com")
        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_bonus_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found or not pending"):
            await hr_service.approve_bonus(999, "admin@test.com")

    @pytest.mark.asyncio
    async def test_get_bonus_summary(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={
            "bonus_count": 3, "approved_total": 300000, "pending_total": 100000, "grand_total": 400000,
        })
        result = await hr_service.get_bonus_summary(1, 4, 2026)
        assert result["bonus_count"] == 3


# ============================================================================
# Payroll
# ============================================================================


class TestPayroll:
    @pytest.mark.asyncio
    @patch("backend.app.services.hr.hr_service.calculate_bpjs")
    @patch("backend.app.services.hr.hr_service.calculate_pph21_monthly")
    async def test_calculate_payroll(self, mock_pph, mock_bpjs, hr_service, mock_db_pool):
        mock_bpjs.return_value = {
            "kesehatan": {"employee": 50000, "employer": 200000},
            "jht": {"employee": 100000, "employer": 185000},
            "jkk": {"employer": 12000},
            "jkm": {"employer": 15000},
            "jp": {"employee": 50000, "employer": 100000},
        }
        mock_pph.return_value = 150000

        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": 1},  # period
            {"total": 200000},  # bonus sum
            {"id": 10},  # payslip
        ])
        conn.fetch = AsyncMock(return_value=[{
            "id": 1, "base_salary_idr": 5000000, "ptkp_status": "TK/0",
            "full_name": "Alice", "email": "alice@t.com",
        }])
        conn.execute = AsyncMock()

        result = await hr_service.calculate_payroll(4, 2026, "admin@test.com")
        assert result["employee_count"] == 1
        assert result["month"] == 4
        assert result["year"] == 2026

    @pytest.mark.asyncio
    async def test_list_payroll_periods(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "payroll_month": 4, "payroll_year": 2026, "status": "calculated"},
        ])
        result = await hr_service.list_payroll_periods()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_payslips_no_filter(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await hr_service.get_payslips()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_payslips_with_filters(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await hr_service.get_payslips(employee_id=1, period_id=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_payslip_detail_found(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={
            "id": 1, "base_salary_idr": 5000000, "net_salary_idr": 4500000,
        })
        conn.fetch = AsyncMock(return_value=[
            {"deduction_type": "pph21", "amount_idr": 150000, "is_employer": False},
        ])
        result = await hr_service.get_payslip_detail(1)
        assert result is not None
        assert "deductions" in result

    @pytest.mark.asyncio
    async def test_get_payslip_detail_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await hr_service.get_payslip_detail(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_approve_payroll(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={
            "id": 1, "status": "approved", "approved_by": "admin",
        })
        result = await hr_service.approve_payroll(1, "admin")
        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_payroll_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await hr_service.approve_payroll(999, "admin")

    @pytest.mark.asyncio
    async def test_mark_payroll_paid(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value={"id": 1, "status": "paid"})
        conn.execute = AsyncMock()
        result = await hr_service.mark_payroll_paid(1)
        assert result["status"] == "paid"

    @pytest.mark.asyncio
    async def test_mark_payroll_paid_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found or not approved"):
            await hr_service.mark_payroll_paid(999)


# ============================================================================
# Leave
# ============================================================================


class TestLeave:
    @pytest.mark.asyncio
    async def test_request_leave(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": 1},  # leave_type check
            {"allocated_days": 12, "carried_over": 0, "used_days": 2, "pending_days": 0, "id": 1},  # balance
            {"id": 1, "employee_id": 1, "status": "pending"},  # insert
        ])
        conn.execute = AsyncMock()

        data = {
            "employee_id": 1, "leave_type_id": 1,
            "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 3),
            "total_days": 3,
        }
        result = await hr_service.request_leave(data)
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_request_leave_insufficient_balance(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": 1},  # leave type
            {"allocated_days": 5, "carried_over": 0, "used_days": 4, "pending_days": 0, "id": 1},
        ])
        data = {
            "employee_id": 1, "leave_type_id": 1,
            "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 5),
            "total_days": 5,
        }
        with pytest.raises(ValueError, match="Insufficient leave balance"):
            await hr_service.request_leave(data)

    @pytest.mark.asyncio
    async def test_request_leave_invalid_type(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        data = {
            "employee_id": 1, "leave_type_id": 999,
            "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 2),
            "total_days": 2,
        }
        with pytest.raises(ValueError, match="not found or inactive"):
            await hr_service.request_leave(data)

    @pytest.mark.asyncio
    async def test_approve_leave(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        row = {
            "id": 1, "status": "approved", "total_days": 2,
            "employee_id": 1, "leave_type_id": 1, "start_date": date(2026, 5, 1),
        }
        conn.fetchrow = AsyncMock(return_value=row)
        conn.execute = AsyncMock()
        result = await hr_service.approve_leave(1, "admin")
        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_leave_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found or not pending"):
            await hr_service.approve_leave(999, "admin")

    @pytest.mark.asyncio
    async def test_reject_leave(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        row = {
            "id": 1, "status": "rejected", "total_days": 2,
            "employee_id": 1, "leave_type_id": 1, "start_date": date(2026, 5, 1),
        }
        conn.fetchrow = AsyncMock(return_value=row)
        conn.execute = AsyncMock()
        result = await hr_service.reject_leave(1, "admin", "No coverage")
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reject_leave_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found or not pending"):
            await hr_service.reject_leave(999, "admin", "reason")

    @pytest.mark.asyncio
    async def test_get_leave_request_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "status": "pending"})
        result = await hr_service.get_leave_request(1)
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_get_leave_request_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await hr_service.get_leave_request(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_leave_type_name_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value={"name": "Annual Leave"})
        result = await hr_service.get_leave_type_name(1)
        assert result == "Annual Leave"

    @pytest.mark.asyncio
    async def test_get_leave_type_name_not_found(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await hr_service.get_leave_type_name(999)
        assert result == "Leave type #999"

    @pytest.mark.asyncio
    async def test_get_leave_balance(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {"leave_type_name": "Annual", "allocated_days": 12, "used_days": 3},
        ])
        result = await hr_service.get_leave_balance(1, 2026)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_leave_balance_default_year(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await hr_service.get_leave_balance(1)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_team_leave_summary(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await hr_service.get_team_leave_summary(2026)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_leave_requests(self, hr_service, mock_db_pool):
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await hr_service.list_leave_requests(employee_id=1, status="pending")
        assert result == []


# ============================================================================
# Dashboard
# ============================================================================


class TestDashboard:
    @pytest.mark.asyncio
    async def test_admin_dashboard(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(side_effect=[10, 0, 5, 2])
        conn.fetchrow = AsyncMock(side_effect=[
            {"count": 3, "total": 500000},  # pending bonuses
            {"id": 1, "payroll_month": 4},  # current period
        ])
        result = await hr_service.get_admin_dashboard()
        assert result["employee_count"] == 10
        assert "pending_bonuses" in result

    @pytest.mark.asyncio
    async def test_admin_dashboard_no_period(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetchrow = AsyncMock(side_effect=[
            {"count": 0, "total": 0},
            None,  # no current period
        ])
        result = await hr_service.get_admin_dashboard()
        assert result["current_period"] is None

    @pytest.mark.asyncio
    async def test_my_dashboard(self, hr_service, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=[
            {"count": 2, "total": 200000},  # bonuses
            {"id": 1, "payroll_month": 3, "payroll_year": 2026},  # latest payslip
        ])
        conn.fetch = AsyncMock(return_value=[])  # leave balances
        result = await hr_service.get_my_dashboard(1)
        assert "month_bonuses" in result
        assert "latest_payslip" in result
        assert "leave_balances" in result
