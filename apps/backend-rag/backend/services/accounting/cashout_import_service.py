"""Import Asya's weekly cashout PDF (GABUNGAN BS) into the weekly_cashout table.

Asya delivers her weekly cashout as a digital, spreadsheet-exported PDF (parsed
with pdfplumber — no OCR). It is the already-processed 9-column worksheet, NOT a
raw bank statement, and a single file ("GABUNGAN") usually stacks several weeks,
each opened by a "NEW CASHOUT DD MONTH YYYY" title row.

This module:
  * reuses the IDR/cell helpers from the (orphaned, safe-to-reuse) owner_cashout
    parser instead of re-implementing Indonesian-number parsing;
  * walks the extracted tables itself — the existing parse_cashout_pdf() collapses
    every week into one flat list and drops the per-week date, which we need for
    weekly_cashout.movement_date / week_label;
  * maps each CashoutRow into a weekly_cashout insert dict (pure, unit-tested).

The DB write (idempotent upsert per week_label) lives in the router/endpoint layer
so this stays import-only and easy to test without a database.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from backend.services.hr.owner_cashout.parser import CashoutRow, parse_idr
from backend.services.hr.owner_cashout.pdf_parser import (
    _CASHOUT_SKIP_PATTERNS,
    _clean_cell,
)

logger = logging.getLogger(__name__)

# Month names seen in Asya's titles: English + Indonesian + common abbreviations
# and observed typos ("MARH" for March). Lower-cased keys.
_MONTH_MAP: dict[str, int] = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "marh": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "december": 12, "des": 12, "dec": 12,
}

# "NEW CASHOUT 6 MARCH 2026" / "CASHOUT 13 Maret 2026" — day, month-word, year.
_WEEK_TITLE_RE = re.compile(
    r"CASHOUT\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)


def week_label_for(d: date) -> str:
    """ISO week label like '2026-W10' (matches reconcile_service week_label)."""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _parse_week_title(cell0: str) -> date | None:
    """Return the week-start date if cell0 is a 'NEW CASHOUT …' title, else None."""
    m = _WEEK_TITLE_RE.search(cell0)
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTH_MAP.get(m.group(2).lower())
    year = int(m.group(3))
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def map_cashout_row(row: CashoutRow, *, week_start: date) -> dict[str, Any]:
    """Map one parsed CashoutRow onto a weekly_cashout insert dict.

    The cashout worksheet is income from confirmed work, so every row is an
    inbound invoice payment. The two margin columns (BS + BZ) collapse into the
    single margin_idr column. The headline number lives in total_income_idr for
    BZ-schema rows and in final_price_idr for BS-schema rows.
    """
    final = row.total_income_idr or row.final_price_idr
    return {
        "movement_date": week_start,
        "week_label": week_label_for(week_start),
        "direction": "in",
        "type": "invoice_payment",
        "counterparty": row.client_name,
        "description": row.note or None,
        "category": row.process or None,
        "pnbp_idr": row.pnbp_idr,
        "urgent_idr": row.urgent_idr,
        "rptka_imta_idr": row.rptka_imta_idr,
        "margin_idr": row.margin_bs_idr + row.margin_bz_idr,
        "final_price_idr": final,
        "amount_idr": final,
        # rows that carry no money at all are separators the parser let through;
        # the caller drops them rather than inserting a 0-rupiah cashout entry.
        "skippable": final == 0 and row.pnbp_idr == 0 and row.urgent_idr == 0,
    }


def parse_cashout_pdf_with_weeks(pdf_path: str | Path) -> list[dict[str, Any]]:
    """Parse a (possibly multi-week) GABUNGAN cashout PDF into weekly_cashout dicts.

    Walks every table row, tracking the current week from each 'NEW CASHOUT …'
    title row, and maps client rows onto inserts. Skippable (zero-money) rows are
    dropped. Raises ValueError if no week title is ever found (so an undated PDF
    fails loudly instead of producing rows with a wrong date).
    """
    pdf_path = Path(pdf_path)
    logger.info("[CASHOUT-IMPORT] Parsing %s", pdf_path.name)

    out: list[dict[str, Any]] = []
    current_week: date | None = None
    saw_title = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for raw_row in table:
                    if raw_row is None:
                        continue
                    padded = (list(raw_row) + [None] * 9)[:9]
                    cell0 = str(padded[0]).strip() if padded[0] else ""
                    if not cell0:
                        continue

                    week = _parse_week_title(cell0)
                    if week is not None:
                        current_week = week
                        saw_title = True
                        continue

                    # header / TOTAL / FEE / stray title rows
                    if _CASHOUT_SKIP_PATTERNS.match(cell0):
                        continue
                    if current_week is None:
                        # data before any title — can't be dated, skip safely
                        continue

                    row = CashoutRow(
                        entity="BZ",
                        row_index=len(out) + 1,
                        client_name=cell0,
                        process=_clean_cell(padded[1]),
                        pnbp_idr=parse_idr(padded[2]),
                        urgent_idr=parse_idr(padded[3]),
                        rptka_imta_idr=parse_idr(padded[4]),
                        total_income_idr=parse_idr(padded[6]),  # FINAL PRICE col
                        margin_bs_idr=parse_idr(padded[5]),     # MARGIN BS col
                        margin_bz_idr=0,
                        final_price_idr=0,
                        note=_clean_cell(padded[7]),
                    )
                    mapped = map_cashout_row(row, week_start=current_week)
                    if mapped.pop("skippable"):
                        continue
                    out.append(mapped)

    if not saw_title:
        raise ValueError(
            f"{pdf_path.name!r}: no 'NEW CASHOUT …' week title found — "
            "cannot date the rows (is this really a cashout worksheet PDF?)"
        )

    logger.info("[CASHOUT-IMPORT] %d dated rows from %s", len(out), pdf_path.name)
    return out


# ── DB write (idempotent per week) ──────────────────────────────────────────
#
# Re-uploading the same GABUNGAN file MUST NOT double-insert. The file is the
# source of truth for the weeks it covers, so for each week_label present in the
# upload we delete the previously-imported rows for that week and re-insert.
#
# The delete is scoped to PDF-imported rows only — those have no reconciliation
# links (linked_bank_txn_id / linked_practice_id / linked_invoice_id all NULL)
# and were written by this importer (recorded_by = _IMPORT_SOURCE). A row that
# the reconciliation service confirmed (and therefore linked) is NEVER touched,
# so a manual /confirm and a PDF import for the same week coexist safely
# (superscar #9: a single shared table, two writers, each owning disjoint rows).

# recorded_by sentinel that marks a row as "came from a GABUNGAN PDF import",
# so the idempotent delete can scope to exactly the rows this importer owns.
_IMPORT_SOURCE = "cashout-pdf-import"


async def persist_cashout_rows(
    conn: Any,
    rows: list[dict[str, Any]],
    *,
    imported_by: str,
    source_filename: str | None = None,
) -> dict[str, Any]:
    """Idempotently write parsed cashout rows into weekly_cashout.

    For every distinct week_label in ``rows`` the prior PDF-imported rows of that
    week are deleted and the new ones inserted, inside a single transaction. Rows
    linked to a reconciliation (linked_* set) are left untouched.

    Returns a summary: {"imported": N, "weeks": [...], "deleted": M}.
    """
    if not rows:
        return {"imported": 0, "weeks": [], "deleted": 0}

    weeks = sorted({r["week_label"] for r in rows})
    deleted = 0
    inserted = 0

    async with conn.transaction():
        for week in weeks:
            # delete only this importer's prior rows for the week (never a
            # reconciliation-linked row).
            del_status = await conn.execute(
                """
                DELETE FROM weekly_cashout
                WHERE week_label = $1
                  AND recorded_by = $2
                  AND linked_practice_id IS NULL
                  AND linked_invoice_id IS NULL
                  AND linked_bank_txn_id IS NULL
                """,
                week,
                _IMPORT_SOURCE,
            )
            # asyncpg returns "DELETE <n>"
            try:
                deleted += int(del_status.split()[-1])
            except (ValueError, IndexError, AttributeError):
                pass

        for r in rows:
            await conn.execute(
                """
                INSERT INTO weekly_cashout
                    (movement_date, week_label, direction, type, amount_idr,
                     pnbp_idr, urgent_idr, rptka_imta_idr, margin_idr, final_price_idr,
                     category, description, counterparty, recorded_by, recorded_at)
                VALUES ($1, $2, $3, $4, $5,
                        $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, now())
                """,
                r["movement_date"],
                r["week_label"],
                r["direction"],
                r["type"],
                r["amount_idr"],
                r["pnbp_idr"],
                r["urgent_idr"],
                r["rptka_imta_idr"],
                r["margin_idr"],
                r["final_price_idr"],
                r.get("category"),
                r.get("description"),
                r.get("counterparty"),
                _IMPORT_SOURCE,
            )
            inserted += 1

    logger.info(
        "[CASHOUT-IMPORT] persisted %d rows over %d week(s) from %s by %s "
        "(replaced %d prior import rows)",
        inserted, len(weeks), source_filename or "?", imported_by, deleted,
    )
    return {"imported": inserted, "weeks": weeks, "deleted": deleted}
