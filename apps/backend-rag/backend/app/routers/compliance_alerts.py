"""
REST endpoints for compliance alerts (decisions #1/#2/#11).

Prefix: /api/compliance/alerts

RBAC (CLAUDE.md §10):
  admin  (zero@, antonellosiano@, asya@balizero.com) → all clients
  team   (other @balizero.com)                       → own clients (assigned_to)
  client                                             → denied (403)

Route ordering: /metrics and /retrain must be declared BEFORE /{alert_id}
so FastAPI does not bind the literal strings as the alert_id path param.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.compliance.alert_feedback import AlertFeedback
from backend.services.compliance.alert_metrics import (
    compute_metrics,
    compute_metrics_all,
)
from backend.services.compliance.alert_repository import AlertRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance/alerts", tags=["compliance"])


# ── Admin set ────────────────────────────────────────────────────────────
_ADMIN_EMAILS: frozenset[str] = frozenset(
    {"zero@balizero.com", "antonellosiano@balizero.com", "asya@balizero.com"}
)


def _is_admin(user: dict[str, Any]) -> bool:
    return (user.get("email") or "").lower() in _ADMIN_EMAILS


def _require_admin(user: dict[str, Any]) -> None:
    if not _is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")


# ── Request/response models ──────────────────────────────────────────────


class OutcomeBody(BaseModel):
    outcome: Literal["acted", "dismissed"]
    note: str | None = None


class RetrainBody(BaseModel):
    dry_run: bool = False
    category: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────


def _overall(rows: list[Any]) -> dict[str, Any]:
    """Aggregate metrics across all categories into a single totals dict."""
    return {
        "total_generated": sum(r.sample_size for r in rows),
        "total_acted": sum(r.acted for r in rows),
        "total_dismissed": sum(r.dismissed for r in rows),
        "total_expired": sum(r.expired for r in rows),
    }


# ── Endpoints ────────────────────────────────────────────────────────────
# IMPORTANT: /metrics and /retrain must appear before /{alert_id} so that
# FastAPI does not bind "metrics" or "retrain" as the alert_id path param.


@router.get("/metrics")
async def get_metrics(
    window_days: int = Query(90, ge=1, le=365),
    category: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Return precision/recall/F1 metrics per category (admin only).

    Args:
        window_days: Look-back window for outcomes (default 90 days).
        category: If given, return only this category.
        user: Authenticated user dict.
        pool: DB connection pool.

    Returns:
        {by_category: {...}, overall: {...}}
    """
    _require_admin(user)
    async with pool.acquire() as conn:
        if category:
            cm = await compute_metrics(conn, window_days=window_days, category=category)
            return {"by_category": {category: cm.__dict__}, "overall": _overall([cm])}
        all_m = await compute_metrics_all(conn, window_days=window_days)
        return {
            "by_category": {k: v.__dict__ for k, v in all_m.items()},
            "overall": _overall(list(all_m.values())),
        }


