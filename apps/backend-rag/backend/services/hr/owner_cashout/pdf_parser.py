"""PDF parser for historical cashout and bonus data.

Uses pdfplumber to extract tables from spreadsheet-exported PDFs.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pdfplumber

from backend.services.hr.owner_cashout.parser import CashoutRow, parse_idr

logger = logging.getLogger(__name__)

# Rows to skip in cashout PDFs (title, header, separator, total)
_CASHOUT_SKIP_PATTERNS = re.compile(
    r"^(NAME|CASHOUT|TOTAL|FEE\s)",
    re.IGNORECASE,
)
_DATE_MONTHS = re.compile(
    r"(MARET|FEBRUARI|FEBRUARY|APRIL|JANUARI|MEI|JUNI|JULI|AGUSTUS|SEPTEMBER|OKTOBER|NOVEMBER|DESEMBER|MARCH|MAY|JUNE|JULY|AUGUST|OCTOBER|DECEMBER)",
    re.IGNORECASE,
)

# Bonus PDF: metadata rows to skip within employee sections
_BONUS_SKIP_PREFIXES = (
    "ACCOUNTING TASK",
    "ATTACKER TASK",
    "Kredit & Invoice",
    "Kredit &amp; Invoice",
    "Total data",
    "Not Paid",
    "- Not Paid",
    "- Paid",
    "Calculate to precentage",
    "Calculate to percentage",
    "NAME",
)

_BONUS_TOTAL_RE = re.compile(r"TOTAL\s*=\s*([\d,\.]+)\s*IDR", re.IGNORECASE)


def parse_cashout_pdf(pdf_path: str | Path) -> list[CashoutRow]:
    """Parse a weekly cashout BZ PDF into CashoutRow objects.

    Args:
        pdf_path: Path to the cashout PDF file.

    Returns:
        List of CashoutRow with entity='BZ' and 1-based row_index.
    """
    pdf_path = Path(pdf_path)
    logger.info("[PDF] Parsing cashout PDF: %s", pdf_path.name)

    rows_out: list[CashoutRow] = []
    seq = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if not tables:
                logger.debug("[PDF] Page %d: no tables found", page_num)
                continue

            for table in tables:
                for raw_row in table:
                    if raw_row is None:
                        continue

                    # Pad to 9 columns
                    padded = (list(raw_row) + [None] * 9)[:9]

                    # First cell determines if row is data
                    cell0 = str(padded[0]).strip() if padded[0] else ""
                    if not cell0:
                        continue  # separator row

                    # Skip header/title/total rows
                    if _CASHOUT_SKIP_PATTERNS.match(cell0):
                        continue
                    if _DATE_MONTHS.search(cell0):
                        continue

                    seq += 1
                    rows_out.append(
                        CashoutRow(
                            entity="BZ",
                            row_index=seq,
                            client_name=cell0,
                            process=_clean_cell(padded[1]),
                            pnbp_idr=parse_idr(padded[2]),
                            urgent_idr=parse_idr(padded[3]),
                            rptka_imta_idr=parse_idr(padded[4]),
                            total_income_idr=parse_idr(padded[5]),
                            margin_bs_idr=parse_idr(padded[6]),
                            margin_bz_idr=parse_idr(padded[7]),
                            final_price_idr=0,
                            note=_clean_cell(padded[8]),
                        )
                    )

    logger.info("[PDF] Parsed %d cashout rows from %s", len(rows_out), pdf_path.name)
    return rows_out


def parse_bonus_pdf(pdf_path: str | Path) -> list[dict[str, Any]]:
    """Parse a bonus list PDF into structured employee bonus data.

    Args:
        pdf_path: Path to the bonus PDF file.

    Returns:
        List of dicts with keys: employee_name, total_amount_idr,
        accounting (dict or None), items (list of dicts).
    """
    pdf_path = Path(pdf_path)
    logger.info("[PDF] Parsing bonus PDF: %s", pdf_path.name)

    # Collect all rows from all pages into a flat list
    all_rows: list[list[str | None]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in (tables or []):
                for row in table:
                    if row is not None:
                        all_rows.append(row)

    employees: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    accounting: dict[str, int] | None = None
    item_seq = 0

    for raw_row in all_rows:
        padded = (list(raw_row) + [None] * 2)[:2]
        cell0 = str(padded[0]).strip() if padded[0] else ""
        cell1 = str(padded[1]).strip() if padded[1] else ""

        if not cell0:
            continue

        # Check for TOTAL line -> closes current employee section
        total_match = _BONUS_TOTAL_RE.match(cell0)
        if total_match:
            if current is not None:
                amount_str = total_match.group(1).replace(",", "").replace(".", "")
                current["total_amount_idr"] = int(amount_str)
                current["accounting"] = accounting
                employees.append(current)
            current = None
            accounting = None
            item_seq = 0
            continue

        # Check for title row (skip)
        if cell0.startswith("LIST BONUS"):
            continue

        # Check if this is an employee name header
        # Employee headers: single cell, no second column, uppercase name,
        # not a skip prefix, not a data row (no service in cell1)
        if _is_employee_header(cell0, cell1, current):
            # Save previous employee if any (shouldn't happen without TOTAL, but safety)
            if current is not None and current["items"]:
                current["accounting"] = accounting
                employees.append(current)

            current = {
                "employee_name": cell0,
                "total_amount_idr": 0,
                "accounting": None,
                "items": [],
            }
            accounting = None
            item_seq = 0
            continue

        if current is None:
            continue

        # Skip metadata rows
        if _is_skip_row(cell0):
            # Parse accounting data if present
            if cell0.startswith("Total data"):
                accounting = accounting or {"total_data": 0, "not_paid": 0, "paid": 0}
                accounting["total_data"] = _parse_accounting_number(cell1)
            elif cell0 in ("- Not Paid", "Not Paid") and accounting is not None:
                # Only take first occurrence (second is percentage row)
                if accounting["not_paid"] == 0:
                    accounting["not_paid"] = _parse_accounting_number(cell1)
            elif cell0 in ("- Paid",) and accounting is not None:
                if accounting["paid"] == 0:
                    accounting["paid"] = _parse_accounting_number(cell1)
            continue

        # Skip header row "NAME | SERVICE"
        if cell0 == "NAME" and cell1 == "SERVICE":
            continue

        # This is a data row (client + service)
        if cell1 or cell0:
            item_seq += 1
            current["items"].append({
                "client_name": cell0,
                "service_type": cell1 or "",
                "row_index": item_seq,
            })

    # Handle last employee if no trailing TOTAL (shouldn't happen but safety)
    if current is not None and current["items"]:
        current["accounting"] = accounting
        employees.append(current)

    logger.info("[PDF] Parsed %d employees from %s", len(employees), pdf_path.name)
    return employees


def _clean_cell(value: Any) -> str | None:
    """Return stripped string or None for empty/None cells."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _is_employee_header(cell0: str, cell1: str, current: dict[str, Any] | None) -> bool:
    """Detect employee name headers in bonus PDFs.

    Employee headers are typically uppercase names with no second column,
    and they don't match any known skip patterns.
    """
    # Must not have a service column
    if cell1:
        return False
    # Must be mostly uppercase letters/spaces
    if not re.match(r"^[A-Z][A-Z\s]+$", cell0):
        return False
    # Must not be a skip prefix
    if _is_skip_row(cell0):
        return False
    # Must not be TOTAL
    if cell0.startswith("TOTAL"):
        return False
    return True


def _is_skip_row(cell0: str) -> bool:
    """Check if row should be skipped (metadata rows in bonus PDFs)."""
    for prefix in _BONUS_SKIP_PREFIXES:
        if cell0.startswith(prefix):
            return True
    return False


def _parse_accounting_number(value: str) -> int:
    """Parse accounting values like '20 + 262 = 282' -> 282 (last number)."""
    if not value:
        return 0
    # Find all numbers in the string, take the last one
    numbers = re.findall(r"\d+", value)
    if numbers:
        return int(numbers[-1])
    return 0
