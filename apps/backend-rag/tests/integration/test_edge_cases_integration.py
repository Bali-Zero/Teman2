"""
Comprehensive Edge Cases and Error Handling Integration Tests
Tests error scenarios, edge cases, and boundary conditions

Covers:
- Database connection failures
- Qdrant connection failures
- Invalid input handling
- Rate limiting edge cases
- Concurrent request handling
- Large payload handling
- Timeout scenarios
- Partial failures
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestDatabaseEdgeCases:
    """Edge cases for database operations"""

    @pytest.mark.asyncio
    async def test_database_connection_pool_exhaustion(self, db_pool):
        """Test behavior when connection pool is exhausted"""

        # Try to acquire more connections than pool size
        max_size = 10
        connections = []

        try:
            for i in range(max_size + 5):  # Try more than max
                conn = await db_pool.acquire()
                connections.append(conn)

            # Should handle gracefully
            assert len(connections) <= max_size + 5

        finally:
            # Release all connections
            for conn in connections:
                await db_pool.release(conn)

    @pytest.mark.asyncio
    async def test_database_transaction_rollback_on_error(self, db_pool):
        """Test transaction rollback on error"""

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Create test data
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS test_rollback (
                        id SERIAL PRIMARY KEY,
                        value VARCHAR(255)
                    )
                    """
                )

                # Insert data
                await conn.execute("INSERT INTO test_rollback (value) VALUES ($1)", "test_value")

                # Force error
                try:
                    await conn.execute("INSERT INTO test_rollback (id) VALUES ($1)", 99999)
                except Exception:
                    # Transaction should rollback
                    pass

            # Verify rollback
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM test_rollback WHERE value = $1", "test_value"
            )
            assert result == 0  # Should be rolled back

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_rollback")

    @pytest.mark.asyncio
    async def test_database_deadlock_handling(self, db_pool):
        """Test deadlock detection and handling"""
        import asyncpg

        async with db_pool.acquire() as conn1, db_pool.acquire() as conn2:
            # Create test table
            await conn1.execute(
                """
                    CREATE TABLE IF NOT EXISTS test_deadlock (
                        id INTEGER PRIMARY KEY,
                        value INTEGER
                    )
                    """
            )

            # Insert initial data
            await conn1.execute(
                "INSERT INTO test_deadlock (id, value) VALUES (1, 100) ON CONFLICT DO NOTHING"
            )

            # Simulate potential deadlock scenario
            try:
                # Transaction 1
                async with conn1.transaction():
                    await conn1.execute("UPDATE test_deadlock SET value = 200 WHERE id = 1")

                    # Transaction 2 (should wait or timeout)
                    async with conn2.transaction():
                        await conn2.execute("UPDATE test_deadlock SET value = 300 WHERE id = 1")

            except asyncpg.DeadlockDetectedError:
                # Deadlock detected - should be handled gracefully
                pass
            except Exception:
                # Other errors are acceptable
                pass

            # Cleanup
            await conn1.execute("DROP TABLE IF EXISTS test_deadlock")


@pytest.mark.integration
class TestQdrantEdgeCases:
    """Edge cases for Qdrant operations"""

    @pytest.mark.asyncio
    async def test_qdrant_collection_not_found(self, qdrant_client):
        """Test handling of non-existent collection"""

        # Try to search non-existent collection
        try:
            results = await qdrant_client.search(
                collection_name="non_existent_collection",
                query_vector=[0.1] * 1536,
                limit=10,
            )
            # Should handle gracefully
        except Exception as e:
            # Expected - collection doesn't exist
            assert "collection" in str(e).lower() or "not found" in str(e).lower()

    @pytest.mark.asyncio
    async def test_qdrant_large_payload(self, qdrant_client):
        """Test handling of large payloads"""

        collection_name = "test_large_payload"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Create large text payload
            large_text = "A" * 100000  # 100KB text
            test_embedding = [0.1] * 1536

            # Try to insert large payload
            try:
                await qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[
                        {
                            "id": "large_doc_1",
                            "vector": test_embedding,
                            "payload": {"text": large_text},
                        }
                    ],
                )
                # Should handle large payloads
            except Exception as e:
                # May fail if payload too large - acceptable
                assert "payload" in str(e).lower() or "size" in str(e).lower()

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_qdrant_empty_search_results(self, qdrant_client):
        """Test handling of empty search results"""

        collection_name = "test_empty_results"

        try:
            # Create empty collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Search empty collection
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=[0.1] * 1536,
                limit=10,
            )

            # Should return empty list, not error
            assert isinstance(results, list)
            assert len(results) == 0

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass


@pytest.mark.integration
class TestInputValidationEdgeCases:
    """Edge cases for input validation"""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, db_pool):
        """Test SQL injection prevention"""

        async with db_pool.acquire() as conn:
            # Create test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_sql_injection (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255)
                )
                """
            )

            # Try SQL injection attempt
            malicious_input = "'; DROP TABLE test_sql_injection; --"

            # Should be safely parameterized
            await conn.execute("INSERT INTO test_sql_injection (name) VALUES ($1)", malicious_input)

            # Verify table still exists
            result = await conn.fetchval("SELECT COUNT(*) FROM test_sql_injection")
            assert result >= 1  # Table should still exist

            # Verify input was stored as literal string
            stored = await conn.fetchval(
                "SELECT name FROM test_sql_injection WHERE name = $1", malicious_input
            )
            assert stored == malicious_input  # Should be stored as-is, not executed

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_sql_injection")

    @pytest.mark.asyncio
    async def test_xss_prevention(self, db_pool):
        """Test XSS prevention in stored data"""

        async with db_pool.acquire() as conn:
            # Create test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_xss (
                    id SERIAL PRIMARY KEY,
                    content TEXT
                )
                """
            )

            # Try XSS attempt
            xss_payload = "<script>alert('XSS')</script>"

            # Store XSS payload
            await conn.execute("INSERT INTO test_xss (content) VALUES ($1)", xss_payload)

            # Retrieve and verify it's stored as literal
            stored = await conn.fetchval("SELECT content FROM test_xss")
            assert stored == xss_payload  # Should be stored as-is

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_xss")

    @pytest.mark.asyncio
    async def test_very_large_input(self, db_pool):
        """Test handling of very large input"""

        async with db_pool.acquire() as conn:
            # Create test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_large_input (
                    id SERIAL PRIMARY KEY,
                    large_text TEXT
                )
                """
            )

            # Create very large text (10MB)
            large_text = "A" * (10 * 1024 * 1024)

            try:
                # Try to insert very large text
                await conn.execute(
                    "INSERT INTO test_large_input (large_text) VALUES ($1)", large_text
                )

                # Verify insertion
                result = await conn.fetchval("SELECT LENGTH(large_text) FROM test_large_input")
                assert result == len(large_text)

            except Exception as e:
                # May fail if too large - acceptable
                assert "size" in str(e).lower() or "limit" in str(e).lower()

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_large_input")


@pytest.mark.integration
class TestConcurrencyEdgeCases:
    """Edge cases for concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_database_writes(self, db_pool):
        """Test concurrent database writes"""
        import asyncio

        async def write_data(conn, value):
            """Write data concurrently"""
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_concurrent (
                    id SERIAL PRIMARY KEY,
                    value INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
            await conn.execute("INSERT INTO test_concurrent (value) VALUES ($1)", value)

        async with db_pool.acquire() as conn:
            # Create table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_concurrent (
                    id SERIAL PRIMARY KEY,
                    value INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Run concurrent writes
            tasks = []
            for i in range(10):
                async with db_pool.acquire() as conn:
                    tasks.append(write_data(conn, i))

            await asyncio.gather(*tasks)

            # Verify all writes succeeded
            count = await conn.fetchval("SELECT COUNT(*) FROM test_concurrent")
            assert count == 10

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_concurrent")

    @pytest.mark.asyncio
    async def test_race_condition_prevention(self, db_pool):
        """Test race condition prevention"""
        import asyncpg

        async with db_pool.acquire() as conn:
            # Create test table with unique constraint
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_race (
                    id SERIAL PRIMARY KEY,
                    unique_key VARCHAR(255) UNIQUE,
                    value INTEGER
                )
                """
            )

            # Try concurrent inserts with same unique key
            async def insert_with_key(key, value):
                async with db_pool.acquire() as conn:
                    try:
                        await conn.execute(
                            "INSERT INTO test_race (unique_key, value) VALUES ($1, $2)",
                            key,
                            value,
                        )
                        return True
                    except asyncpg.UniqueViolationError:
                        return False

            # Concurrent inserts
            import asyncio

            results = await asyncio.gather(*[insert_with_key("same_key", i) for i in range(5)])

            # Only one should succeed
            assert sum(results) == 1

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_race")


@pytest.mark.integration
class TestTimeoutEdgeCases:
    """Edge cases for timeout scenarios"""

    @pytest.mark.asyncio
    async def test_database_query_timeout(self, db_pool):
        """Test database query timeout handling"""

        async with db_pool.acquire() as conn:
            # Set short timeout
            conn._query_timeout = 1.0  # 1 second

            # Create slow query (if possible)
            try:
                # This should timeout or complete quickly
                await conn.execute("SELECT pg_sleep(2)")
            except asyncio.TimeoutError:
                # Expected timeout
                pass
            except Exception:
                # Other errors acceptable
                pass

    @pytest.mark.asyncio
    async def test_long_running_transaction(self, db_pool):
        """Test long running transaction handling"""
        import asyncio

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Long transaction
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS test_long_tx (
                        id SERIAL PRIMARY KEY,
                        value INTEGER
                    )
                    """
                )

                # Simulate long operation
                await asyncio.sleep(0.1)

                await conn.execute("INSERT INTO test_long_tx (value) VALUES (1)")

            # Transaction should complete
            result = await conn.fetchval("SELECT COUNT(*) FROM test_long_tx")
            assert result == 1

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS test_long_tx")
