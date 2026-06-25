"""Cash-control read/query logic over the weekly_cashout + bank_transactions tables.

Data/logic separation: callers pass an asyncpg connection. All money is IDR
(BIGINT). Cash-basis: P&L = paid invoices in − expenses/payroll/etc out.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def list_cashout(
    conn: asyncpg.Connection,
    *,
    week_label: str | None = None,
    type_filter: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return weekly_cashout rows, newest first, optionally filtered.

    Mirrors Asya's sheet: each invoice_payment row carries the price
    decomposition (pnbp/urgent/rptka_imta/margin/final_price).
    """
    query_parts = [
        """
        SELECT wc.id, wc.movement_date, wc.week_label, wc.direction, wc.type,
               wc.amount_idr, wc.pnbp_idr, wc.urgent_idr, wc.rptka_imta_idr,
               wc.margin_idr, wc.final_price_idr, wc.original_currency,
               wc.original_amount, wc.fx_rate, wc.fx_date, wc.pph_withheld_idr,
               wc.bank_fee_idr, wc.linked_practice_id, wc.linked_invoice_id,
               wc.category, wc.description, wc.counterparty, wc.payment_method,
               wc.recorded_by, wc.recorded_at, wc.reversed_by_id,
               c.full_name AS client_name
        FROM weekly_cashout wc
        LEFT JOIN practices p ON wc.linked_practice_id = p.id
        LEFT JOIN clients c ON p.client_id = c.id
        WHERE wc.reversed_by_id IS NULL
        """
    ]
    params: list[Any] = []
    idx = 1
    if week_label:
        query_parts.append(f" AND wc.week_label = ${idx}")
        params.append(week_label)
        idx += 1
    if type_filter:
        query_parts.append(f" AND wc.type = ${idx}")
        params.append(type_filter)
        idx += 1
    query_parts.append(f" ORDER BY wc.movement_date DESC, wc.id DESC LIMIT ${idx}")
    params.append(limit)

    rows = await conn.fetch("".join(query_parts), *params)
    return [dict(r) for r in rows]


async def list_bank_transactions(
    conn: asyncpg.Connection,
    *,
    reconciled_status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return bank_transactions, newest first, optionally filtered by status."""
    query_parts = [
        """
        SELECT bt.id, bt.statement_id, bt.txn_date, bt.description, bt.amount_idr,
               bt.direction, bt.running_balance_idr, bt.bank_account_id,
               bt.reconciled_status, bt.matched_practice_id, bt.matched_invoice_id,
               bt.created_at
        FROM bank_transactions bt
        WHERE 1=1
        """
    ]
    params: list[Any] = []
    idx = 1
    if reconciled_status:
        query_parts.append(f" AND bt.reconciled_status = ${idx}")
        params.append(reconciled_status)
        idx += 1
    query_parts.append(f" ORDER BY bt.txn_date DESC, bt.id DESC LIMIT ${idx}")
    params.append(limit)

    rows = await conn.fetch("".join(query_parts), *params)
    return [dict(r) for r in rows]


async def cashbook_summary(
    conn: asyncpg.Connection,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, Any]:
    """Cash-basis P&L summary over weekly_cashout.

    income  = sum(amount) where direction='in'
    outgoing = sum(amount) where direction='out'
    net     = income - outgoing
    Plus margin_total (Bali Zero margin) and a breakdown by type.
    Excludes reversed rows.
    """
    where = ["wc.reversed_by_id IS NULL"]
    params: list[Any] = []
    idx = 1
    if period_start:
        where.append(f"wc.movement_date >= ${idx}")
        params.append(period_start)
        idx += 1
    if period_end:
        where.append(f"wc.movement_date <= ${idx}")
        params.append(period_end)
        idx += 1
    where_sql = " AND ".join(where)

    totals_row = await conn.fetchrow(
        f"""
        SELECT
            COALESCE(SUM(amount_idr) FILTER (WHERE direction='in'), 0)  AS income_idr,
            COALESCE(SUM(amount_idr) FILTER (WHERE direction='out'), 0) AS outgoing_idr,
            COALESCE(SUM(margin_idr) FILTER (WHERE type='invoice_payment'), 0) AS margin_total_idr,
            COALESCE(SUM(pnbp_idr) FILTER (WHERE type='invoice_payment'), 0)   AS pnbp_total_idr,
            COUNT(*) AS row_count
        FROM weekly_cashout wc
        WHERE {where_sql}
        """,
        *params,
    )
    totals = dict(totals_row) if totals_row else {}
    income = int(totals.get("income_idr", 0) or 0)
    outgoing = int(totals.get("outgoing_idr", 0) or 0)

    by_type_rows = await conn.fetch(
        f"""
        SELECT type, direction,
               COALESCE(SUM(amount_idr), 0) AS total_idr,
               COUNT(*) AS n
        FROM weekly_cashout wc
        WHERE {where_sql}
        GROUP BY type, direction
        ORDER BY total_idr DESC
        """,
        *params,
    )

    return {
        "income_idr": income,
        "outgoing_idr": outgoing,
        "net_idr": income - outgoing,
        "margin_total_idr": int(totals.get("margin_total_idr", 0) or 0),
        "pnbp_total_idr": int(totals.get("pnbp_total_idr", 0) or 0),
        "row_count": int(totals.get("row_count", 0) or 0),
        "by_type": [dict(r) for r in by_type_rows],
    }
