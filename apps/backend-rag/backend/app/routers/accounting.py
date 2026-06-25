"""Accounting router — cash-control endpoints for Asya (the agency accountant).

P0: read-only views (cashout log, bank transactions, cashbook summary).
P1 adds: statement upload, reconciliation matching, payment confirm.

RBAC: gated to CRM admins (asya@balizero.com is already in CRM_EXTRA_ADMIN_EMAILS)
via is_crm_admin(). Money is IDR. See migration 232_accounting_asya.sql.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.accounting import cashout_service, reconcile_service
from backend.services.accounting.matcher import OpenInvoice, rank_candidates
from backend.services.accounting.reconcile_service import ReconcileError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm/accounting", tags=["crm-accounting"])


def _require_accounting_access(current_user: dict[str, Any]) -> None:
    """Gate to CRM admins (includes Asya). Raises 403 otherwise."""
    if not is_crm_admin(current_user):
        raise HTTPException(status_code=403, detail="Accounting access denied")


@router.get("/cashout")
async def get_cashout(
    week_label: str | None = Query(None, description="Filter by week label, e.g. '16 - 23 JAN 26'"),
    type_filter: str | None = Query(None, alias="type", description="Filter by movement type"),
    limit: int = Query(200, ge=1, le=1000),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Weekly cashout rows (mirrors Asya's sheet), newest first."""
    _require_accounting_access(current_user)
    async with db_pool.acquire() as conn:
        return await cashout_service.list_cashout(
            conn, week_label=week_label, type_filter=type_filter, limit=limit
        )


@router.get("/bank-transactions")
async def get_bank_transactions(
    reconciled_status: str | None = Query(
        None, description="unmatched | matched | manual | ignored"
    ),
    limit: int = Query(200, ge=1, le=1000),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Parsed bank statement transactions, newest first."""
    _require_accounting_access(current_user)
    if reconciled_status is not None and reconciled_status not in (
        "unmatched",
        "matched",
        "manual",
        "ignored",
    ):
        raise HTTPException(status_code=422, detail="invalid reconciled_status")
    async with db_pool.acquire() as conn:
        return await cashout_service.list_bank_transactions(
            conn, reconciled_status=reconciled_status, limit=limit
        )


@router.get("/summary")
async def get_summary(
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Cash-basis P&L summary over the cashout log."""
    _require_accounting_access(current_user)
    async with db_pool.acquire() as conn:
        return await cashout_service.cashbook_summary(
            conn, period_start=period_start, period_end=period_end
        )


# ── P1: reconciliation ──────────────────────────────────────────────────────


@router.get("/match-candidates/{txn_id}")
async def match_candidates(
    txn_id: int,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Propose invoice candidates for an incoming (credit) bank transaction.

    The accountant picks the right one and calls /confirm. Never auto-confirms.
    """
    _require_accounting_access(current_user)
    async with db_pool.acquire() as conn:
        tx = await conn.fetchrow(
            "SELECT id, txn_date, amount_idr, direction, description FROM bank_transactions WHERE id = $1",
            txn_id,
        )
        if tx is None:
            raise HTTPException(status_code=404, detail="bank transaction not found")
        if tx["direction"] != "credit":
            raise HTTPException(status_code=422, detail="only incoming (credit) transactions are matched")

        # open invoices = invoices whose practice is not yet fully paid
        rows = await conn.fetch(
            """
            SELECT i.id AS invoice_id, i.practice_id, i.amount_idr,
                   i.generated_at, COALESCE(i.pph_expected_idr, 0) AS pph_expected_idr,
                   c.full_name AS client_name
            FROM invoices i
            JOIN practices p ON i.practice_id = p.id
            LEFT JOIN clients c ON p.client_id = c.id
            WHERE COALESCE(p.payment_status, 'unpaid') <> 'paid'
            """
        )
        open_invoices = [
            OpenInvoice(
                invoice_id=r["invoice_id"],
                practice_id=r["practice_id"],
                client_name=r["client_name"] or "",
                amount_idr=int(r["amount_idr"] or 0),
                generated_at=r["generated_at"].date() if r["generated_at"] else None,
                pph_expected_idr=int(r["pph_expected_idr"] or 0),
            )
            for r in rows
        ]
        candidates = rank_candidates(
            transfer_amount_idr=int(tx["amount_idr"]),
            transfer_date=tx["txn_date"],
            payer_memo=tx["description"] or "",
            open_invoices=open_invoices,
        )
        return {
            "txn_id": txn_id,
            "transfer_amount_idr": int(tx["amount_idr"]),
            "candidates": [
                {
                    "invoice_id": c.invoice_id,
                    "practice_id": c.practice_id,
                    "client_name": c.client_name,
                    "invoice_amount_idr": c.invoice_amount_idr,
                    "confidence": c.confidence,
                    "reasons": c.reasons,
                    "amount_delta_idr": c.amount_delta_idr,
                    "likely_withheld": c.likely_withheld,
                }
                for c in candidates
            ],
        }


class ConfirmRequest(BaseModel):
    bank_txn_id: int | None = None
    practice_id: int
    invoice_id: int | None = None
    amount_applied_idr: int = Field(ge=0)
    new_status: str = "paid"
    payment_method: str = "bank_transfer"
    payment_reference: str | None = None
    pph_withheld_idr: int = 0
    bank_fee_idr: int = 0
    pnbp_idr: int = 0
    urgent_idr: int = 0
    rptka_imta_idr: int = 0
    margin_idr: int = 0
    movement_date: date | None = None


@router.post("/confirm")
async def confirm_reconciliation(
    payload: ConfirmRequest,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Confirm a payment match. Single writer of payment_status (superscar #9).

    Does NOT auto-transition the practice to on_process — Zero's decision #1:
    Asya moves it with a second explicit click.
    """
    _require_accounting_access(current_user)
    confirmed_by = (current_user.get("email") or "unknown").lower()
    async with db_pool.acquire() as conn:
        try:
            result = await reconcile_service.confirm_payment(
                conn,
                bank_txn_id=payload.bank_txn_id,
                practice_id=payload.practice_id,
                invoice_id=payload.invoice_id,
                amount_applied_idr=payload.amount_applied_idr,
                new_status=payload.new_status,
                confirmed_by=confirmed_by,
                payment_method=payload.payment_method,
                payment_reference=payload.payment_reference,
                pph_withheld_idr=payload.pph_withheld_idr,
                bank_fee_idr=payload.bank_fee_idr,
                pnbp_idr=payload.pnbp_idr,
                urgent_idr=payload.urgent_idr,
                rptka_imta_idr=payload.rptka_imta_idr,
                margin_idr=payload.margin_idr,
                movement_date=payload.movement_date,
            )
        except ReconcileError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Same cache keys the CRM uses (superscar #9) — payment_status changed.
    try:
        from backend.core.cache import invalidate_cache

        await invalidate_cache("zantara:crm_practices_stats:*")
        await invalidate_cache("zantara:crm_clients_stats:*")
    except Exception as cache_exc:  # cache failure must not fail the write
        logger.warning("accounting confirm cache invalidation failed: %s", cache_exc)

    return {
        "practice_id": result.practice_id,
        "invoice_id": result.invoice_id,
        "cashout_id": result.cashout_id,
        "reconciliation_log_id": result.reconciliation_log_id,
        "status_before": result.status_before,
        "status_after": result.status_after,
    }
