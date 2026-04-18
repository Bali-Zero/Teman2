"""
Admin PII Router.

Surfaces the durable audit trail written by `backend.services.pii.
violation_store` (migration 114 → `pii_violations` table). Admin auth
required via `verify_debug_access`.

Endpoints:
- GET /api/admin/pii/violations   — paginated recent violations
- GET /api/admin/pii/trend         — 7/30-day rollup per pattern
- GET /api/admin/pii/by-route      — top routes ranked by violation count
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.deps.database import get_database_pool
from backend.app.routers.debug import verify_debug_access
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/pii", tags=["admin-pii"])


@router.get("/violations")
async def list_violations(
    since: datetime | None = Query(
        default=None,
        description="Return violations with created_at >= since (ISO8601). "
                    "Defaults to 24 hours ago.",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: int | None = Query(
        default=None,
        description="Cursor from a previous page's `next_cursor`. "
                    "Omit for the first page.",
    ),
    pattern: str | None = Query(
        default=None,
        description="Filter to a single pattern (ID_KTP, ID_NPWP, etc.)",
    ),
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """Paginated recent violations, newest first. Keyset pagination on id DESC."""
    since = since or (datetime.now(timezone.utc) - timedelta(days=1))

    params: list[Any] = [since]
    cursor_clause = ""
    if cursor is not None:
        params.append(cursor)
        cursor_clause = f" AND id < ${len(params)}"
    pattern_clause = ""
    if pattern is not None:
        params.append(pattern)
        pattern_clause = f" AND pattern_matched = ${len(params)}"
    params.append(limit)
    limit_idx = len(params)

    rows = await pool.fetch(
        f"""
        SELECT id, request_id, route, pattern_matched, severity,
               user_hash, occurrence_count, created_at
        FROM pii_violations
        WHERE created_at >= $1{cursor_clause}{pattern_clause}
        ORDER BY id DESC
        LIMIT ${limit_idx}
        """,
        *params,
    )
    items = [dict(r) for r in rows]
    next_cursor = items[-1]["id"] if len(items) == limit else None
    return {
        "since": since.isoformat(),
        "count": len(items),
        "next_cursor": next_cursor,
        "items": items,
    }


@router.get("/trend")
async def pattern_trend(
    days: int = Query(default=7, ge=1, le=90),
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """Per-day violation counts per pattern for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await pool.fetch(
        """
        SELECT
            pattern_matched,
            DATE_TRUNC('day', created_at) AS day,
            COUNT(*) AS count,
            SUM(occurrence_count) AS total_occurrences
        FROM pii_violations
        WHERE created_at >= $1
        GROUP BY pattern_matched, day
        ORDER BY day DESC, count DESC
        """,
        since,
    )
    return {
        "since": since.isoformat(),
        "days": days,
        "buckets": [dict(r) for r in rows],
    }


@router.get("/by-route")
async def top_routes(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=200),
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """Top routes by violation count over the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await pool.fetch(
        """
        SELECT
            route,
            COUNT(*) AS violation_count,
            SUM(occurrence_count) AS total_occurrences,
            COUNT(DISTINCT pattern_matched) AS distinct_patterns,
            MAX(created_at) AS last_seen
        FROM pii_violations
        WHERE created_at >= $1
        GROUP BY route
        ORDER BY violation_count DESC
        LIMIT $2
        """,
        since,
        limit,
    )
    return {
        "since": since.isoformat(),
        "days": days,
        "routes": [dict(r) for r in rows],
    }
