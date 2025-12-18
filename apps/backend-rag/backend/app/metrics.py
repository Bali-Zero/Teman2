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

# Database Metrics
db_connections_active = Gauge("zantara_db_connections_active", "Active database connections")
db_query_duration = Histogram("zantara_db_query_duration_seconds", "Database query duration")
db_pool_size = Gauge("zantara_db_pool_size", "Database connection pool size", ["service"])
db_pool_idle = Gauge("zantara_db_pool_idle", "Database connection pool idle connections", ["service"])

# RAG Pipeline Metrics (Performance Debug Phase 1)
rag_embedding_duration = Histogram("zantara_rag_embedding_duration_seconds", "Embedding generation duration")
rag_vector_search_duration = Histogram("zantara_rag_vector_search_duration_seconds", "Vector search duration")
rag_reranking_duration = Histogram("zantara_rag_reranking_duration_seconds", "Reranking duration")
rag_pipeline_duration = Histogram("zantara_rag_pipeline_duration_seconds", "Total RAG pipeline duration")
rag_early_exit_total = Counter("zantara_rag_early_exit_total", "Total early exits (skipped reranking)")
rag_cache_hit_rate = Gauge("zantara_rag_cache_hit_rate", "RAG cache hit rate")
rag_parallel_searches = Counter("zantara_rag_parallel_searches_total", "Parallel collection searches executed")

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

    def update_db_connections(self, count: int):
        """Update database connection count"""
        db_connections_active.set(count)

    def record_db_query(self, duration: float):
        """Record database query duration"""
        db_query_duration.observe(duration)


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