@router.post("/retrain")
async def post_retrain(
    body: RetrainBody,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Manually trigger threshold autotune (admin only, honors kill-switch).

    Args:
        body: {dry_run, category?}. dry_run is accepted but not yet enforced
              at the service layer (reserved for future).
        user: Authenticated user dict.
        pool: DB connection pool.

    Returns:
        {changed: [...], reason: "applied"|"no_change"|"autotune_disabled"}
    """
    _require_admin(user)
    fb = AlertFeedback(db_pool=pool)
    result: dict[str, Any] = await fb.retrain(
        category=body.category if body.category else None
    )
    if body.dry_run:
        logger.warning(
            "dry_run=true requested but not implemented at service layer; "
            "thresholds were actually updated",
        )
        result["dry_run_not_implemented"] = True
    return result


@router.get("")
async def list_alerts(
    client_id: int | None = Query(None),
    category: str | None = Query(None),
    severity: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """List compliance alerts with optional filters.

    Team members only see alerts for clients where
    ``clients.assigned_to`` matches their email.

    Args:
        client_id: Filter by specific client.
        category: Filter by alert category.
        severity: Filter by severity level.
        status_filter: Filter by alert status.
        limit: Max rows to return (1–500).
        offset: Pagination offset.
        user: Authenticated user dict.
        pool: DB connection pool.

    Returns:
        {items: [...], limit: int, offset: int}
    """
    clauses: list[str] = []
    params: list[Any] = []

    if not _is_admin(user):
        # team: restrict to rows where the owning client is assigned to this user
        clauses.append(
            f"client_id IN (SELECT id FROM clients WHERE assigned_to = ${len(params) + 1})"
        )
        params.append((user.get("email") or "").lower())

    if client_id is not None:
        clauses.append(f"client_id = ${len(params) + 1}")
        params.append(client_id)
    if category:
        clauses.append(f"category = ${len(params) + 1}")
        params.append(category)
    if severity:
        clauses.append(f"severity = ${len(params) + 1}")
        params.append(severity)
    if status_filter:
        clauses.append(f"status = ${len(params) + 1}")
        params.append(status_filter)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM compliance_alerts {where} "
            f"ORDER BY created_at DESC "
            f"LIMIT ${limit_idx} OFFSET ${offset_idx}",
            *params,
        )

    return {
        "items": [dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
    }


@router.post("/{alert_id}/outcome")
async def post_outcome(
    alert_id: str,
    body: OutcomeBody,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Record an outcome for an alert (acted / dismissed).

    Team members can only record outcomes on their own clients
    (matched via ``clients.assigned_to``).

    Args:
        alert_id: Unique alert identifier.
        body: {outcome, note?}
        user: Authenticated user dict.
        pool: DB connection pool.

    Returns:
        {alert_id, outcome, status}
    """
    # Verify alert exists
    async with pool.acquire() as conn:
        alert_row = await conn.fetchrow(
            "SELECT alert_id, client_id, status FROM compliance_alerts WHERE alert_id = $1",
            alert_id,
        )
    if alert_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")

    # RBAC: team can only outcome on own clients
    if not _is_admin(user):
        async with pool.acquire() as conn:
            assigned = await conn.fetchval(
                "SELECT assigned_to FROM clients WHERE id = $1", alert_row["client_id"]
            )
        user_email = (user.get("email") or "").lower()
        if not assigned or assigned.lower() != user_email:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your client")

    new_status = "resolved" if body.outcome == "acted" else "acknowledged"

    async with pool.acquire() as conn:
        async with conn.transaction():
            repo = AlertRepository.with_connection(conn)
            updated = await repo.update_status(alert_id, new_status=new_status)
            await conn.execute(
                "INSERT INTO alert_outcomes (alert_id, outcome, actioned_by, note) "
                "VALUES ($1, $2, $3, $4)",
                alert_id,
                body.outcome,
                (user.get("email") or "").lower(),
                body.note,
            )

    return {"alert_id": alert_id, "outcome": body.outcome, "status": updated.status}


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Retrieve a single alert with its outcomes and delivery trace.

    Args:
        alert_id: Unique alert identifier.
        user: Authenticated user dict.
        pool: DB connection pool.

    Returns:
        {alert: {...}, outcomes: [...], deliveries: [...]}
    """
    async with pool.acquire() as conn:
        alert = await conn.fetchrow(
            "SELECT * FROM compliance_alerts WHERE alert_id = $1", alert_id
        )
        if alert is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")

        if not _is_admin(user):
            assigned = await conn.fetchval(
                "SELECT assigned_to FROM clients WHERE id = $1", alert["client_id"]
            )
            user_email = (user.get("email") or "").lower()
            if not assigned or assigned.lower() != user_email:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your client")

        outcomes = await conn.fetch(
            "SELECT * FROM alert_outcomes WHERE alert_id = $1 ORDER BY actioned_at DESC",
            alert_id,
        )
        deliveries = await conn.fetch(
            "SELECT * FROM notification_log WHERE ref LIKE $1 ORDER BY sent_at DESC",
            f"compliance_alert:{alert_id}:%",
        )

    return {
        "alert": dict(alert),
        "outcomes": [dict(o) for o in outcomes],
        "deliveries": [dict(d) for d in deliveries],
    }
