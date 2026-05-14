"""
NUZANTARA RAG - Metrics Tracker for A/B Testing

Persistent storage for A/B testing metrics using PostgreSQL.
Stores per-query metrics and provides aggregation queries for analysis.

Schema:
- ab_test_metrics: Main table for metric storage
  - query_id: Unique query identifier
  - user_id: User identifier
  - experiment: Experiment name
  - variant: Variant assigned (A/B)
  - metric: Metric name (ctr, satisfaction, response_time, evidence_score)
  - value: Metric value
  - timestamp: When metric was recorded
  - metadata: JSON with additional context

Features:
- Async PostgreSQL operations
- Automatic table creation
- Metric aggregation by experiment/variant
- Time-windowed queries
- Raw data export for external analysis

Example:
    >>> tracker = MetricsTracker()
    >>> await tracker.initialize()
    >>> await tracker.record_metric(
    ...     experiment="hybrid_vs_dense",
    ...     variant="hybrid",
    ...     metric="ctr",
    ...     value=1.0,
    ...     user_id="user123",
    ...     query_id="query456"
    ... )
    >>> aggregates = await tracker.get_experiment_aggregates(
    ...     experiment="hybrid_vs_dense",
    ...     variants=["dense_only", "hybrid"]
    ... )
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class QueryMetric:
    """Single metric record for a query.

    Attributes:
        query_id: Unique query identifier
        user_id: User identifier
        experiment: Experiment name
        variant: Variant assigned
        metric: Metric name
        value: Metric value
        timestamp: When recorded
        metadata: Additional context
    """

    query_id: str
    user_id: str
    experiment: str
    variant: str
    metric: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "query_id": self.query_id,
            "user_id": self.user_id,
            "experiment": self.experiment,
            "variant": self.variant,
            "metric": self.metric,
            "value": self.value,
            "timestamp": self.timestamp,
            "metadata": json.dumps(self.metadata) if self.metadata else None,
        }


class MetricsTracker:
    """
    Metrics tracker for A/B testing with PostgreSQL storage.

    Manages persistent storage of query-level metrics for A/B test analysis.
    Provides aggregation functions for computing experiment statistics.

    Attributes:
        pool: asyncpg connection pool
        _initialized: Whether tables have been created

    Example:
        >>> tracker = MetricsTracker()
        >>> await tracker.initialize()
        >>>
        >>> # Record a metric
        >>> await tracker.record_metric(
        ...     experiment="hybrid_vs_dense",
        ...     variant="hybrid",
        ...     metric="ctr",
        ...     value=1.0,
        ...     user_id="user123",
        ...     query_id="query456"
        ... )
        >>>
        >>> # Get aggregates
        >>> results = await tracker.get_experiment_aggregates(
        ...     experiment="hybrid_vs_dense",
        ...     variants=["dense_only", "hybrid"]
        ... )
    """

    def __init__(self, pool: asyncpg.Pool | None = None) -> None:
        """
        Initialize MetricsTracker.

        Args:
            pool: Optional existing database pool
        """
        self.pool = pool
        self._initialized = False

    async def _get_pool(self) -> asyncpg.Pool | None:
        """Get or create database connection pool."""
        if self.pool is not None:
            return self.pool

        try:
            self.pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=5,
                command_timeout=30,
            )
            return self.pool
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            return None

    async def initialize(self) -> bool:
        """
        Initialize database tables.

        Creates the ab_test_metrics table if it doesn't exist.

        Returns:
            True if initialization successful
        """
        pool = await self._get_pool()
        if pool is None:
            logger.warning("Database pool not available, metrics will not be persisted")
            return False

        try:
            async with pool.acquire() as conn:
                # Main metrics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS ab_test_metrics (
                        id SERIAL PRIMARY KEY,
                        query_id VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        experiment VARCHAR(100) NOT NULL,
                        variant VARCHAR(50) NOT NULL,
                        metric VARCHAR(50) NOT NULL,
                        value FLOAT NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        metadata JSONB DEFAULT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)

                # Indexes for efficient querying
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ab_metrics_experiment_variant
                    ON ab_test_metrics(experiment, variant)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ab_metrics_query_id
                    ON ab_test_metrics(query_id)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ab_metrics_timestamp
                    ON ab_test_metrics(timestamp)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ab_metrics_user_experiment
                    ON ab_test_metrics(user_id, experiment)
                """)

                # Summary table for faster dashboard queries
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS ab_test_summaries (
                        id SERIAL PRIMARY KEY,
                        experiment VARCHAR(100) NOT NULL,
                        variant VARCHAR(50) NOT NULL,
                        metric VARCHAR(50) NOT NULL,
                        count INTEGER DEFAULT 0,
                        sum_values FLOAT DEFAULT 0,
                        sum_squares FLOAT DEFAULT 0,
                        min_value FLOAT DEFAULT 0,
                        max_value FLOAT DEFAULT 0,
                        last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        UNIQUE(experiment, variant, metric)
                    )
                """)

                self._initialized = True
                logger.info("A/B testing metrics tables initialized")
                return True

        except Exception as e:
            logger.error(f"Failed to initialize metrics tables: {e}")
            return False

    async def record_metric(
        self,
        experiment: str,
        variant: str,
        metric: str,
        value: float,
        user_id: str | None = None,
        query_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Record a single metric.

        Args:
            experiment: Experiment name
            variant: Variant identifier
            metric: Metric name (ctr, satisfaction, response_time, evidence_score)
            value: Metric value
            user_id: Optional user identifier
            query_id: Optional query identifier (generated if not provided)
            metadata: Optional additional context

        Returns:
            True if metric was recorded successfully

        Example:
            >>> await tracker.record_metric(
            ...     experiment="hybrid_vs_dense",
            ...     variant="hybrid",
            ...     metric="ctr",
            ...     value=1.0,
            ...     user_id="user123",
            ...     query_id="query456",
            ...     metadata={"source": "web", "query_length": 25}
            ... )
        """
        pool = await self._get_pool()
        if pool is None:
            logger.debug(f"Metric not persisted (no DB): {experiment}/{variant}/{metric}={value}")
            return False

        if not self._initialized:
            await self.initialize()

        query_id = query_id or str(uuid.uuid4())
        user_id = user_id or "anonymous"

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO ab_test_metrics
                    (query_id, user_id, experiment, variant, metric, value, timestamp, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7)
                    """,
                    query_id,
                    user_id,
                    experiment,
                    variant,
                    metric,
                    value,
                    # Self-created asyncpg pool (_get_pool) has NO jsonb codec
                    # registered — json.dumps() is REQUIRED here, unlike the
                    # app/runtime codec-on pool where it double-encodes.
                    json.dumps(metadata) if metadata else None,
                )

                # Update summary table
                await conn.execute(
                    """
                    INSERT INTO ab_test_summaries
                    (experiment, variant, metric, count, sum_values, sum_squares, min_value, max_value, last_updated)
                    VALUES ($1, $2, $3, 1, $4, $5, $4, $4, NOW())
                    ON CONFLICT (experiment, variant, metric)
                    DO UPDATE SET
                        count = ab_test_summaries.count + 1,
                        sum_values = ab_test_summaries.sum_values + $4,
                        sum_squares = ab_test_summaries.sum_squares + $5,
                        min_value = LEAST(ab_test_summaries.min_value, $4),
                        max_value = GREATEST(ab_test_summaries.max_value, $4),
                        last_updated = NOW()
                    """,
                    experiment,
                    variant,
                    metric,
                    value,
                    value * value,
                )

                return True

        except Exception as e:
            logger.error(f"Failed to record metric: {e}")
            return False

    async def record_query_metrics(
        self,
        query_id: str,
        user_id: str,
        experiment: str,
        variant: str,
        metrics: dict[str, float],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Record multiple metrics for a single query.

        Efficiently records all metrics for a query in a single transaction.

        Args:
            query_id: Unique query identifier
            user_id: User identifier
            experiment: Experiment name
            variant: Variant identifier
            metrics: Dictionary of metric_name -> value
            metadata: Optional additional context

        Returns:
            True if all metrics were recorded successfully

        Example:
            >>> await tracker.record_query_metrics(
            ...     query_id="query456",
            ...     user_id="user123",
            ...     experiment="hybrid_vs_dense",
            ...     variant="hybrid",
            ...     metrics={
            ...         "response_time": 1.25,
            ...         "evidence_score": 0.85,
            ...         "ctr": 1.0,
            ...     }
            ... )
        """
        pool = await self._get_pool()
        if pool is None:
            logger.debug(f"Metrics not persisted (no DB): {experiment}/{variant}")
            return False

        if not self._initialized:
            await self.initialize()

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for metric_name, value in metrics.items():
                        await conn.execute(
                            """
                            INSERT INTO ab_test_metrics
                            (query_id, user_id, experiment, variant, metric, value, timestamp, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7)
                            """,
                            query_id,
                            user_id,
                            experiment,
                            variant,
                            metric_name,
                            value,
                            # Self-created asyncpg pool (_get_pool) has NO jsonb
                            # codec — json.dumps() is REQUIRED here.
                            json.dumps(metadata) if metadata else None,
                        )

                        # Update summary
                        await conn.execute(
                            """
                            INSERT INTO ab_test_summaries
                            (experiment, variant, metric, count, sum_values, sum_squares, min_value, max_value, last_updated)
                            VALUES ($1, $2, $3, 1, $4, $5, $4, $4, NOW())
                            ON CONFLICT (experiment, variant, metric)
                            DO UPDATE SET
                                count = ab_test_summaries.count + 1,
                                sum_values = ab_test_summaries.sum_values + $4,
                                sum_squares = ab_test_summaries.sum_squares + $5,
                                min_value = LEAST(ab_test_summaries.min_value, $4),
                                max_value = GREATEST(ab_test_summaries.max_value, $4),
                                last_updated = NOW()
                            """,
                            experiment,
                            variant,
                            metric_name,
                            value,
                            value * value,
                        )

                return True

        except Exception as e:
            logger.error(f"Failed to record query metrics: {e}")
            return False

    async def get_experiment_aggregates(
        self,
        experiment: str,
        variants: list[str] | None = None,
        since: datetime | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Get aggregated metrics for an experiment.

        Returns statistics for each variant including count, mean, std dev,
        and min/max values for all tracked metrics.

        Args:
            experiment: Experiment name
            variants: Optional list of variants to include (all if None)
            since: Optional start time for metrics

        Returns:
            Dictionary mapping variant -> metrics -> statistics

        Example:
            >>> results = await tracker.get_experiment_aggregates(
            ...     experiment="hybrid_vs_dense",
            ...     variants=["dense_only", "hybrid"]
            ... )
            >>> print(results["hybrid"]["metrics"]["ctr"]["mean"])
        """
        pool = await self._get_pool()
        if pool is None:
            return {}

        if not self._initialized:
            await self.initialize()

        since = since or datetime.now(timezone.utc) - timedelta(days=30)

        try:
            async with pool.acquire() as conn:
                # Build query
                variant_filter = ""
                params = [experiment, since]

                if variants:
                    variant_placeholders = ", ".join(f"${i + 3}" for i in range(len(variants)))
                    variant_filter = f"AND variant IN ({variant_placeholders})"
                    params.extend(variants)

                # Get aggregates from summary table
                rows = await conn.fetch(
                    f"""
                    SELECT
                        variant,
                        metric,
                        count,
                        sum_values,
                        sum_squares,
                        min_value,
                        max_value
                    FROM ab_test_summaries
                    WHERE experiment = $1
                    AND last_updated >= $2
                    {variant_filter}
                    ORDER BY variant, metric
                    """,
                    *params,
                )

                # Organize results
                results: dict[str, dict[str, Any]] = {}

                for row in rows:
                    variant = row["variant"]
                    metric = row["metric"]
                    count = row["count"]
                    sum_values = row["sum_values"]
                    sum_squares = row["sum_squares"]

                    if variant not in results:
                        results[variant] = {
                            "variant": variant,
                            "count": 0,
                            "metrics": {},
                            "raw": {},
                        }

                    mean = sum_values / count if count > 0 else 0
                    variance = (sum_squares / count) - (mean * mean) if count > 0 else 0
                    std_dev = variance**0.5 if variance > 0 else 0

                    results[variant]["metrics"][metric] = {
                        "count": count,
                        "mean": round(mean, 4),
                        "std_dev": round(std_dev, 4),
                        "min": round(row["min_value"], 4),
                        "max": round(row["max_value"], 4),
                        "sum": round(sum_values, 4),
                    }
                    results[variant]["count"] += count

                # Get raw data for significance testing
                for variant in variants or []:
                    if variant not in results:
                        results[variant] = {
                            "variant": variant,
                            "count": 0,
                            "metrics": {},
                            "raw": {},
                        }

                    metric_rows = await conn.fetch(
                        """
                        SELECT metric, value
                        FROM ab_test_metrics
                        WHERE experiment = $1
                        AND variant = $2
                        AND timestamp >= $3
                        ORDER BY metric, timestamp
                        """,
                        experiment,
                        variant,
                        since,
                    )

                    raw_data: dict[str, list[float]] = {}
                    for row in metric_rows:
                        m = row["metric"]
                        if m not in raw_data:
                            raw_data[m] = []
                        raw_data[m].append(float(row["value"]))

                    results[variant]["raw"] = raw_data

                return results

        except Exception as e:
            logger.error(f"Failed to get experiment aggregates: {e}")
            return {}

    async def get_metrics_by_query(
        self,
        query_id: str,
    ) -> list[QueryMetric]:
        """
        Get all metrics for a specific query.

        Args:
            query_id: Query identifier

        Returns:
            List of QueryMetric records
        """
        pool = await self._get_pool()
        if pool is None:
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        query_id,
                        user_id,
                        experiment,
                        variant,
                        metric,
                        value,
                        timestamp,
                        metadata
                    FROM ab_test_metrics
                    WHERE query_id = $1
                    ORDER BY timestamp
                    """,
                    query_id,
                )

                return [
                    QueryMetric(
                        query_id=row["query_id"],
                        user_id=row["user_id"],
                        experiment=row["experiment"],
                        variant=row["variant"],
                        metric=row["metric"],
                        value=float(row["value"]),
                        timestamp=row["timestamp"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get metrics by query: {e}")
            return []

    async def get_user_exposure(
        self,
        user_id: str,
        experiment: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get experiment exposure history for a user.

        Args:
            user_id: User identifier
            experiment: Optional experiment filter

        Returns:
            List of exposure records
        """
        pool = await self._get_pool()
        if pool is None:
            return []

        try:
            async with pool.acquire() as conn:
                if experiment:
                    rows = await conn.fetch(
                        """
                        SELECT DISTINCT
                            experiment,
                            variant,
                            MIN(timestamp) as first_exposure,
                            COUNT(*) as query_count
                        FROM ab_test_metrics
                        WHERE user_id = $1
                        AND experiment = $2
                        GROUP BY experiment, variant
                        ORDER BY first_exposure DESC
                        """,
                        user_id,
                        experiment,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT DISTINCT
                            experiment,
                            variant,
                            MIN(timestamp) as first_exposure,
                            COUNT(*) as query_count
                        FROM ab_test_metrics
                        WHERE user_id = $1
                        GROUP BY experiment, variant
                        ORDER BY first_exposure DESC
                        """,
                        user_id,
                    )

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get user exposure: {e}")
            return []

    async def export_experiment_data(
        self,
        experiment: str,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Export raw experiment data for external analysis.

        Args:
            experiment: Experiment name
            since: Optional start time filter

        Returns:
            List of raw metric records
        """
        pool = await self._get_pool()
        if pool is None:
            return []

        since = since or datetime.now(timezone.utc) - timedelta(days=30)

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        query_id,
                        user_id,
                        experiment,
                        variant,
                        metric,
                        value,
                        timestamp,
                        metadata
                    FROM ab_test_metrics
                    WHERE experiment = $1
                    AND timestamp >= $2
                    ORDER BY timestamp DESC
                    """,
                    experiment,
                    since,
                )

                return [
                    {
                        "query_id": row["query_id"],
                        "user_id": row["user_id"],
                        "experiment": row["experiment"],
                        "variant": row["variant"],
                        "metric": row["metric"],
                        "value": float(row["value"]),
                        "timestamp": row["timestamp"].isoformat(),
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to export experiment data: {e}")
            return []

    async def get_active_experiments(
        self,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """
        Get experiments with activity in the last N hours.

        Args:
            hours: Time window in hours

        Returns:
            List of active experiment summaries
        """
        pool = await self._get_pool()
        if pool is None:
            return []

        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        experiment,
                        variant,
                        COUNT(*) as query_count,
                        COUNT(DISTINCT user_id) as unique_users,
                        MIN(timestamp) as first_query,
                        MAX(timestamp) as last_query
                    FROM ab_test_metrics
                    WHERE timestamp >= $1
                    GROUP BY experiment, variant
                    ORDER BY query_count DESC
                    """,
                    since,
                )

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get active experiments: {e}")
            return []

    async def cleanup_old_metrics(self, days: int = 90) -> int:
        """
        Clean up metrics older than specified days.

        Args:
            days: Age threshold for deletion

        Returns:
            Number of records deleted
        """
        pool = await self._get_pool()
        if pool is None:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM ab_test_metrics
                    WHERE timestamp < $1
                    """,
                    cutoff,
                )

                # Parse result (e.g., "DELETE 150")
                deleted = int(result.split()[1]) if len(result.split()) > 1 else 0

                logger.info(f"Cleaned up {deleted} old metrics (older than {days} days)")
                return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")
            return 0
