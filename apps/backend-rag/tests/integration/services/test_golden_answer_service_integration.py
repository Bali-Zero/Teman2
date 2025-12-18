"""
Integration Tests for GoldenAnswerService
Tests golden answer lookup with real PostgreSQL database
"""

import hashlib
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest_asyncio.fixture(scope="function")
async def golden_answer_service(db_pool):
    """Create GoldenAnswerService instance with test database"""
    from services.golden_answer_service import GoldenAnswerService

    # Get database URL from pool
    database_url = str(db_pool._connection_kwargs["dsn"])

    service = GoldenAnswerService(database_url)
    await service.connect()

    # Create necessary tables
    async with db_pool.acquire() as conn:
        # Create golden_answers table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS golden_answers (
                cluster_id VARCHAR(255) PRIMARY KEY,
                canonical_question TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources TEXT DEFAULT '[]',
                confidence FLOAT DEFAULT 1.0,
                usage_count INTEGER DEFAULT 0,
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """
        )

        # Create query_clusters table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_clusters (
                id SERIAL PRIMARY KEY,
                cluster_id VARCHAR(255) NOT NULL,
                query_hash VARCHAR(32) NOT NULL,
                query_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (cluster_id) REFERENCES golden_answers(cluster_id)
            )
        """
        )

        # Create indexes
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_query_clusters_hash ON query_clusters(query_hash)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_query_clusters_cluster ON query_clusters(cluster_id)"
        )

    yield service

    # Cleanup
    await service.close()


@pytest_asyncio.fixture(scope="function")
async def sample_golden_answers(db_pool):
    """Insert sample golden answers for testing"""
    async with db_pool.acquire() as conn:
        # Insert test golden answers
        cluster_id_1 = "test-cluster-001"
        cluster_id_2 = "test-cluster-002"

        await conn.execute(
            """
            INSERT INTO golden_answers (cluster_id, canonical_question, answer, sources, confidence)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (cluster_id) DO NOTHING
        """,
            cluster_id_1,
            "How to get KITAS in Indonesia?",
            "To get KITAS in Indonesia, you need to...",
            "[]",
            0.95,
        )

        await conn.execute(
            """
            INSERT INTO golden_answers (cluster_id, canonical_question, answer, sources, confidence)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (cluster_id) DO NOTHING
        """,
            cluster_id_2,
            "What is PT PMA?",
            "PT PMA is a foreign investment company in Indonesia...",
            "[]",
            0.90,
        )

        # Insert query clusters
        query1_hash = hashlib.md5("how to get kitas".lower().strip().encode("utf-8")).hexdigest()
        query2_hash = hashlib.md5("what is pt pma".lower().strip().encode("utf-8")).hexdigest()

        await conn.execute(
            """
            INSERT INTO query_clusters (cluster_id, query_hash, query_text)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """,
            cluster_id_1,
            query1_hash,
            "how to get kitas",
        )

        await conn.execute(
            """
            INSERT INTO query_clusters (cluster_id, query_hash, query_text)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """,
            cluster_id_2,
            query2_hash,
            "what is pt pma",
        )

    yield

    # Cleanup
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM query_clusters WHERE cluster_id LIKE $1", "test-cluster-%")
        await conn.execute("DELETE FROM golden_answers WHERE cluster_id LIKE $1", "test-cluster-%")


@pytest.mark.integration
@pytest.mark.database
class TestGoldenAnswerServiceIntegration:
    """Comprehensive integration tests for GoldenAnswerService"""

    @pytest.mark.asyncio
    async def test_exact_match_lookup(self, golden_answer_service, sample_golden_answers):
        """Test exact match lookup via query hash"""
        query = "how to get kitas"

        result = await golden_answer_service.lookup_golden_answer(query)

        assert result is not None
        assert result["match_type"] == "exact"
        assert result["cluster_id"] == "test-cluster-001"
        assert "KITAS" in result["answer"]
        assert result["confidence"] > 0

    @pytest.mark.asyncio
    async def test_no_match_found(self, golden_answer_service):
        """Test lookup when no match exists"""
        query = "completely unrelated query that does not exist"

        result = await golden_answer_service.lookup_golden_answer(query)

        assert result is None

    @pytest.mark.asyncio
    async def test_usage_count_increment(
        self, golden_answer_service, sample_golden_answers, db_pool
    ):
        """Test that usage count increments on lookup"""
        query = "how to get kitas"

        # Get initial usage count
        async with db_pool.acquire() as conn:
            initial_count = await conn.fetchval(
                "SELECT usage_count FROM golden_answers WHERE cluster_id = $1", "test-cluster-001"
            )

        # Lookup (should increment)
        await golden_answer_service.lookup_golden_answer(query)

        # Check updated count
        async with db_pool.acquire() as conn:
            updated_count = await conn.fetchval(
                "SELECT usage_count FROM golden_answers WHERE cluster_id = $1", "test-cluster-001"
            )

        assert updated_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_get_golden_answer_stats(self, golden_answer_service, sample_golden_answers):
        """Test getting golden answer statistics"""
        stats = await golden_answer_service.get_golden_answer_stats()

        assert "total_golden_answers" in stats
        assert "total_hits" in stats
        assert "avg_confidence" in stats
        assert "max_usage" in stats
        assert "min_usage" in stats
        assert "top_10" in stats
        assert isinstance(stats["top_10"], list)

    @pytest.mark.asyncio
    async def test_semantic_lookup_threshold(self, golden_answer_service, sample_golden_answers):
        """Test semantic lookup respects similarity threshold"""
        # Query similar but not exact
        query = "How can I obtain a KITAS visa in Indonesia?"

        result = await golden_answer_service.lookup_golden_answer(query)

        # May or may not match depending on similarity threshold
        # If it matches, should be semantic match
        if result:
            assert result["match_type"] == "semantic"
            assert "similarity" in result
            assert result["similarity"] >= 0.80

    @pytest.mark.asyncio
    async def test_multiple_lookups(self, golden_answer_service, sample_golden_answers):
        """Test multiple lookups in sequence"""
        queries = [
            "how to get kitas",
            "what is pt pma",
            "how to get kitas",  # Repeat
        ]

        results = []
        for query in queries:
            result = await golden_answer_service.lookup_golden_answer(query)
            results.append(result)

        # First two should match
        assert results[0] is not None
        assert results[1] is not None
        # Third should also match (same as first)
        assert results[2] is not None

    @pytest.mark.asyncio
    async def test_case_insensitive_lookup(self, golden_answer_service, sample_golden_answers):
        """Test that lookup is case insensitive"""
        queries = [
            "HOW TO GET KITAS",
            "How To Get Kitas",
            "how to get kitas",
        ]

        for query in queries:
            result = await golden_answer_service.lookup_golden_answer(query)
            assert result is not None
            assert result["match_type"] == "exact"

    @pytest.mark.asyncio
    async def test_empty_database(self, golden_answer_service):
        """Test behavior with empty database"""
        query = "test query"

        result = await golden_answer_service.lookup_golden_answer(query)

        # Should return None, not raise error
        assert result is None

    @pytest.mark.asyncio
    async def test_stats_with_no_data(self, golden_answer_service):
        """Test stats with no golden answers"""
        stats = await golden_answer_service.get_golden_answer_stats()

        assert stats["total_golden_answers"] >= 0
        assert stats["total_hits"] >= 0
        assert isinstance(stats["top_10"], list)
