"""
Comprehensive unit tests for backend/services/rag/evaluation/monitoring.py
Covers: safe_register_metric, QueryMetricsRecord, AlertThresholds,
        RetrievalQualityMonitor (all methods), get_retrieval_quality_monitor.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# safe_register_metric
# ============================================================================

class TestSafeRegisterMetric:

    def test_register_new_metric(self):
        from backend.services.rag.evaluation.monitoring import safe_register_metric
        from prometheus_client import Gauge, REGISTRY

        # Use a unique name to avoid collision
        name = "test_unique_metric_safe_register_12345"
        # Clean up first if exists
        if name in REGISTRY._names_to_collectors:
            REGISTRY.unregister(REGISTRY._names_to_collectors[name])

        metric = safe_register_metric(Gauge, name, "Test metric")
        assert metric is not None

        # Clean up
        try:
            REGISTRY.unregister(metric)
        except Exception:
            pass

    def test_register_existing_returns_existing(self):
        from backend.services.rag.evaluation.monitoring import safe_register_metric
        from prometheus_client import Gauge, REGISTRY

        name = "test_duplicate_metric_67890"
        if name in REGISTRY._names_to_collectors:
            REGISTRY.unregister(REGISTRY._names_to_collectors[name])

        m1 = safe_register_metric(Gauge, name, "Test")
        m2 = safe_register_metric(Gauge, name, "Test")
        assert m2 is not None  # Should return existing, not raise

        try:
            REGISTRY.unregister(m1)
        except Exception:
            pass


# ============================================================================
# QueryMetricsRecord
# ============================================================================

class TestQueryMetricsRecord:

    def test_create_record(self):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        record = QueryMetricsRecord(
            timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            query_hash="abc123",
            query_text="test query",
            retrieval_score=0.75,
            latency_ms=150.0,
            search_type="hybrid",
            use_reranker=True,
            cache_hit=False,
            result_count=5,
        )
        assert record.retrieval_score == 0.75
        assert record.abstained is False
        assert record.abstain_reason is None

    def test_create_abstain_record(self):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        record = QueryMetricsRecord(
            timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            query_hash="hash",
            query_text="",
            retrieval_score=0.0,
            latency_ms=0.0,
            search_type="none",
            use_reranker=False,
            cache_hit=False,
            result_count=0,
            abstained=True,
            abstain_reason="low_confidence",
        )
        assert record.abstained is True
        assert record.abstain_reason == "low_confidence"


# ============================================================================
# AlertThresholds
# ============================================================================

class TestAlertThresholds:

    def test_defaults(self):
        from backend.services.rag.evaluation.monitoring import AlertThresholds

        t = AlertThresholds()
        assert t.min_score == 0.3
        assert t.max_abstain_rate == 0.2
        assert t.max_latency_ms == 5000.0
        assert t.min_cache_hit_rate == 0.5

    def test_to_dict(self):
        from backend.services.rag.evaluation.monitoring import AlertThresholds

        t = AlertThresholds(min_score=0.4)
        d = t.to_dict()
        assert d["min_score"] == 0.4
        assert "max_latency_ms" in d

    def test_from_dict(self):
        from backend.services.rag.evaluation.monitoring import AlertThresholds

        data = {"min_score": 0.5, "max_abstain_rate": 0.1}
        t = AlertThresholds.from_dict(data)
        assert t.min_score == 0.5
        assert t.max_abstain_rate == 0.1
        # Defaults for missing keys
        assert t.max_latency_ms == 5000.0

    def test_from_dict_empty(self):
        from backend.services.rag.evaluation.monitoring import AlertThresholds

        t = AlertThresholds.from_dict({})
        assert t.min_score == 0.3  # Default


# ============================================================================
# RetrievalQualityMonitor
# ============================================================================

class TestRetrievalQualityMonitor:

    @pytest.fixture
    def monitor(self):
        from backend.services.rag.evaluation.monitoring import RetrievalQualityMonitor
        return RetrievalQualityMonitor()

    # --- record_query_metrics ---

    def test_record_query_metrics_basic(self, monitor):
        monitor.record_query_metrics(
            query="test query",
            results=[{"score": 0.8}],
            latency_ms=100.0,
            search_type="dense",
        )
        assert len(monitor._query_records) == 1
        assert monitor._query_records[0].retrieval_score == 0.8

    def test_record_query_metrics_no_score(self, monitor):
        """When no retrieval_score provided, calculates from results."""
        monitor.record_query_metrics(
            query="test",
            results=[{"score": 0.6}, {"score": 0.8}],
            latency_ms=50.0,
        )
        assert monitor._query_records[0].retrieval_score == 0.7

    def test_record_query_metrics_empty_results(self, monitor):
        monitor.record_query_metrics(
            query="empty",
            results=[],
            latency_ms=10.0,
        )
        assert monitor._query_records[0].retrieval_score == 0.0

    def test_record_query_metrics_with_explicit_score(self, monitor):
        monitor.record_query_metrics(
            query="test",
            results=[{"score": 0.5}],
            latency_ms=100.0,
            retrieval_score=0.9,
        )
        assert monitor._query_records[0].retrieval_score == 0.9

    def test_record_query_metrics_increments_unflushed(self, monitor):
        monitor.record_query_metrics("q", [{"score": 0.5}], 10.0)
        assert monitor._unflushed_count == 1
        monitor.record_query_metrics("q2", [{"score": 0.6}], 20.0)
        assert monitor._unflushed_count == 2

    def test_record_query_low_score_alert(self, monitor):
        """Score below threshold triggers low_score counter."""
        monitor.record_query_metrics(
            query="bad query",
            results=[{"score": 0.1}],
            latency_ms=100.0,
        )
        # Should not raise; just records the metric

    # --- record_retrieval_score ---

    def test_record_retrieval_score(self, monitor):
        monitor.record_retrieval_score(0.75)
        # Should not raise

    def test_record_retrieval_score_clamped(self, monitor):
        monitor.record_retrieval_score(1.5)  # Above max
        monitor.record_retrieval_score(-0.5)  # Below min

    def test_record_retrieval_score_below_threshold(self, monitor):
        monitor.record_retrieval_score(0.1)  # Below default 0.3

    # --- record_abstain ---

    def test_record_abstain(self, monitor):
        monitor.record_abstain(domain="visa", reason="low_confidence")
        assert len(monitor._query_records) == 1
        assert monitor._query_records[0].abstained is True
        assert monitor._query_records[0].abstain_reason == "low_confidence"

    def test_record_abstain_defaults(self, monitor):
        monitor.record_abstain()
        assert monitor._query_records[0].abstain_reason == "low_confidence"

    # --- record_cache_access ---

    def test_record_cache_hit(self, monitor):
        monitor.record_cache_access(hit=True)

    def test_record_cache_miss(self, monitor):
        monitor.record_cache_access(hit=False)

    # --- record_reranker_effectiveness ---

    def test_record_reranker_effectiveness(self, monitor):
        monitor.record_reranker_effectiveness(
            before_scores=[0.3, 0.4, 0.5],
            after_scores=[0.6, 0.7, 0.8],
        )
        # Should not raise

    def test_record_reranker_empty_lists(self, monitor):
        monitor.record_reranker_effectiveness([], [])
        # Should return early without error

    def test_record_reranker_negative_improvement(self, monitor):
        monitor.record_reranker_effectiveness(
            before_scores=[0.8, 0.9],
            after_scores=[0.3, 0.4],
        )

    # --- set/get alert thresholds ---

    def test_set_and_get_thresholds(self, monitor):
        from backend.services.rag.evaluation.monitoring import AlertThresholds

        new_thresholds = AlertThresholds(min_score=0.5, max_abstain_rate=0.1)
        monitor.set_alert_thresholds(new_thresholds)
        assert monitor.get_alert_thresholds().min_score == 0.5

    # --- set_db_pool ---

    def test_set_db_pool(self, monitor):
        mock_pool = MagicMock()
        monitor.set_db_pool(mock_pool)
        assert monitor._db_pool is mock_pool

    def test_set_db_pool_none(self, monitor):
        monitor.set_db_pool(None)
        assert monitor._db_pool is None

    # --- get_dashboard_data ---

    @pytest.mark.asyncio
    async def test_dashboard_data_empty(self, monitor):
        data = await monitor.get_dashboard_data("24h")
        assert data["total_queries"] == 0
        assert data["time_range"] == "24h"

    @pytest.mark.asyncio
    async def test_dashboard_data_with_records(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        for i in range(5):
            monitor._query_records.append(QueryMetricsRecord(
                timestamp=now - timedelta(minutes=i),
                query_hash=f"h{i}",
                query_text=f"query {i}",
                retrieval_score=0.5 + i * 0.1,
                latency_ms=100.0 + i * 50,
                search_type="dense",
                use_reranker=False,
                cache_hit=i % 2 == 0,
                result_count=3,
            ))

        data = await monitor.get_dashboard_data("1h")
        assert data["total_queries"] == 5
        assert data["retrieval_quality"]["average_score"] > 0
        assert data["performance"]["average_latency_ms"] > 0
        assert data["usage_patterns"]["cache_hit_rate"] > 0

    @pytest.mark.asyncio
    async def test_dashboard_data_with_abstains(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        monitor._query_records.append(QueryMetricsRecord(
            timestamp=now,
            query_hash="a1",
            query_text="abstain",
            retrieval_score=0.0,
            latency_ms=0.0,
            search_type="none",
            use_reranker=False,
            cache_hit=False,
            result_count=0,
            abstained=True,
            abstain_reason="low_confidence",
        ))
        monitor._query_records.append(QueryMetricsRecord(
            timestamp=now,
            query_hash="q1",
            query_text="normal",
            retrieval_score=0.8,
            latency_ms=100.0,
            search_type="dense",
            use_reranker=False,
            cache_hit=False,
            result_count=3,
        ))

        data = await monitor.get_dashboard_data("1h")
        assert data["usage_patterns"]["abstain_rate"] == 50.0

    # --- get_scores_trend ---

    @pytest.mark.asyncio
    async def test_scores_trend_empty(self, monitor):
        trend = await monitor.get_scores_trend(days=7)
        assert trend == []

    @pytest.mark.asyncio
    async def test_scores_trend_with_data(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        for i in range(3):
            monitor._query_records.append(QueryMetricsRecord(
                timestamp=now - timedelta(days=i),
                query_hash=f"t{i}",
                query_text=f"trend {i}",
                retrieval_score=0.7,
                latency_ms=100.0,
                search_type="dense",
                use_reranker=False,
                cache_hit=False,
                result_count=3,
            ))

        trend = await monitor.get_scores_trend(days=7)
        assert len(trend) > 0
        assert "avg_score" in trend[0]

    # --- get_abstain_statistics ---

    @pytest.mark.asyncio
    async def test_abstain_statistics_empty(self, monitor):
        stats = await monitor.get_abstain_statistics(days=7)
        assert stats["total_abstains"] == 0
        assert stats["abstain_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_abstain_statistics_with_data(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        monitor._query_records.append(QueryMetricsRecord(
            timestamp=now, query_hash="a", query_text="", retrieval_score=0.0,
            latency_ms=0.0, search_type="none", use_reranker=False, cache_hit=False,
            result_count=0, abstained=True, abstain_reason="safety",
        ))
        monitor._query_records.append(QueryMetricsRecord(
            timestamp=now, query_hash="b", query_text="normal", retrieval_score=0.8,
            latency_ms=100.0, search_type="dense", use_reranker=False, cache_hit=False,
            result_count=3,
        ))

        stats = await monitor.get_abstain_statistics(days=7)
        assert stats["total_abstains"] == 1
        assert stats["by_reason"]["safety"] == 1
        assert stats["abstain_rate"] == 50.0

    # --- get_latency_percentiles ---

    @pytest.mark.asyncio
    async def test_latency_percentiles_empty(self, monitor):
        result = await monitor.get_latency_percentiles(days=7)
        assert result["total_queries"] == 0

    @pytest.mark.asyncio
    async def test_latency_percentiles_with_data(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        for ms in [50, 100, 200, 500, 1000]:
            monitor._query_records.append(QueryMetricsRecord(
                timestamp=now, query_hash="l", query_text="", retrieval_score=0.5,
                latency_ms=ms, search_type="dense", use_reranker=False, cache_hit=False,
                result_count=3,
            ))

        result = await monitor.get_latency_percentiles(days=7)
        assert result["total_queries"] == 5
        assert result["percentiles"]["p50"] > 0
        assert result["min"] == 50.0
        assert result["max"] == 1000.0

    # --- flush_to_db ---

    @pytest.mark.asyncio
    async def test_flush_no_db_pool(self, monitor):
        monitor._db_pool = None
        result = await monitor.flush_to_db()
        assert result == 0

    @pytest.mark.asyncio
    async def test_flush_no_records(self, monitor):
        mock_pool = MagicMock()
        monitor._db_pool = mock_pool
        result = await monitor.flush_to_db()
        assert result == 0

    # --- load_historical_stats ---

    @pytest.mark.asyncio
    async def test_load_historical_no_db(self, monitor):
        monitor._db_pool = None
        result = await monitor.load_historical_stats()
        assert result == []

    # --- _maybe_flush ---

    @pytest.mark.asyncio
    async def test_maybe_flush_no_db(self, monitor):
        monitor._db_pool = None
        await monitor._maybe_flush()  # Should not raise

    # --- _parse_time_range ---

    def test_parse_time_range_1h(self, monitor):
        delta = monitor._parse_time_range("1h")
        assert delta == timedelta(hours=1)

    def test_parse_time_range_7d(self, monitor):
        delta = monitor._parse_time_range("7d")
        assert delta == timedelta(days=7)

    def test_parse_time_range_unknown(self, monitor):
        delta = monitor._parse_time_range("unknown")
        assert delta == timedelta(hours=24)  # Default

    # --- _percentile ---

    def test_percentile_empty(self, monitor):
        assert monitor._percentile([], 0.5) == 0.0

    def test_percentile_single(self, monitor):
        assert monitor._percentile([10.0], 0.5) == 10.0

    def test_percentile_multiple(self, monitor):
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        p50 = monitor._percentile(data, 0.5)
        assert p50 == 6.0  # Index 5

    # --- _calculate_score_distribution ---

    def test_score_distribution_empty(self, monitor):
        dist = monitor._calculate_score_distribution([])
        assert all(v == 0 for v in dist.values())

    def test_score_distribution(self, monitor):
        scores = [0.05, 0.15, 0.75, 0.95]
        dist = monitor._calculate_score_distribution(scores)
        assert dist["0.0-0.1"] == 1
        assert dist["0.1-0.2"] == 1
        assert dist["0.7-0.8"] == 1
        assert dist["0.9-1.0"] == 1

    # --- _empty_dashboard_data ---

    def test_empty_dashboard_data(self, monitor):
        data = monitor._empty_dashboard_data("24h")
        assert data["total_queries"] == 0
        assert data["time_range"] == "24h"
        assert "retrieval_quality" in data
        assert "performance" in data
        assert "usage_patterns" in data

    # --- _get_threshold_breaches ---

    def test_no_breaches(self, monitor):
        breaches = monitor._get_threshold_breaches(
            avg_score=0.8, abstain_rate_val=0.05,
            avg_latency=100.0, cache_hit_rate_val=0.7,
        )
        assert len(breaches) == 0

    def test_all_breaches(self, monitor):
        breaches = monitor._get_threshold_breaches(
            avg_score=0.1,        # Below 0.3
            abstain_rate_val=0.5, # Above 0.2
            avg_latency=10000.0,  # Above 5000
            cache_hit_rate_val=0.1,  # Below 0.5
        )
        assert len(breaches) == 4
        metrics = [b["metric"] for b in breaches]
        assert "retrieval_score" in metrics
        assert "abstain_rate" in metrics
        assert "latency" in metrics
        assert "cache_hit_rate" in metrics

    def test_score_breach_only(self, monitor):
        breaches = monitor._get_threshold_breaches(
            avg_score=0.1, abstain_rate_val=0.05,
            avg_latency=100.0, cache_hit_rate_val=0.8,
        )
        assert len(breaches) == 1
        assert breaches[0]["metric"] == "retrieval_score"
        assert breaches[0]["severity"] == "warning"

    def test_abstain_breach_is_critical(self, monitor):
        breaches = monitor._get_threshold_breaches(
            avg_score=0.8, abstain_rate_val=0.5,
            avg_latency=100.0, cache_hit_rate_val=0.8,
        )
        assert len(breaches) == 1
        assert breaches[0]["severity"] == "critical"

    # --- _get_daily_abstain_breakdown ---

    def test_daily_abstain_breakdown_empty(self, monitor):
        result = monitor._get_daily_abstain_breakdown([], days=7)
        assert result == []

    def test_daily_abstain_breakdown_with_data(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        records = [
            QueryMetricsRecord(
                timestamp=now, query_hash="a", query_text="",
                retrieval_score=0.0, latency_ms=0.0, search_type="none",
                use_reranker=False, cache_hit=False, result_count=0,
                abstained=True, abstain_reason="safety",
            ),
            QueryMetricsRecord(
                timestamp=now, query_hash="b", query_text="",
                retrieval_score=0.0, latency_ms=0.0, search_type="none",
                use_reranker=False, cache_hit=False, result_count=0,
                abstained=True, abstain_reason="low_confidence",
            ),
        ]
        result = monitor._get_daily_abstain_breakdown(records, days=1)
        assert len(result) == 1
        assert result[0]["count"] == 2
        assert result[0]["reasons"]["safety"] == 1
        assert result[0]["reasons"]["low_confidence"] == 1

    # --- _update_prometheus_metrics ---

    def test_update_prometheus_metrics(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        record = QueryMetricsRecord(
            timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            query_hash="pm", query_text="prometheus test",
            retrieval_score=0.8, latency_ms=200.0,
            search_type="hybrid", use_reranker=True,
            cache_hit=False, result_count=5,
        )
        monitor._update_prometheus_metrics(record)  # Should not raise

    def test_update_prometheus_abstained_record(self, monitor):
        from backend.services.rag.evaluation.monitoring import QueryMetricsRecord

        record = QueryMetricsRecord(
            timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            query_hash="abs", query_text="",
            retrieval_score=0.0, latency_ms=0.0,
            search_type="none", use_reranker=False,
            cache_hit=False, result_count=0,
            abstained=True,
        )
        monitor._update_prometheus_metrics(record)  # Abstained → no evidence_score observe


# ============================================================================
# Global instance and dependency injection helper
# ============================================================================

class TestGlobalMonitor:

    def test_global_instance_exists(self):
        from backend.services.rag.evaluation.monitoring import retrieval_quality_monitor
        assert retrieval_quality_monitor is not None

    @pytest.mark.asyncio
    async def test_get_retrieval_quality_monitor(self):
        from backend.services.rag.evaluation.monitoring import get_retrieval_quality_monitor
        monitor = await get_retrieval_quality_monitor()
        assert monitor is not None
