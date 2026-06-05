"""
Frontend Metrics Ingestion Router.

Receives best-effort browser metrics from the Next.js frontend
(apps/mouth/src/lib/metrics.ts flush()) and appends them to the
``frontend_metrics`` table (migration 206).

Public, unauthenticated POST: metrics.ts flushes from every page including
unauthenticated public surfaces (blog/KBLI/visa/homepage) with no auth
header, so the path is registered in PUBLIC_ENDPOINTS. No PII is accepted —
only metric name/value/labels/timestamp.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import get_database_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics/frontend", tags=["observability", "frontend"])

# Cap a single flush batch to bound a malicious/runaway client.
_MAX_BATCH = 1000


class FrontendMetric(BaseModel):
    """One metric sample, mirroring metrics.ts MetricValue."""

    name: str = Field(..., max_length=200)
    value: float
    labels: dict[str, Any] | None = None
    timestamp: int | None = None  # epoch milliseconds (Date.now())


class FrontendMetricsPayload(BaseModel):
    metrics: list[FrontendMetric] = Field(default_factory=list)
    client_session: str | None = Field(default=None, max_length=200)


def _to_ts(ms: int | None) -> datetime:
    if not ms:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return datetime.now(tz=timezone.utc)


@router.post("", status_code=202)
async def ingest_frontend_metrics(
    request: Request,
    payload: FrontendMetricsPayload = Body(...),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, int]:
    """Append a batch of frontend metrics. Best-effort: returns 202 Accepted."""
    metrics = payload.metrics[:_MAX_BATCH]
    if not metrics:
        return {"accepted": 0}

    # NOTE: the app pool registers a jsonb codec (encoder=json.dumps) in
    # init_db_connection, so labels is passed as a raw dict with NO ::jsonb
    # cast — avoids the JSONB double-encoding scar (2026-05-14).
    rows = [
        (
            _to_ts(m.timestamp),
            m.name,
            float(m.value),
            m.labels,
            payload.client_session,
        )
        for m in metrics
    ]

    try:
        async with db_pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO frontend_metrics
                    (ts_utc, metric_name, metric_value, labels, client_session)
                VALUES ($1, $2, $3, $4, $5)
                """,
                rows,
            )
    except (asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
        # Best-effort sink: never 500 the browser over a metrics write.
        logger.warning(
            "frontend_metrics insert failed (%d samples, names=%s): %s",
            len(rows),
            sorted({m.name for m in metrics}),
            exc,
        )
        return {"accepted": 0}

    logger.info(
        "frontend_metrics ingested: %d samples, names=%s",
        len(rows),
        sorted({m.name for m in metrics}),
    )
    return {"accepted": len(rows)}
