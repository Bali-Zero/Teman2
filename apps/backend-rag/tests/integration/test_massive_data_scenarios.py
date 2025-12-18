"""
Massive Data Scenarios Integration Tests
Tests system behavior with massive amounts of data

Covers:
- Large datasets
- Bulk operations
- Performance with large data
- Data pagination
- Large query results
"""

import os
import sys
from datetime import datetime, timedelta
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
class TestMassiveDataScenarios:
    """Massive data scenario integration tests"""

    @pytest.mark.asyncio
    async def test_massive_client_dataset(self, db_pool):
        """Test with massive client dataset"""

        async with db_pool.acquire() as conn:
            # Create 10,000 clients
            massive_count = 10000
            batch_size = 100

            for batch_start in range(0, massive_count, batch_size):
                batch_values = [
                    (
                        f"Massive Client {i}",
                        f"massive{i}@example.com",
                        f"+628123456789{i % 10000}",
                        "active",
                        "team@example.com",
                        datetime.now(),
                        datetime.now(),
                    )
                    for i in range(batch_start, min(batch_start + batch_size, massive_count))
                ]

                await conn.executemany(
                    """
                    INSERT INTO clients (
                        full_name, email, phone, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    batch_values,
                )

            # Verify massive dataset
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE email LIKE 'massive%@example.com'"
            )

            assert count == massive_count

            # Test pagination
            page_size = 100
            page = await conn.fetch(
                """
                SELECT id, full_name, email
                FROM clients
                WHERE email LIKE 'massive%@example.com'
                ORDER BY id
                LIMIT $1 OFFSET $2
                """,
                page_size,
                0,
            )

            assert len(page) == page_size

            # Test search performance
            search_start = datetime.now()
            search_results = await conn.fetch(
                """
                SELECT id, full_name
                FROM clients
                WHERE email LIKE 'massive%@example.com'
                AND full_name LIKE '%5000%'
                LIMIT 10
                """
            )
            search_time = (datetime.now() - search_start).total_seconds()

            assert len(search_results) > 0
            assert search_time < 5.0  # Should be fast even with large dataset

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE email LIKE 'massive%@example.com'")

    @pytest.mark.asyncio
    async def test_massive_practice_dataset(self, db_pool):
        """Test with massive practice dataset"""

        async with db_pool.acquire() as conn:
            # Create client first
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Massive Practice Client",
                "massive.practice@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create 5,000 practices
            practice_count = 5000
            practice_types = ["KITAS", "PT", "Tax", "Visa", "License"]

            batch_values = [
                (
                    client_id,
                    practice_types[i % len(practice_types)],
                    "in_progress" if i % 2 == 0 else "pending",
                    "high" if i % 3 == 0 else "medium",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )
                for i in range(practice_count)
            ]

            await conn.executemany(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, priority, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                batch_values,
            )

            # Verify massive practices
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM practices WHERE client_id = $1", client_id
            )

            assert count == practice_count

            # Test aggregation performance
            agg_start = datetime.now()
            stats = await conn.fetchrow(
                """
                SELECT
                    practice_type,
                    COUNT(*) as count,
                    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_count
                FROM practices
                WHERE client_id = $1
                GROUP BY practice_type
                ORDER BY count DESC
                """,
                client_id,
            )
            agg_time = (datetime.now() - agg_start).total_seconds()

            assert stats is not None
            assert agg_time < 3.0  # Should be fast

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_massive_interaction_dataset(self, db_pool):
        """Test with massive interaction dataset"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Massive Interaction Client",
                "massive.interaction@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create 20,000 interactions
            interaction_count = 20000
            interaction_types = ["chat", "email", "call", "meeting", "note"]

            batch_size = 500
            for batch_start in range(0, interaction_count, batch_size):
                batch_values = [
                    (
                        client_id,
                        interaction_types[i % len(interaction_types)],
                        f"Interaction {i}",
                        "positive" if i % 3 == 0 else "neutral",
                        "team@example.com",
                        datetime.now() - timedelta(days=i % 365),
                    )
                    for i in range(batch_start, min(batch_start + batch_size, interaction_count))
                ]

                await conn.executemany(
                    """
                    INSERT INTO interactions (
                        client_id, interaction_type, summary, sentiment, created_by, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    batch_values,
                )

            # Verify massive interactions
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM interactions WHERE client_id = $1", client_id
            )

            assert count == interaction_count

            # Test time-based queries
            recent_start = datetime.now()
            recent_interactions = await conn.fetch(
                """
                SELECT id, interaction_type, created_at
                FROM interactions
                WHERE client_id = $1
                AND created_at >= $2
                ORDER BY created_at DESC
                LIMIT 100
                """,
                client_id,
                datetime.now() - timedelta(days=7),
            )
            recent_time = (datetime.now() - recent_start).total_seconds()

            assert len(recent_interactions) <= 100
            assert recent_time < 2.0  # Should be fast with index

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_massive_qdrant_dataset(self, qdrant_client):
        """Test with massive Qdrant dataset"""

        collection_name = "massive_test"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert 10,000 vectors
            massive_count = 10000
            batch_size = 100

            for batch_start in range(0, massive_count, batch_size):
                points = [
                    {
                        "id": f"doc_{i}",
                        "vector": [0.1 + (i % 100) / 1000.0] * 1536,
                        "payload": {
                            "text": f"Document {i}",
                            "index": i,
                            "batch": batch_start // batch_size,
                        },
                    }
                    for i in range(batch_start, min(batch_start + batch_size, massive_count))
                ]

                await qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points,
                )

            # Verify massive dataset
            info = await qdrant_client.get_collection_info(collection_name=collection_name)
            assert info["points_count"] == massive_count

            # Test search performance
            import time

            search_start = time.time()
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=[0.1] * 1536,
                limit=10,
            )
            search_time = time.time() - search_start

            assert len(results) == 10
            assert search_time < 2.0  # Should be fast

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass
