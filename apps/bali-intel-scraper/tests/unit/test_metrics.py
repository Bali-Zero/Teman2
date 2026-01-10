"""
Tests for metrics.py - Metrics & Observability Module
Covers: MetricsCollector, track_latency, StructuredLogger
"""

import pytest
import sys
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from metrics import (
    MetricValue,
    LatencyMetric,
    PipelineMetrics,
    MetricsCollector,
    track_latency,
    StructuredLogger,
    get_metrics,
    reset_metrics,
)


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestMetricValue:
    """Test MetricValue dataclass"""

    def test_create_metric_value(self):
        """Test creating metric value"""
        mv = MetricValue(name="test_metric", value=42.0)
        assert mv.name == "test_metric"
        assert mv.value == 42.0
        assert mv.timestamp is not None

    def test_with_labels(self):
        """Test metric value with labels"""
        mv = MetricValue(name="test", value=1.0, labels={"env": "prod"})
        assert mv.labels["env"] == "prod"


class TestLatencyMetric:
    """Test LatencyMetric dataclass"""

    def test_create_latency_metric(self):
        """Test creating latency metric"""
        lm = LatencyMetric(name="api_call", duration_ms=150.5)
        assert lm.name == "api_call"
        assert lm.duration_ms == 150.5
        assert lm.success is True

    def test_with_failure(self):
        """Test latency metric for failed operation"""
        lm = LatencyMetric(name="api_call", duration_ms=5000, success=False)
        assert lm.success is False


class TestPipelineMetrics:
    """Test PipelineMetrics dataclass"""

    def test_default_values(self):
        """Test default values are zero"""
        pm = PipelineMetrics()
        assert pm.total_articles_input == 0
        assert pm.total_errors == 0
        assert pm.avg_llama_latency_ms == 0.0

    def test_all_fields_present(self):
        """Test all expected fields exist"""
        pm = PipelineMetrics()
        expected_fields = [
            "total_articles_input", "total_articles_processed",
            "total_articles_published", "total_articles_rejected",
            "total_errors", "dedup_filtered", "llama_scored",
            "claude_validated", "enriched", "images_generated",
            "avg_llama_latency_ms", "total_pipeline_duration_ms",
        ]
        for field in expected_fields:
            assert hasattr(pm, field), f"Missing field: {field}"


# =============================================================================
# METRICS COLLECTOR TESTS
# =============================================================================


class TestMetricsCollectorInit:
    """Test MetricsCollector initialization"""

    def test_default_init(self):
        """Test default initialization"""
        mc = MetricsCollector()
        assert mc.app_name == "bali_intel_scraper"

    def test_custom_app_name(self):
        """Test custom app name"""
        mc = MetricsCollector(app_name="custom_app")
        assert mc.app_name == "custom_app"


class TestCounterOperations:
    """Test counter operations"""

    def test_increment_counter(self):
        """Test incrementing counter"""
        mc = MetricsCollector()
        mc.increment("test_counter")
        assert mc.get_counter("test_counter") == 1

    def test_increment_by_value(self):
        """Test incrementing by specific value"""
        mc = MetricsCollector()
        mc.increment("test_counter", 5)
        assert mc.get_counter("test_counter") == 5

    def test_multiple_increments(self):
        """Test multiple increments accumulate"""
        mc = MetricsCollector()
        mc.increment("test_counter", 2)
        mc.increment("test_counter", 3)
        assert mc.get_counter("test_counter") == 5

    def test_counter_with_labels(self):
        """Test counter with labels"""
        mc = MetricsCollector()
        mc.increment("requests", labels={"status": "200"})
        mc.increment("requests", labels={"status": "500"})
        assert mc.get_counter("requests", labels={"status": "200"}) == 1
        assert mc.get_counter("requests", labels={"status": "500"}) == 1

    def test_pipeline_counter_updates(self):
        """Test pipeline-specific counters are updated"""
        mc = MetricsCollector()
        mc.increment("articles_input", 10)
        mc.increment("llama_scored", 8)
        pm = mc.get_pipeline_metrics()
        assert pm.total_articles_input == 10
        assert pm.llama_scored == 8


class TestGaugeOperations:
    """Test gauge operations"""

    def test_set_gauge(self):
        """Test setting gauge"""
        mc = MetricsCollector()
        mc.set_gauge("queue_size", 42)
        assert mc.get_gauge("queue_size") == 42

    def test_gauge_can_decrease(self):
        """Test gauge can go down"""
        mc = MetricsCollector()
        mc.set_gauge("queue_size", 100)
        mc.set_gauge("queue_size", 50)
        assert mc.get_gauge("queue_size") == 50

    def test_gauge_with_labels(self):
        """Test gauge with labels"""
        mc = MetricsCollector()
        mc.set_gauge("memory", 1024, labels={"process": "main"})
        assert mc.get_gauge("memory", labels={"process": "main"}) == 1024


class TestLatencyTracking:
    """Test latency tracking"""

    def test_record_latency(self):
        """Test recording latency"""
        mc = MetricsCollector()
        mc.record_latency("api_call", 150.0)
        stats = mc.get_latency_stats("api_call")
        assert stats["count"] == 1
        assert stats["avg"] == 150.0

    def test_multiple_latencies(self):
        """Test multiple latency recordings"""
        mc = MetricsCollector()
        mc.record_latency("api_call", 100.0)
        mc.record_latency("api_call", 200.0)
        mc.record_latency("api_call", 300.0)
        stats = mc.get_latency_stats("api_call")
        assert stats["count"] == 3
        assert stats["avg"] == 200.0
        assert stats["min"] == 100.0
        assert stats["max"] == 300.0

    def test_latency_percentiles(self):
        """Test latency percentile calculations"""
        mc = MetricsCollector()
        # Record 100 values from 1 to 100
        for i in range(1, 101):
            mc.record_latency("test", float(i))
        stats = mc.get_latency_stats("test")
        # p50 should be around 50 (allow some margin due to index calculation)
        assert 49.0 <= stats["p50"] <= 52.0
        assert stats["p95"] >= 94.0

    def test_empty_latency_stats(self):
        """Test empty latency stats"""
        mc = MetricsCollector()
        stats = mc.get_latency_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["avg"] == 0


class TestErrorTracking:
    """Test error tracking"""

    def test_record_error(self):
        """Test recording error"""
        mc = MetricsCollector()
        mc.record_error("llama", "timeout")
        assert mc.get_error_count("llama", "timeout") == 1

    def test_multiple_errors(self):
        """Test multiple error recordings"""
        mc = MetricsCollector()
        mc.record_error("llama", "timeout")
        mc.record_error("llama", "timeout")
        mc.record_error("llama", "parse_error")
        assert mc.get_error_count("llama", "timeout") == 2
        assert mc.get_error_count("llama") == 3  # Total for component

    def test_error_increments_counter(self):
        """Test error recording increments errors counter"""
        mc = MetricsCollector()
        mc.record_error("test", "error")
        assert mc.get_counter("errors") == 1


class TestPipelineLifecycle:
    """Test pipeline start/end lifecycle"""

    def test_start_pipeline(self):
        """Test starting pipeline"""
        mc = MetricsCollector()
        mc.start_pipeline()
        pm = mc.get_pipeline_metrics()
        assert pm.started_at != ""

    def test_end_pipeline(self):
        """Test ending pipeline"""
        mc = MetricsCollector()
        mc.start_pipeline()
        time.sleep(0.01)  # Small delay
        mc.end_pipeline()
        pm = mc.get_pipeline_metrics()
        assert pm.completed_at != ""
        assert pm.total_pipeline_duration_ms > 0


