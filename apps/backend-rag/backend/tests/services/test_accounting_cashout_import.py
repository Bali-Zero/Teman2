"""Tests for the cashout-PDF import service (GABUNGAN BS → weekly_cashout rows).

Asya's weekly cashout is delivered as a digital (spreadsheet-exported) PDF named
"GABUNGAN BS …". It is NOT a raw bank statement — it is the already-processed
9-column cashout worksheet (NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA |
MARGIN BS | FINAL PRICE | NOTE), grouped per week by a "NEW CASHOUT DD MONTH YYYY"
title row.

This service reuses the existing, orphaned parse_cashout_pdf (owner_cashout) for
table extraction and maps each CashoutRow into a weekly_cashout insert dict, while
tracking the per-week movement_date / week_label boundary that the flat parser
drops on the floor.

Two layers tested:
  1. pure mapping  — map_cashout_row(): CashoutRow + week_start -> weekly_cashout dict
  2. PDF end-to-end — parse_cashout_pdf_with_weeks(): a reportlab-generated
     multi-week GABUNGAN PDF -> rows carrying the right week_label.
"""

from __future__ import annotations

import io
from datetime import date

import pytest

from backend.services.accounting.cashout_import_service import (
    map_cashout_row,
    parse_cashout_pdf_with_weeks,
    week_label_for,
)
from backend.services.hr.owner_cashout.parser import CashoutRow


def _row(**kw) -> CashoutRow:
    base = dict(
        entity="BZ",
        row_index=1,
        client_name="X",
        process=None,
        pnbp_idr=0,
        urgent_idr=0,
        rptka_imta_idr=0,
        total_income_idr=0,
        margin_bs_idr=0,
        margin_bz_idr=0,
        final_price_idr=0,
        note=None,
    )
    base.update(kw)
    return CashoutRow(**base)


# ---------------------------------------------------------------- pure mapping


def test_map_simple_row_from_real_pdf() -> None:
    # ANASTASIIA KOVALENKO (RUSLANA) | Bridging Visa | PNBP 1.000.000 |
    #   | | MARGIN BS 1.000.000 | FINAL 4.400.000
    row = _row(
        client_name="ANASTASIIA KOVALENKO (RUSLANA)",
        process="Bridging Visa",
        pnbp_idr=1_000_000,
        margin_bs_idr=1_000_000,
        total_income_idr=4_400_000,  # in the BZ schema FINAL lands in total_income col
    )
    out = map_cashout_row(row, week_start=date(2026, 3, 6))

    assert out["movement_date"] == date(2026, 3, 6)
    assert out["week_label"] == "2026-W10"  # 6 Mar 2026 is ISO week 10
    assert out["direction"] == "in"
    assert out["type"] == "invoice_payment"
    assert out["counterparty"] == "ANASTASIIA KOVALENKO (RUSLANA)"
    assert out["category"] == "Bridging Visa"
    assert out["pnbp_idr"] == 1_000_000
    # the two margin columns collapse into the single margin_idr
    assert out["margin_idr"] == 1_000_000
    # final price / amount must be the headline number, never zero when income present
    assert out["final_price_idr"] == 4_400_000
    assert out["amount_idr"] == 4_400_000


def test_margins_are_summed() -> None:
    # a BZ row that carries both MARGIN BS and MARGIN BZ must collapse to one number
    row = _row(margin_bs_idr=600_000, margin_bz_idr=400_000, total_income_idr=2_300_000)
    out = map_cashout_row(row, week_start=date(2026, 3, 6))
    assert out["margin_idr"] == 1_000_000
    assert out["amount_idr"] == 2_300_000


def test_final_price_falls_back_to_final_price_col_for_bs_entity() -> None:
    # BS-schema rows put the headline in final_price_idr, not total_income_idr
    row = _row(
        entity="BS",
        client_name="SOMEONE",
        final_price_idr=8_000_000,
        total_income_idr=0,
        margin_bs_idr=3_000_000,
    )
    out = map_cashout_row(row, week_start=date(2026, 3, 13))
    assert out["final_price_idr"] == 8_000_000
    assert out["amount_idr"] == 8_000_000


