"""Tests for PDF parser — runs against actual PDFs in ~/Downloads."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.services.hr.owner_cashout.pdf_parser import (
    parse_bonus_pdf,
    parse_cashout_pdf,
)

CASHOUT_PDF = Path.home() / "Downloads" / "Weekly Cashout 2026 - BZ 27 MAR 26.pdf"
BONUS_PDF = Path.home() / "Downloads" / "LIST BONUS FEBRUARY 2026.pdf"


# ---------- Cashout PDF tests ----------


@pytest.mark.skipif(
    not CASHOUT_PDF.exists(),
    reason=f"Cashout PDF not found: {CASHOUT_PDF}",
)
class TestCashoutPdf:
    """Test parse_cashout_pdf against Weekly Cashout 2026 - BZ 27 MAR 26.pdf."""

    @pytest.fixture(scope="class")
    def rows(self) -> list:
        return parse_cashout_pdf(CASHOUT_PDF)

    def test_returns_rows(self, rows: list) -> None:
        assert len(rows) > 0, "Expected non-empty list of rows"

    def test_first_row_has_client_name(self, rows: list) -> None:
        assert rows[0].client_name, "First row should have a client_name"

    def test_all_entity_bz(self, rows: list) -> None:
        for row in rows:
            assert row.entity == "BZ", f"Row {row.row_index} entity should be BZ"

    def test_total_income_sum_positive(self, rows: list) -> None:
        total = sum(r.total_income_idr for r in rows)
        assert total > 0, f"Total income sum should be > 0, got {total}"

    def test_row_count_minimum(self, rows: list) -> None:
        assert len(rows) >= 25, f"Expected >= 25 rows, got {len(rows)}"

    def test_first_row_pnbp(self, rows: list) -> None:
        """VIKTOR SZABO, C1, PNBP = Rp1.000.000."""
        assert rows[0].client_name == "VIKTOR SZABO"
        assert rows[0].pnbp_idr == 1_000_000

    def test_row_index_sequential(self, rows: list) -> None:
        for i, row in enumerate(rows, start=1):
            assert row.row_index == i, f"Expected row_index {i}, got {row.row_index}"

    def test_no_header_rows_in_output(self, rows: list) -> None:
        for row in rows:
            assert row.client_name.upper() != "NAME"
            assert not row.client_name.upper().startswith("CASHOUT")
            assert not row.client_name.upper().startswith("TOTAL")


# ---------- Bonus PDF tests ----------


@pytest.mark.skipif(
    not BONUS_PDF.exists(),
    reason=f"Bonus PDF not found: {BONUS_PDF}",
)
class TestBonusPdf:
    """Test parse_bonus_pdf against LIST BONUS FEBRUARY 2026.pdf."""

    @pytest.fixture(scope="class")
    def employees(self) -> list:
        return parse_bonus_pdf(BONUS_PDF)

    def test_returns_employees(self, employees: list) -> None:
        assert len(employees) >= 2, f"Expected >= 2 employees, got {len(employees)}"

    def test_sahira_present(self, employees: list) -> None:
        names = [e["employee_name"] for e in employees]
        assert "SAHIRA" in names, f"SAHIRA not found in {names}"

    def test_krisna_present(self, employees: list) -> None:
        names = [e["employee_name"] for e in employees]
        assert "KRISNA" in names, f"KRISNA not found in {names}"

    def test_sahira_items_count(self, employees: list) -> None:
        sahira = next(e for e in employees if e["employee_name"] == "SAHIRA")
        assert len(sahira["items"]) >= 15, (
            f"SAHIRA should have >= 15 items, got {len(sahira['items'])}"
        )

    def test_sahira_total(self, employees: list) -> None:
        sahira = next(e for e in employees if e["employee_name"] == "SAHIRA")
        assert sahira["total_amount_idr"] == 3_000_000, (
            f"SAHIRA total should be 3,000,000, got {sahira['total_amount_idr']}"
        )

    def test_items_have_required_fields(self, employees: list) -> None:
        for emp in employees:
            for item in emp["items"]:
                assert "client_name" in item, f"Missing client_name in {emp['employee_name']}"
                assert "service_type" in item, f"Missing service_type in {emp['employee_name']}"

    def test_sahira_accounting(self, employees: list) -> None:
        sahira = next(e for e in employees if e["employee_name"] == "SAHIRA")
        assert sahira["accounting"] is not None, "SAHIRA should have accounting data"
        assert sahira["accounting"]["total_data"] == 282
        assert sahira["accounting"]["not_paid"] == 24
        assert sahira["accounting"]["paid"] == 258

    def test_employee_names_uppercase(self, employees: list) -> None:
        for emp in employees:
            assert emp["employee_name"] == emp["employee_name"].upper(), (
                f"Employee name should be uppercase: {emp['employee_name']}"
            )
