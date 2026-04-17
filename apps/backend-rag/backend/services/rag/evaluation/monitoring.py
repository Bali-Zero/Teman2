"""
Retrieval Quality Monitoring Service for RAG System

Provides comprehensive metrics tracking for retrieval quality including:
- Retrieval scores (average, percentiles)
- Abstain rate tracking
- Evidence score distribution
- Query latency measurements
- Cache hit rates
- Hybrid search usage statistics
- Reranker effectiveness

Metrics are exposed via Prometheus and aggregated for dashboard consumption.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

from backend.services.common.background import spawn

logger = logging.getLogger(__name__)


# ============================================================================
# Prometheus Metrics Definitions
# ============================================================================


def safe_register_metric(metric_class: type, name: str, *args: Any, **kwargs: Any) -> Any:
    """Safely register a Prometheus metric, returning existing if already registered."""
    try:
        return metric_class(name, *args, **kwargs)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


# Retrieval Quality Metrics
retrieval_scores_avg = safe_register_metric(
    Gauge,
    "rag_retrieval_scores_avg",
    "Average retrieval score over time (0.0-1.0)",
    ["time_window"],  # 1h, 24h, 7d, 30d
)

retrieval_scores_p95 = safe_register_metric(
    Gauge, "rag_retrieval_scores_p95", "95th percentile retrieval score (0.0-1.0)", ["time_window"],
)

retrieval_scores_p99 = safe_register_metric(
    Gauge, "rag_retrieval_scores_p99", "99th percentile retrieval score (0.0-1.0)", ["time_window"],
)

abstain_rate = safe_register_metric(
    Gauge,
    "rag_abstain_rate_percent",
    "Percentage of queries that resulted in ABSTAIN",
    ["domain"],  # visa, tax, legal, general
)

abstain_total = safe_register_metric(
    Counter,
    "rag_abstain_total",
    "Total number of ABSTAIN responses",
    ["domain", "reason"],  # reason: low_confidence, no_results, safety
)

query_total = safe_register_metric(
    Counter,
    "rag_query_total",
    "Total number of RAG queries",
    ["search_type", "use_reranker"],  # search_type: hybrid, dense
)

evidence_score_distribution = safe_register_metric(
    Histogram,
    "rag_evidence_score_distribution",
    "Distribution of evidence scores",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

query_latency_ms = safe_register_metric(
    Histogram,
    "rag_query_latency_milliseconds",
    "Query response time in milliseconds",
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)

cache_hit_rate = safe_register_metric(
    Gauge,
    "rag_cache_hit_rate_percent",
    "Redis cache hit rate percentage",
)

cache_hits_total = safe_register_metric(Counter, "rag_cache_hits_total", "Total cache hits")

cache_misses_total = safe_register_metric(Counter, "rag_cache_misses_total", "Total cache misses")

hybrid_search_usage = safe_register_metric(
    Gauge,
    "rag_hybrid_search_usage_percent",
    "Percentage of queries using hybrid search (vs dense only)",
)

reranker_usage = safe_register_metric(
    Gauge, "rag_reranker_usage_percent", "Percentage of queries using reranking",
)

reranker_improvement = safe_register_metric(
    Histogram,
    "rag_reranker_improvement",
    "Score improvement from reranking (after_score - before_score)",
    buckets=[-0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5, 1.0],
)

low_score_queries_total = safe_register_metric(
    Counter,
    "rag_low_score_queries_total",
    "Total queries with score below threshold",
    ["threshold"],
)

alert_threshold_breaches = safe_register_metric(
    Counter,
    "rag_alert_threshold_breaches_total",
    "Number of times alert thresholds were breached",
    ["metric_name", "severity"],  # severity: warning, critical
)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class QueryMetricsRecord:
    """Individual query metrics record."""

    timestamp: datetime
    query_hash: str
    query_text: str
    retrieval_score: float
    latency_ms: float
    search_type: str  # hybrid, dense
    use_reranker: bool
    cache_hit: bool
    result_count: int
    abstained: bool = False
    abstain_reason: str | None = None


@dataclass
class AlertThresholds:
    """Alert threshold configuration."""

    min_score: float = 0.3
    max_abstain_rate: float = 0.2
    max_latency_ms: float = 5000.0
    min_cache_hit_rate: float = 0.5

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "min_score": self.min_score,
            "max_abstain_rate": self.max_abstain_rate,
            "max_latency_ms": self.max_latency_ms,
            "min_cache_hit_rate": self.min_cache_hit_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> AlertThresholds:
        """Create from dictionary."""
        return cls(
            min_score=data.get("min_score", 0.3),
            max_abstain_rate=data.get("max_abstain_rate", 0.2),
            max_latency_ms=data.get("max_latency_ms", 5000.0),
            min_cache_hit_rate=data.get("min_cache_hit_rate", 0.5),
        )


# ============================================================================
# Retrieval Quality Monitor
# ============================================================================


class RetrievalQualityMonitor:
    """
    Monitors and tracks retrieval quality metrics for the RAG system.

    This class provides:
    - Real-time metric recording
    - Historical data aggregation
    - Alert threshold management
    - Dashboard data generation

    Usage:
        monitor = RetrievalQualityMonitor()
        monitor.record_query_metrics(query, results, latency_ms)
        dashboard_data = monitor.get_dashboard_data("24h")
    """

    # Maximum number of records to keep in memory (for 30 days at ~1000 queries/day)
    MAX_RECORDS = 50000

    # Flush to PostgreSQL every N records or every FLUSH_INTERVAL
    FLUSH_BATCH_SIZE = 100
    FLUSH_INTERVAL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        """Initialize the retrieval quality monitor."""
        self._query_records: deque[QueryMetricsRecord] = deque(maxlen=self.MAX_RECORDS)
        self._alert_thresholds = AlertThresholds()
        self._lock = None  # For thread safety if needed
        self._initialized_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        self._db_pool = None  # Set via set_db_pool() after startup
        self._unflushed_count = 0
        self._last_flush_time = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        self._flush_task: Any = None

        logger.info("RetrievalQualityMonitor initialized")

    def set_db_pool(self, db_pool: Any) -> None:
        """Inject the database pool for persistent storage.

        Call this after app startup to enable PostgreSQL persistence.
        Without it, metrics are in-memory only (lost on restart).
        """
        self._db_pool = db_pool
        if db_pool:
            logger.info("RetrievalQualityMonitor: PostgreSQL persistence enabled")

    async def flush_to_db(self) -> int:
        """Flush accumulated daily stats to PostgreSQL.

        Writes an aggregated summary row per day to `rag_daily_stats`.
        This is idempotent — uses UPSERT to avoid duplicates.

        Returns:
            Number of days flushed
        """
        if not self._db_pool:
            return 0

        try:
            # Group records by day
            daily_data: dict[str, list[QueryMetricsRecord]] = {}
            for record in self._query_records:
                day_key = record.timestamp.strftime("%Y-%m-%d")
                if day_key not in daily_data:
                    daily_data[day_key] = []
                daily_data[day_key].append(record)

            if not daily_data:
                return 0

            async with self._db_pool.acquire() as conn:
                # Ensure table exists
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS rag_daily_stats (
                        stat_date DATE PRIMARY KEY,
                        total_queries INTEGER NOT NULL DEFAULT 0,
                        avg_score FLOAT NOT NULL DEFAULT 0,
                        p95_score FLOAT NOT NULL DEFAULT 0,
                        avg_latency_ms FLOAT NOT NULL DEFAULT 0,
                        p95_latency_ms FLOAT NOT NULL DEFAULT 0,
                        abstain_count INTEGER NOT NULL DEFAULT 0,
                        abstain_rate FLOAT NOT NULL DEFAULT 0,
                        cache_hit_count INTEGER NOT NULL DEFAULT 0,
                        cache_hit_rate FLOAT NOT NULL DEFAULT 0,
                        hybrid_count INTEGER NOT NULL DEFAULT 0,
                        reranker_count INTEGER NOT NULL DEFAULT 0,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)

                flushed = 0
                for day_key, records in daily_data.items():
                    scores = [r.retrieval_score for r in records if not r.abstained]
                    latencies = [r.latency_ms for r in records if r.latency_ms > 0]
                    abstains = [r for r in records if r.abstained]
                    cache_hits = [r for r in records if r.cache_hit]
                    hybrid = [r for r in records if r.search_type == "hybrid"]
                    reranker = [r for r in records if r.use_reranker]

                    total = len(records)
                    avg_score = sum(scores) / len(scores) if scores else 0.0
                    p95_score = self._percentile(scores, 0.95) if scores else 0.0
                    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
                    p95_latency = self._percentile(latencies, 0.95) if latencies else 0.0

                    await conn.execute(
                        """
                        INSERT INTO rag_daily_stats
                            (stat_date, total_queries, avg_score, p95_score,
                             avg_latency_ms, p95_latency_ms, abstain_count, abstain_rate,
                             cache_hit_count, cache_hit_rate, hybrid_count, reranker_count, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
                        ON CONFLICT (stat_date) DO UPDATE SET
                            total_queries = EXCLUDED.total_queries,
                            avg_score = EXCLUDED.avg_score,
                            p95_score = EXCLUDED.p95_score,
                            avg_latency_ms = EXCLUDED.avg_latency_ms,
                            p95_latency_ms = EXCLUDED.p95_latency_ms,
                            abstain_count = EXCLUDED.abstain_count,
                            abstain_rate = EXCLUDED.abstain_rate,
                            cache_hit_count = EXCLUDED.cache_hit_count,
                            cache_hit_rate = EXCLUDED.cache_hit_rate,
                            hybrid_count = EXCLUDED.hybrid_count,
                            reranker_count = EXCLUDED.reranker_count,
                            updated_at = NOW()
                        """,
                        datetime.strptime(day_key, "%Y-%m-%d").date(),
                        total,
                        round(avg_score, 4),
                        round(p95_score, 4),
                        round(avg_latency, 2),
                        round(p95_latency, 2),
                        len(abstains),
                        round(len(abstains) / total * 100, 2) if total > 0 else 0.0,
                        len(cache_hits),
                        round(len(cache_hits) / total * 100, 2) if total > 0 else 0.0,
                        len(hybrid),
                        len(reranker),
                    )
                    flushed += 1

            self._unflushed_count = 0
            self._last_flush_time = datetime.now(tz=timezone.utc).replace(tzinfo=None)
            logger.info(f"RetrievalQualityMonitor: flushed {flushed} day(s) to PostgreSQL")
            return flushed

        except Exception as e:
            logger.error(f"Failed to flush RAG stats to PostgreSQL: {e}")
            return 0

    async def load_historical_stats(self, days: int = 30) -> list[dict[str, Any]]:
        """Load historical daily stats from PostgreSQL.

        Args:
            days: Number of days to load

        Returns:
            List of daily stat dicts
        """
        if not self._db_pool:
            return []

        try:
            async with self._db_pool.acquire() as conn:
                # Check if table exists
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rag_daily_stats')",
                )
                if not exists:
                    return []

                rows = await conn.fetch(
                    """
                    SELECT * FROM rag_daily_stats
                    WHERE stat_date >= CURRENT_DATE - $1
                    ORDER BY stat_date DESC
                    """,
                    days,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to load historical RAG stats: {e}")
            return []

    async def _maybe_flush(self) -> None:
        """Auto-flush if batch size or time interval exceeded."""
        if not self._db_pool:
            return

        elapsed = (
            datetime.now(tz=timezone.utc).replace(tzinfo=None) - self._last_flush_time
        ).total_seconds()
        if self._unflushed_count >= self.FLUSH_BATCH_SIZE or elapsed >= self.FLUSH_INTERVAL_SECONDS:
            await self.flush_to_db()

    def record_query_metrics(
        self,
        query: str,
        results: list[dict[str, Any]],
        latency_ms: float,
        search_type: str = "dense",
        use_reranker: bool = False,
        cache_hit: bool = False,
        retrieval_score: float | None = None,
    ) -> None:
        """
        Record metrics for a single query.

        Args:
            query: The query text
            results: List of retrieval results with scores
            latency_ms: Query latency in milliseconds
            search_type: Type of search used (hybrid, dense)
            use_reranker: Whether reranker was used
            cache_hit: Whether result was served from cache
            retrieval_score: Optional pre-calculated score
        """
        try:
            # Calculate query hash for deduplication
            query_hash = str(hash(query) % 10000000)

            # Calculate average score from results if not provided
            if retrieval_score is None and results:
                scores = [
                    r.get("score", 0.0) for r in results if isinstance(r.get("score"), (int, float))
                ]
                retrieval_score = sum(scores) / len(scores) if scores else 0.0
            elif retrieval_score is None:
                retrieval_score = 0.0

            record = QueryMetricsRecord(
                timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
                query_hash=query_hash,
                query_text=query[:200],  # Truncate for memory efficiency
                retrieval_score=retrieval_score,
                latency_ms=latency_ms,
                search_type=search_type,
                use_reranker=use_reranker,
                cache_hit=cache_hit,
                result_count=len(results),
            )

            self._query_records.append(record)
            self._unflushed_count += 1

            # Update Prometheus metrics
            self._update_prometheus_metrics(record)

            # Schedule async flush if thresholds exceeded
            try:
                asyncio.get_running_loop()
                spawn(self._maybe_flush(), name="rag_eval_maybe_flush")
            except RuntimeError:
                logger.debug("no running event loop — flush deferred to next async call")

            # Check for low score
            if retrieval_score < self._alert_thresholds.min_score:
                low_score_queries_total.labels(
                    threshold=str(self._alert_thresholds.min_score),
                ).inc()

            logger.debug(
                f"Recorded query metrics: score={retrieval_score:.3f}, "
                f"latency={latency_ms:.1f}ms, search={search_type}",
            )

        except Exception as e:
            logger.error(f"Failed to record query metrics: {e}")

    def record_retrieval_score(self, score: float) -> None:
        """
        Record a standalone retrieval score.

        Args:
            score: Retrieval score between 0.0 and 1.0
        """
        try:
            # Clamp score to valid range
            score = max(0.0, min(1.0, score))

            # Update histogram
            evidence_score_distribution.observe(score)

            # Check threshold breach
            if score < self._alert_thresholds.min_score:
                alert_threshold_breaches.labels(
                    metric_name="retrieval_score", severity="warning",
                ).inc()
                logger.warning(f"Low retrieval score detected: {score:.3f}")

        except Exception as e:
            logger.error(f"Failed to record retrieval score: {e}")

    def record_abstain(self, domain: str = "general", reason: str = "low_confidence") -> None:
        """
        Record an ABSTAIN response.

        Args:
            domain: Domain that abstained (visa, tax, legal, general)
            reason: Reason for abstaining (low_confidence, no_results, safety)
        """
        try:
            abstain_total.labels(domain=domain, reason=reason).inc()

            # Create a record for this abstain
            record = QueryMetricsRecord(
                timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
                query_hash="abstain",
                query_text="",
                retrieval_score=0.0,
                latency_ms=0.0,
                search_type="none",
                use_reranker=False,
                cache_hit=False,
                result_count=0,
                abstained=True,
                abstain_reason=reason,
            )
            self._query_records.append(record)
            self._unflushed_count += 1

            # Schedule async flush if thresholds exceeded
            try:
                asyncio.get_running_loop()
                spawn(self._maybe_flush(), name="rag_eval_abstain_flush")
            except RuntimeError:
                logger.debug("no running event loop — abstain flush deferred")

            logger.info(f"Recorded ABSTAIN: domain={domain}, reason={reason}")

        except Exception as e:
            logger.error(f"Failed to record abstain: {e}")

    def record_cache_access(self, hit: bool) -> None:
        """
        Record a cache access event.

        Args:
            hit: True if cache hit, False if miss
        """
        try:
            if hit:
                cache_hits_total.inc()
            else:
                cache_misses_total.inc()
        except Exception as e:
            logger.error(f"Failed to record cache access: {e}")

    def record_reranker_effectiveness(
        self, before_scores: list[float], after_scores: list[float],
    ) -> None:
        """
        Record reranker effectiveness metrics.

        Args:
            before_scores: Scores before reranking
            after_scores: Scores after reranking
        """
        try:
            if not before_scores or not after_scores:
                return

            before_avg = sum(before_scores) / len(before_scores)
            after_avg = sum(after_scores) / len(after_scores)
            improvement = after_avg - before_avg

            reranker_improvement.observe(improvement)

            logger.debug(f"Reranker improvement: {improvement:.3f}")

        except Exception as e:
            logger.error(f"Failed to record reranker effectiveness: {e}")

    def set_alert_thresholds(self, thresholds: AlertThresholds) -> None:
        """
        Update alert threshold configuration.

        Args:
            thresholds: New threshold configuration
        """
        self._alert_thresholds = thresholds
        logger.info(f"Updated alert thresholds: {thresholds.to_dict()}")

    def get_alert_thresholds(self) -> AlertThresholds:
        """Get current alert thresholds."""
        return self._alert_thresholds

    async def get_dashboard_data(self, time_range: str) -> dict[str, Any]:
        """
        Get aggregated dashboard data for the specified time range.

        Args:
            time_range: Time range (1h, 24h, 7d, 30d)

        Returns:
            Dictionary with aggregated metrics
        """
        try:
            # Parse time range
            delta = self._parse_time_range(time_range)
            cutoff_time = datetime.now(tz=timezone.utc).replace(tzinfo=None) - delta

            # Filter records
            filtered_records = [r for r in self._query_records if r.timestamp >= cutoff_time]

            if not filtered_records:
                return self._empty_dashboard_data(time_range)

            # Calculate metrics
            scores = [r.retrieval_score for r in filtered_records if not r.abstained]
            latencies = [r.latency_ms for r in filtered_records if r.latency_ms > 0]
            abstains = [r for r in filtered_records if r.abstained]
            cache_hits = [r for r in filtered_records if r.cache_hit]
            hybrid_queries = [r for r in filtered_records if r.search_type == "hybrid"]
            reranker_queries = [r for r in filtered_records if r.use_reranker]

            # Calculate percentiles
            avg_score = sum(scores) / len(scores) if scores else 0.0
            p95_score = self._percentile(scores, 0.95) if scores else 0.0
            p99_score = self._percentile(scores, 0.99) if scores else 0.0

            # Latency percentiles
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            p95_latency = self._percentile(latencies, 0.95) if latencies else 0.0
            p99_latency = self._percentile(latencies, 0.99) if latencies else 0.0

            # Rates
            total_queries = len(filtered_records)
            abstain_rate_val = len(abstains) / total_queries if total_queries > 0 else 0.0
            cache_hit_rate_val = len(cache_hits) / total_queries if total_queries > 0 else 0.0
            hybrid_usage_val = len(hybrid_queries) / total_queries if total_queries > 0 else 0.0
            reranker_usage_val = len(reranker_queries) / total_queries if total_queries > 0 else 0.0

            # Score distribution
            score_distribution = self._calculate_score_distribution(scores)

            # Low score queries (for alert table)
            low_score_queries = [
                {
                    "query_hash": r.query_hash,
                    "query_preview": r.query_text[:100] + "..."
                    if len(r.query_text) > 100
                    else r.query_text,
                    "score": r.retrieval_score,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in filtered_records
                if not r.abstained and r.retrieval_score < self._alert_thresholds.min_score
            ]
            low_score_queries.sort(key=lambda x: x["score"])
            low_score_queries = low_score_queries[:10]  # Top 10 lowest

            # Update Prometheus gauges
            retrieval_scores_avg.labels(time_window=time_range).set(avg_score)
            retrieval_scores_p95.labels(time_window=time_range).set(p95_score)
            retrieval_scores_p99.labels(time_window=time_range).set(p99_score)
            abstain_rate.labels(domain="all").set(abstain_rate_val * 100)
            cache_hit_rate.set(cache_hit_rate_val * 100)
            hybrid_search_usage.set(hybrid_usage_val * 100)
            reranker_usage.set(reranker_usage_val * 100)

            return {
                "time_range": time_range,
                "total_queries": total_queries,
                "timestamp": datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat(),
                "retrieval_quality": {
                    "average_score": round(avg_score, 4),
                    "p95_score": round(p95_score, 4),
                    "p99_score": round(p99_score, 4),
                    "score_distribution": score_distribution,
                },
                "performance": {
                    "average_latency_ms": round(avg_latency, 2),
                    "p95_latency_ms": round(p95_latency, 2),
                    "p99_latency_ms": round(p99_latency, 2),
                },
                "usage_patterns": {
                    "abstain_rate": round(abstain_rate_val * 100, 2),
                    "cache_hit_rate": round(cache_hit_rate_val * 100, 2),
                    "hybrid_search_usage": round(hybrid_usage_val * 100, 2),
                    "reranker_usage": round(reranker_usage_val * 100, 2),
                },
                "alerts": {
                    "low_score_queries": low_score_queries,
                    "threshold_breaches": self._get_threshold_breaches(
                        avg_score, abstain_rate_val, avg_latency, cache_hit_rate_val,
                    ),
                },
                "alert_thresholds": self._alert_thresholds.to_dict(),
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return self._empty_dashboard_data(time_range)

    async def get_scores_trend(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Get daily score trends for the specified number of days.

        Args:
            days: Number of days to retrieve (1-30)

        Returns:
            List of daily score aggregates
        """
        try:
            days = max(1, min(30, days))
            cutoff_time = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(days=days)

            # Group by day
            daily_data: dict[str, list[QueryMetricsRecord]] = {}
            for record in self._query_records:
                if record.timestamp >= cutoff_time and not record.abstained:
                    day_key = record.timestamp.strftime("%Y-%m-%d")
                    if day_key not in daily_data:
                        daily_data[day_key] = []
                    daily_data[day_key].append(record)

            # Calculate daily aggregates
            trend = []
            for day_key in sorted(daily_data.keys()):
                day_records = daily_data[day_key]
                scores = [r.retrieval_score for r in day_records]

                trend.append(
                    {
                        "date": day_key,
                        "query_count": len(day_records),
                        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
                        "p95_score": round(self._percentile(scores, 0.95), 4) if scores else 0.0,
                        "min_score": round(min(scores), 4) if scores else 0.0,
                        "max_score": round(max(scores), 4) if scores else 0.0,
                    },
                )

            return trend

        except Exception as e:
            logger.error(f"Failed to get scores trend: {e}")
            return []

    async def get_abstain_statistics(self, days: int = 7) -> dict[str, Any]:
        """
        Get detailed abstain statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Abstain statistics dictionary
        """
        try:
            days = max(1, min(30, days))
            cutoff_time = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(days=days)

            abstain_records = [
                r for r in self._query_records if r.timestamp >= cutoff_time and r.abstained
            ]

            total_in_period = len([r for r in self._query_records if r.timestamp >= cutoff_time])

            # Group by reason
            by_reason: dict[str, int] = {}
            for r in abstain_records:
                reason = r.abstain_reason or "unknown"
                by_reason[reason] = by_reason.get(reason, 0) + 1

            abstain_rate_val = (
                len(abstain_records) / total_in_period if total_in_period > 0 else 0.0
            )

            return {
                "period_days": days,
                "total_abstains": len(abstain_records),
                "total_queries": total_in_period,
                "abstain_rate": round(abstain_rate_val * 100, 2),
                "by_reason": by_reason,
                "daily_breakdown": self._get_daily_abstain_breakdown(abstain_records, days),
            }

        except Exception as e:
            logger.error(f"Failed to get abstain statistics: {e}")
            return {
                "period_days": days,
                "total_abstains": 0,
                "total_queries": 0,
                "abstain_rate": 0.0,
                "by_reason": {},
                "daily_breakdown": [],
            }

    async def get_latency_percentiles(self, days: int = 7) -> dict[str, Any]:
        """
        Get latency percentile statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Latency statistics dictionary
        """
        try:
            days = max(1, min(30, days))
            cutoff_time = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(days=days)

            latencies = [
                r.latency_ms
                for r in self._query_records
                if r.timestamp >= cutoff_time and r.latency_ms > 0
            ]

            if not latencies:
                return {
                    "period_days": days,
                    "total_queries": 0,
                    "percentiles": {},
                }

            latencies.sort()

            return {
                "period_days": days,
                "total_queries": len(latencies),
                "percentiles": {
                    "p50": round(self._percentile(latencies, 0.50), 2),
                    "p75": round(self._percentile(latencies, 0.75), 2),
                    "p90": round(self._percentile(latencies, 0.90), 2),
                    "p95": round(self._percentile(latencies, 0.95), 2),
                    "p99": round(self._percentile(latencies, 0.99), 2),
                    "p99_9": round(self._percentile(latencies, 0.999), 2),
                },
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
                "avg": round(sum(latencies) / len(latencies), 2),
            }

        except Exception as e:
            logger.error(f"Failed to get latency percentiles: {e}")
            return {
                "period_days": days,
                "total_queries": 0,
                "percentiles": {},
            }

    def _update_prometheus_metrics(self, record: QueryMetricsRecord) -> None:
        """Update Prometheus metrics with a new record."""
        try:
            # Query counter
            query_total.labels(
                search_type=record.search_type, use_reranker=str(record.use_reranker),
            ).inc()

            # Latency histogram
            if record.latency_ms > 0:
                query_latency_ms.observe(record.latency_ms)

            # Evidence score distribution
            if not record.abstained:
                evidence_score_distribution.observe(record.retrieval_score)

        except Exception as e:
            logger.error(f"Failed to update Prometheus metrics: {e}")

    def _parse_time_range(self, time_range: str) -> timedelta:
        """Parse time range string to timedelta."""
        mapping = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "1d": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        return mapping.get(time_range, timedelta(hours=24))

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile from sorted data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _calculate_score_distribution(self, scores: list[float]) -> dict[str, int]:
        """Calculate score distribution buckets."""
        buckets = {
            "0.0-0.1": 0,
            "0.1-0.2": 0,
            "0.2-0.3": 0,
            "0.3-0.4": 0,
            "0.4-0.5": 0,
            "0.5-0.6": 0,
            "0.6-0.7": 0,
            "0.7-0.8": 0,
            "0.8-0.9": 0,
            "0.9-1.0": 0,
        }

        for score in scores:
            bucket = min(int(score * 10), 9)
            bucket_key = f"{bucket / 10:.1f}-{(bucket + 1) / 10:.1f}"
            buckets[bucket_key] = buckets.get(bucket_key, 0) + 1

        return buckets

    def _empty_dashboard_data(self, time_range: str) -> dict[str, Any]:
        """Return empty dashboard data structure."""
        return {
            "time_range": time_range,
            "total_queries": 0,
            "timestamp": datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat(),
            "retrieval_quality": {
                "average_score": 0.0,
                "p95_score": 0.0,
                "p99_score": 0.0,
                "score_distribution": {},
            },
            "performance": {
                "average_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
            },
            "usage_patterns": {
                "abstain_rate": 0.0,
                "cache_hit_rate": 0.0,
                "hybrid_search_usage": 0.0,
                "reranker_usage": 0.0,
            },
            "alerts": {
                "low_score_queries": [],
                "threshold_breaches": [],
            },
            "alert_thresholds": self._alert_thresholds.to_dict(),
        }

    def _get_threshold_breaches(
        self,
        avg_score: float,
        abstain_rate_val: float,
        avg_latency: float,
        cache_hit_rate_val: float,
    ) -> list[dict[str, Any]]:
        """Check for threshold breaches."""
        breaches = []

        if avg_score < self._alert_thresholds.min_score:
            breaches.append(
                {
                    "metric": "retrieval_score",
                    "severity": "warning",
                    "message": f"Average score {avg_score:.3f} below threshold {self._alert_thresholds.min_score}",
                    "current_value": avg_score,
                    "threshold": self._alert_thresholds.min_score,
                },
            )

        if abstain_rate_val > self._alert_thresholds.max_abstain_rate:
            breaches.append(
                {
                    "metric": "abstain_rate",
                    "severity": "critical",
                    "message": f"Abstain rate {abstain_rate_val * 100:.1f}% exceeds threshold {self._alert_thresholds.max_abstain_rate * 100:.1f}%",
                    "current_value": abstain_rate_val,
                    "threshold": self._alert_thresholds.max_abstain_rate,
                },
            )

        if avg_latency > self._alert_thresholds.max_latency_ms:
            breaches.append(
                {
                    "metric": "latency",
                    "severity": "warning",
                    "message": f"Average latency {avg_latency:.0f}ms exceeds threshold {self._alert_thresholds.max_latency_ms:.0f}ms",
                    "current_value": avg_latency,
                    "threshold": self._alert_thresholds.max_latency_ms,
                },
            )

        if cache_hit_rate_val < self._alert_thresholds.min_cache_hit_rate:
            breaches.append(
                {
                    "metric": "cache_hit_rate",
                    "severity": "warning",
                    "message": f"Cache hit rate {cache_hit_rate_val * 100:.1f}% below threshold {self._alert_thresholds.min_cache_hit_rate * 100:.1f}%",
                    "current_value": cache_hit_rate_val,
                    "threshold": self._alert_thresholds.min_cache_hit_rate,
                },
            )

        return breaches

    def _get_daily_abstain_breakdown(
        self, abstain_records: list[QueryMetricsRecord], days: int,
    ) -> list[dict[str, Any]]:
        """Get daily abstain breakdown."""
        cutoff_time = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(days=days)

        # Group by day
        daily: dict[str, dict[str, Any]] = {}
        for record in abstain_records:
            if record.timestamp >= cutoff_time:
                day_key = record.timestamp.strftime("%Y-%m-%d")
                if day_key not in daily:
                    daily[day_key] = {"date": day_key, "count": 0, "reasons": {}}
                daily[day_key]["count"] += 1
                reason = record.abstain_reason or "unknown"
                daily[day_key]["reasons"][reason] = daily[day_key]["reasons"].get(reason, 0) + 1

        return list(daily.values())


# ============================================================================
# Global Monitor Instance
# ============================================================================

# Global instance for use across the application
retrieval_quality_monitor = RetrievalQualityMonitor()


async def get_retrieval_quality_monitor() -> RetrievalQualityMonitor:
    """Dependency injection helper for FastAPI."""
    return retrieval_quality_monitor
