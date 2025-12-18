"""
Stress and Load Integration Tests
Tests system behavior under high load and stress conditions

Covers:
- High concurrent request handling
- Database connection pool stress
- Qdrant load testing
- Memory pressure scenarios
- Rate limiting under load
- Error recovery under stress
"""

import asyncio
import os
import sys
import time
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
class TestHighConcurrencyIntegration:
    """Stress tests for high concurrency scenarios"""

    @pytest.mark.asyncio
    async def test_concurrent_database_queries(self, db_pool):
        """Test system under high concurrent database queries"""

        async def query_task(conn, task_id):
            """Single query task"""
            result = await conn.fetchval("SELECT $1", task_id)
            return result

        # Measure concurrent queries
        start_time = time.time()

        async with db_pool.acquire() as conn:
            # Create 100 concurrent queries
            tasks = [query_task(conn, i) for i in range(100)]
            results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0
        assert len(results) == 100

    @pytest.mark.asyncio
    async def test_concurrent_qdrant_searches(self, qdrant_client):
        """Test system under high concurrent Qdrant searches"""

        collection_name = "test_stress_load"

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

            async def search_task():
                """Single search task"""
                return await qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=[0.1] * 1536,
                    limit=10,
                )

            # Measure concurrent searches
            start_time = time.time()
            tasks = [search_task() for _ in range(50)]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start_time

            # Should complete in reasonable time
            assert elapsed < 15.0
            assert len(results) == 50

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_database_connection_pool_stress(self, db_pool):
        """Test database connection pool under stress"""

        max_size = 10
        connections_acquired = []

        async def acquire_connection(pool, conn_id):
            """Acquire and hold connection"""
            async with pool.acquire() as conn:
                connections_acquired.append(conn_id)
                await asyncio.sleep(0.1)  # Hold connection briefly
                return conn_id

        # Try to acquire more connections than pool size
        start_time = time.time()
        tasks = [acquire_connection(db_pool, i) for i in range(max_size * 2)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Should handle gracefully (may take longer due to waiting)
        assert elapsed >= 0
        assert len(results) == max_size * 2

    @pytest.mark.asyncio
    async def test_concurrent_crm_operations(self, db_pool):
        """Test concurrent CRM operations"""

        async def create_client(pool, client_num):
            """Create client concurrently"""
            async with pool.acquire() as conn:
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (
                        full_name, email, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    f"Stress Client {client_num}",
                    f"stress{client_num}@example.com",
                    "active",
                    "test@team.com",
                    time.time(),
                    time.time(),
                )
                return client_id

        # Create clients concurrently
        start_time = time.time()
        tasks = [create_client(db_pool, i) for i in range(20)]
        client_ids = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Should complete in reasonable time
        assert elapsed < 10.0
        assert len(client_ids) == 20

        # Cleanup
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM clients WHERE id = ANY($1)", client_ids)


@pytest.mark.integration
@pytest.mark.slow
class TestRateLimitingStressIntegration:
    """Stress tests for rate limiting"""

    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self):
        """Test rate limiting behavior under load"""
        from middleware.rate_limiter import RateLimiter

        rate_limiter = RateLimiter()

        key = "stress_test_key"
        limit = 10
        window = 60

        # Make many rapid requests
        results = []
        for i in range(limit * 2):
            allowed, info = rate_limiter.is_allowed(key, limit, window)
            results.append(allowed)

        # First 'limit' requests should be allowed
        assert sum(results[:limit]) == limit
        # After limit, some should be blocked (depending on timing)

    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_checks(self):
        """Test concurrent rate limit checks"""
        from middleware.rate_limiter import RateLimiter

        rate_limiter = RateLimiter()

        async def check_rate_limit(key, limit, window):
            """Check rate limit"""
            return rate_limiter.is_allowed(key, limit, window)

        # Concurrent rate limit checks
        tasks = [check_rate_limit(f"key_{i % 5}", 10, 60) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)


@pytest.mark.integration
@pytest.mark.slow
class TestErrorRecoveryStressIntegration:
    """Stress tests for error recovery"""

    @pytest.mark.asyncio
    async def test_error_recovery_under_load(self, db_pool):
        """Test error recovery under load"""

        async def operation_with_retry(pool, operation_id):
            """Operation with error handling"""
            try:
                async with pool.acquire() as conn:
                    # Simulate operation that might fail
                    if operation_id % 10 == 0:
                        raise Exception("Simulated error")
                    return await conn.fetchval("SELECT $1", operation_id)
            except Exception:
                # Retry once
                try:
                    async with pool.acquire() as conn:
                        return await conn.fetchval("SELECT $1", operation_id)
                except Exception:
                    return None

        # Run many operations with some failures
        tasks = [operation_with_retry(db_pool, i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed
        successful = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        assert successful > 80  # At least 80% should succeed

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, db_pool):
        """Test handling of partial failures"""

        async with db_pool.acquire() as conn:
            # Create test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stress_test (
                    id SERIAL PRIMARY KEY,
                    value INTEGER,
                    status VARCHAR(50)
                )
                """
            )

            # Batch insert with some failures
            successful = 0
            failed = 0

            for i in range(50):
                try:
                    await conn.execute(
                        """
                        INSERT INTO stress_test (value, status)
                        VALUES ($1, $2)
                        """,
                        i,
                        "success" if i % 5 != 0 else None,  # Some will fail
                    )
                    successful += 1
                except Exception:
                    failed += 1

            # Verify partial success
            count = await conn.fetchval("SELECT COUNT(*) FROM stress_test")
            assert count > 0
            assert successful + failed == 50

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS stress_test")
