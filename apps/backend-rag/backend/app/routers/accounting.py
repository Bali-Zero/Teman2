"""Accounting router — cash-control endpoints for Asya (the agency accountant).

P0: read-only views (cashout log, bank transactions, cashbook summary).
P1 adds: statement upload, reconciliation matching, payment confirm.

RBAC: gated to CRM admins (asya@balizero.com is already in CRM_EXTRA_ADMIN_EMAILS)
via is_crm_admin(). Money is IDR. See migration 238_accounting_asya.sql.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.accounting import (
    cashout_import_service,
    cashout_service,
    reconcile_service,
)
from backend.services.accounting.matcher import OpenInvoice, rank_candidates
from backend.services.accounting.reconcile_service import ReconcileError

# 8 MB is generous for a digital cashout worksheet PDF (Asya's are < 1 MB).
_MAX_CASHOUT_PDF_BYTES = 8 * 1024 * 1024

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


# ── Cashout PDF import (Asya's weekly GABUNGAN worksheet) ────────────────────


@router.post("/import-cashout")
async def import_cashout_pdf(
    file: UploadFile = File(..., description="Asya's GABUNGAN cashout worksheet PDF"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Import a weekly cashout worksheet PDF into the cashout log.

    The file is Asya's already-processed 9-column worksheet (NAME/PROCESS/PNBP/
    URGENT/RPTKA-IMTA/MARGIN BS/FINAL PRICE/NOTE), digitally exported (parsed with
    pdfplumber — no OCR), usually stacking several weeks each opened by a
    "NEW CASHOUT DD MONTH YYYY" title row.

    Idempotent: re-uploading the same file replaces that week's prior import rows
    instead of duplicating them, and never touches reconciliation-linked rows.
    """
    _require_accounting_access(current_user)

    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="only .pdf cashout worksheets are accepted")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty file")
    if len(data) > _MAX_CASHOUT_PDF_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 8 MB)")

    imported_by = (current_user.get("email") or "unknown").lower()

    # pdfplumber needs a real path; write to a private temp file and clean up.
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        try:
            rows = cashout_import_service.parse_cashout_pdf_with_weeks(tmp_path)
        except ValueError as exc:
            # undated / non-cashout PDF — loud, not a silent empty import (superscar #2)
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if not rows:
            raise HTTPException(
                status_code=422,
                detail="no cashout rows found in the PDF (parsed 0 client rows)",
            )

        async with db_pool.acquire() as conn:
            result = await cashout_import_service.persist_cashout_rows(
                conn, rows, imported_by=imported_by, source_filename=filename
            )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    # Cashout log changed → drop the same CRM caches the confirm path drops.
    try:
        from backend.core.cache import invalidate_cache

        await invalidate_cache("zantara:crm_clients_stats:*")
    except Exception as cache_exc:  # cache failure must not fail the import
        logger.warning("accounting import-cashout cache invalidation failed: %s", cache_exc)

    return {
        "source_filename": filename,
        "imported": result["imported"],
        "weeks": result["weeks"],
        "replaced": result["deleted"],
    }


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


# ── P3: Google Sheets export ────────────────────────────────────────────────

# The service account cannot CREATE a Drive file (no Drive quota): Zero creates
# the target spreadsheet, shares it with the SA email as Editor, and sets its id
# in ACCOUNTING_EXPORT_SHEET_ID. The app only writes into that existing sheet.
EXPORT_SHEET_ID_ENV = "ACCOUNTING_EXPORT_SHEET_ID"
# Which tab to write into. Defaults to "Cashout"; override via env for a fresh
# sheet whose tab is still "Sheet1"/"Foglio1" (no need to rename the tab).
EXPORT_SHEET_TAB_ENV = "ACCOUNTING_EXPORT_SHEET_TAB"
EXPORT_SHEET_TAB_DEFAULT = "Cashout"


def _export_range() -> str:
    """Build the A1 write anchor for the configured tab.

    Tab names with spaces or special chars must be single-quoted in A1 notation
    (e.g. 'Weekly Cashout'!A1); embedded single quotes are doubled per the API.
    """
    tab = (os.environ.get(EXPORT_SHEET_TAB_ENV, "") or EXPORT_SHEET_TAB_DEFAULT).strip()
    if not tab:
        tab = EXPORT_SHEET_TAB_DEFAULT
    safe = tab.replace("'", "''")
    return f"'{safe}'!A1"


@router.post("/export-sheet")
async def export_to_sheet(
    week_label: str | None = Query(None, description="Optional week filter"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """On-demand push of the weekly cashout to Zero's Google Sheet.

    NOT auto-sync (Zero's decision #4): Asya clicks Export. The target sheet is
    pre-created+shared by Zero; we write into it via the existing SheetsService.
    """
    _require_accounting_access(current_user)

    spreadsheet_id = os.environ.get(EXPORT_SHEET_ID_ENV, "").strip()
    if not spreadsheet_id:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{EXPORT_SHEET_ID_ENV} is not configured. Zero must create the "
                "Google Sheet, share it with the service-account email as Editor, "
                f"and set {EXPORT_SHEET_ID_ENV}."
            ),
        )

    export_range = _export_range()

    async with db_pool.acquire() as conn:
        rows = await cashout_service.list_cashout(
            conn, week_label=week_label, limit=1000
        )
    values = cashout_service.build_export_rows(rows)

    try:
        from backend.services.integrations.sheets_service import SheetsService

        svc = SheetsService()
        result = await svc.write_range(spreadsheet_id, export_range, values)
    except FileNotFoundError as exc:
        # SA credentials not present in this environment.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface the Sheets API failure as 502
        logger.error("accounting export-sheet failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=(
                "Google Sheets write failed. Verify the sheet is shared with the "
                f"service account and the tab {export_range.split('!')[0]} exists "
                f"(override with {EXPORT_SHEET_TAB_ENV}). ({exc})"
            ),
        ) from exc

    # values includes the header row; data rows = len-1.
    return {
        "spreadsheet_id": spreadsheet_id,
        "rows_exported": max(len(values) - 1, 0),
        "updated_cells": result.get("updatedCells", 0),
        "range": export_range,
    }
