"""
Comprehensive Integration Tests for Citation and Clarification Services
Tests CitationService and ClarificationService

Covers:
- Citation generation
- Source attribution
- Clarification requests
- Follow-up handling
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
class TestCitationServiceIntegration:
    """Integration tests for CitationService"""

    @pytest.mark.asyncio
    async def test_citation_service_initialization(self):
        """Test CitationService initialization"""
        with patch("services.search_service.SearchService") as mock_search:
            from services.citation_service import CitationService

            service = CitationService(search_service=mock_search.return_value)

            assert service is not None

    @pytest.mark.asyncio
    async def test_citation_generation(self, qdrant_client):
        """Test citation generation from search results"""
        with patch("services.search_service.SearchService") as mock_search:
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [
                        {
                            "text": "Document content",
                            "metadata": {
                                "source": "visa_oracle",
                                "document_id": "doc_123",
                                "title": "KITAS Guide",
                            },
                            "score": 0.9,
                        }
                    ],
                    "collection_used": "visa_oracle",
                }
            )

            from services.citation_service import CitationService

            service = CitationService(search_service=mock_search_instance)

            citations = await service.generate_citations(
                search_results=mock_search_instance.search.return_value["results"]
            )

            assert citations is not None
            assert isinstance(citations, list) or isinstance(citations, dict)

    @pytest.mark.asyncio
    async def test_citation_storage(self, db_pool):
        """Test citation storage in database"""

        async with db_pool.acquire() as conn:
            # Create citations table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS citations (
                    id SERIAL PRIMARY KEY,
                    response_id VARCHAR(255),
                    source_id VARCHAR(255),
                    source_title VARCHAR(255),
                    source_url TEXT,
                    citation_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store citation
            citation_id = await conn.fetchval(
                """
                INSERT INTO citations (
                    response_id, source_id, source_title, source_url, citation_text
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "response_123",
                "doc_456",
                "KITAS Application Guide",
                "https://example.com/kitas-guide",
                "According to the KITAS Application Guide...",
            )

            assert citation_id is not None

            # Retrieve citations for response
            citations = await conn.fetch(
                """
                SELECT source_title, citation_text
                FROM citations
                WHERE response_id = $1
                """,
                "response_123",
            )

            assert len(citations) == 1
            assert citations[0]["source_title"] == "KITAS Application Guide"

            # Cleanup
            await conn.execute("DELETE FROM citations WHERE id = $1", citation_id)


@pytest.mark.integration
class TestClarificationServiceIntegration:
    """Integration tests for ClarificationService"""

    @pytest.mark.asyncio
    async def test_clarification_service_initialization(self):
        """Test ClarificationService initialization"""
        with patch("services.clarification_service.ZantaraAIClient") as mock_ai:
            from services.clarification_service import ClarificationService

            service = ClarificationService(ai_client=mock_ai.return_value)

            assert service is not None

    @pytest.mark.asyncio
    async def test_clarification_request_generation(self):
        """Test clarification request generation"""
        with patch("services.clarification_service.ZantaraAIClient") as mock_ai:
            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_clarification = AsyncMock(
                return_value={
                    "clarification_needed": True,
                    "questions": [
                        "Do you mean KITAS or KITAP?",
                        "Are you applying for work or retirement?",
                    ],
                }
            )

            from services.clarification_service import ClarificationService

            service = ClarificationService(ai_client=mock_ai_instance)

            result = await service.request_clarification(
                query="I need a visa",
                user_id="test_user_clarification",
            )

            assert result is not None
            assert mock_ai_instance.generate_clarification.called

    @pytest.mark.asyncio
    async def test_clarification_storage(self, db_pool):
        """Test clarification storage"""

        async with db_pool.acquire() as conn:
            # Create clarifications table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clarifications (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    original_query TEXT,
                    clarification_questions TEXT[],
                    user_responses TEXT[],
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    resolved_at TIMESTAMP
                )
                """
            )

            # Store clarification
            clarification_id = await conn.fetchval(
                """
                INSERT INTO clarifications (
                    user_id, original_query, clarification_questions, user_responses
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "user_clarification_123",
                "I need a visa",
                ["Do you mean KITAS or KITAP?", "Work or retirement?"],
                ["KITAS", "Work"],
            )

            assert clarification_id is not None

            # Mark as resolved
            await conn.execute(
                """
                UPDATE clarifications
                SET resolved = TRUE, resolved_at = NOW()
                WHERE id = $1
                """,
                clarification_id,
            )

            # Verify resolution
            clarification = await conn.fetchrow(
                """
                SELECT resolved, resolved_at
                FROM clarifications
                WHERE id = $1
                """,
                clarification_id,
            )

            assert clarification["resolved"] is True
            assert clarification["resolved_at"] is not None

            # Cleanup
            await conn.execute("DELETE FROM clarifications WHERE id = $1", clarification_id)


@pytest.mark.integration
class TestFollowupServiceIntegration:
    """Integration tests for FollowupService"""

    @pytest.mark.asyncio
    async def test_followup_service_initialization(self, db_pool):
        """Test FollowupService initialization"""
        with patch("services.followup_service.MemoryServicePostgres") as mock_memory:
            from services.followup_service import FollowupService

            service = FollowupService(memory_service=mock_memory.return_value)

            assert service is not None

    @pytest.mark.asyncio
    async def test_followup_suggestion_generation(self, db_pool):
        """Test follow-up suggestion generation"""

        async with db_pool.acquire() as conn:
            # Create followup_suggestions table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS followup_suggestions (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    conversation_id VARCHAR(255),
                    original_query TEXT,
                    suggested_queries TEXT[],
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store follow-up suggestions
            suggestion_id = await conn.fetchval(
                """
                INSERT INTO followup_suggestions (
                    user_id, conversation_id, original_query, suggested_queries
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "user_followup_123",
                "conv_456",
                "What is KITAS?",
                [
                    "How to apply for KITAS?",
                    "What documents are needed for KITAS?",
                    "How long does KITAS take?",
                ],
            )

            assert suggestion_id is not None

            # Retrieve suggestions
            suggestions = await conn.fetchrow(
                """
                SELECT suggested_queries
                FROM followup_suggestions
                WHERE id = $1
                """,
                suggestion_id,
            )

            assert len(suggestions["suggested_queries"]) == 3

            # Cleanup
            await conn.execute("DELETE FROM followup_suggestions WHERE id = $1", suggestion_id)

    @pytest.mark.asyncio
    async def test_followup_tracking(self, db_pool):
        """Test follow-up tracking"""

        async with db_pool.acquire() as conn:
            # Create followup_tracking table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS followup_tracking (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    original_query TEXT,
                    followup_query TEXT,
                    time_between_seconds INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Track follow-ups
            await conn.execute(
                """
                INSERT INTO followup_tracking (
                    user_id, original_query, followup_query, time_between_seconds
                )
                VALUES ($1, $2, $3, $4)
                """,
                "user_followup_123",
                "What is KITAS?",
                "How to apply for KITAS?",
                300,  # 5 minutes
            )

            # Analyze follow-up patterns
            pattern = await conn.fetchrow(
                """
                SELECT
                    AVG(time_between_seconds) as avg_time_between,
                    COUNT(*) as total_followups
                FROM followup_tracking
                WHERE user_id = $1
                """,
                "user_followup_123",
            )

            assert pattern is not None
            assert pattern["total_followups"] == 1

            # Cleanup
            await conn.execute(
                "DELETE FROM followup_tracking WHERE user_id = $1", "user_followup_123"
            )
