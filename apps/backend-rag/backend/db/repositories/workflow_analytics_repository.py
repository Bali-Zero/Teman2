"""
Workflow Analytics Repository
Handles database operations for LangGraph workflow tracking and feedback.

Provides:
- Logging workflow generation with metadata (steps, confidence, source)
- User feedback recording (score + comment)
- Dashboard aggregation queries (follow rate, avg confidence, top workflows)
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger, log_error, log_success

logger = get_logger(__name__)


class WorkflowAnalyticsRepository:
    """Repository for workflow analytics persistence and aggregation."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    # ========== WRITE OPERATIONS ==========

    async def log_workflow(
        self,
        workflow_id: str,
        query: str,
        user_email: str | None = None,
        workflow_type: str | None = None,
        workflow_name: str | None = None,
        steps_count: int = 0,
        steps_json: dict | list | None = None,
        source: str = "kg_langgraph",
        confidence: float = 0.0,
        execution_time_ms: int | None = None,
    ) -> int | None:
        """
        Log a workflow generation event.

        Returns:
            Row id if successful, None otherwise.
        """
        try:
            import json

            steps_jsonb = json.dumps(steps_json) if steps_json else None

            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO workflow_analytics (
                        workflow_id, query, user_email,
                        workflow_type, workflow_name, steps_count,
                        steps_json, source, confidence, execution_time_ms
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10)
                    RETURNING id
                    """,
                    workflow_id,
                    query,
                    user_email,
                    workflow_type,
                    workflow_name,
                    steps_count,
                    steps_jsonb,
                    source,
                    confidence,
                    execution_time_ms,
                )

                row_id = row["id"] if row else None
                logger.debug(
                    "Logged workflow analytics",
                    extra={
                        "workflow_id": workflow_id,
                        "steps_count": steps_count,
                        "confidence": confidence,
                    },
                )
                return row_id

        except Exception as e:
            log_error(logger, "Failed to log workflow analytics", error=e)
            return None

    async def record_feedback(
        self,
        workflow_id: str,
        followed: bool,
        feedback_score: float | None = None,
        feedback_comment: str | None = None,
    ) -> bool:
        """
        Record user feedback for a workflow.

        Args:
            workflow_id: The workflow identifier
            followed: Whether the user followed the suggested workflow
            feedback_score: Optional score (0.0 - 5.0)
            feedback_comment: Optional text comment

        Returns:
            True if updated successfully.
        """
        if feedback_score is not None and not (0.0 <= feedback_score <= 5.0):
            logger.warning(f"Invalid feedback score: {feedback_score}")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE workflow_analytics
                    SET followed = $1, feedback_score = $2, feedback_comment = $3
                    WHERE workflow_id = $4
                    """,
                    followed,
                    feedback_score,
                    feedback_comment,
                    workflow_id,
                )
                updated = result.split()[-1] != "0"
                if updated:
                    log_success(
                        logger,
                        "Recorded workflow feedback",
                        workflow_id=workflow_id,
                        followed=followed,
                        score=feedback_score,
                    )
                return updated

        except Exception as e:
            log_error(logger, "Failed to record workflow feedback", error=e)
            return False

    # ========== DASHBOARD AGGREGATION QUERIES ==========

    async def get_follow_rate(self, days: int = 7) -> dict[str, Any]:
        """Percentage of workflows that were followed by users."""
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) AS total_workflows,
                        COUNT(*) FILTER (WHERE followed = TRUE) AS followed_count,
                        ROUND(
                            COUNT(*) FILTER (WHERE followed = TRUE)::numeric
                            / NULLIF(COUNT(*), 0) * 100, 1
                        ) AS follow_rate_percent,
                        ROUND(AVG(confidence)::numeric, 3) AS avg_confidence,
                        ROUND(AVG(feedback_score)::numeric, 2) AS avg_feedback_score
                    FROM workflow_analytics
                    WHERE timestamp >= $1
                    """,
                    cutoff,
                )
                return (
                    dict(row)
                    if row
                    else {
                        "total_workflows": 0,
                        "followed_count": 0,
                        "follow_rate_percent": None,
                        "avg_confidence": None,
                        "avg_feedback_score": None,
                    }
                )

        except Exception as e:
            log_error(logger, "Failed to get follow rate", error=e)
            return {
                "total_workflows": 0,
                "followed_count": 0,
                "follow_rate_percent": None,
                "avg_confidence": None,
                "avg_feedback_score": None,
            }

    async def get_top_workflows(self, limit: int = 10, days: int = 7) -> list[dict[str, Any]]:
        """Top N most generated workflow types by frequency."""
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        workflow_name,
                        workflow_type,
                        COUNT(*) AS generation_count,
                        ROUND(AVG(confidence)::numeric, 3) AS avg_confidence,
                        COUNT(*) FILTER (WHERE followed = TRUE) AS followed_count,
                        ROUND(AVG(feedback_score)::numeric, 2) AS avg_score
                    FROM workflow_analytics
                    WHERE timestamp >= $1 AND workflow_name IS NOT NULL
                    GROUP BY workflow_name, workflow_type
                    ORDER BY generation_count DESC
                    LIMIT $2
                    """,
                    cutoff,
                    limit,
                )
                return [dict(r) for r in rows]

        except Exception as e:
            log_error(logger, "Failed to get top workflows", error=e)
            return []

    async def get_workflow_volume(
        self, granularity: str = "hour", days: int = 7
    ) -> list[dict[str, Any]]:
        """Workflow generation volume over time."""
        trunc = "hour" if granularity == "hour" else "day"
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT
                        date_trunc('{trunc}', timestamp) AS bucket,
                        COUNT(*) AS workflow_count,
                        ROUND(AVG(confidence)::numeric, 3) AS avg_confidence,
                        ROUND(AVG(execution_time_ms)::numeric, 0) AS avg_latency_ms
                    FROM workflow_analytics
                    WHERE timestamp >= $1
                    GROUP BY bucket
                    ORDER BY bucket DESC
                    """,
                    cutoff,
                )
                return [
                    {
                        "bucket": r["bucket"].isoformat() if r["bucket"] else None,
                        "workflow_count": r["workflow_count"],
                        "avg_confidence": float(r["avg_confidence"])
                        if r["avg_confidence"]
                        else None,
                        "avg_latency_ms": int(r["avg_latency_ms"] or 0),
                    }
                    for r in rows
                ]

        except Exception as e:
            log_error(logger, "Failed to get workflow volume", error=e)
            return []

    async def get_dashboard_summary(self, days: int = 7) -> dict[str, Any]:
        """
        Aggregated workflow analytics dashboard summary.
        Single call for the frontend dashboard.
        """
        follow_rate = await self.get_follow_rate(days=days)
        top_workflows = await self.get_top_workflows(limit=10, days=days)
        hourly_volume = await self.get_workflow_volume(granularity="hour", days=min(days, 2))
        daily_volume = await self.get_workflow_volume(granularity="day", days=days)

        return {
            "period_days": days,
            "follow_rate": follow_rate,
            "top_workflows": top_workflows,
            "workflow_volume_hourly": hourly_volume,
            "workflow_volume_daily": daily_volume,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
