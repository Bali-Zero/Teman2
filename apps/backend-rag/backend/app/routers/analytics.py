"""
Analytics API Router
Exposes historical analytics endpoints and unified dashboard for founder consumption.

Endpoints:
- POST /api/analytics/funnel-event           - Ingest funnel event (public, 11 whitelisted events)
- GET /api/analytics/dashboard               - Unified analytics dashboard (cached)
- GET /api/analytics/completion-rates
- GET /api/analytics/response-times
- GET /api/analytics/sla-compliance
- GET /api/analytics/revenue
- GET /api/analytics/monthly-report/{year}/{month}
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.database import get_database_pool as get_database_pool_dep
from backend.services.analytics.historical_analytics import (
    calculate_completion_rate,
    calculate_response_times,
    calculate_revenue_metrics,
    calculate_sla_compliance,
    generate_monthly_report,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# ---------------------------------------------------------------------------
# F-19: Funnel event ingest (public — no auth required)
# ---------------------------------------------------------------------------

ALLOWED_EVENTS: frozenset[str] = frozenset(
    {
        "visa_quiz_completed",
        "visa_result_viewed",
        "visa_chat_question",
        "visa_whatsapp_cta",
        "visa_calling_block",
        "kbli_code_viewed",
        "kbli_search",
        "kbli_chat_question",
        "kbli_whatsapp_cta",
        "tax_dashboard_viewed",
        "tax_whatsapp_cta",
        "property_cta_clicked",
        "property_chat_question",
        "property_whatsapp_cta",
    }
)


class FunnelEvent(BaseModel):
    session_id: str = Field(min_length=32, max_length=64)
    event: str
    payload: dict = Field(default_factory=dict)


@router.post("/funnel-event")
async def ingest_funnel_event(
    req: FunnelEvent,
    pool=Depends(get_database_pool_dep),
) -> dict[str, Any]:
    """
    Ingest a funnel analytics event. Never blocks the UX: unknown events
    return ok=False instead of raising an error.
    """
    if req.event not in ALLOWED_EVENTS:
        return {"ok": False, "reason": "unknown_event"}
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE funnel_sessions
            SET step_state = step_state || jsonb_build_object(
                    'last_event', $2::text,
                    'last_event_at', to_jsonb(NOW())
                ),
                last_touched_at = NOW()
            WHERE session_id = $1
            """,
            req.session_id,
            req.event,
        )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Founder-only endpoints
# ---------------------------------------------------------------------------


def verify_founder_access(current_user: Any = Depends(get_current_user)) -> Any:
    """
    Verify that the user has founder or admin level access.
    """
    if current_user.get("role") not in ["Founder", "admin"]:
        raise HTTPException(
            status_code=403, detail="Access denied. This dashboard is for founders only.",
        )
    return current_user


