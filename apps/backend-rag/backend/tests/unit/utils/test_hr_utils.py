"""Tests for HR utility functions — PPh21, BPJS, THR, RBAC."""

from datetime import date

from backend.app.utils.hr_utils import (
    UMK_BADUNG_2026,
    calculate_bpjs,
    calculate_pph21_annual,
    calculate_pph21_monthly,
    calculate_thr,
    is_hr_admin,
    total_employee_deductions,
    validate_minimum_wage,
)

# ─── RBAC ────────────────────────────────────────────────────────────────

class TestIsHrAdmin:
    def test_admin_by_email(self) -> None:
        assert is_hr_admin({"email": "zero@balizero.com", "role": "member"})

    def test_admin_by_asya_email(self) -> None:
        assert is_hr_admin({"email": "asya@balizero.com", "role": "member"})

    def test_admin_by_role(self) -> None:
        assert is_hr_admin({"email": "anyone@example.com", "role": "admin"})

    def test_not_admin(self) -> None:
        assert not is_hr_admin({"email": "team@balizero.com", "role": "member"})

    def test_case_insensitive_email(self) -> None:
        # is_hr_admin lowercases input, so uppercase matches
        assert is_hr_admin({"email": "ZERO@BALIZERO.COM", "role": "member"})

    def test_empty_user(self) -> None:
        assert not is_hr_admin({})


# ─── PPh21 ───────────────────────────────────────────────────────────────

class TestPPh21:
    def test_below_ptkp_is_zero(self) -> None:
        """Income below PTKP (54M) should have zero tax."""
        assert calculate_pph21_annual(50_000_000, "TK/0") == 0

    def test_exactly_ptkp(self) -> None:
        assert calculate_pph21_annual(54_000_000, "TK/0") == 0

    def test_first_bracket(self) -> None:
        """60M taxable = 5% of 60M = 3M."""
        # gross = 54M (PTKP) + 60M = 114M
        tax = calculate_pph21_annual(114_000_000, "TK/0")
        assert tax == 3_000_000

    def test_second_bracket(self) -> None:
        """100M taxable: 5% of 60M + 15% of 40M = 3M + 6M = 9M."""
        tax = calculate_pph21_annual(154_000_000, "TK/0")
        assert tax == 9_000_000

    def test_married_ptkp(self) -> None:
        """K/3 PTKP = 72M. 72M gross = 0 tax."""
        assert calculate_pph21_annual(72_000_000, "K/3") == 0

    def test_monthly_is_annual_divided_12(self) -> None:
        monthly = calculate_pph21_monthly(10_000_000, "TK/0")
        annual = calculate_pph21_annual(120_000_000, "TK/0")
        assert monthly == annual // 12

    def test_unknown_ptkp_defaults_to_tk0(self) -> None:
        tax_unknown = calculate_pph21_annual(100_000_000, "INVALID")
        tax_tk0 = calculate_pph21_annual(100_000_000, "TK/0")
        assert tax_unknown == tax_tk0


# ─── BPJS ────────────────────────────────────────────────────────────────

class TestBPJS:
    def test_standard_salary(self) -> None:
        bpjs = calculate_bpjs(10_000_000)
        # Kesehatan: 4% + 1% of 10M
        assert bpjs["kesehatan"]["employer"] == 400_000
        assert bpjs["kesehatan"]["employee"] == 100_000
        # JHT: 3.7% + 2% of 10M
        assert bpjs["jht"]["employer"] == 370_000
        assert bpjs["jht"]["employee"] == 200_000
        # JKK: 0.24% of 10M (int truncation: 23999)
        assert bpjs["jkk"]["employer"] == int(10_000_000 * 0.0024)
        assert bpjs["jkk"]["employee"] == 0
        # JKM: 0.30% of 10M
        assert bpjs["jkm"]["employer"] == 30_000
        # JP: 2% + 1% of 10M (below cap)
        assert bpjs["jp"]["employer"] == 200_000
        assert bpjs["jp"]["employee"] == 100_000

    def test_kesehatan_cap(self) -> None:
        """Salary above 12M: BPJS Kes capped at 12M base."""
        bpjs = calculate_bpjs(20_000_000)
        assert bpjs["kesehatan"]["employer"] == 480_000  # 4% of 12M
        assert bpjs["kesehatan"]["employee"] == 120_000  # 1% of 12M

    def test_jp_cap(self) -> None:
        """Salary above JP cap: JP contributions capped."""
        bpjs = calculate_bpjs(15_000_000)
        # JP cap = 10_042_300, so 2% of cap = 200_846
        assert bpjs["jp"]["employer"] == 200_846
        assert bpjs["jp"]["employee"] == 100_423

    def test_zero_salary(self) -> None:
        bpjs = calculate_bpjs(0)
        assert bpjs["kesehatan"]["total"] == 0
        assert bpjs["jht"]["total"] == 0


# ─── Total Deductions ────────────────────────────────────────────────────

class TestTotalDeductions:
    def test_deduction_sum(self) -> None:
        d = total_employee_deductions(10_000_000, "TK/0")
        assert d["total"] == d["bpjs_kes"] + d["bpjs_jht"] + d["bpjs_jp"] + d["pph21"]
        assert d["bpjs_kes"] == 100_000
        assert d["bpjs_jht"] == 200_000


# ─── THR ─────────────────────────────────────────────────────────────────

class TestTHR:
    def test_full_year(self) -> None:
        """After 12 months: full salary."""
        thr = calculate_thr(10_000_000, date(2025, 1, 1), date(2026, 3, 1))
        assert thr == 10_000_000

    def test_pro_rata(self) -> None:
        """~5 months: pro-rata."""
        thr = calculate_thr(10_000_000, date(2025, 10, 1), date(2026, 3, 29))
        # 179 days / 30 = 5 months → 5/12 * 10M
        assert thr == int(10_000_000 * 5 / 12)

    def test_less_than_month(self) -> None:
        """Less than 30 days: no THR."""
        thr = calculate_thr(10_000_000, date(2026, 3, 10), date(2026, 3, 29))
        assert thr == 0

    def test_exactly_12_months(self) -> None:
        thr = calculate_thr(5_000_000, date(2025, 3, 1), date(2026, 3, 29))
        assert thr == 5_000_000


# ─── UMK ─────────────────────────────────────────────────────────────────

class TestUMK:
    def test_above_minimum(self) -> None:
        assert validate_minimum_wage(4_000_000, 2026)

    def test_below_minimum(self) -> None:
        assert not validate_minimum_wage(3_000_000, 2026)

    def test_exact_minimum(self) -> None:
        assert validate_minimum_wage(UMK_BADUNG_2026, 2026)
