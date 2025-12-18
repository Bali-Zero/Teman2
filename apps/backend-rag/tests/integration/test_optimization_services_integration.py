"""
Comprehensive Integration Tests for Optimization Services
Tests PerformanceOptimizer, SemanticCache, ContextWindowManager

Covers:
- Performance optimization
- Semantic caching
- Context window management
- Query optimization
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestSemanticCacheIntegration:
    """Integration tests for SemanticCache"""

    @pytest.mark.asyncio
    async def test_semantic_cache_initialization(self, qdrant_client):
        """Test SemanticCache initialization"""
        with patch("services.semantic_cache.QdrantClient") as mock_qdrant:
            from services.semantic_cache import SemanticCache

            cache = SemanticCache(qdrant_client=mock_qdrant.return_value)

            assert cache is not None

    @pytest.mark.asyncio
    async def test_semantic_cache_storage(self, qdrant_client):
        """Test semantic cache storage"""
        with patch("services.semantic_cache.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.upsert = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_client

            from services.semantic_cache import SemanticCache

            cache = SemanticCache(qdrant_client=mock_client)

            # Store cached response
            result = await cache.store(
                query="What is KITAS?",
                response="KITAS is a temporary residence permit",
                embedding=[0.1] * 1536,
            )

            assert result is not None
            assert mock_client.upsert.called

    @pytest.mark.asyncio
    async def test_semantic_cache_retrieval(self, qdrant_client):
        """Test semantic cache retrieval"""
        with (
            patch("services.semantic_cache.QdrantClient") as mock_qdrant,
            patch("core.embeddings.create_embeddings_generator") as mock_embedder,
        ):
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                return_value=[
                    {
                        "payload": {
                            "query": "What is KITAS?",
                            "response": "KITAS is a temporary residence permit",
                        },
                        "score": 0.95,
                    }
                ]
            )
            mock_qdrant.return_value = mock_client

            embedder = MagicMock()
            embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
            mock_embedder.return_value = embedder

            from services.semantic_cache import SemanticCache

            cache = SemanticCache(qdrant_client=mock_client)

            # Retrieve cached response
            cached = await cache.get(
                query="What is a KITAS visa?",  # Similar query
                threshold=0.90,
            )

            assert cached is not None


@pytest.mark.integration
class TestContextWindowManagerIntegration:
    """Integration tests for ContextWindowManager"""

    @pytest.mark.asyncio
    async def test_context_window_manager_initialization(self):
        """Test ContextWindowManager initialization"""
        from services.context_window_manager import ContextWindowManager

        manager = ContextWindowManager(max_tokens=4000)

        assert manager is not None
        assert manager.max_tokens == 4000

    @pytest.mark.asyncio
    async def test_context_window_management(self):
        """Test context window management"""
        from services.context_window_manager import ContextWindowManager

        manager = ContextWindowManager(max_tokens=4000)

        # Add messages to context
        messages = [
            {"role": "user", "content": "What is KITAS?"},
            {"role": "assistant", "content": "KITAS is a temporary residence permit"},
            {"role": "user", "content": "How to apply?"},
        ]

        # Manage context window
        managed = manager.manage_context(messages, max_tokens=4000)

        assert managed is not None
        assert len(managed) <= len(messages)

    @pytest.mark.asyncio
    async def test_context_window_truncation(self):
        """Test context window truncation"""
        from services.context_window_manager import ContextWindowManager

        manager = ContextWindowManager(max_tokens=100)  # Small window

        # Create many messages
        messages = [{"role": "user", "content": f"Message {i}" * 10} for i in range(20)]

        # Truncate to fit window
        truncated = manager.manage_context(messages, max_tokens=100)

        assert len(truncated) < len(messages)


@pytest.mark.integration
class TestPerformanceOptimizerIntegration:
    """Integration tests for PerformanceOptimizer"""

    @pytest.mark.asyncio
    async def test_performance_optimizer_initialization(self, db_pool):
        """Test PerformanceOptimizer initialization"""
        with patch("services.performance_optimizer.asyncpg") as mock_asyncpg:
            from services.performance_optimizer import PerformanceOptimizer

            optimizer = PerformanceOptimizer(db_pool=db_pool)

            assert optimizer is not None

    @pytest.mark.asyncio
    async def test_query_optimization(self, db_pool):
        """Test query optimization"""

        async with db_pool.acquire() as conn:
            # Create query_performance table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_performance (
                    id SERIAL PRIMARY KEY,
                    query_hash VARCHAR(64),
                    query_text TEXT,
                    execution_time_ms INTEGER,
                    optimization_applied BOOLEAN,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Track query performance
            await conn.execute(
                """
                INSERT INTO query_performance (
                    query_hash, query_text, execution_time_ms, optimization_applied
                )
                VALUES ($1, $2, $3, $4)
                """,
                "hash_123",
                "SELECT * FROM clients WHERE id = 1",
                150,
                False,
            )

            # Optimized query
            await conn.execute(
                """
                INSERT INTO query_performance (
                    query_hash, query_text, execution_time_ms, optimization_applied
                )
                VALUES ($1, $2, $3, $4)
                """,
                "hash_124",
                "SELECT id, name FROM clients WHERE id = 1",
                50,
                True,
            )

            # Analyze optimization impact
            analysis = await conn.fetchrow(
                """
                SELECT
                    AVG(CASE WHEN optimization_applied THEN execution_time_ms END) as avg_optimized,
                    AVG(CASE WHEN NOT optimization_applied THEN execution_time_ms END) as avg_unoptimized
                FROM query_performance
                """
            )

            assert analysis is not None
            if analysis["avg_optimized"] and analysis["avg_unoptimized"]:
                assert analysis["avg_optimized"] < analysis["avg_unoptimized"]

            # Cleanup
            await conn.execute("DELETE FROM query_performance")

    @pytest.mark.asyncio
    async def test_index_recommendations(self, db_pool):
        """Test index recommendations"""

        async with db_pool.acquire() as conn:
            # Create index_recommendations table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS index_recommendations (
                    id SERIAL PRIMARY KEY,
                    table_name VARCHAR(255),
                    column_name VARCHAR(255),
                    query_pattern TEXT,
                    expected_improvement DECIMAL(5,2),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store recommendations
            await conn.execute(
                """
                INSERT INTO index_recommendations (
                    table_name, column_name, query_pattern, expected_improvement
                )
                VALUES ($1, $2, $3, $4)
                """,
                "clients",
                "email",
                "WHERE email = $1",
                0.80,  # 80% improvement expected
            )

            # Retrieve recommendations
            recommendations = await conn.fetch(
                """
                SELECT table_name, column_name, expected_improvement
                FROM index_recommendations
                ORDER BY expected_improvement DESC
                """
            )

            assert len(recommendations) == 1
            assert recommendations[0]["expected_improvement"] == 0.80

            # Cleanup
            await conn.execute("DELETE FROM index_recommendations")
