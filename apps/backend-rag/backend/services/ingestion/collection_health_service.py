"""
Collection Health Monitor - Phase 3

Monitors the health and quality of all Qdrant collections:
- Last update timestamps
- Document counts
- Query hit rates
- Average confidence scores
- Staleness detection
- Actionable recommendations

Provides admin dashboard with collection health metrics.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels"""

    EXCELLENT = "excellent"  # All metrics green
    GOOD = "good"  # Minor issues
    WARNING = "warning"  # Needs attention
    CRITICAL = "critical"  # Urgent action required


class StalenessSeverity(str, Enum):
    """Staleness severity levels"""

    FRESH = "fresh"  # Updated recently (<1 month)
    AGING = "aging"  # 1-3 months old
    STALE = "stale"  # 3-6 months old
    VERY_STALE = "very_stale"  # >6 months old


@dataclass
class CollectionMetrics:
    """Metrics for a single collection"""

    collection_name: str
    document_count: int
    last_updated: str | None  # ISO timestamp
    query_count: int  # Total queries to this collection
    hit_count: int  # Queries that returned results
    avg_confidence: float  # Average confidence score
    avg_results_per_query: float
    health_status: HealthStatus
    staleness: StalenessSeverity
    issues: list[str]  # List of detected issues
    recommendations: list[str]  # Suggested actions


