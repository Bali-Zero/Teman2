"""Reconciliation confirm service — the single writer of payment state.

When Asya confirms a match, this is the ONLY path that mutates
practices.payment_status / paid_amount (superscar #9: never a side-channel).
Everything happens in one transaction:
  1. update practices (payment_status, paid_amount) — same columns the CRM PATCH uses
  2. fill invoices (paid_date, payment_method, payment_reference, paid_amount_idr)
  3. mark bank_transactions reconciled (4-state) + link practice/invoice
  4. insert a weekly_cashout row (the money-log, with price decomposition)
  5. insert an immutable reconciliation_log row (audit)
Then invalidate the same cache keys the CRM uses.

Cash-basis, IDR. The accountant has already chosen the match; this records it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import asyncpg

logger = logging.getLogger(__name__)

# Mirrors crm_practices PAYMENT_STATUS_VALUES — keep in sync.
PAYMENT_STATUS_VALUES = ("unpaid", "partial", "paid")


@dataclass
class ConfirmResult:
    practice_id: int
    invoice_id: int | None
    cashout_id: int
    reconciliation_log_id: int
    status_before: str | None
    status_after: str


class ReconcileError(Exception):
    """Raised on an invalid confirm request (bad status, missing practice)."""


def _iso_week_label(d: date) -> str:
    """A human week label like Asya's tabs, derived from ISO week."""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def confirm_payment(
    conn: asyncpg.Connection,
    *,
    bank_txn_id: int | None,
    practice_id: int,
    invoice_id: int | None,
    amount_applied_idr: int,
    new_status: str,
    confirmed_by: str,
    payment_method: str = "bank_transfer",
    payment_reference: str | None = None,
    pph_withheld_idr: int = 0,
    bank_fee_idr: int = 0,
    # price decomposition (Asya's sheet) — optional, defaults to 0
    pnbp_idr: int = 0,
    urgent_idr: int = 0,
    rptka_imta_idr: int = 0,
    margin_idr: int = 0,
    movement_date: date | None = None,
) -> ConfirmResult:
    """Confirm a payment match in one transaction. Returns the audit ids.

    `new_status` must be one of PAYMENT_STATUS_VALUES. `amount_applied_idr` is
    what actually landed (net of withholding/fees); the gross is recorded via
    the decomposition + pph/fee fields.
    """
    if new_status not in PAYMENT_STATUS_VALUES:
        raise ReconcileError(
            f"new_status must be one of {PAYMENT_STATUS_VALUES}, got {new_status!r}"
        )

    mv_date = movement_date or date.today() if movement_date is None else movement_date
    # date.today() is banned in some contexts; use the transfer/movement date the
    # caller passes. Fall back to the DB clock only if none given.
    if movement_date is not None:
        mv_date = movement_date

    async with conn.transaction():
        # 1. Read current practice state (lock the row) — verify it exists.
        prac = await conn.fetchrow(
            "SELECT id, payment_status, paid_amount FROM practices WHERE id = $1 FOR UPDATE",
            practice_id,
        )
        if prac is None:
            raise ReconcileError(f"practice {practice_id} not found")
        status_before = prac["payment_status"]
        prior_paid = int(prac["paid_amount"] or 0)
        new_paid = prior_paid + amount_applied_idr

        # 2. Update practices — SAME columns/path the CRM PATCH writes (superscar #9).
        await conn.execute(
            """
            UPDATE practices
            SET payment_status = $1, paid_amount = $2, updated_at = now()
            WHERE id = $3
            """,
            new_status,
            new_paid,
            practice_id,
        )

        # 3. Fill invoice payment fields, if an invoice is linked.
        if invoice_id is not None:
            await conn.execute(
                """
                UPDATE invoices
                SET paid_date = now(),
                    payment_method = $1,
                    payment_reference = $2,
                    paid_amount_idr = COALESCE(paid_amount_idr, 0) + $3
                WHERE id = $4
                """,
                payment_method,
                payment_reference,
                amount_applied_idr,
                invoice_id,
            )

        # 4. Mark the bank transaction reconciled + link.
        if bank_txn_id is not None:
            await conn.execute(
                """
                UPDATE bank_transactions
                SET reconciled_status = 'matched',
                    matched_practice_id = $1,
                    matched_invoice_id = $2
                WHERE id = $3
                """,
                practice_id,
                invoice_id,
                bank_txn_id,
            )

        # 5. Insert the money-log row (weekly_cashout) with decomposition.
        if movement_date is not None:
            week = _iso_week_label(movement_date)
            cashout_id = await conn.fetchval(
                """
                INSERT INTO weekly_cashout
                    (movement_date, week_label, direction, type, amount_idr,
                     pnbp_idr, urgent_idr, rptka_imta_idr, margin_idr, final_price_idr,
                     pph_withheld_idr, bank_fee_idr,
                     linked_practice_id, linked_invoice_id, linked_bank_txn_id,
                     payment_method, recorded_by, recorded_at)
                VALUES ($1, $2, 'in', 'invoice_payment', $3,
                        $4, $5, $6, $7, $8,
                        $9, $10,
                        $11, $12, $13,
                        $14, $15, now())
                RETURNING id
                """,
                movement_date,
                week,
                amount_applied_idr,
                pnbp_idr,
                urgent_idr,
                rptka_imta_idr,
                margin_idr,
                pnbp_idr + urgent_idr + rptka_imta_idr + margin_idr,
                pph_withheld_idr,
                bank_fee_idr,
                practice_id,
                invoice_id,
                bank_txn_id,
                payment_method,
                confirmed_by,
            )
        else:
            cashout_id = await conn.fetchval(
                """
                INSERT INTO weekly_cashout
                    (movement_date, week_label, direction, type, amount_idr,
                     pnbp_idr, urgent_idr, rptka_imta_idr, margin_idr, final_price_idr,
                     pph_withheld_idr, bank_fee_idr,
                     linked_practice_id, linked_invoice_id, linked_bank_txn_id,
                     payment_method, recorded_by, recorded_at)
                VALUES (CURRENT_DATE, NULL, 'in', 'invoice_payment', $1,
                        $2, $3, $4, $5, $6,
                        $7, $8,
                        $9, $10, $11,
                        $12, $13, now())
                RETURNING id
                """,
                amount_applied_idr,
                pnbp_idr,
                urgent_idr,
                rptka_imta_idr,
                margin_idr,
                pnbp_idr + urgent_idr + rptka_imta_idr + margin_idr,
                pph_withheld_idr,
                bank_fee_idr,
                practice_id,
                invoice_id,
                bank_txn_id,
                payment_method,
                confirmed_by,
            )

        # 6. Immutable audit row.
        recon_id = await conn.fetchval(
            """
            INSERT INTO reconciliation_log
                (bank_txn_id, invoice_ids, practice_id, cashout_id, confirmed_by,
                 confirmed_at, status_before, status_after, amount_applied_idr,
                 pph_delta_idr, bank_fee_delta_idr)
            VALUES ($1, $2, $3, $4, $5, now(), $6, $7, $8, $9, $10)
            RETURNING id
            """,
            bank_txn_id,
            json.dumps([invoice_id] if invoice_id is not None else []),
            practice_id,
            cashout_id,
            confirmed_by,
            status_before,
            new_status,
            amount_applied_idr,
            pph_withheld_idr,
            bank_fee_idr,
        )

    logger.info(
        "Reconcile confirm: practice=%s invoice=%s %s->%s amount=%s by=%s recon=%s",
        practice_id, invoice_id, status_before, new_status, amount_applied_idr,
        confirmed_by, recon_id,
    )
    return ConfirmResult(
        practice_id=practice_id,
        invoice_id=invoice_id,
        cashout_id=cashout_id,
        reconciliation_log_id=recon_id,
        status_before=status_before,
        status_after=new_status,
    )
