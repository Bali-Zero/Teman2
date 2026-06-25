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

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.accounting import cashout_service

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
