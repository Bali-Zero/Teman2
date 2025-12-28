"""
Enhanced Prometheus Metrics for ZANTARA-PERFECT-100
Provides detailed system monitoring and performance tracking
"""

import logging
import time

import psutil
from prometheus_client import Counter, Gauge, Histogram, generate_latest

logger = logging.getLogger(__name__)

# System Metrics
active_sessions = Gauge("zantara_active_sessions_total", "Number of active user sessions")
redis_latency = Gauge("zantara_redis_latency_ms", "Redis latency in milliseconds")
sse_latency = Gauge("zantara_sse_latency_ms", "Average SSE handshake time")
system_uptime = Gauge("zantara_system_uptime_seconds", "System uptime in seconds")
cpu_usage = Gauge("zantara_cpu_usage_percent", "CPU usage percentage")
memory_usage = Gauge("zantara_memory_usage_mb", "Memory usage in MB")

# Request Metrics
http_requests_total = Counter(
    "zantara_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
request_duration = Histogram(
    "zantara_request_duration_seconds", "Request duration in seconds", ["method", "endpoint"]
)

# Cache Metrics
cache_hits = Counter("zantara_cache_hits_total", "Total cache hits")
cache_misses = Counter("zantara_cache_misses_total", "Total cache misses")
cache_set_operations = Counter("zantara_cache_set_operations_total", "Total cache set operations")

# AI Metrics
ai_requests = Counter("zantara_ai_requests_total", "Total AI requests", ["model"])
ai_latency = Histogram("zantara_ai_latency_seconds", "AI response latency", ["model"])
ai_tokens_used = Counter("zantara_ai_tokens_used_total", "Total AI tokens used", ["model"])

# LLM Token Usage Metrics (Detailed)
llm_prompt_tokens = Counter(
    "zantara_llm_prompt_tokens_total",
    "Total prompt/input tokens used",
    ["model", "endpoint"]
)
llm_completion_tokens = Counter(
    "zantara_llm_completion_tokens_total",
    "Total completion/output tokens used",
    ["model", "endpoint"]
)
llm_cost_usd = Counter(
    "zantara_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["model"]
)
llm_request_tokens = Histogram(
    "zantara_llm_request_tokens",
    "Tokens per request distribution",
    ["model", "type"],  # type = "prompt" or "completion"
    buckets=[10, 50, 100, 500, 1000, 2000, 5000, 10000, 20000]
)

# Database Metrics
db_connections_active = Gauge("zantara_db_connections_active", "Active database connections")
db_query_duration = Histogram("zantara_db_query_duration_seconds", "Database query duration")
db_pool_size = Gauge("zantara_db_pool_size", "Database connection pool size", ["service"])
db_pool_idle = Gauge(
    "zantara_db_pool_idle", "Database connection pool idle connections", ["service"]
)

# RAG Pipeline Metrics (Performance Debug Phase 1)
rag_embedding_duration = Histogram(
    "zantara_rag_embedding_duration_seconds", "Embedding generation duration"
)
rag_vector_search_duration = Histogram(
    "zantara_rag_vector_search_duration_seconds", "Vector search duration"
)
rag_reranking_duration = Histogram("zantara_rag_reranking_duration_seconds", "Reranking duration")
rag_pipeline_duration = Histogram(
    "zantara_rag_pipeline_duration_seconds", "Total RAG pipeline duration"
)
rag_early_exit_total = Counter(
    "zantara_rag_early_exit_total", "Total early exits (skipped reranking)"
)
rag_cache_hit_rate = Gauge("zantara_rag_cache_hit_rate", "RAG cache hit rate")
rag_parallel_searches = Counter(
    "zantara_rag_parallel_searches_total", "Parallel collection searches executed"
)

# RAG Query Metrics (Dec 2025 - Dashboard Alignment)
rag_queries_total = Counter(
    "zantara_rag_queries_total",
    "Total RAG queries processed",
    ["collection", "route_used", "status"]
)
rag_tool_calls_total = Counter(
    "zantara_rag_tool_calls_total",
    "Total tool calls in agentic RAG",
    ["tool_name", "status"]
)
rag_fallback_count = Counter(
    "zantara_rag_fallback_count_total",
    "LLM model fallback events",
    ["from_model", "to_model"]
)
rag_context_length = Histogram(
    "zantara_rag_context_length_tokens",
    "Context length in tokens per query",
    ["collection"],
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000, 32000]
)

# Boot time tracking
BOOT_TIME = time.time()


