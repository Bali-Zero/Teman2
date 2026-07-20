"""
Unit tests for app/metrics.py
Target: >95% coverage
"""

# Use absolute import instead of sys.path hacking
from backend.app import metrics


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

    def test_curated_qa_injections_metric_exists_and_increments(self):
        """P14/SPEC v2 D3: curated_qa_injections_total counts D3-L2 grounding
        injections (curated_qa hit prepended as evidence to the ReAct context)."""
        assert hasattr(metrics, "curated_qa_injections_total")
        before = metrics.curated_qa_injections_total._value.get()
        metrics.curated_qa_injections_total.inc()
        after = metrics.curated_qa_injections_total._value.get()
        assert after == before + 1

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
        before = metrics.cache_hits._value.get()
        metrics.cache_hits.inc()
        assert metrics.cache_hits._value.get() == before + 1

    def test_metrics_increment_with_value(self):
        """Test incrementing a counter metric with value"""
        before = metrics.cache_hits._value.get()
        metrics.cache_hits.inc(5)
        assert metrics.cache_hits._value.get() == before + 5

    def test_metrics_set_gauge(self):
        """Test setting a gauge metric"""
        metrics.active_sessions.set(10)
        assert metrics.active_sessions._value.get() == 10

    def test_metrics_observe_histogram(self):
        """Test observing a histogram metric"""
        # request_duration requires labels (method, endpoint)
        child = metrics.request_duration.labels(method="GET", endpoint="/test")
        before = child._sum.get()
        child.observe(0.5)
        assert child._sum.get() == before + 0.5

    def test_metrics_labels(self):
        """Test metrics with labels"""
        child = metrics.http_requests_total.labels(method="GET", endpoint="/test", status=200)
        before = child._value.get()
        child.inc()
        assert child._value.get() == before + 1

    def test_rag_queries_total(self):
        """Test RAG queries counter"""
        child = metrics.rag_queries_total.labels(
            collection="test",
            route_used="fast",
            status="success",
        )
        before = child._value.get()
        child.inc()
        assert child._value.get() == before + 1

    def test_rag_tool_calls_total(self):
        """Test RAG tool calls counter"""
        child = metrics.rag_tool_calls_total.labels(tool_name="vector_search", status="success")
        before = child._value.get()
        child.inc()
        assert child._value.get() == before + 1

    def test_database_init_metrics(self):
        """Test database initialization metrics"""
        assert hasattr(metrics, "database_init_success_total")
        assert hasattr(metrics, "database_init_failed_total")

        before_success = metrics.database_init_success_total._value.get()
        metrics.database_init_success_total.inc()
        assert metrics.database_init_success_total._value.get() == before_success + 1

        failed_child = metrics.database_init_failed_total.labels(
            error_type="test", is_transient="true"
        )
        before_failed = failed_child._value.get()
        failed_child.inc()
        assert failed_child._value.get() == before_failed + 1
