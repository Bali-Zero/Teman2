"""
Comprehensive Integration Tests for Oracle System
Tests complete Oracle workflows with real Qdrant and PostgreSQL

Covers:
- Oracle query processing
- Document ingestion
- Feedback storage
- Analytics tracking
- Multi-collection routing
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", os.getenv("QDRANT_URL", "http://localhost:6333"))
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestOracleComprehensiveIntegration:
    """Comprehensive integration tests for Oracle system"""

    @pytest.mark.asyncio
    async def test_oracle_query_with_qdrant_search(self, qdrant_client, db_pool):
        """Test Oracle query with real Qdrant search"""
        from services.search_service import SearchService

        # Initialize search service with test Qdrant
        search_service = SearchService()

        # Mock embedding generation
        with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
            embedder = MagicMock()
            embedder.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536  # Mock 1536-dim embedding
            )
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            # Test search
            result = await search_service.search("test query", user_level=1, limit=5)

            assert result is not None
            assert "results" in result
            assert "collection_used" in result

    @pytest.mark.asyncio
    async def test_oracle_query_analytics_storage(self, db_pool):
        """Test Oracle query analytics storage in PostgreSQL"""

        async with db_pool.acquire() as conn:
            # Create analytics table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oracle_query_analytics (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    query_hash VARCHAR(64),
                    query_text TEXT,
                    response_text TEXT,
                    language_preference VARCHAR(10),
                    model_used VARCHAR(100),
                    response_time_ms INTEGER,
                    document_count INTEGER,
                    session_id VARCHAR(255),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store analytics
            query_hash = "test_hash_12345"
            analytics_id = await conn.fetchval(
                """
                INSERT INTO oracle_query_analytics (
                    user_id, query_hash, query_text, response_text,
                    language_preference, model_used, response_time_ms,
                    document_count, session_id, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                "test_user_123",
                query_hash,
                "What is KITAS?",
                "KITAS is a temporary residence permit...",
                "en",
                "gemini-2.5-flash",
                150,
                3,
                "session_123",
                {"collection": "visa_oracle"},
            )

            assert analytics_id is not None

            # Retrieve analytics
            analytics = await conn.fetchrow(
                """
                SELECT query_text, model_used, document_count
                FROM oracle_query_analytics
                WHERE id = $1
                """,
                analytics_id,
            )

            assert analytics is not None
            assert analytics["query_text"] == "What is KITAS?"
            assert analytics["model_used"] == "gemini-2.5-flash"
            assert analytics["document_count"] == 3

            # Cleanup
            await conn.execute("DELETE FROM oracle_query_analytics WHERE id = $1", analytics_id)

    @pytest.mark.asyncio
    async def test_oracle_feedback_storage(self, db_pool):
        """Test Oracle feedback storage and retrieval"""

        async with db_pool.acquire() as conn:
            # Create feedback table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oracle_feedback (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    query_text TEXT,
                    response_text TEXT,
                    feedback_type VARCHAR(50),
                    feedback_text TEXT,
                    rating INTEGER,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store feedback
            feedback_id = await conn.fetchval(
                """
                INSERT INTO oracle_feedback (
                    user_id, query_text, response_text,
                    feedback_type, feedback_text, rating, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "test_user_123",
                "What is KITAS?",
                "KITAS is a temporary residence permit...",
                "correction",
                "The response was helpful but missing some details",
                4,
                {"helpful": True},
            )

            assert feedback_id is not None

            # Retrieve feedback
            feedback = await conn.fetchrow(
                """
                SELECT feedback_type, rating, feedback_text
                FROM oracle_feedback
                WHERE id = $1
                """,
                feedback_id,
            )

            assert feedback is not None
            assert feedback["feedback_type"] == "correction"
            assert feedback["rating"] == 4

            # Test feedback aggregation
            avg_rating = await conn.fetchval(
                """
                SELECT AVG(rating)::FLOAT
                FROM oracle_feedback
                WHERE user_id = $1
                """,
                "test_user_123",
            )
            assert avg_rating == 4.0

            # Cleanup
            await conn.execute("DELETE FROM oracle_feedback WHERE id = $1", feedback_id)

    @pytest.mark.asyncio
    async def test_oracle_document_ingestion(self, qdrant_client):
        """Test Oracle document ingestion into Qdrant"""

        # Create test collection
        collection_name = "test_oracle_integration"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Mock embedding
            test_embedding = [0.1] * 1536

            # Insert test document
            document_id = "test_doc_1"
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": document_id,
                        "vector": test_embedding,
                        "payload": {
                            "text": "Test document content for Oracle integration",
                            "metadata": {"source": "test", "type": "integration"},
                        },
                    }
                ],
            )

            # Search for document
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                limit=1,
            )

            assert len(results) > 0
            assert results[0]["id"] == document_id

        finally:
            # Cleanup: delete collection
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass  # Collection might not exist

    @pytest.mark.asyncio
    async def test_oracle_multi_collection_routing(self, qdrant_client):
        """Test Oracle routing across multiple collections"""
        from services.query_router import QueryRouter
        from services.search_service import SearchService

        # Initialize services
        search_service = SearchService()
        query_router = QueryRouter()

        # Mock embedding
        with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
            embedder = MagicMock()
            embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            # Test routing for visa query
            visa_result = await query_router.route_query("What is KITAS visa?")
            assert visa_result is not None
            assert "collection_name" in visa_result

            # Test routing for tax query
            tax_result = await query_router.route_query("What are Indonesian tax rates?")
            assert tax_result is not None

    @pytest.mark.asyncio
    async def test_oracle_session_tracking(self, db_pool):
        """Test Oracle session tracking across multiple queries"""

        async with db_pool.acquire() as conn:
            # Create session tracking table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oracle_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255),
                    started_at TIMESTAMP DEFAULT NOW(),
                    last_activity TIMESTAMP DEFAULT NOW(),
                    query_count INTEGER DEFAULT 0,
                    metadata JSONB DEFAULT '{}'
                )
                """
            )

            session_id = "test_session_123"

            # Create session
            await conn.execute(
                """
                INSERT INTO oracle_sessions (session_id, user_id, query_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id) DO UPDATE
                SET last_activity = NOW(), query_count = oracle_sessions.query_count + 1
                """,
                session_id,
                "test_user_123",
                1,
            )

            # Update session with query
            await conn.execute(
                """
                UPDATE oracle_sessions
                SET query_count = query_count + 1, last_activity = NOW()
                WHERE session_id = $1
                """,
                session_id,
            )

            # Retrieve session
            session = await conn.fetchrow(
                """
                SELECT query_count, last_activity
                FROM oracle_sessions
                WHERE session_id = $1
                """,
                session_id,
            )

            assert session is not None
            assert session["query_count"] == 2

            # Cleanup
            await conn.execute("DELETE FROM oracle_sessions WHERE session_id = $1", session_id)
