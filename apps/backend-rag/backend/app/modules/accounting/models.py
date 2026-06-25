"""
Accounting Module Data Layer
SQLModel models for the cash-control workflow (migration 232_accounting_asya.sql).

Single-entry, cash-basis, IDR-native (USD per-line with explicit FX). Mirrors
Asya's real "Weekly Cashout 2026" Google Sheet. See
research/operations/2026-06-25-accounting-asya-architecture.md.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Column, Text
from sqlmodel import Field, SQLModel


class BankStatement(SQLModel, table=True):
    """One uploaded bank statement file (CSV/PDF) per import."""

    __tablename__ = "bank_statements"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    bank_code: str = Field(default="cimb_niaga")
    account_label: str | None = Field(default=None)
    uploaded_by: str | None = Field(default=None)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    source_filename: str | None = Field(default=None)
    source_format: str = Field(default="csv")  # csv | xlsx | pdf | manual
    period_start: date | None = Field(default=None)
    period_end: date | None = Field(default=None)
    opening_balance_idr: int | None = Field(default=None, sa_column=Column("opening_balance_idr", BigInteger))
    closing_balance_idr: int | None = Field(default=None, sa_column=Column("closing_balance_idr", BigInteger))
    parse_status: str = Field(default="parsed")  # parsed | needs_review | failed
    balance_check_ok: bool | None = Field(default=None)
    txn_count: int = Field(default=0)


class BankTransaction(SQLModel, table=True):
    """A normalized transaction row parsed from a statement.

    `direction` normalizes BCA's DB/CR flag and Mandiri/BRI's two columns.
    `reconciled_status` is the 4-state contract — nothing is ever silently
    dropped (superscar #2).
    """

    __tablename__ = "bank_transactions"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="bank_statements.id")
    txn_date: date
    description: str | None = Field(default=None, sa_column=Column(Text))
    amount_idr: int = Field(sa_column=Column("amount_idr", BigInteger, nullable=False))
    direction: str  # credit (in) | debit (out)
    running_balance_idr: int | None = Field(default=None, sa_column=Column("running_balance_idr", BigInteger))
    bank_account_id: str | None = Field(default=None)
    reconciled_status: str = Field(default="unmatched")  # unmatched | matched | manual | ignored
    matched_practice_id: int | None = Field(default=None, foreign_key="practices.id")
    matched_invoice_id: int | None = Field(default=None, sa_column=Column("matched_invoice_id", BigInteger))
    raw_row: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WeeklyCashout(SQLModel, table=True):
    """THE single flat money-log (single-entry, cash-basis).

    One row per money event. For an invoice payment the price is decomposed
    exactly like Asya's sheet: pnbp + urgent + rptka_imta are cost components;
    margin_idr is Bali Zero's margin; final_price_idr is what the client paid.
    Generic out-flows (IT/SaaS subs, office) are rows with type='expense'.
    Append-only: correct by reversal (reversed_by_id), never hard-edit.
    """

    __tablename__ = "weekly_cashout"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    movement_date: date
    week_label: str | None = Field(default=None)
    direction: str  # in | out
    type: str  # invoice_payment | expense | payroll | commission | bank_fee | pnbp_payment | tax_payment | refund | manual
    amount_idr: int = Field(sa_column=Column("amount_idr", BigInteger, nullable=False))

    # price decomposition (Asya's columns) — populated for invoice_payment rows
    pnbp_idr: int = Field(default=0, sa_column=Column("pnbp_idr", BigInteger, nullable=False, server_default="0"))
    urgent_idr: int = Field(default=0, sa_column=Column("urgent_idr", BigInteger, nullable=False, server_default="0"))
    rptka_imta_idr: int = Field(default=0, sa_column=Column("rptka_imta_idr", BigInteger, nullable=False, server_default="0"))
    margin_idr: int = Field(default=0, sa_column=Column("margin_idr", BigInteger, nullable=False, server_default="0"))
    final_price_idr: int = Field(default=0, sa_column=Column("final_price_idr", BigInteger, nullable=False, server_default="0"))

    # multi-currency LIGHT, FX explicit
    original_currency: str = Field(default="IDR")
    original_amount: float | None = Field(default=None)
    fx_rate: float | None = Field(default=None)
    fx_date: date | None = Field(default=None)

    # tax reality (dormant unless used)
    pph_withheld_idr: int = Field(default=0, sa_column=Column("pph_withheld_idr", BigInteger, nullable=False, server_default="0"))
    bank_fee_idr: int = Field(default=0, sa_column=Column("bank_fee_idr", BigInteger, nullable=False, server_default="0"))

    # typed links
    linked_practice_id: int | None = Field(default=None, foreign_key="practices.id")
    linked_invoice_id: int | None = Field(default=None, sa_column=Column("linked_invoice_id", BigInteger))
    linked_bank_txn_id: int | None = Field(default=None, foreign_key="bank_transactions.id")

    category: str | None = Field(default=None)
    description: str | None = Field(default=None, sa_column=Column(Text))
    counterparty: str | None = Field(default=None)
    payment_method: str | None = Field(default=None)  # cash | bank_transfer | card
    receipt_drive_file_id: str | None = Field(default=None)

    recorded_by: str | None = Field(default=None)
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    reversed_by_id: int | None = Field(default=None, foreign_key="weekly_cashout.id")


class ReconciliationLog(SQLModel, table=True):
    """Immutable audit trail per payment confirmation.

    Un-reconcile appends a reversal row (reversal_of_id), never deletes.
    """

    __tablename__ = "reconciliation_log"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    bank_txn_id: int | None = Field(default=None, foreign_key="bank_transactions.id")
    invoice_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    practice_id: int | None = Field(default=None, foreign_key="practices.id")
    cashout_id: int | None = Field(default=None, foreign_key="weekly_cashout.id")
    confirmed_by: str | None = Field(default=None)
    confirmed_at: datetime = Field(default_factory=datetime.utcnow)
    status_before: str | None = Field(default=None)
    status_after: str | None = Field(default=None)
    amount_applied_idr: int | None = Field(default=None, sa_column=Column("amount_applied_idr", BigInteger))
    pph_delta_idr: int = Field(default=0, sa_column=Column("pph_delta_idr", BigInteger, nullable=False, server_default="0"))
    bank_fee_delta_idr: int = Field(default=0, sa_column=Column("bank_fee_delta_idr", BigInteger, nullable=False, server_default="0"))
    reversal_of_id: int | None = Field(default=None, foreign_key="reconciliation_log.id")
    note: str | None = Field(default=None, sa_column=Column(Text))