class MetricsCollector:
    """Collects and manages system metrics"""

    def __init__(self):
        self.session_count = 0
        self.last_redis_check = 0
        self.last_sse_latency = 0

    def update_session_count(self, count: int):
        """Update active sessions count"""
        self.session_count = count
        active_sessions.set(count)

    async def measure_redis_latency(self) -> float:
        """Measure Redis latency in milliseconds"""
        try:
            from core.cache import get_cache_service

            cache = get_cache_service()
            start = time.time()
            cache.set("metrics_ping", "pong", ttl=1)
            cache.get("metrics_ping")  # Verify cache works
            latency = (time.time() - start) * 1000
            redis_latency.set(latency)
            self.last_redis_check = latency
            return latency
        except Exception as e:
            logger.warning(f"Failed to measure Redis latency: {e}")
            return -1

    async def measure_sse_latency(self) -> float:
        """Measure SSE connection latency"""
        # This would be updated by actual SSE connections
        # For now, return last known value
        return self.last_sse_latency

    def update_sse_latency(self, latency: float):
        """Update SSE latency from actual measurements"""
        self.last_sse_latency = latency
        sse_latency.set(latency)

    def update_system_metrics(self):
        """Update system-level metrics"""
        # Uptime
        uptime = time.time() - BOOT_TIME
        system_uptime.set(uptime)

        # CPU usage
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_usage.set(cpu_percent)
        except Exception:
            pass

        # Memory usage
        try:
            memory = psutil.virtual_memory()
            memory_mb = memory.used / 1024 / 1024
            memory_usage.set(memory_mb)
        except Exception:
            pass

    def record_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def record_cache_hit(self):
        """Record a cache hit"""
        cache_hits.inc()

    def record_cache_miss(self):
        """Record a cache miss"""
        cache_misses.inc()

    def record_cache_set(self):
        """Record a cache set operation"""
        cache_set_operations.inc()

    def record_ai_request(self, model: str, latency: float, tokens: int = 0):
        """Record AI request metrics"""
        ai_requests.labels(model=model).inc()
        ai_latency.labels(model=model).observe(latency)
        if tokens > 0:
            ai_tokens_used.labels(model=model).inc(tokens)

    def record_llm_token_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        endpoint: str = "chat",
    ):
        """Record detailed LLM token usage metrics.

        Args:
            model: Model name (e.g., 'gemini-3-flash-preview')
            prompt_tokens: Number of input/prompt tokens
            completion_tokens: Number of output/completion tokens
            cost_usd: Cost in USD for this request
            endpoint: API endpoint that triggered the request
        """
        # Increment counters
        llm_prompt_tokens.labels(model=model, endpoint=endpoint).inc(prompt_tokens)
        llm_completion_tokens.labels(model=model, endpoint=endpoint).inc(completion_tokens)
        llm_cost_usd.labels(model=model).inc(cost_usd)

        # Record token distributions
        if prompt_tokens > 0:
            llm_request_tokens.labels(model=model, type="prompt").observe(prompt_tokens)
        if completion_tokens > 0:
            llm_request_tokens.labels(model=model, type="completion").observe(completion_tokens)

        # Also update legacy counter for backward compatibility
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens > 0:
            ai_tokens_used.labels(model=model).inc(total_tokens)

    def update_db_connections(self, count: int):
        """Update database connection count"""
        db_connections_active.set(count)

    def record_db_query(self, duration: float):
        """Record database query duration"""
        db_query_duration.observe(duration)

    def record_rag_query(
        self,
        collection: str,
        route_used: str,
        status: str,
        context_tokens: int = 0,
    ):
        """Record a RAG query with routing and status info.

        Args:
            collection: Collection searched (e.g., 'visa_oracle', 'legal_unified')
            route_used: Routing method ('fast', 'pro', 'deep_think', 'federated')
            status: Query outcome ('success', 'error', 'fallback', 'cache_hit')
            context_tokens: Number of tokens in the context (for histogram)
        """
        rag_queries_total.labels(
            collection=collection,
            route_used=route_used,
            status=status
        ).inc()

        if context_tokens > 0:
            rag_context_length.labels(collection=collection).observe(context_tokens)

    def record_tool_call(self, tool_name: str, status: str):
        """Record a tool call in agentic RAG.

        Args:
            tool_name: Name of the tool (e.g., 'vector_search', 'pricing', 'calculator')
            status: Call outcome ('success', 'error', 'timeout')
        """
        rag_tool_calls_total.labels(tool_name=tool_name, status=status).inc()

    def record_llm_fallback(self, from_model: str, to_model: str):
        """Record an LLM model fallback event.

        Args:
            from_model: Model that failed (e.g., 'gemini-3-flash-preview')
            to_model: Fallback model used (e.g., 'gemini-2.0-flash')
        """
        rag_fallback_count.labels(from_model=from_model, to_model=to_model).inc()


# Global metrics collector instance
metrics_collector = MetricsCollector()


async def get_active_sessions_count() -> int:
    """Get count of active sessions"""
    # This would be implemented based on your session management
    # For now, return the stored value
    return metrics_collector.session_count


async def collect_all_metrics():
    """Collect all metrics for Prometheus endpoint"""
    # Update system metrics
    metrics_collector.update_system_metrics()

    # Measure Redis latency
    await metrics_collector.measure_redis_latency()

    # Return Prometheus format
    return generate_latest()


def get_metrics_middleware():
    """Middleware to track request metrics"""
    import time

    from fastapi import Request

    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        metrics_collector.record_request(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            duration=duration,
        )

        return response

    return metrics_middleware
