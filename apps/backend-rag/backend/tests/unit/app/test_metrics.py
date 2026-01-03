"""
Unit tests for app/metrics.py
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app import metrics


class TestMetrics:
    """Tests for metrics module"""

    def test_metrics_imported(self):
        """Test that metrics can be imported"""
        assert metrics is not None

    def test_system_metrics_exist(self):
        """Test that system metrics are defined"""
        assert hasattr(metrics, "active_sessions")
        assert hasattr(metrics, "redis_latency")
        assert hasattr(metrics, "system_uptime")
        assert hasattr(metrics, "cpu_usage")
        assert hasattr(metrics, "memory_usage")

    def test_request_metrics_exist(self):
        """Test that request metrics are defined"""
        assert hasattr(metrics, "http_requests_total")
        assert hasattr(metrics, "request_duration")

    def test_cache_metrics_exist(self):
        """Test that cache metrics are defined"""
        assert hasattr(metrics, "cache_hits")
        assert hasattr(metrics, "cache_misses")
        assert hasattr(metrics, "cache_set_operations")

    def test_ai_metrics_exist(self):
        """Test that AI metrics are defined"""
        assert hasattr(metrics, "ai_requests")
        assert hasattr(metrics, "ai_latency")
        assert hasattr(metrics, "ai_tokens_used")

    def test_llm_metrics_exist(self):
        """Test that LLM metrics are defined"""
        assert hasattr(metrics, "llm_prompt_tokens")
        assert hasattr(metrics, "llm_completion_tokens")
        assert hasattr(metrics, "llm_cost_usd")

    def test_database_metrics_exist(self):
        """Test that database metrics are defined"""
        assert hasattr(metrics, "db_connections_active")
        assert hasattr(metrics, "db_query_duration")
        assert hasattr(metrics, "db_pool_size")

    def test_rag_metrics_exist(self):
        """Test that RAG metrics are defined"""
        assert hasattr(metrics, "rag_embedding_duration")
        assert hasattr(metrics, "rag_vector_search_duration")
        assert hasattr(metrics, "rag_reranking_duration")
        assert hasattr(metrics, "rag_pipeline_duration")

    def test_metrics_increment(self):
        """Test incrementing a counter metric"""
        metrics.cache_hits.inc()
        # Should not raise exception

    def test_metrics_increment_with_value(self):
        """Test incrementing a counter metric with value"""
        metrics.cache_hits.inc(5)
        # Should not raise exception

    def test_metrics_set_gauge(self):
        """Test setting a gauge metric"""
        metrics.active_sessions.set(10)
        # Should not raise exception

    def test_metrics_observe_histogram(self):
        """Test observing a histogram metric"""
        metrics.request_duration.observe(0.5)
        # Should not raise exception

    def test_metrics_labels(self):
        """Test metrics with labels"""
        metrics.http_requests_total.labels(method="GET", endpoint="/test", status=200).inc()
        # Should not raise exception

    def test_rag_queries_total(self):
        """Test RAG queries counter"""
        metrics.rag_queries_total.labels(collection="test", route_used="fast", status="success").inc()
        # Should not raise exception

    def test_rag_tool_calls_total(self):
        """Test RAG tool calls counter"""
        metrics.rag_tool_calls_total.labels(tool_name="vector_search", status="success").inc()
        # Should not raise exception

    def test_database_init_metrics(self):
        """Test database initialization metrics"""
        if hasattr(metrics, "database_init_success_total"):
            metrics.database_init_success_total.inc()
        if hasattr(metrics, "database_init_failed_total"):
            metrics.database_init_failed_total.labels(error_type="test", is_transient="true").inc()
        # Should not raise exception
