from __future__ import annotations

import asyncio

from backend.app.setup.route_walk import iter_leaf_routes
from backend.services.misc import performance_optimizer as perf_module
from backend.services.misc.performance_optimizer import (
    AsyncLRUCache,
    BatchProcessor,
    ConnectionPool,
    MemoryOptimizer,
    OptimizedSearchService,
    PerformanceMonitor,
    async_timed,
    create_optimized_app,
    timed,
)


def test_performance_monitor_records_requests_components_and_rates() -> None:
    monitor = PerformanceMonitor()

    monitor.record_request(0.5, cache_hit=True)
    monitor.record_request(1.5, cache_hit=False)
    monitor.record_component_time("search_time", 0.25)
    monitor.record_component_time("unknown_component", 1.0)

    metrics = monitor.get_metrics()

    assert metrics["request_count"] == 2
    assert metrics["total_time"] == 2.0
    assert metrics["avg_response_time"] == 1.0
    assert metrics["cache_hit_rate"] == 0.5
    assert metrics["search_time"] == 0.25
    assert metrics["requests_per_second"] == 1.0


async def test_async_timed_records_component_time(monkeypatch) -> None:
    monitor = PerformanceMonitor()
    monkeypatch.setattr(perf_module, "perf_monitor", monitor)

    @async_timed("llm_time")
    async def run(value: int) -> int:
        return value + 1

    assert await run(1) == 2
    assert monitor.get_metrics()["llm_time"] >= 0


def test_timed_records_component_time(monkeypatch) -> None:
    monitor = PerformanceMonitor()
    monkeypatch.setattr(perf_module, "perf_monitor", monitor)

    @timed("search_time")
    def run(value: int) -> int:
        return value + 1

    assert run(1) == 2
    assert monitor.get_metrics()["search_time"] >= 0


async def test_async_lru_cache_get_set_ttl_eviction_and_clear(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr(perf_module.time, "time", lambda: now)
    cache = AsyncLRUCache(maxsize=1, ttl=10)

    await cache.set("a", 1)
    assert await cache.get("a") == 1

    await cache.set("b", 2)
    assert await cache.get("a") is None
    assert await cache.get("b") == 2

    now = 111.0
    assert await cache.get("b") is None

    await cache.set("c", 3)
    await cache.clear()
    assert await cache.get("c") is None


async def test_connection_pool_reuses_connections_and_closes_when_full() -> None:
    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    pool = ConnectionPool(max_connections=1)
    first = FakeConnection()
    second = FakeConnection()

    await pool.return_connection(first)
    await pool.return_connection(second)

    assert second.closed is True
    assert await pool.get_connection() is first


async def test_batch_processor_processes_concurrent_requests() -> None:
    class EchoBatchProcessor(BatchProcessor):
        async def _process_batch_items(self, batch: list[dict[str, object]]) -> list[object]:
            return [item["value"] for item in batch]

    processor = EchoBatchProcessor(batch_size=2, max_wait=0.05)

    assert await asyncio.gather(
        processor.add_request({"value": "a"}),
        processor.add_request({"value": "b"}),
    ) == ["a", "b"]


async def test_optimized_search_service_caches_embeddings_and_search(monkeypatch) -> None:
    class FakeEmbedding:
        def tolist(self) -> list[float]:
            return [0.1, 0.2]

    class FakeEmbeddingModel:
        def __init__(self) -> None:
            self.calls = 0

        def encode(self, _text: str) -> FakeEmbedding:
            self.calls += 1
            return FakeEmbedding()

    class FakeOriginal:
        def __init__(self) -> None:
            self.embedding_model = FakeEmbeddingModel()
            self.search_calls = 0

        def search_with_embedding(
            self,
            embedding: list[float],
            k: int,
        ) -> list[dict[str, object]]:
            self.search_calls += 1
            return [{"embedding": embedding, "k": k}]

    monkeypatch.setattr(perf_module, "embedding_cache", AsyncLRUCache(maxsize=10, ttl=60))
    monkeypatch.setattr(perf_module, "search_cache", AsyncLRUCache(maxsize=10, ttl=60))
    monkeypatch.setattr(perf_module, "perf_monitor", PerformanceMonitor())
    original = FakeOriginal()
    service = OptimizedSearchService(original)

    first = await service.search_cached("visa", k=3)
    second = await service.search_cached("visa", k=3)

    assert first == [{"embedding": [0.1, 0.2], "k": 3}]
    assert second == first
    assert original.embedding_model.calls == 1
    assert original.search_calls == 1


def test_create_optimized_app_registers_expected_routes() -> None:
    app = create_optimized_app()
    route_paths = {route.path for route in iter_leaf_routes(app)}

    assert app.title == "ZANTARA RAG API - Optimized"
    assert "/metrics" in route_paths
    assert "/clear-cache" in route_paths


def test_memory_optimizer_returns_static_settings() -> None:
    assert MemoryOptimizer.optimize_chroma_settings()["allow_reset"] is False
    assert MemoryOptimizer.optimize_embedding_model() == {
        "device": "cpu",
        "normalize_embeddings": True,
        "batch_size": 32,
    }
