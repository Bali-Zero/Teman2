"""Tests for the bank statement CSV parser (Indonesian gotchas + balance check)."""

from __future__ import annotations

from datetime import date

import pytest

from backend.services.accounting.bank_parser import (
    _CONFIGS,
    BankConfig,
    BankParseError,
    parse_csv,
    verify_balance,
)


def test_cimb_two_column_decimal_comma() -> None:
    # CIMB-style: Debet/Kredit columns, dd/mm/yyyy, decimal-comma amounts,
    # semicolon-delimited (because comma is the decimal separator).
    csv_text = (
        "Tanggal;Keterangan;Debet;Kredit;Saldo\n"
        "25/06/2026;TRANSFER DARI DINA;;4.000.000,00;10.000.000,00\n"
        "26/06/2026;BIAYA ADMIN;15.000,00;;9.985.000,00\n"
    )
    txns = parse_csv(csv_text, bank_code="cimb_niaga")
    assert len(txns) == 2
    assert txns[0].txn_date == date(2026, 6, 25)
    assert txns[0].direction == "credit"
    assert txns[0].amount_idr == 4_000_000
    assert txns[1].direction == "debit"
    assert txns[1].amount_idr == 15_000


def test_leading_apostrophe_and_skip_blank_date() -> None:
    csv_text = (
        "Tanggal;Keterangan;Debet;Kredit;Saldo\n"
        "'25/06/2026;GUARDED DATE;;1.000.000,00;1.000.000,00\n"
        ";TOTAL ROW (no date);;;\n"
    )
    txns = parse_csv(csv_text, bank_code="cimb_niaga")
    assert len(txns) == 1
    assert txns[0].txn_date == date(2026, 6, 25)


def test_generic_signed_amount() -> None:
    csv_text = (
        "date,description,amount,balance\n"
        "2026-06-25,incoming,4000000,10000000\n"
        "2026-06-26,outgoing,-500000,9500000\n"
    )
    txns = parse_csv(csv_text, bank_code="generic")
    assert txns[0].direction == "credit" and txns[0].amount_idr == 4_000_000
    assert txns[1].direction == "debit" and txns[1].amount_idr == 500_000


def test_flag_mode() -> None:
    cfg = BankConfig(
        bank_code="flagbank", date_col="d", desc_col="m",
        amount_col="amt", flag_col="dc", decimal_comma=False,
    )
    _CONFIGS["flagbank"] = cfg
    csv_text = "d,m,amt,dc\n25/06/2026,in,4000000,CR\n26/06/2026,out,500000,DB\n"
    txns = parse_csv(csv_text, bank_code="flagbank")
    assert txns[0].direction == "credit"
    assert txns[1].direction == "debit"


def test_unknown_bank_raises() -> None:
    with pytest.raises(BankParseError):
        parse_csv("a,b\n1,2\n", bank_code="nope")


def test_wrong_delimiter_raises_not_silent_empty() -> None:
    # D7 (superscar #2 — no green-but-empty): a real CIMB export is semicolon-
    # delimited, but a comma-delimited config would read the whole line as one
    # column -> no date_col -> every data row skipped -> [] silently WITHOUT
    # the guard. That must fail loudly instead.
    cfg = BankConfig(
        bank_code="cimb_wrongdelim",
        date_col="Tanggal", desc_col="Keterangan",
        debit_col="Debet", credit_col="Kredit", balance_col="Saldo",
        decimal_comma=True, delimiter=",",  # WRONG: should be ';'
    )
    _CONFIGS["cimb_wrongdelim"] = cfg
    semicolon_content = (
        "Tanggal;Keterangan;Debet;Kredit;Saldo\n"
        "25/06/2026;TRANSFER DARI DINA;;4.000.000,00;10.000.000,00\n"
        "26/06/2026;BIAYA ADMIN;15.000,00;;9.985.000,00\n"
    )
    with pytest.raises(BankParseError, match="parsed 0 transactions"):
        parse_csv(semicolon_content, bank_code="cimb_wrongdelim")


def test_header_only_no_data_rows_returns_empty_not_raise() -> None:
    # Innocence case for D7: a header with NO data rows is not a wrong-delimiter
    # failure (skipped == 0), so it must return [] quietly, never raise.
    out = parse_csv("Tanggal;Keterangan;Debet;Kredit;Saldo\n", bank_code="cimb_niaga")
    assert out == []


def test_verify_balance_ok_and_fail() -> None:
    csv_text = (
        "Tanggal;Keterangan;Debet;Kredit;Saldo\n"
        "25/06/2026;IN;;4.000.000,00;14.000.000,00\n"
        "26/06/2026;OUT;1.000.000,00;;13.000.000,00\n"
    )
    txns = parse_csv(csv_text, bank_code="cimb_niaga")
    # opening 10M + 4M - 1M = 13M closing
    assert verify_balance(txns, 10_000_000, 13_000_000) is True
    assert verify_balance(txns, 10_000_000, 99_999_999) is False
