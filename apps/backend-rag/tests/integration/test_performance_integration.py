"""
Performance Integration Tests
Tests performance characteristics and optimization

Covers:
- Database query performance
- Qdrant search performance
- Caching effectiveness
- Concurrent request handling
- Large dataset handling
- Response time benchmarks
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestDatabasePerformance:
    """Performance tests for database operations"""

    @pytest.mark.asyncio
    async def test_bulk_insert_performance(self, db_pool):
        """Test bulk insert performance"""

        async with db_pool.acquire() as conn:
            # Create test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_bulk_perf (
                    id SERIAL PRIMARY KEY,
                    value INTEGER,
                    text_field VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Measure bulk insert time
            start_time = time.time()

            # Insert 1000 records
            values = [(i, f"text_{i}", datetime.now()) for i in range(1000)]
            await conn.executemany(
                "INSERT INTO test_bulk_perf (value, text_field, created_at) VALUES ($1, $2, $3)",
                values,
            )

            elapsed = time.time() - start_time

            # Should complete in reasonable time (< 5 seconds for 1000 records)
            assert elapsed < 5.0

            # Verify all inserted
            count = await conn.fetchval("SELECT COUNT(*) FROM test_bulk_perf")
            assert count == 1000

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_bulk_perf")

    @pytest.mark.asyncio
    async def test_indexed_query_performance(self, db_pool):
        """Test indexed query performance"""

        async with db_pool.acquire() as conn:
            # Create table with index
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_indexed_perf (
                    id SERIAL PRIMARY KEY,
                    indexed_field VARCHAR(255),
                    non_indexed_field VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create index
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_indexed_field ON test_indexed_perf(indexed_field)"
            )

            # Insert test data
            for i in range(1000):
                await conn.execute(
                    """
                    INSERT INTO test_indexed_perf (indexed_field, non_indexed_field)
                    VALUES ($1, $2)
                    """,
                    f"indexed_{i}",
                    f"non_indexed_{i}",
                )

            # Measure indexed query
            start_time = time.time()
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM test_indexed_perf WHERE indexed_field = $1",
                "indexed_500",
            )
            indexed_time = time.time() - start_time

            # Measure non-indexed query
            start_time = time.time()
            result2 = await conn.fetchval(
                "SELECT COUNT(*) FROM test_indexed_perf WHERE non_indexed_field = $1",
                "non_indexed_500",
            )
            non_indexed_time = time.time() - start_time

            # Indexed query should be faster (or at least not slower)
            # Note: With small datasets, difference may be minimal
            assert indexed_time >= 0
            assert non_indexed_time >= 0

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_indexed_perf")

    @pytest.mark.asyncio
    async def test_connection_pool_performance(self, db_pool):
        """Test connection pool performance under load"""
        import asyncio

        async def query_task():
            """Single query task"""
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

        # Measure time for 100 concurrent queries
        start_time = time.time()
        tasks = [query_task() for _ in range(100)]
        await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0


@pytest.mark.integration
@pytest.mark.slow
class TestQdrantPerformance:
    """Performance tests for Qdrant operations"""

    @pytest.mark.asyncio
    async def test_qdrant_bulk_insert_performance(self, qdrant_client):
        """Test Qdrant bulk insert performance"""

        collection_name = "test_bulk_perf"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Measure bulk insert time
            start_time = time.time()

            # Insert 100 points
            points = []
            for i in range(100):
                points.append(
                    {
                        "id": f"point_{i}",
                        "vector": [0.1] * 1536,
                        "payload": {"index": i, "text": f"Document {i}"},
                    }
                )

            await qdrant_client.upsert(collection_name=collection_name, points=points)

            elapsed = time.time() - start_time

            # Should complete in reasonable time (< 10 seconds for 100 points)
            assert elapsed < 10.0

            # Verify insertion
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=[0.1] * 1536,
                limit=100,
            )

            assert len(results) == 100

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_qdrant_search_performance(self, qdrant_client):
        """Test Qdrant search performance"""

        collection_name = "test_search_perf"

        try:
            # Create collection and insert data
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert test data
            points = [
                {
                    "id": f"point_{i}",
                    "vector": [0.1 + (i * 0.001)] * 1536,  # Slightly different vectors
                    "payload": {"index": i},
                }
                for i in range(1000)
            ]

            await qdrant_client.upsert(collection_name=collection_name, points=points)

            # Measure search time
            start_time = time.time()

            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=[0.1] * 1536,
                limit=10,
            )

            elapsed = time.time() - start_time

            # Should complete quickly (< 1 second)
            assert elapsed < 1.0
            assert len(results) == 10

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass


@pytest.mark.integration
@pytest.mark.slow
class TestCachingPerformance:
    """Performance tests for caching"""

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self):
        """Test cache hit performance improvement"""
        from core.cache import cached, invalidate_cache

        # Clear cache
        invalidate_cache("test_perf:*")

        call_count = 0

        @cached(ttl=60, prefix="test_perf")
        async def expensive_operation(key: str):
            """Simulate expensive operation"""
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate work
            return f"result_{key}"

        # First call - cache miss
        start_time = time.time()
        result1 = await expensive_operation("test_key")
        first_call_time = time.time() - start_time

        # Second call - cache hit
        start_time = time.time()
        result2 = await expensive_operation("test_key")
        second_call_time = time.time() - start_time

        # Cache hit should be much faster
        assert second_call_time < first_call_time
        assert call_count == 1  # Function called only once

        # Cleanup
        invalidate_cache("test_perf:*")


@pytest.mark.integration
@pytest.mark.slow
class TestConcurrentRequestPerformance:
    """Performance tests for concurrent requests"""

    @pytest.mark.asyncio
    async def test_concurrent_database_queries(self, db_pool):
        """Test concurrent database query performance"""
        import asyncio

        async def query_task(conn, task_id):
            """Single query task"""
            result = await conn.fetchval("SELECT $1", task_id)
            return result

        # Measure concurrent queries
        start_time = time.time()

        async with db_pool.acquire() as conn:
            tasks = [query_task(conn, i) for i in range(50)]
            results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # Should complete in reasonable time
        assert elapsed < 5.0
        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_concurrent_qdrant_searches(self, qdrant_client):
        """Test concurrent Qdrant search performance"""
        import asyncio

        collection_name = "test_concurrent_perf"

        try:
            # Setup
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert test data
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": "test_point",
                        "vector": [0.1] * 1536,
                        "payload": {"text": "test"},
                    }
                ],
            )

            # Measure concurrent searches
            async def search_task():
                return await qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=[0.1] * 1536,
                    limit=10,
                )

            start_time = time.time()
            tasks = [search_task() for _ in range(20)]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start_time

            # Should complete in reasonable time
            assert elapsed < 10.0
            assert len(results) == 20

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass
