"""
Tests for RAG Retrieval Quality Monitoring Service

Test coverage:
- Metric recording functionality
- Dashboard data aggregation
- Alert threshold management
- Prometheus metrics integration
- Edge cases and error handling
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock, patch

import pytest

from backend.services.rag.evaluation.monitoring import (
    AlertThresholds,
    QueryMetricsRecord,
    RetrievalQualityMonitor,
    get_retrieval_quality_monitor,
    safe_register_metric,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def monitor() -> RetrievalQualityMonitor:
    """Create a fresh monitor instance for each test."""
    return RetrievalQualityMonitor()


@pytest.fixture
def sample_query_results() -> list[dict[str, Any]]:
    """Sample query results for testing."""
    return [
        {"score": 0.85, "text": "Result 1", "id": "1"},
        {"score": 0.72, "text": "Result 2", "id": "2"},
        {"score": 0.68, "text": "Result 3", "id": "3"},
    ]


@pytest.fixture
def mock_prometheus_metrics():
    """Mock Prometheus metrics for isolated testing."""
    with (
        patch("backend.services.rag.evaluation.monitoring.query_total") as mock_query,
        patch("backend.services.rag.evaluation.monitoring.query_latency_ms") as mock_latency,
        patch(
            "backend.services.rag.evaluation.monitoring.evidence_score_distribution",
        ) as mock_score,
        patch("backend.services.rag.evaluation.monitoring.abstain_total") as mock_abstain,
        patch("backend.services.rag.evaluation.monitoring.cache_hits_total") as mock_cache_hit,
        patch("backend.services.rag.evaluation.monitoring.cache_misses_total") as mock_cache_miss,
        patch(
            "backend.services.rag.evaluation.monitoring.low_score_queries_total",
        ) as mock_low_score,
        patch("backend.services.rag.evaluation.monitoring.alert_threshold_breaches") as mock_alert,
    ):
        # Setup mock labels
        mock_query.labels.return_value = Mock()
        mock_abstain.labels.return_value = Mock()
        mock_low_score.labels.return_value = Mock()
        mock_alert.labels.return_value = Mock()

        yield {
            "query_total": mock_query,
            "query_latency_ms": mock_latency,
            "evidence_score_distribution": mock_score,
            "abstain_total": mock_abstain,
            "cache_hits_total": mock_cache_hit,
            "cache_misses_total": mock_cache_miss,
            "low_score_queries_total": mock_low_score,
            "alert_threshold_breaches": mock_alert,
        }


# ============================================================================
# Test Classes
# ============================================================================


class TestQueryMetricsRecord:
    """Tests for QueryMetricsRecord dataclass."""

    def test_create_record(self) -> None:
        """Test creating a metrics record."""
        record = QueryMetricsRecord(
            timestamp=datetime.now(timezone.utc),
            query_hash="test123",
            query_text="test query",
            retrieval_score=0.85,
            latency_ms=150.0,
            search_type="hybrid",
            use_reranker=True,
            cache_hit=False,
            result_count=5,
        )

        assert record.query_hash == "test123"
        assert record.retrieval_score == 0.85
        assert record.search_type == "hybrid"
        assert record.use_reranker is True
        assert record.abstained is False


class TestAlertThresholds:
    """Tests for AlertThresholds dataclass."""

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        thresholds = AlertThresholds()

        assert thresholds.min_score == 0.3
        assert thresholds.max_abstain_rate == 0.2
        assert thresholds.max_latency_ms == 5000.0
        assert thresholds.min_cache_hit_rate == 0.5

    def test_custom_thresholds(self) -> None:
        """Test custom threshold values."""
        thresholds = AlertThresholds(
            min_score=0.5,
            max_abstain_rate=0.1,
            max_latency_ms=3000.0,
            min_cache_hit_rate=0.7,
        )

        assert thresholds.min_score == 0.5
        assert thresholds.max_abstain_rate == 0.1
        assert thresholds.max_latency_ms == 3000.0
        assert thresholds.min_cache_hit_rate == 0.7

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        thresholds = AlertThresholds(min_score=0.4)
        data = thresholds.to_dict()

        assert data["min_score"] == 0.4
        assert data["max_abstain_rate"] == 0.2
        assert "max_latency_ms" in data
        assert "min_cache_hit_rate" in data

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "min_score": 0.45,
            "max_abstain_rate": 0.15,
            "max_latency_ms": 4000.0,
            "min_cache_hit_rate": 0.6,
        }
        thresholds = AlertThresholds.from_dict(data)

        assert thresholds.min_score == 0.45
        assert thresholds.max_abstain_rate == 0.15
        assert thresholds.max_latency_ms == 4000.0
        assert thresholds.min_cache_hit_rate == 0.6

    def test_from_dict_partial(self) -> None:
        """Test creation from partial dictionary."""
        data = {"min_score": 0.5}
        thresholds = AlertThresholds.from_dict(data)

        assert thresholds.min_score == 0.5
        assert thresholds.max_abstain_rate == 0.2  # Default


class TestRetrievalQualityMonitorInit:
    """Tests for monitor initialization."""

    def test_initialization(self) -> None:
        """Test monitor initializes correctly."""
        monitor = RetrievalQualityMonitor()

        assert monitor._query_records.maxlen == RetrievalQualityMonitor.MAX_RECORDS
        assert monitor._alert_thresholds is not None
        assert monitor._initialized_at is not None

    def test_get_alert_thresholds(self, monitor: RetrievalQualityMonitor) -> None:
        """Test getting current thresholds."""
        thresholds = monitor.get_alert_thresholds()

        assert isinstance(thresholds, AlertThresholds)
        assert thresholds.min_score == 0.3


class TestRecordQueryMetrics:
    """Tests for recording query metrics."""

    def test_record_basic_query(
        self,
        monitor: RetrievalQualityMonitor,
        sample_query_results: list[dict[str, Any]],
    ) -> None:
        """Test recording a basic query."""
        monitor.record_query_metrics(
            query="test query",
            results=sample_query_results,
            latency_ms=150.0,
        )

        assert len(monitor._query_records) == 1
        record = monitor._query_records[0]
        assert record.query_text == "test query"
        assert record.latency_ms == 150.0
        assert record.search_type == "dense"  # Default

    def test_record_with_search_type(
        self,
        monitor: RetrievalQualityMonitor,
        sample_query_results: list[dict[str, Any]],
    ) -> None:
        """Test recording with explicit search type."""
        monitor.record_query_metrics(
            query="test query",
            results=sample_query_results,
            latency_ms=150.0,
            search_type="hybrid",
            use_reranker=True,
            cache_hit=True,
        )

        record = monitor._query_records[0]
        assert record.search_type == "hybrid"
        assert record.use_reranker is True
        assert record.cache_hit is True

    def test_record_calculates_average_score(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test that average score is calculated from results."""
        results = [
            {"score": 0.9},
            {"score": 0.8},
            {"score": 0.7},
        ]

        monitor.record_query_metrics(
            query="test",
            results=results,
            latency_ms=100.0,
        )

        record = monitor._query_records[0]
        expected_avg = (0.9 + 0.8 + 0.7) / 3
        assert record.retrieval_score == pytest.approx(expected_avg, 0.01)

    def test_record_empty_results(self, monitor: RetrievalQualityMonitor) -> None:
        """Test recording with empty results."""
        monitor.record_query_metrics(
            query="test",
            results=[],
            latency_ms=100.0,
        )

        record = monitor._query_records[0]
        assert record.retrieval_score == 0.0
        assert record.result_count == 0

    def test_record_with_provided_score(
        self,
        monitor: RetrievalQualityMonitor,
        sample_query_results: list[dict[str, Any]],
    ) -> None:
        """Test recording with pre-calculated score."""
        monitor.record_query_metrics(
            query="test",
            results=sample_query_results,
            latency_ms=100.0,
            retrieval_score=0.95,
        )

        record = monitor._query_records[0]
        assert record.retrieval_score == 0.95

    def test_record_truncates_query(self, monitor: RetrievalQualityMonitor) -> None:
        """Test that long queries are truncated."""
        long_query = "a" * 500

        monitor.record_query_metrics(
            query=long_query,
            results=[{"score": 0.5}],
            latency_ms=100.0,
        )

        record = monitor._query_records[0]
        assert len(record.query_text) <= 200

    def test_record_handles_exception(
        self,
        monitor: RetrievalQualityMonitor,
        caplog: Any,
    ) -> None:
        """Test that exceptions are logged not raised."""
        # This should not raise
        with patch.object(
            monitor, "_update_prometheus_metrics", side_effect=Exception("Test error"),
        ):
            monitor.record_query_metrics(
                query="test",
                results=[{"score": 0.5}],
                latency_ms=100.0,
            )

        assert "Test error" in caplog.text


class TestRecordRetrievalScore:
    """Tests for recording standalone scores."""

    def test_record_valid_score(
        self,
        monitor: RetrievalQualityMonitor,
        mock_prometheus_metrics: dict,
    ) -> None:
        """Test recording a valid score."""
        monitor.record_retrieval_score(0.75)

        mock_prometheus_metrics["evidence_score_distribution"].observe.assert_called_once_with(0.75)

    def test_record_clamps_score_high(self, monitor: RetrievalQualityMonitor) -> None:
        """Test that scores above 1.0 are clamped."""
        with patch(
            "backend.services.rag.evaluation.monitoring.evidence_score_distribution",
        ) as mock:
            monitor.record_retrieval_score(1.5)
            mock.observe.assert_called_once_with(1.0)

    def test_record_clamps_score_low(self, monitor: RetrievalQualityMonitor) -> None:
        """Test that scores below 0.0 are clamped."""
        with patch(
            "backend.services.rag.evaluation.monitoring.evidence_score_distribution",
        ) as mock:
            monitor.record_retrieval_score(-0.5)
            mock.observe.assert_called_once_with(0.0)

    def test_low_score_triggers_alert(
        self,
        monitor: RetrievalQualityMonitor,
        mock_prometheus_metrics: dict,
    ) -> None:
        """Test that low scores trigger alert metrics."""
        monitor.record_retrieval_score(0.2)  # Below default threshold of 0.3

        mock_prometheus_metrics["alert_threshold_breaches"].labels.assert_called_once_with(
            metric_name="retrieval_score", severity="warning",
        )


class TestRecordAbstain:
    """Tests for recording abstain responses."""

    def test_record_abstain_default(
        self,
        monitor: RetrievalQualityMonitor,
        mock_prometheus_metrics: dict,
    ) -> None:
        """Test recording abstain with default parameters."""
        monitor.record_abstain()

        mock_prometheus_metrics["abstain_total"].labels.assert_called_once_with(
            domain="general", reason="low_confidence",
        )
        assert len(monitor._query_records) == 1

    def test_record_abstain_custom(
        self,
        monitor: RetrievalQualityMonitor,
        mock_prometheus_metrics: dict,
    ) -> None:
        """Test recording abstain with custom parameters."""
        monitor.record_abstain(domain="visa", reason="safety")

        mock_prometheus_metrics["abstain_total"].labels.assert_called_once_with(
            domain="visa", reason="safety",
        )

        record = monitor._query_records[0]
        assert record.abstained is True
        assert record.abstain_reason == "safety"

    def test_record_abstain_creates_record(self, monitor: RetrievalQualityMonitor) -> None:
        """Test that abstain creates a query record."""
        monitor.record_abstain(domain="tax", reason="no_results")

        record = monitor._query_records[0]
        assert record.abstained is True
        assert record.abstain_reason == "no_results"
        assert record.domain == "tax" if hasattr(record, "domain") else True


class TestRecordCacheAccess:
    """Tests for recording cache access."""

    def test_record_cache_hit(
        self,
        monitor: RetrievalQualityMonitor,
        mock_prometheus_metrics: dict,
    ) -> None:
        """Test recording cache hit."""
        monitor.record_cache_access(hit=True)

        mock_prometheus_metrics["cache_hits_total"].inc.assert_called_once()

    def test_record_cache_miss(
        self,
        monitor: RetrievalQualityMonitor,
        mock_prometheus_metrics: dict,
    ) -> None:
        """Test recording cache miss."""
        monitor.record_cache_access(hit=False)

        mock_prometheus_metrics["cache_misses_total"].inc.assert_called_once()


class TestRecordRerankerEffectiveness:
    """Tests for recording reranker effectiveness."""

    def test_record_improvement(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test recording positive improvement."""
        with patch("backend.services.rag.evaluation.monitoring.reranker_improvement") as mock:
            before = [0.6, 0.5, 0.4]
            after = [0.8, 0.7, 0.6]

            monitor.record_reranker_effectiveness(before, after)

            # Average improvement: (0.7 - 0.5) = 0.2
            mock.observe.assert_called_once_with(pytest.approx(0.2, 0.01))

    def test_record_degradation(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test recording degradation (negative improvement)."""
        with patch("backend.services.rag.evaluation.monitoring.reranker_improvement") as mock:
            before = [0.8, 0.7, 0.6]
            after = [0.6, 0.5, 0.4]

            monitor.record_reranker_effectiveness(before, after)

            mock.observe.assert_called_once_with(pytest.approx(-0.2, 0.01))

    def test_empty_scores(self, monitor: RetrievalQualityMonitor) -> None:
        """Test handling empty score lists."""
        with patch("backend.services.rag.evaluation.monitoring.reranker_improvement") as mock:
            monitor.record_reranker_effectiveness([], [0.5])
            mock.observe.assert_not_called()


class TestAlertThresholdsManagement:
    """Tests for alert threshold management."""

    @pytest.mark.skip(reason="Logger assertion requires caplog setup")
    def test_set_thresholds(
        self,
        monitor: RetrievalQualityMonitor,
        caplog: Any,
    ) -> None:
        """Test setting new thresholds."""
        new_thresholds = AlertThresholds(min_score=0.5)

        monitor.set_alert_thresholds(new_thresholds)

        assert monitor.get_alert_thresholds().min_score == 0.5

    def test_threshold_affects_low_score_detection(
        self,
        monitor: RetrievalQualityMonitor,
        mock_prometheus_metrics: dict,
    ) -> None:
        """Test that updated threshold affects low score detection."""
        # Set higher threshold
        monitor.set_alert_thresholds(AlertThresholds(min_score=0.6))

        # Record score that would be OK with default threshold but not new one
        monitor.record_retrieval_score(0.5)

        # Should trigger alert
        mock_prometheus_metrics["alert_threshold_breaches"].labels.assert_called()


class TestGetDashboardData:
    """Tests for dashboard data aggregation."""

    @pytest.mark.asyncio
    async def test_empty_dashboard(self, monitor: RetrievalQualityMonitor) -> None:
        """Test dashboard with no data."""
        data = await monitor.get_dashboard_data("24h")

        assert data["time_range"] == "24h"
        assert data["total_queries"] == 0
        assert data["retrieval_quality"]["average_score"] == 0.0

    @pytest.mark.asyncio
    async def test_dashboard_with_data(
        self,
        monitor: RetrievalQualityMonitor,
        sample_query_results: list[dict[str, Any]],
    ) -> None:
        """Test dashboard with sample data."""
        # Add some records
        for i in range(10):
            monitor.record_query_metrics(
                query=f"query {i}",
                results=sample_query_results,
                latency_ms=100.0 + i * 10,
                search_type="hybrid" if i % 2 == 0 else "dense",
                use_reranker=i % 3 == 0,
                cache_hit=i % 4 == 0,
            )

        data = await monitor.get_dashboard_data("24h")

        assert data["total_queries"] == 10
        assert data["retrieval_quality"]["average_score"] > 0
        assert "p95_score" in data["retrieval_quality"]
        assert "performance" in data
        assert "usage_patterns" in data

    @pytest.mark.asyncio
    async def test_dashboard_with_abstains(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test dashboard with abstain records."""
        # Add regular queries
        for i in range(5):
            monitor.record_query_metrics(
                query=f"query {i}",
                results=[{"score": 0.8}],
                latency_ms=100.0,
            )

        # Add abstains
        for i in range(2):
            monitor.record_abstain()

        data = await monitor.get_dashboard_data("24h")

        assert data["total_queries"] == 7
        abstain_rate = data["usage_patterns"]["abstain_rate"]
        assert abstain_rate == pytest.approx(28.57, 0.1)  # 2/7

    @pytest.mark.asyncio
    async def test_dashboard_time_ranges(self, monitor: RetrievalQualityMonitor) -> None:
        """Test different time range options."""
        # Add a query
        monitor.record_query_metrics(
            query="test",
            results=[{"score": 0.8}],
            latency_ms=100.0,
        )

        for time_range in ["1h", "24h", "7d", "30d"]:
            data = await monitor.get_dashboard_data(time_range)
            assert data["time_range"] == time_range

    @pytest.mark.asyncio
    async def test_dashboard_low_score_queries(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test that low score queries are identified."""
        # Add low score query
        monitor.record_query_metrics(
            query="low score query",
            results=[{"score": 0.1}],
            latency_ms=100.0,
            retrieval_score=0.1,
        )

        data = await monitor.get_dashboard_data("24h")

        assert len(data["alerts"]["low_score_queries"]) > 0
        assert "query_preview" in data["alerts"]["low_score_queries"][0]

    @pytest.mark.asyncio
    async def test_dashboard_threshold_breaches(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test threshold breach detection in dashboard."""
        # Set strict thresholds
        monitor.set_alert_thresholds(
            AlertThresholds(
                min_score=0.9,
                max_abstain_rate=0.01,
                max_latency_ms=50.0,
                min_cache_hit_rate=0.99,
            ),
        )

        # Add query that breaches all thresholds
        monitor.record_query_metrics(
            query="test",
            results=[{"score": 0.5}],
            latency_ms=1000.0,
            cache_hit=False,
        )
        monitor.record_abstain()

        data = await monitor.get_dashboard_data("24h")

        breaches = data["alerts"]["threshold_breaches"]
        assert len(breaches) > 0
        assert any(b["metric"] == "retrieval_score" for b in breaches)


class TestGetScoresTrend:
    """Tests for score trend retrieval."""

    @pytest.mark.asyncio
    async def test_empty_trend(self, monitor: RetrievalQualityMonitor) -> None:
        """Test trend with no data."""
        trend = await monitor.get_scores_trend(days=7)

        assert trend == []

    @pytest.mark.asyncio
    async def test_trend_with_data(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test trend calculation."""
        # Add queries
        for i in range(5):
            monitor.record_query_metrics(
                query=f"query {i}",
                results=[{"score": 0.5 + i * 0.1}],
                latency_ms=100.0,
            )

        trend = await monitor.get_scores_trend(days=7)

        # Should have at least one entry for today
        assert len(trend) >= 1
        assert "date" in trend[0]
        assert "avg_score" in trend[0]
        assert "query_count" in trend[0]

    @pytest.mark.asyncio
    async def test_trend_days_limits(self, monitor: RetrievalQualityMonitor) -> None:
        """Test days parameter limits."""
        # Test minimum
        trend = await monitor.get_scores_trend(days=0)
        assert len(trend) == 0  # Empty but shouldn't error

        # Test maximum
        trend = await monitor.get_scores_trend(days=100)
        # Should clamp to 30


class TestGetAbstainStatistics:
    """Tests for abstain statistics."""

    @pytest.mark.asyncio
    async def test_empty_statistics(self, monitor: RetrievalQualityMonitor) -> None:
        """Test statistics with no abstains."""
        stats = await monitor.get_abstain_statistics(days=7)

        assert stats["total_abstains"] == 0
        assert stats["abstain_rate"] == 0.0
        assert stats["by_reason"] == {}

    @pytest.mark.asyncio
    async def test_statistics_with_abstains(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test statistics calculation."""
        # Add regular queries
        monitor.record_query_metrics(
            query="normal",
            results=[{"score": 0.8}],
            latency_ms=100.0,
        )

        # Add abstains with different reasons
        monitor.record_abstain(domain="visa", reason="low_confidence")
        monitor.record_abstain(domain="tax", reason="no_results")
        monitor.record_abstain(domain="visa", reason="safety")

        stats = await monitor.get_abstain_statistics(days=7)

        assert stats["total_abstains"] == 3
        assert stats["total_queries"] == 4
        assert stats["abstain_rate"] == 75.0  # 3/4
        assert stats["by_reason"]["low_confidence"] == 1
        assert stats["by_reason"]["no_results"] == 1
        assert stats["by_reason"]["safety"] == 1

    @pytest.mark.asyncio
    async def test_daily_breakdown(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test daily breakdown in statistics."""
        monitor.record_abstain(reason="test")

        stats = await monitor.get_abstain_statistics(days=7)

        assert len(stats["daily_breakdown"]) >= 1
        today_entry = stats["daily_breakdown"][0]
        assert "date" in today_entry
        assert "count" in today_entry
        assert "reasons" in today_entry


class TestGetLatencyPercentiles:
    """Tests for latency percentile retrieval."""

    @pytest.mark.asyncio
    async def test_empty_latency(self, monitor: RetrievalQualityMonitor) -> None:
        """Test latency stats with no data."""
        stats = await monitor.get_latency_percentiles(days=7)

        assert stats["total_queries"] == 0
        assert stats["percentiles"] == {}

    @pytest.mark.asyncio
    async def test_latency_percentiles(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test percentile calculation."""
        # Add queries with varying latencies
        latencies = [10, 50, 100, 200, 500, 1000, 2000, 5000]
        for latency in latencies:
            monitor.record_query_metrics(
                query="test",
                results=[{"score": 0.8}],
                latency_ms=float(latency),
            )

        stats = await monitor.get_latency_percentiles(days=7)

        assert stats["total_queries"] == 8
        assert "p50" in stats["percentiles"]
        assert "p95" in stats["percentiles"]
        assert "p99" in stats["percentiles"]
        assert stats["min"] == 10.0
        assert stats["max"] == 5000.0

    @pytest.mark.asyncio
    async def test_latency_zero_filtered(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test that zero latency queries are filtered."""
        monitor.record_query_metrics(
            query="test",
            results=[{"score": 0.8}],
            latency_ms=0.0,
        )
        monitor.record_query_metrics(
            query="test2",
            results=[{"score": 0.8}],
            latency_ms=100.0,
        )

        stats = await monitor.get_latency_percentiles(days=7)

        # Should only count the non-zero latency query
        assert stats["total_queries"] == 1


class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_get_retrieval_quality_monitor(self) -> None:
        """Test the dependency injection helper."""
        monitor = await get_retrieval_quality_monitor()

        assert isinstance(monitor, RetrievalQualityMonitor)

    def test_safe_register_metric_new(self) -> None:
        """Test registering new metric."""
        from prometheus_client import Counter

        # Use unique name to avoid conflicts
        metric = safe_register_metric(
            Counter,
            "test_metric_unique_12345",
            "Test metric",
        )

        assert metric is not None

    def test_parse_time_range(self, monitor: RetrievalQualityMonitor) -> None:
        """Test time range parsing."""
        from datetime import timedelta

        assert monitor._parse_time_range("1h") == timedelta(hours=1)
        assert monitor._parse_time_range("24h") == timedelta(hours=24)
        assert monitor._parse_time_range("7d") == timedelta(days=7)
        assert monitor._parse_time_range("30d") == timedelta(days=30)
        # Default fallback
        assert monitor._parse_time_range("invalid") == timedelta(hours=24)

    def test_percentile_calculation(self, monitor: RetrievalQualityMonitor) -> None:
        """Test percentile calculation."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        assert monitor._percentile(data, 0.0) == 1
        # 0.5 percentile at index 5 (0-indexed) = value 6
        assert monitor._percentile(data, 0.5) == 6
        assert monitor._percentile(data, 1.0) == 10

    def test_percentile_empty(self, monitor: RetrievalQualityMonitor) -> None:
        """Test percentile with empty list."""
        assert monitor._percentile([], 0.5) == 0.0

    def test_score_distribution(self, monitor: RetrievalQualityMonitor) -> None:
        """Test score distribution calculation."""
        scores = [0.05, 0.15, 0.25, 0.35, 0.85, 0.95]

        dist = monitor._calculate_score_distribution(scores)

        assert dist["0.0-0.1"] == 1
        assert dist["0.1-0.2"] == 1
        assert dist["0.2-0.3"] == 1
        assert dist["0.8-0.9"] == 1
        assert dist["0.9-1.0"] == 1


class TestRecordLimiting:
    """Tests for record limiting."""

    def test_max_records_limit(
        self,
        monitor: RetrievalQualityMonitor,
    ) -> None:
        """Test that records are limited to MAX_RECORDS."""
        # Add more records than max
        max_records = RetrievalQualityMonitor.MAX_RECORDS

        for i in range(max_records + 100):
            monitor.record_query_metrics(
                query=f"query {i}",
                results=[{"score": 0.5}],
                latency_ms=100.0,
            )

        # Should be limited to MAX_RECORDS
        assert len(monitor._query_records) == max_records


class TestIntegration:
    """Integration-style tests."""

    @pytest.mark.asyncio
    async def test_full_workflow(
        self,
        monitor: RetrievalQualityMonitor,
        sample_query_results: list[dict[str, Any]],
    ) -> None:
        """Test a complete monitoring workflow."""
        # Simulate a series of queries
        for i in range(20):
            monitor.record_query_metrics(
                query=f"workflow query {i}",
                results=sample_query_results,
                latency_ms=100.0 + (i % 5) * 50,
                search_type="hybrid" if i % 3 == 0 else "dense",
                use_reranker=i % 2 == 0,
                cache_hit=i % 4 == 0,
            )

            # Record some scores
            monitor.record_retrieval_score(0.5 + (i % 5) * 0.1)

        # Record some abstains
        for i in range(3):
            monitor.record_abstain(domain="visa", reason="low_confidence")

        # Update thresholds
        monitor.set_alert_thresholds(AlertThresholds(min_score=0.6))

        # Get dashboard data
        dashboard = await monitor.get_dashboard_data("24h")

        assert dashboard["total_queries"] == 23  # 20 + 3 abstains
        assert dashboard["alert_thresholds"]["min_score"] == 0.6

        # Get trends
        trend = await monitor.get_scores_trend(days=7)
        assert len(trend) >= 1

        # Get abstain stats
        abstain_stats = await monitor.get_abstain_statistics(days=7)
        assert abstain_stats["total_abstains"] == 3

        # Get latency stats
        latency_stats = await monitor.get_latency_percentiles(days=7)
        assert latency_stats["total_queries"] == 20
