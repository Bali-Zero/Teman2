"""
Performance Optimization Enhancements
For ZANTARA RAG Backend Python
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)

# Global thread pool for CPU-bound operations
thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag_")


class PerformanceMonitor:
    """Monitor and log performance metrics"""

    def __init__(self):
        self.metrics = {
            "request_count": 0,
            "total_time": 0,
            "avg_response_time": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "embedding_time": 0,
            "search_time": 0,
            "llm_time": 0,
        }
        self.lock = threading.Lock()

    def record_request(self, duration: float, cache_hit: bool = False):
        with self.lock:
            self.metrics["request_count"] += 1
            self.metrics["total_time"] += duration
            self.metrics["avg_response_time"] = (
                self.metrics["total_time"] / self.metrics["request_count"]
            )

            if cache_hit:
                self.metrics["cache_hits"] += 1
            else:
                self.metrics["cache_misses"] += 1

    def record_component_time(self, component: str, duration: float):
        with self.lock:
            if component in self.metrics:
                self.metrics[component] += duration

    def get_metrics(self) -> dict[str, Any]:
        with self.lock:
            cache_hit_rate = 0
            if self.metrics["cache_hits"] + self.metrics["cache_misses"] > 0:
                cache_hit_rate = self.metrics["cache_hits"] / (
                    self.metrics["cache_hits"] + self.metrics["cache_misses"]
                )

            return {
                **self.metrics,
                "cache_hit_rate": cache_hit_rate,
                "requests_per_second": self.metrics["request_count"]
                / max(self.metrics["total_time"], 1),
            }


# Global performance monitor
perf_monitor = PerformanceMonitor()


def async_timed(component: str = "request"):
    """Decorator to time async functions"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                perf_monitor.record_component_time(component, duration)
                logger.debug(f"{func.__name__} took {duration:.3f}s")

        return wrapper

    return decorator


def timed(component: str = "request"):
    """Decorator to time sync functions"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                perf_monitor.record_component_time(component, duration)
                logger.debug(f"{func.__name__} took {duration:.3f}s")

        return wrapper

    return decorator


class AsyncLRUCache:
    """Async-safe LRU cache with TTL"""

    def __init__(self, maxsize: int = 128, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = {}
        self.timestamps = {}
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self.lock:
            if key in self.cache:
                # Check TTL
                if time.time() - self.timestamps[key] < self.ttl:
                    return self.cache[key]
                else:
                    # Expired
                    del self.cache[key]
                    del self.timestamps[key]
            return None

    async def set(self, key: str, value: Any):
        async with self.lock:
            # Implement LRU eviction if needed
            if len(self.cache) >= self.maxsize and key not in self.cache:
                # Remove oldest entry
                oldest_key = min(self.timestamps.keys(), key=lambda k: self.timestamps[k])
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]

            self.cache[key] = value
            self.timestamps[key] = time.time()

    async def clear(self):
        async with self.lock:
            self.cache.clear()
            self.timestamps.clear()


# Global caches
embedding_cache = AsyncLRUCache(maxsize=500, ttl=3600)  # 1 hour TTL
search_cache = AsyncLRUCache(maxsize=200, ttl=300)  # 5 minute TTL


class ConnectionPool:
    """Simple connection pool for HTTP clients"""

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections = asyncio.Queue(maxsize=max_connections)
        self.created_connections = 0
        self.lock = asyncio.Lock()

    async def get_connection(self):
        """Get a connection from pool or create new one"""
        try:
            # Try to get existing connection
            return self.connections.get_nowait()
        except asyncio.QueueEmpty:
            async with self.lock:
                if self.created_connections < self.max_connections:
                    # Create new connection (this would be actual HTTP client)
                    import httpx

                    client = httpx.AsyncClient(
                        timeout=30.0,
                        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                    )
                    self.created_connections += 1
                    return client
                else:
                    # Wait for available connection
                    return await self.connections.get()

    async def return_connection(self, connection):
        """Return connection to pool"""
        try:
            self.connections.put_nowait(connection)
        except asyncio.QueueFull:
            # Pool is full, close connection
            await connection.aclose()


# Global connection pool
http_pool = ConnectionPool()


class BatchProcessor:
    """Process multiple requests in batches for efficiency"""

    def __init__(self, batch_size: int = 10, max_wait: float = 0.1):
        self.batch_size = batch_size
        self.max_wait = max_wait
        self.queue = asyncio.Queue()
        self.processing = False

    async def add_request(self, request_data: dict[str, Any]) -> Any:
        """Add request to batch and wait for result"""
        future = asyncio.Future()
        await self.queue.put((request_data, future))

        # Start processing if not already running
        if not self.processing:
            asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self):
        """Process requests in batches"""
        if self.processing:
            return

        self.processing = True
        try:
            while True:
                batch = []
                futures = []

                # Collect batch
                start_time = time.time()
                while len(batch) < self.batch_size and time.time() - start_time < self.max_wait:
                    try:
                        item = await asyncio.wait_for(self.queue.get(), timeout=0.01)
                        batch.append(item[0])
                        futures.append(item[1])
                    except asyncio.TimeoutError:
                        break

                if not batch:
                    break

                # Process batch
                try:
                    results = await self._process_batch_items(batch)
                    for future, result in zip(futures, results, strict=True):
                        future.set_result(result)
                except Exception as e:
                    for future in futures:
                        future.set_exception(e)
        finally:
            self.processing = False

    async def _process_batch_items(self, batch: list[dict[str, Any]]) -> list[Any]:
        """Override this method to implement actual batch processing"""
        # Default: process individually
        results = []
        for item in batch:
            # This would be replaced with actual batch processing logic
            results.append(f"Processed: {item}")
        return results


class OptimizedSearchService:
    """Performance-optimized search service"""

    def __init__(self, original_search_service):
        self.original = original_search_service
        self.batch_processor = BatchProcessor(batch_size=5, max_wait=0.05)

    @async_timed("embedding")
    async def get_embedding_cached(self, text: str) -> list[float]:
        """Get embedding with caching"""
        cache_key = f"emb:{hash(text)}"

        # Check cache first
        cached = await embedding_cache.get(cache_key)
        if cached:
            perf_monitor.record_request(0, cache_hit=True)
            return cached

        # Compute embedding
        embedding = await self._compute_embedding(text)
        await embedding_cache.set(cache_key, embedding)
        perf_monitor.record_request(0, cache_hit=False)
        return embedding

    async def _compute_embedding(self, text: str) -> list[float]:
        """Compute embedding using original service"""
        # Run in thread pool for CPU-bound work
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            thread_pool, lambda: self.original.embedding_model.encode(text).tolist()
        )

    @async_timed("search")
    async def search_cached(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search with caching and optimization"""
        cache_key = f"search:{hash(query)}:{k}"

        # Check cache
        cached = await search_cache.get(cache_key)
        if cached:
            return cached

        # Perform search
        embedding = await self.get_embedding_cached(query)
        results = await self._search_with_embedding(embedding, k)

        await search_cache.set(cache_key, results)
        return results

    async def _search_with_embedding(self, embedding: list[float], k: int) -> list[dict[str, Any]]:
        """Search using embedding"""
        # Run search in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            thread_pool, lambda: self.original.search_with_embedding(embedding, k)
        )


