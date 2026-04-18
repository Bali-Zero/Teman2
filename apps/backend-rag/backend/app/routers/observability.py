"""Admin-only RAG observability router.

Exposes ``GET /api/observability/rag-stats`` — a small, cached window over
the ``rag_traces`` ledger intended for the internal Grafana dashboard and
ad-hoc triage. Every response is admin-gated; unauthenticated and
non-admin callers receive 401 / 403 respectively.
"""

from __future__ import annotations

from typing import Annotated, Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.observability.stats_aggregator import (
    StatsRequest,
    aggregate_rag_stats,
)

router = APIRouter(prefix="/api/observability", tags=["observability"])


def _require_admin(user: dict[str, Any]) -> None:
    """Match the admin check used elsewhere (see workspace_analytics)."""
    if user.get("role") == "admin":
        return
    email = (user.get("email") or "").lower()
    if email in settings.admin_emails_set:
        return
    raise HTTPException(status_code=403, detail="admin only")


@router.get("/rag-stats")
async def rag_stats(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    pool: Annotated[asyncpg.Pool, Depends(get_database_pool)],
    window_hours: Annotated[int, Query(ge=1, le=168, alias="window")] = 24,
    domain: Annotated[str | None, Query(max_length=64)] = None,
) -> dict[str, Any]:
    """Return aggregated stage timings + cost for the last ``window`` hours.

    Query parameters:

    * ``window`` (int, 1-168, default 24) — rolling window in hours.
    * ``domain`` (str, optional) — restrict to a single domain bucket
      (``visa``, ``tax``, ``property``, …). Omit for the global view.
    """
    _require_admin(user)

    redis_client = _resolve_redis_client()
    request = StatsRequest(window_hours=window_hours, domain=domain)
    return await aggregate_rag_stats(pool, request, redis_client=redis_client)


def _resolve_redis_client() -> Any | None:
    """Return the shared async Redis client if the manager is initialised.

    Import inside the function so the router module can be imported in
    environments (e.g. unit tests) where Redis is not configured.
    """
    try:
        from backend.core.redis_manager import RedisManager
    except Exception:
        return None
    try:
        return RedisManager.get_instance().get_async_client()
    except Exception:
        return None
