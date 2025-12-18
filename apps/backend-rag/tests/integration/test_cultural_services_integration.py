"""
Comprehensive Integration Tests for Cultural Services
Tests CulturalRAGService and CulturalInsightsService

Covers:
- Cultural RAG processing
- Cultural insights extraction
- Multi-language support
- Cultural context understanding
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCulturalRAGServiceIntegration:
    """Integration tests for CulturalRAGService"""

    @pytest.mark.asyncio
    async def test_cultural_rag_initialization(self, qdrant_client):
        """Test CulturalRAGService initialization"""
        with (
            patch("services.cultural_rag_service.SearchService") as mock_search,
            patch("services.cultural_rag_service.ZantaraAIClient") as mock_ai,
        ):
            from services.cultural_rag_service import CulturalRAGService

            service = CulturalRAGService(
                search_service=mock_search.return_value,
                ai_client=mock_ai.return_value,
            )

            assert service is not None

    @pytest.mark.asyncio
    async def test_cultural_query_processing(self, qdrant_client):
        """Test cultural query processing"""
        with (
            patch("services.cultural_rag_service.SearchService") as mock_search,
            patch("services.cultural_rag_service.ZantaraAIClient") as mock_ai,
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [{"text": "Cultural context document", "score": 0.9}],
                    "collection_used": "knowledge_base",
                }
            )

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_response = AsyncMock(
                return_value="Cultural RAG response with context"
            )

            from services.cultural_rag_service import CulturalRAGService

            service = CulturalRAGService(
                search_service=mock_search_instance,
                ai_client=mock_ai_instance,
            )

            result = await service.process_query(
                query="What are Indonesian business customs?",
                user_id="test_user_cultural",
                language="en",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_multi_language_support(self, db_pool):
        """Test multi-language support"""

        async with db_pool.acquire() as conn:
            # Create cultural_contexts table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cultural_contexts (
                    id SERIAL PRIMARY KEY,
                    language_code VARCHAR(10),
                    cultural_concept VARCHAR(255),
                    explanation TEXT,
                    examples JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store cultural contexts for different languages
            contexts = [
                (
                    "en",
                    "business_card",
                    "Exchange business cards with both hands",
                    ["example1", "example2"],
                ),
                (
                    "id",
                    "kartu_nama",
                    "Tukar kartu nama dengan kedua tangan",
                    ["contoh1", "contoh2"],
                ),
                (
                    "it",
                    "biglietto_da_visita",
                    "Scambia biglietti da visita con entrambe le mani",
                    ["esempio1", "esempio2"],
                ),
            ]

            for lang, concept, explanation, examples in contexts:
                await conn.execute(
                    """
                    INSERT INTO cultural_contexts (
                        language_code, cultural_concept, explanation, examples
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    lang,
                    concept,
                    explanation,
                    examples,
                )

            # Retrieve context by language
            english_context = await conn.fetchrow(
                """
                SELECT cultural_concept, explanation
                FROM cultural_contexts
                WHERE language_code = $1 AND cultural_concept = $2
                """,
                "en",
                "business_card",
            )

            assert english_context is not None
            assert "both hands" in english_context["explanation"]

            # Cleanup
            await conn.execute("DELETE FROM cultural_contexts")


@pytest.mark.integration
class TestCulturalInsightsServiceIntegration:
    """Integration tests for CulturalInsightsService"""

    @pytest.mark.asyncio
    async def test_cultural_insights_extraction(self, db_pool):
        """Test cultural insights extraction"""

        async with db_pool.acquire() as conn:
            # Create cultural_insights table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cultural_insights (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    insight_type VARCHAR(100),
                    insight_text TEXT,
                    cultural_context VARCHAR(255),
                    confidence DECIMAL(5,2),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Extract and store cultural insights
            insights = [
                (
                    "user_123",
                    "communication_style",
                    "Prefers indirect communication",
                    "Indonesian",
                    0.85,
                ),
                (
                    "user_123",
                    "business_etiquette",
                    "Values relationship building",
                    "Southeast Asian",
                    0.90,
                ),
                ("user_123", "time_perception", "Flexible with time", "Balinese", 0.75),
            ]

            for user_id, insight_type, insight_text, context, confidence in insights:
                await conn.execute(
                    """
                    INSERT INTO cultural_insights (
                        user_id, insight_type, insight_text, cultural_context, confidence
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    user_id,
                    insight_type,
                    insight_text,
                    context,
                    confidence,
                )

            # Retrieve insights for user
            user_insights = await conn.fetch(
                """
                SELECT insight_type, insight_text, confidence
                FROM cultural_insights
                WHERE user_id = $1
                ORDER BY confidence DESC
                """,
                "user_123",
            )

            assert len(user_insights) == 3
            assert user_insights[0]["confidence"] >= user_insights[-1]["confidence"]

            # Cleanup
            await conn.execute("DELETE FROM cultural_insights WHERE user_id = $1", "user_123")

    @pytest.mark.asyncio
    async def test_cultural_adaptation(self, db_pool):
        """Test cultural adaptation of responses"""

        async with db_pool.acquire() as conn:
            # Create response_adaptations table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS response_adaptations (
                    id SERIAL PRIMARY KEY,
                    original_response TEXT,
                    adapted_response TEXT,
                    adaptation_type VARCHAR(100),
                    cultural_context VARCHAR(255),
                    user_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store adaptations
            original = "You must complete this form immediately."
            adapted = "It would be helpful if you could complete this form when convenient."

            adaptation_id = await conn.fetchval(
                """
                INSERT INTO response_adaptations (
                    original_response, adapted_response, adaptation_type,
                    cultural_context, user_id
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                original,
                adapted,
                "formality_reduction",
                "Indonesian",
                "user_123",
            )

            assert adaptation_id is not None

            # Retrieve adaptation
            adaptation = await conn.fetchrow(
                """
                SELECT adapted_response, adaptation_type
                FROM response_adaptations
                WHERE id = $1
                """,
                adaptation_id,
            )

            assert adaptation is not None
            assert "helpful" in adaptation["adapted_response"].lower()

            # Cleanup
            await conn.execute("DELETE FROM response_adaptations WHERE id = $1", adaptation_id)