class TestExportMethods:
    """Test export methods"""

    def test_to_dict(self):
        """Test export to dictionary"""
        mc = MetricsCollector()
        mc.increment("test_counter", 5)
        mc.set_gauge("test_gauge", 10)
        data = mc.to_dict()
        assert "counters" in data
        assert "gauges" in data
        assert "pipeline" in data
        assert data["app_name"] == "bali_intel_scraper"

    def test_to_json(self):
        """Test export to JSON"""
        mc = MetricsCollector()
        mc.increment("test", 1)
        json_str = mc.to_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert "counters" in data

    def test_export_prometheus(self):
        """Test Prometheus format export"""
        mc = MetricsCollector()
        mc.increment("test_counter", 5)
        mc.record_latency("test_latency", 100.0)
        prom = mc.export_prometheus()
        assert "counter" in prom
        assert "bali_intel_scraper_test_counter" in prom
        assert "5" in prom

    def test_save_to_file(self):
        """Test saving metrics to file"""
        mc = MetricsCollector()
        mc.increment("test", 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = f"{tmpdir}/metrics.json"
            mc.save_to_file(filepath)
            assert Path(filepath).exists()
            with open(filepath) as f:
                data = json.load(f)
            assert "counters" in data


class TestReset:
    """Test reset functionality"""

    def test_reset_clears_all(self):
        """Test reset clears all metrics"""
        mc = MetricsCollector()
        mc.increment("test", 5)
        mc.set_gauge("gauge", 10)
        mc.record_latency("lat", 100)
        mc.record_error("comp", "err")

        mc.reset()

        assert mc.get_counter("test") == 0
        assert mc.get_gauge("gauge") == 0
        assert mc.get_latency_stats("lat")["count"] == 0
        assert mc.get_error_count("comp") == 0


# =============================================================================
# CONTEXT MANAGER TESTS
# =============================================================================


class TestTrackLatencyContextManager:
    """Test track_latency context manager"""

    def test_tracks_successful_operation(self):
        """Test tracking successful operation"""
        mc = MetricsCollector()
        with track_latency(mc, "test_op"):
            time.sleep(0.01)
        stats = mc.get_latency_stats("test_op")
        assert stats["count"] == 1
        assert stats["avg"] >= 10  # At least 10ms

    def test_tracks_failed_operation(self):
        """Test tracking failed operation records error"""
        mc = MetricsCollector()
        with pytest.raises(ValueError):
            with track_latency(mc, "test_op"):
                raise ValueError("Test error")
        # Should still record latency
        stats = mc.get_latency_stats("test_op")
        assert stats["count"] == 1
        # Should record error
        assert mc.get_error_count("test_op") >= 1


# =============================================================================
# STRUCTURED LOGGER TESTS
# =============================================================================


class TestStructuredLogger:
    """Test StructuredLogger"""

    def test_init(self):
        """Test initialization"""
        logger = StructuredLogger("test_component")
        assert logger.component == "test_component"

    def test_with_metrics(self):
        """Test logger with metrics"""
        mc = MetricsCollector()
        logger = StructuredLogger("test", metrics=mc)
        assert logger.metrics is mc

    def test_set_context(self):
        """Test setting context"""
        logger = StructuredLogger("test")
        logger.set_context(request_id="123", user="test")
        assert logger._context["request_id"] == "123"

    def test_clear_context(self):
        """Test clearing context"""
        logger = StructuredLogger("test")
        logger.set_context(key="value")
        logger.clear_context()
        assert len(logger._context) == 0

    def test_format_message(self):
        """Test message formatting"""
        logger = StructuredLogger("test")
        msg = logger._format_message("Hello", key="value")
        assert "[test]" in msg
        assert "Hello" in msg
        assert "key=value" in msg

    def test_error_records_metric(self):
        """Test error logging records metric"""
        mc = MetricsCollector()
        logger = StructuredLogger("test_comp", metrics=mc)
        logger.error("Test error")
        assert mc.get_error_count("test_comp") >= 1


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Test singleton functions"""

    def test_get_metrics_returns_same_instance(self):
        """Test get_metrics returns same instance"""
        reset_metrics()
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_reset_metrics(self):
        """Test reset_metrics clears global instance"""
        m = get_metrics()
        m.increment("test", 5)
        reset_metrics()
        # After reset, counter should be 0
        assert get_metrics().get_counter("test") == 0


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================


class TestThreadSafety:
    """Test thread safety"""

    def test_concurrent_increments(self):
        """Test concurrent increments don't lose data"""
        import threading

        mc = MetricsCollector()
        num_threads = 10
        increments_per_thread = 100

        def increment_counter():
            for _ in range(increments_per_thread):
                mc.increment("concurrent_test")

        threads = [threading.Thread(target=increment_counter) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * increments_per_thread
        assert mc.get_counter("concurrent_test") == expected