class CollectionHealthService:
    """
    Monitors and reports on Qdrant collection health.

    Tracks:
    - Collection usage patterns
    - Data freshness
    - Query performance
    - Quality metrics

    Provides:
    - Health scores per collection
    - Staleness alerts
    - Actionable recommendations
    - Admin dashboard data
    """

    def __init__(self, search_service=None, qdrant_client=None):
        """
        Initialize health monitor.

        Args:
            search_service: Optional SearchService instance
            qdrant_client: Optional QdrantClient instance (for test compatibility)
            search_service: Optional SearchService for collection access
        """
        self.search_service = search_service

        # Per-collection metrics tracking
        self.metrics = {
            # Initialize 14 collections
            "bali_zero_pricing": self._init_metrics("bali_zero_pricing"),
            "visa_oracle": self._init_metrics("visa_oracle"),
            "kbli_eye": self._init_metrics("kbli_eye"),
            "tax_genius": self._init_metrics("tax_genius"),
            "legal_architect": self._init_metrics("legal_architect"),
            "kb_indonesian": self._init_metrics("kb_indonesian"),
            "kbli_comprehensive": self._init_metrics("kbli_comprehensive"),
            "zantara_books": self._init_metrics("zantara_books"),
            "cultural_insights": self._init_metrics("cultural_insights"),
            "tax_updates": self._init_metrics("tax_updates"),
            "tax_knowledge": self._init_metrics("tax_knowledge"),
            "property_listings": self._init_metrics("property_listings"),
            "property_knowledge": self._init_metrics("property_knowledge"),
            "legal_updates": self._init_metrics("legal_updates"),
        }

        # Staleness thresholds (in days)
        self.staleness_thresholds = {
            StalenessSeverity.FRESH: 30,  # <1 month
            StalenessSeverity.AGING: 90,  # 1-3 months
            StalenessSeverity.STALE: 180,  # 3-6 months
            StalenessSeverity.VERY_STALE: 365,  # >6 months = critical
        }

        logger.info("✅ CollectionHealthService initialized")
        logger.info(f"   Monitoring {len(self.metrics)} collections")

    def _init_metrics(self, _collection_name: str) -> dict:
        """Initialize empty metrics for a collection"""
        return {
            "query_count": 0,
            "hit_count": 0,
            "total_results": 0,
            "confidence_scores": [],
            "last_queried": None,
            "last_updated": None,  # Should be set by ingestion service
        }

    def record_query(
        self, collection_name: str, had_results: bool, result_count: int = 0, avg_score: float = 0.0
    ):
        """
        Record a query to a collection for health tracking.

        Args:
            collection_name: Collection that was queried
            had_results: Whether query returned results
            result_count: Number of results returned
            avg_score: Average confidence score of results
        """
        if collection_name not in self.metrics:
            logger.warning(f"Unknown collection: {collection_name}")
            return

        metrics = self.metrics[collection_name]
        metrics["query_count"] += 1
        metrics["last_queried"] = datetime.now().isoformat()

        if had_results:
            metrics["hit_count"] += 1
            metrics["total_results"] += result_count
            if avg_score > 0:
                metrics["confidence_scores"].append(avg_score)

    def record_queries_batch(self, health_metrics: list[dict[str, Any]]):
        """
        Record multiple query metrics in a single batch operation.

        This is a performance optimization to avoid N+1 writes in search loops.

        Args:
            health_metrics: List of metric dicts with keys:
                - collection_name: Collection that was queried
                - had_results: Whether query returned results
                - result_count: Number of results returned (optional)
                - avg_score: Average confidence score (optional)
        """
        if not health_metrics:
            return

        timestamp = datetime.now().isoformat()

        for metric in health_metrics:
            collection_name = metric.get("collection_name")
            if not collection_name or collection_name not in self.metrics:
                logger.warning(f"Unknown collection in batch: {collection_name}")
                continue

            metrics = self.metrics[collection_name]
            metrics["query_count"] += 1
            metrics["last_queried"] = timestamp

            if metric.get("had_results", False):
                metrics["hit_count"] += 1
                metrics["total_results"] += metric.get("result_count", 0)
                avg_score = metric.get("avg_score", 0.0)
                if avg_score > 0:
                    metrics["confidence_scores"].append(avg_score)

        logger.debug(f"Recorded {len(health_metrics)} health metrics in batch")

    def calculate_staleness(self, last_updated: str | None) -> StalenessSeverity:
        """
        Calculate staleness severity based on last update timestamp.

        Args:
            last_updated: ISO timestamp of last update

        Returns:
            StalenessSeverity enum
        """
        if not last_updated:
            return StalenessSeverity.VERY_STALE

        try:
            last_update_date = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            days_old = (datetime.now() - last_update_date).days

            if days_old < self.staleness_thresholds[StalenessSeverity.FRESH]:
                return StalenessSeverity.FRESH
            elif days_old < self.staleness_thresholds[StalenessSeverity.AGING]:
                return StalenessSeverity.AGING
            elif days_old < self.staleness_thresholds[StalenessSeverity.STALE]:
                return StalenessSeverity.STALE
            else:
                return StalenessSeverity.VERY_STALE

        except Exception as e:
            logger.error(f"Error calculating staleness: {e}")
            return StalenessSeverity.VERY_STALE

    def calculate_health_status(
        self, hit_rate: float, avg_confidence: float, staleness: StalenessSeverity, query_count: int
    ) -> HealthStatus:
        """
        Calculate overall health status for a collection.

        Scoring:
        - Excellent: hit_rate >80%, confidence >0.7, fresh, queries >10
        - Good: hit_rate >60%, confidence >0.5, aging, queries >5
        - Warning: hit_rate >40%, confidence >0.3, stale
        - Critical: Below warning thresholds or very_stale

        Args:
            hit_rate: Percentage of queries with results
            avg_confidence: Average confidence score
            staleness: Staleness severity
            query_count: Total query count

        Returns:
            HealthStatus enum
        """
        # Critical conditions
        if staleness == StalenessSeverity.VERY_STALE:
            return HealthStatus.CRITICAL
        if query_count > 10 and hit_rate < 0.4:
            return HealthStatus.CRITICAL
        if query_count > 10 and avg_confidence < 0.3:
            return HealthStatus.CRITICAL

        # Warning conditions
        if staleness == StalenessSeverity.STALE:
            return HealthStatus.WARNING
        if query_count > 5 and hit_rate < 0.6:
            return HealthStatus.WARNING
        if query_count > 5 and avg_confidence < 0.5:
            return HealthStatus.WARNING

        # Excellent conditions
        if (
            staleness == StalenessSeverity.FRESH
            and hit_rate > 0.8
            and avg_confidence > 0.7
            and query_count > 10
        ):
            return HealthStatus.EXCELLENT

        # Default to good
        return HealthStatus.GOOD

    def generate_recommendations(
        self,
        collection_name: str,
        _health_status: HealthStatus,
        staleness: StalenessSeverity,
        hit_rate: float,
        avg_confidence: float,
        query_count: int,
    ) -> list[str]:
        """
        Generate actionable recommendations based on metrics.

        Args:
            collection_name: Collection name
            health_status: Current health status
            staleness: Staleness severity
            hit_rate: Query hit rate
            avg_confidence: Average confidence
            query_count: Total queries

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Staleness recommendations
        if staleness == StalenessSeverity.VERY_STALE:
            recommendations.append(f"🚨 URGENT: Re-ingest {collection_name} - data >6 months old")
        elif staleness == StalenessSeverity.STALE:
            recommendations.append(
                f"⚠️ WARNING: Consider updating {collection_name} - data 3-6 months old"
            )
        elif staleness == StalenessSeverity.AGING:
            recommendations.append(
                f"ℹ️ INFO: Schedule update for {collection_name} - data 1-3 months old"
            )

        # Hit rate recommendations
        if query_count > 10:
            if hit_rate < 0.4:
                recommendations.append(
                    f"🚨 Low hit rate ({hit_rate * 100:.0f}%) - review collection content relevance"
                )
            elif hit_rate < 0.6:
                recommendations.append(
                    f"⚠️ Medium hit rate ({hit_rate * 100:.0f}%) - consider expanding collection content"
                )

        # Confidence recommendations
        if query_count > 10:
            if avg_confidence < 0.3:
                recommendations.append(
                    f"🚨 Low confidence ({avg_confidence:.2f}) - review embedding quality"
                )
            elif avg_confidence < 0.5:
                recommendations.append(
                    f"⚠️ Medium confidence ({avg_confidence:.2f}) - consider improving content specificity"
                )

        # Usage recommendations
        if query_count == 0:
            recommendations.append("ℹ️ No queries yet - collection unused or routing issue")
        elif query_count < 5:
            recommendations.append(f"ℹ️ Low usage ({query_count} queries) - verify routing keywords")

        # Specific collection recommendations
        if "updates" in collection_name and staleness != StalenessSeverity.FRESH:
            recommendations.append("🚨 Updates collection should be fresh - enable auto-ingestion")

        if not recommendations:
            recommendations.append("✅ Collection health is good - no action needed")

        return recommendations

    def get_collection_health(
        self,
        collection_name: str,
        document_count: int | None = None,
        last_updated: str | None = None,
    ) -> CollectionMetrics:
        """
        Get health metrics for a single collection.

        Args:
            collection_name: Collection to check
            document_count: Optional document count (from Qdrant)
            last_updated: Optional last update timestamp

        Returns:
            CollectionMetrics with full health analysis
        """
        if collection_name not in self.metrics:
            # Return default metrics for unknown collection
            return CollectionMetrics(
                collection_name=collection_name,
                document_count=0,
                last_updated=None,
                query_count=0,
                hit_count=0,
                avg_confidence=0.0,
                avg_results_per_query=0.0,
                health_status=HealthStatus.CRITICAL,
                staleness=StalenessSeverity.VERY_STALE,
                issues=["Collection not found"],
                recommendations=["Check collection exists in Qdrant"],
            )

        metrics = self.metrics[collection_name]

        # Calculate derived metrics
        query_count = metrics["query_count"]
        hit_count = metrics["hit_count"]
        hit_rate = hit_count / query_count if query_count > 0 else 0.0

        confidence_scores = metrics["confidence_scores"]
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        )

        avg_results = metrics["total_results"] / hit_count if hit_count > 0 else 0.0

        # Use provided last_updated or fall back to tracked
        last_update_timestamp = last_updated or metrics.get("last_updated")

        # Calculate staleness
        staleness = self.calculate_staleness(last_update_timestamp)

        # Calculate health status
        health_status = self.calculate_health_status(
            hit_rate, avg_confidence, staleness, query_count
        )

        # Detect issues
        issues = []
        if staleness in [StalenessSeverity.STALE, StalenessSeverity.VERY_STALE]:
            issues.append(f"Stale data ({staleness.value})")
        if query_count > 10 and hit_rate < 0.5:
            issues.append(f"Low hit rate ({hit_rate * 100:.0f}%)")
        if query_count > 10 and avg_confidence < 0.5:
            issues.append(f"Low confidence ({avg_confidence:.2f})")
        if document_count is not None and document_count == 0:
            issues.append("Empty collection")

        # Generate recommendations
        recommendations = self.generate_recommendations(
            collection_name, health_status, staleness, hit_rate, avg_confidence, query_count
        )

        return CollectionMetrics(
            collection_name=collection_name,
            document_count=document_count or 0,
            last_updated=last_update_timestamp,
            query_count=query_count,
            hit_count=hit_count,
            avg_confidence=round(avg_confidence, 3),
            avg_results_per_query=round(avg_results, 1),
            health_status=health_status,
            staleness=staleness,
            issues=issues,
            recommendations=recommendations,
        )

    def get_all_collection_health(self, include_empty: bool = True) -> dict[str, CollectionMetrics]:
        """
        Get health metrics for all collections.

        Args:
            include_empty: Include collections with no queries

        Returns:
            Dict mapping collection_name -> CollectionMetrics
        """
        all_health = {}

        for collection_name in self.metrics:
            health = self.get_collection_health(collection_name)

            if include_empty or health.query_count > 0:
                all_health[collection_name] = health

        return all_health

    def get_dashboard_summary(self) -> dict[str, Any]:
        """
        Get summary for admin dashboard.

        Returns:
            Summary dict with overall health statistics
        """
        all_health = self.get_all_collection_health()

        # Count by status
        status_counts = {
            HealthStatus.EXCELLENT: 0,
            HealthStatus.GOOD: 0,
            HealthStatus.WARNING: 0,
            HealthStatus.CRITICAL: 0,
        }

        staleness_counts = {
            StalenessSeverity.FRESH: 0,
            StalenessSeverity.AGING: 0,
            StalenessSeverity.STALE: 0,
            StalenessSeverity.VERY_STALE: 0,
        }

        total_queries = 0
        total_hits = 0
        collections_with_issues = []

        for coll_name, health in all_health.items():
            status_counts[health.health_status] += 1
            staleness_counts[health.staleness] += 1
            total_queries += health.query_count
            total_hits += health.hit_count

            if health.issues:
                collections_with_issues.append(
                    {
                        "collection": coll_name,
                        "status": health.health_status.value,
                        "issues": health.issues,
                    }
                )

        overall_hit_rate = total_hits / total_queries if total_queries > 0 else 0.0

        return {
            "timestamp": datetime.now().isoformat(),
            "total_collections": len(all_health),
            "health_distribution": {status.value: count for status, count in status_counts.items()},
            "staleness_distribution": {
                severity.value: count for severity, count in staleness_counts.items()
            },
            "total_queries": total_queries,
            "overall_hit_rate": f"{overall_hit_rate * 100:.1f}%",
            "collections_with_issues": len(collections_with_issues),
            "critical_collections": [
                c["collection"]
                for c in collections_with_issues
                if c["status"] == HealthStatus.CRITICAL.value
            ],
            "needs_attention": collections_with_issues[:5],  # Top 5
        }

    def get_health_report(self, format: str = "text") -> str:
        """
        Generate human-readable health report.

        Args:
            format: "text" or "markdown"

        Returns:
            Formatted health report string
        """
        all_health = self.get_all_collection_health()
        summary = self.get_dashboard_summary()

        if format == "markdown":
            return self._generate_markdown_report(all_health, summary)
        else:
            return self._generate_text_report(all_health, summary)

    def _generate_text_report(self, all_health: dict[str, CollectionMetrics], summary: dict) -> str:
        """Generate plain text health report"""
        lines = []
        lines.append("=" * 80)
        lines.append("COLLECTION HEALTH REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {summary['timestamp']}")
        lines.append("")

        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Collections: {summary['total_collections']}")
        lines.append(f"Total Queries: {summary['total_queries']}")
        lines.append(f"Overall Hit Rate: {summary['overall_hit_rate']}")
        lines.append("")

        lines.append("Health Distribution:")
        for status, count in summary["health_distribution"].items():
            lines.append(f"  {status.upper()}: {count}")
        lines.append("")

        lines.append("Staleness Distribution:")
        for severity, count in summary["staleness_distribution"].items():
            lines.append(f"  {severity.upper()}: {count}")
        lines.append("")

        if summary["critical_collections"]:
            lines.append("⚠️ CRITICAL COLLECTIONS:")
            for coll in summary["critical_collections"]:
                lines.append(f"  - {coll}")
            lines.append("")

        lines.append("COLLECTION DETAILS")
        lines.append("-" * 80)

        # Sort by health status (critical first)
        sorted_health = sorted(
            all_health.items(),
            key=lambda x: (
                [
                    HealthStatus.CRITICAL,
                    HealthStatus.WARNING,
                    HealthStatus.GOOD,
                    HealthStatus.EXCELLENT,
                ].index(x[1].health_status),
                x[0],
            ),
        )

        for coll_name, health in sorted_health:
            status_emoji = {
                HealthStatus.EXCELLENT: "✅",
                HealthStatus.GOOD: "👍",
                HealthStatus.WARNING: "⚠️",
                HealthStatus.CRITICAL: "🚨",
            }[health.health_status]

            lines.append(f"\n{status_emoji} {coll_name.upper()}")
            lines.append(f"  Status: {health.health_status.value}")
            lines.append(f"  Staleness: {health.staleness.value}")
            lines.append(
                f"  Queries: {health.query_count} (hit rate: {(health.hit_count / health.query_count * 100) if health.query_count > 0 else 0:.0f}%)"
            )
            lines.append(f"  Avg Confidence: {health.avg_confidence:.2f}")

            if health.issues:
                lines.append(f"  Issues: {', '.join(health.issues)}")

            if health.recommendations:
                lines.append("  Recommendations:")
                for rec in health.recommendations:
                    lines.append(f"    • {rec}")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def _generate_markdown_report(
        self, all_health: dict[str, CollectionMetrics], summary: dict
    ) -> str:
        """Generate markdown health report"""
        # Implementation similar to text but with markdown formatting
        return self._generate_text_report(all_health, summary)  # Simplified for now