def test_zero_amount_row_is_marked_skippable() -> None:
    # a row with no income at all (e.g. a stray separator the parser let through)
    row = _row(client_name="JUNK", pnbp_idr=0, total_income_idr=0, final_price_idr=0)
    out = map_cashout_row(row, week_start=date(2026, 3, 6))
    assert out["amount_idr"] == 0
    assert out["skippable"] is True


def test_week_label_for_iso_week() -> None:
    assert week_label_for(date(2026, 3, 6)) == "2026-W10"
    assert week_label_for(date(2026, 3, 13)) == "2026-W11"
    assert week_label_for(date(2026, 3, 27)) == "2026-W13"


# ---------------------------------------------------------------- PDF end-to-end


def _make_gabungan_pdf() -> bytes:
    """Build a minimal multi-week GABUNGAN-style PDF with reportlab.

    Two week blocks, each a title row + header + data rows, rendered as a real
    table so pdfplumber.extract_tables() sees it the way it sees Asya's export.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    header = ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "MARGIN BS", "FINAL PRICE", "NOTE"]

    data = [
        ["NEW CASHOUT 6 MARCH 2026", "", "", "", "", "", "", ""],
        header,
        ["ETHIOPIA YESUF OMUJWOK", "C1", "Rp1.000.000", "", "", "Rp600.000", "Rp2.300.000", ""],
        ["BIANCA ARCHETTI", "C1 - Urgent", "Rp1.000.000", "Rp800.000", "", "Rp600.000", "Rp3.300.000", ""],
        ["NEW CASHOUT 13 MARCH 2026", "", "", "", "", "", "", ""],
        header,
        ["SERENA GUARDIANI", "C1", "Rp1.000.000", "", "", "Rp600.000", "Rp2.300.000", ""],
    ]
    table = Table(data)
    # GRID lines so pdfplumber's line-based table detection sees it the way it
    # sees Asya's spreadsheet export (a borderless reportlab table is invisible
    # to extract_tables()).
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    doc.build([table])
    return buf.getvalue()


def test_parse_pdf_with_weeks_tracks_week_boundary(tmp_path) -> None:
    pdf_path = tmp_path / "GABUNGAN BS TEST.pdf"
    pdf_path.write_bytes(_make_gabungan_pdf())

    rows = parse_cashout_pdf_with_weeks(pdf_path)

    # three client rows across two weeks; no title/header rows leaked in
    names = [r["counterparty"] for r in rows]
    assert "ETHIOPIA YESUF OMUJWOK" in names
    assert "SERENA GUARDIANI" in names
    assert not any("CASHOUT" in n.upper() for n in names)
    assert not any(n == "NAME" for n in names)

    by_name = {r["counterparty"]: r for r in rows}
    # week 1 rows carry the 6 March date, week 2 rows carry 13 March
    assert by_name["ETHIOPIA YESUF OMUJWOK"]["movement_date"] == date(2026, 3, 6)
    assert by_name["BIANCA ARCHETTI"]["movement_date"] == date(2026, 3, 6)
    assert by_name["SERENA GUARDIANI"]["movement_date"] == date(2026, 3, 13)

    # amounts parsed through
    assert by_name["ETHIOPIA YESUF OMUJWOK"]["pnbp_idr"] == 1_000_000
    assert by_name["BIANCA ARCHETTI"]["urgent_idr"] == 800_000


def test_parse_pdf_raises_on_no_week_title(tmp_path) -> None:
    """A PDF whose rows never carry a NEW CASHOUT title can't be dated -> error,
    not silent rows with a wrong/None date (anti 'esiste≠armato')."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    t = Table([["NAME", "PROCESS", "PNBP"], ["JOHN", "C1", "Rp1.000.000"]])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    doc.build([t])
    pdf_path = tmp_path / "no-title.pdf"
    pdf_path.write_bytes(buf.getvalue())

    with pytest.raises(ValueError, match="no .*CASHOUT.* week title"):
        parse_cashout_pdf_with_weeks(pdf_path)