@router.get("/dashboard")
async def get_analytics_dashboard(
    period: int = Query(7, ge=1, le=90, description="Lookback period in days"),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> dict[str, Any]:
    """
    Unified analytics dashboard combining RAG, CRM, team, and system metrics.

    Returns cached data (Redis TTL 5min) for fast loading.
    """
    from backend.app.core.config import settings

    cache_key = f"zantara:analytics_dashboard:{period}d"

    # Try Redis cache first
    try:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                data["_cached"] = True
                return data
        finally:
            await redis.aclose()
    except Exception as e:
        logger.debug(f"Dashboard cache miss or Redis unavailable: {e}")

    start_time = time.time()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=period)
    dashboard: dict[str, Any] = {"period_days": period}

    try:
        async with db_pool.acquire() as conn:
            # --- RAG metrics ---
            rag_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_queries,
                    COUNT(*) FILTER (WHERE chunks_retrieved_count = 0) as failed_queries,
                    ROUND(AVG(execution_time_ms)::numeric, 0) as avg_latency_ms,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                    COUNT(*) FILTER (WHERE user_feedback = 'thumbs_up') as thumbs_up,
                    COUNT(*) FILTER (WHERE user_feedback = 'thumbs_down') as thumbs_down,
                    COUNT(*) FILTER (WHERE user_feedback IS NOT NULL) as total_feedback
                FROM query_analytics
                WHERE created_at >= $1
                """,
                cutoff,
            )
            total_fb = rag_row["total_feedback"] or 0
            dashboard["rag"] = {
                "total_queries": rag_row["total_queries"] or 0,
                "failed_queries": rag_row["failed_queries"] or 0,
                "avg_latency_ms": int(rag_row["avg_latency_ms"] or 0),
                "total_cost_usd": round(float(rag_row["total_cost_usd"] or 0), 4),
                "satisfaction_percent": (
                    round((rag_row["thumbs_up"] or 0) / total_fb * 100, 1)
                    if total_fb > 0 else None
                ),
            }

            # Cache hit rate from Prometheus
            try:
                from backend.app.metrics import cache_hits, cache_misses

                hits = cache_hits._value.get()
                misses = cache_misses._value.get()
                total = hits + misses
                dashboard["rag"]["cache_hit_rate"] = round(hits / total, 3) if total > 0 else 0.0
            except Exception:
                dashboard["rag"]["cache_hit_rate"] = None

            # --- CRM metrics ---
            crm_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_clients,
                    COUNT(*) FILTER (WHERE created_at >= $1) as new_clients,
                    COUNT(*) FILTER (WHERE status = 'active') as active_clients
                FROM clients
                """,
                cutoff,
            )
            rev_row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(quoted_price), 0) as quoted,
                    COALESCE(SUM(actual_price), 0) as actual,
                    COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN actual_price ELSE 0 END), 0) as paid,
                    COUNT(*) as total_practices,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status NOT IN ('completed', 'cancelled')) as active
                FROM practices
                """,
            )
            dashboard["crm"] = {
                "total_clients": crm_row["total_clients"] or 0,
                "new_clients_period": crm_row["new_clients"] or 0,
                "active_clients": crm_row["active_clients"] or 0,
                "practices_total": rev_row["total_practices"] or 0,
                "practices_active": rev_row["active"] or 0,
                "practices_completed": rev_row["completed"] or 0,
                "revenue_quoted": float(rev_row["quoted"] or 0),
                "revenue_paid": float(rev_row["paid"] or 0),
                "revenue_outstanding": float((rev_row["actual"] or 0) - (rev_row["paid"] or 0)),
            }

            # --- Conversations per channel ---
            channel_rows = await conn.fetch(
                """
                SELECT
                    channel,
                    COUNT(*) as count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM conversations
                WHERE created_at >= $1
                GROUP BY channel
                ORDER BY count DESC
                """,
                cutoff,
            )
            dashboard["channels"] = [
                {
                    "channel": r["channel"] or "unknown",
                    "conversations": r["count"],
                    "unique_users": r["unique_users"],
                }
                for r in channel_rows
            ]

            # --- Query volume trend (daily) ---
            volume_rows = await conn.fetch(
                """
                SELECT
                    date_trunc('day', created_at) as day,
                    COUNT(*) as queries
                FROM query_analytics
                WHERE created_at >= $1
                GROUP BY day
                ORDER BY day
                """,
                cutoff,
            )
            dashboard["query_volume_daily"] = [
                {"date": r["day"].isoformat(), "queries": r["queries"]}
                for r in volume_rows
            ]

    except Exception as e:
        logger.error(f"Dashboard query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}") from e

    dashboard["generated_at"] = datetime.now(tz=timezone.utc).isoformat()
    dashboard["query_time_ms"] = int((time.time() - start_time) * 1000)
    dashboard["_cached"] = False

    # Cache in Redis (TTL 5min)
    try:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await redis.set(cache_key, json.dumps(dashboard, default=str), ex=300)
        finally:
            await redis.aclose()
    except Exception as e:
        logger.debug(f"Failed to cache dashboard: {e}")

    return dashboard


@router.get("/completion-rates")
async def get_completion_rates(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get practice completion rates.

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_completion_rate(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate completion rates: {str(e)}",
        ) from e


@router.get("/response-times")
async def get_response_times(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get average response times (inquiry to start, start to completion).

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_response_times(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate response times: {str(e)}") from e


@router.get("/sla-compliance")
async def get_sla_compliance(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get SLA compliance rates (practices completed within expected duration).

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_sla_compliance(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate SLA compliance: {str(e)}") from e


@router.get("/revenue")
async def get_revenue_metrics(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get revenue metrics by practice type.

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_revenue_metrics(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate revenue metrics: {str(e)}",
        ) from e


@router.get("/monthly-report/{year}/{month}")
async def get_monthly_report(
    year: int,
    month: int,
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Generate comprehensive monthly analytics report.

    - **year**: Year (e.g., 2026)
    - **month**: Month (1-12)
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    if year < 2020 or year > 2100:
        raise HTTPException(status_code=400, detail="Invalid year")

    try:
        return await generate_monthly_report(db_pool, year, month)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate monthly report: {str(e)}") from e
