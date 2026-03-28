"""
Query Analytics Repository
Handles all database operations for RAG query analytics tracking.

Provides:
- Logging every query with metadata (collections, chunks, model, cost)
- User feedback (thumbs up/down) recording
- Dashboard aggregation queries (failed queries, collection hit rates, volume, satisfaction)
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger, log_error, log_success

logger = get_logger(__name__)


class QueryAnalyticsRepository:
    """Repository for RAG query analytics persistence and aggregation."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    # ========== WRITE OPERATIONS ==========

    async def log_query(
        self,
        query_text: str,
        user_id: str | None = None,
        session_id: str | None = None,
        collections_queried: list[str] | None = None,
        chunks_retrieved_count: int = 0,
        response_generated: bool = False,
        model_used: str | None = None,
        execution_time_ms: int | None = None,
        token_usage_total: int = 0,
        cost_usd: float = 0.0,
        error_message: str | None = None,
    ) -> str | None:
        """
        Log a RAG query execution to the analytics table.

        Note: The production user_id column is UUID type. We store the
        user email/identifier in the metadata JSONB column and leave
        user_id NULL to avoid type mismatch.

        Returns:
            query_id (UUID string) if successful, None otherwise
        """
        try:
            import hashlib
            import json

            query_hash = hashlib.md5(query_text.encode()).hexdigest()
            metadata = json.dumps({"user_email": user_id} if user_id else {})

            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO query_analytics (
                        query_text, query_hash, session_id, metadata,
                        collections_queried, chunks_retrieved_count,
                        response_generated, model_used, execution_time_ms,
                        token_usage_total, cost_usd, error_message
                    ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12)
                    RETURNING id
                    """,
                    query_text,
                    query_hash,
                    session_id,
                    metadata,
                    collections_queried or [],
                    chunks_retrieved_count,
                    response_generated,
                    model_used,
                    execution_time_ms,
                    token_usage_total,
                    cost_usd,
                    error_message,
                )

                query_id = str(row["id"]) if row else None
                logger.debug(
                    "Logged query analytics",
                    extra={
                        "query_id": query_id,
                        "chunks": chunks_retrieved_count,
                        "collections": collections_queried,
                    },
                )
                return query_id

        except Exception as e:
            log_error(logger, "Failed to log query analytics", error=e)
            return None

    async def record_feedback(
        self,
        query_id: str,
        feedback: str,
        comment: str | None = None,
    ) -> bool:
        """
        Record user feedback (thumbs_up / thumbs_down) for a query.

        Args:
            query_id: UUID of the query
            feedback: 'thumbs_up' or 'thumbs_down'
            comment: Optional feedback comment

        Returns:
            True if updated successfully
        """
        if feedback not in ("thumbs_up", "thumbs_down"):
            logger.warning(f"Invalid feedback value: {feedback}")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE query_analytics
                    SET user_feedback = $1, feedback_comment = $2
                    WHERE id = $3::uuid
                    """,
                    feedback,
                    comment,
                    query_id,
                )
                updated = result.split()[-1] != "0"
                if updated:
                    log_success(logger, "Recorded feedback", query_id=query_id, feedback=feedback)
                return updated

        except Exception as e:
            log_error(logger, "Failed to record feedback", error=e)
            return False

    # ========== DASHBOARD AGGREGATION QUERIES ==========

    async def get_failed_queries(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Top N queries that returned 0 chunks (failed to find relevant content).
        """
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        query_text,
                        COUNT(*) as fail_count,
                        MAX(collections_queried) as collections_attempted,
                        MAX(created_at) as last_seen
                    FROM query_analytics
                    WHERE chunks_retrieved_count = 0
                      AND created_at >= $1
                    GROUP BY query_text
                    ORDER BY fail_count DESC
                    LIMIT $2
                    """,
                    cutoff,
                    limit,
                )
                return [dict(r) for r in rows]

        except Exception as e:
            log_error(logger, "Failed to get failed queries", error=e)
            return []

    async def get_collection_hit_rates(
        self,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Collection usage stats: how often each collection is queried and
        what percentage of queries to that collection return results.
        """
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        col AS collection_name,
                        COUNT(*) AS total_queries,
                        COUNT(*) FILTER (WHERE chunks_retrieved_count > 0) AS successful_queries,
                        ROUND(
                            COUNT(*) FILTER (WHERE chunks_retrieved_count > 0)::numeric
                            / NULLIF(COUNT(*), 0) * 100, 1
                        ) AS hit_rate_percent
                    FROM query_analytics,
                         LATERAL unnest(collections_queried) AS col
                    WHERE created_at >= $1
                    GROUP BY col
                    ORDER BY total_queries DESC
                    """,
                    cutoff,
                )
                return [dict(r) for r in rows]

        except Exception as e:
            log_error(logger, "Failed to get collection hit rates", error=e)
            return []

    async def get_query_volume(
        self,
        granularity: str = "hour",
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Query volume over time (hourly or daily buckets).

        Args:
            granularity: 'hour' or 'day'
            days: lookback window
        """
        trunc = "hour" if granularity == "hour" else "day"
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT
                        date_trunc('{trunc}', created_at) AS bucket,
                        COUNT(*) AS query_count,
                        COUNT(*) FILTER (WHERE chunks_retrieved_count = 0) AS failed_count,
                        ROUND(AVG(execution_time_ms)::numeric, 0) AS avg_latency_ms
                    FROM query_analytics
                    WHERE created_at >= $1
                    GROUP BY bucket
                    ORDER BY bucket DESC
                    """,
                    cutoff,
                )
                return [
                    {
                        "bucket": r["bucket"].isoformat() if r["bucket"] else None,
                        "query_count": r["query_count"],
                        "failed_count": r["failed_count"],
                        "avg_latency_ms": int(r["avg_latency_ms"] or 0),
                    }
                    for r in rows
                ]

        except Exception as e:
            log_error(logger, "Failed to get query volume", error=e)
            return []

    async def get_satisfaction_score(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        User satisfaction metrics from thumbs up/down feedback.
        """
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE user_feedback = 'thumbs_up') AS thumbs_up,
                        COUNT(*) FILTER (WHERE user_feedback = 'thumbs_down') AS thumbs_down,
                        COUNT(*) FILTER (WHERE user_feedback IS NOT NULL) AS total_feedback,
                        COUNT(*) AS total_queries,
                        ROUND(
                            COUNT(*) FILTER (WHERE user_feedback = 'thumbs_up')::numeric
                            / NULLIF(COUNT(*) FILTER (WHERE user_feedback IS NOT NULL), 0) * 100, 1
                        ) AS satisfaction_percent
                    FROM query_analytics
                    WHERE created_at >= $1
                    """,
                    cutoff,
                )
                return (
                    dict(row)
                    if row
                    else {
                        "thumbs_up": 0,
                        "thumbs_down": 0,
                        "total_feedback": 0,
                        "total_queries": 0,
                        "satisfaction_percent": None,
                    }
                )

        except Exception as e:
            log_error(logger, "Failed to get satisfaction score", error=e)
            return {
                "thumbs_up": 0,
                "thumbs_down": 0,
                "total_feedback": 0,
                "total_queries": 0,
                "satisfaction_percent": None,
            }

    async def get_dashboard_summary(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        Aggregated dashboard summary combining all analytics.
        Single call for the frontend dashboard.
        """
        failed_queries = await self.get_failed_queries(limit=10, days=days)
        collection_hits = await self.get_collection_hit_rates(days=days)
        hourly_volume = await self.get_query_volume(granularity="hour", days=min(days, 2))
        daily_volume = await self.get_query_volume(granularity="day", days=days)
        satisfaction = await self.get_satisfaction_score(days=days)

        return {
            "period_days": days,
            "failed_queries": failed_queries,
            "collection_hit_rates": collection_hits,
            "query_volume_hourly": hourly_volume,
            "query_volume_daily": daily_volume,
            "satisfaction": satisfaction,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