def create_optimized_app():
    """Create FastAPI app with performance optimizations"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="ZANTARA RAG API - Optimized",
        version="2.1.0-optimized",
        description="Performance-optimized RAG backend",
    )

    # Optimized CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://zantara.balizero.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event():
        """Initialize services with optimization"""
        logger.info("🚀 Starting optimized RAG backend...")
        # Initialize optimized services here

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown"""
        logger.info("🛑 Shutting down optimized RAG backend...")
        await embedding_cache.clear()
        await search_cache.clear()
        thread_pool.shutdown(wait=True)

    @app.get("/metrics")
    async def get_performance_metrics():
        """Get performance metrics"""
        return perf_monitor.get_metrics()

    @app.post("/clear-cache")
    async def clear_caches():
        """Clear all caches"""
        await embedding_cache.clear()
        await search_cache.clear()
        return {"status": "caches_cleared"}

    return app


# Performance optimization utilities
class MemoryOptimizer:
    """Memory usage optimization"""

    @staticmethod
    def optimize_chroma_settings():
        """Optimize Qdrant settings for production"""
        return {
            "anonymized_telemetry": False,
            "allow_reset": False,
            "chroma_db_impl": "duckdb+parquet",
            "persist_directory": "/tmp/chroma_optimized",
            "chroma_server_cors_allow_origins": [],
        }

    @staticmethod
    def optimize_embedding_model():
        """Optimize embedding model settings"""
        return {
            "device": "cpu",  # Use GPU if available
            "normalize_embeddings": True,
            "batch_size": 32,  # Optimize based on memory
        }


# Export optimized components
__all__ = [
    "PerformanceMonitor",
    "perf_monitor",
    "async_timed",
    "timed",
    "AsyncLRUCache",
    "embedding_cache",
    "search_cache",
    "ConnectionPool",
    "http_pool",
    "BatchProcessor",
    "OptimizedSearchService",
    "create_optimized_app",
    "MemoryOptimizer",
]
