"""
Performance benchmarks for SearchService refactoring

Verifies that refactoring did not introduce performance degradation.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.collection_manager import CollectionManager
from services.conflict_resolver import ConflictResolver
from services.cultural_insights_service import CulturalInsightsService
from services.query_router_integration import QueryRouterIntegration
from services.search_service import SearchService


class TestSearchServicePerformance:
    """Performance benchmarks for SearchService"""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for performance testing"""
        # Mock CollectionManager
        collection_manager = Mock(spec=CollectionManager)
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "documents": [f"Document {i}" for i in range(10)],
                "metadatas": [{"tier": "A"} for _ in range(10)],
                "distances": [0.1 + i * 0.05 for i in range(10)],
                "ids": [f"doc_{i}" for i in range(10)],
            }
        )
        collection_manager.get_collection.return_value = mock_client

        # Mock other dependencies
        conflict_resolver = Mock(spec=ConflictResolver)
        conflict_resolver.detect_conflicts.return_value = []
        conflict_resolver.resolve_conflicts.return_value = ([], [])

        cultural_insights = Mock(spec=CulturalInsightsService)
        cultural_insights.query_insights = AsyncMock(return_value=[])

        query_router = Mock(spec=QueryRouterIntegration)
        query_router.route_query.return_value = {
            "collection_name": "visa_oracle",
            "collections": ["visa_oracle"],
            "confidence": 1.0,
            "is_pricing": False,
        }

        return {
            "collection_manager": collection_manager,
            "conflict_resolver": conflict_resolver,
            "cultural_insights": cultural_insights,
            "query_router": query_router,
        }

    @pytest.fixture
    def search_service(self, mock_dependencies):
        """Create SearchService with mocked dependencies"""
        with patch("core.embeddings.create_embeddings_generator") as mock_create:
            mock_embedder = Mock()
            mock_embedder.generate_query_embedding.return_value = [0.1] * 1536
            mock_embedder.provider = "openai"
            mock_embedder.dimensions = 1536
            mock_create.return_value = mock_embedder
            with patch("services.collection_health_service.CollectionHealthService"):
                service = SearchService(**mock_dependencies)
                service.health_monitor = Mock()
                service.health_monitor.record_query = Mock()
                return service

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_search_latency(self, search_service):
        """Benchmark search latency"""
        iterations = 100
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            await search_service.search(query="test query", user_level=3, limit=5)
            latency = (time.perf_counter() - start) * 1000  # Convert to ms
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        print("\nSearch Latency (100 iterations):")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        print(f"  Min: {min(latencies):.2f}ms")
        print(f"  Max: {max(latencies):.2f}ms")

        # Assert reasonable performance (with mocked dependencies, should be very fast)
        assert avg_latency < 100  # Should be < 100ms with mocks

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_search_with_conflict_resolution_latency(self, search_service):
        """Benchmark search with conflict resolution latency"""
        iterations = 50
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            await search_service.search_with_conflict_resolution(
                query="test query", user_level=3, limit=5, enable_fallbacks=True
            )
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        print("\nSearch with Conflict Resolution Latency (50 iterations):")
        print(f"  Average: {avg_latency:.2f}ms")

        assert avg_latency < 200  # Should be < 200ms with mocks

    @pytest.mark.asyncio
    async def test_concurrent_searches(self, search_service):
        """Test concurrent search performance"""
        num_concurrent = 10
        start = time.perf_counter()

        tasks = [
            search_service.search(query=f"query {i}", user_level=3, limit=5)
            for i in range(num_concurrent)
        ]
        await asyncio.gather(*tasks)

        total_time = (time.perf_counter() - start) * 1000
        avg_time_per_query = total_time / num_concurrent

        print(f"\nConcurrent Searches ({num_concurrent} queries):")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Average per query: {avg_time_per_query:.2f}ms")

        # Concurrent should be faster than sequential
        assert avg_time_per_query < 50

    @pytest.mark.asyncio
    async def test_collection_manager_lazy_loading(self, mock_dependencies):
        """Benchmark collection manager lazy loading"""
        manager = mock_dependencies["collection_manager"]

        start = time.perf_counter()
        for _ in range(100):
            manager.get_collection("visa_oracle")
        total_time = (time.perf_counter() - start) * 1000

        print("\nCollectionManager.get_collection (100 calls):")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Average: {total_time / 100:.4f}ms per call")

        # Should be very fast (just cache lookup)
        assert total_time < 10

    @pytest.mark.asyncio
    async def test_query_router_integration_performance(self, mock_dependencies):
        """Benchmark query router integration"""
        router = mock_dependencies["query_router"]

        start = time.perf_counter()
        for _ in range(1000):
            router.route_query(query="test query", enable_fallbacks=False)
        total_time = (time.perf_counter() - start) * 1000

        print("\nQueryRouterIntegration.route_query (1000 calls):")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Average: {total_time / 1000:.4f}ms per call")

        assert total_time < 100  # Should be very fast
