"""
Comprehensive Integration Tests for RAG Services
Tests RAG-related services with real Qdrant and dependencies

Covers:
- AgenticRAGOrchestrator
- CulturalRAGService
- Context building
- Multi-collection retrieval
- Reranking
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
class TestRAGServicesIntegration:
    """Comprehensive integration tests for RAG services"""

    @pytest.mark.asyncio
    async def test_agentic_rag_orchestrator(self, qdrant_client, db_pool):
        """Test AgenticRAGOrchestrator with a greeting (no external LLM calls)."""
        from backend.services.rag.agentic import create_agentic_rag

        retriever = MagicMock()
        orchestrator = create_agentic_rag(retriever=retriever, db_pool=db_pool)

        result = await orchestrator.process_query(query="hello", user_id="test_user_rag_1")

        assert result is not None
        assert hasattr(result, "answer")
        assert result.answer

    @pytest.mark.asyncio
    async def test_cultural_rag_service(self, qdrant_client):
        """Test CulturalRAGService using mocked CulturalInsightsService."""
        from backend.services.misc.cultural_rag_service import CulturalRAGService

        mock_insights = MagicMock()
        mock_insights.query_insights = AsyncMock(
            return_value=[{"content": "Cultural context document", "score": 0.85}]
        )

        service = CulturalRAGService(cultural_insights_service=mock_insights)
        result = await service.get_cultural_context(
            {
                "query": "What are Indonesian business customs?",
                "intent": "business_simple",
                "conversation_stage": "first_contact",
            }
        )

        assert result is not None
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_multi_collection_retrieval(self, qdrant_client):
        """Test multi-collection retrieval"""
        from backend.services.search.search_service import SearchService

        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            embedder = MagicMock()
            embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 1536)
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            search_service = SearchService()
            mock_vector_db = MagicMock()
            mock_vector_db.search = AsyncMock(
                return_value={
                    "documents": ["Doc"],
                    "distances": [0.5],
                    "metadatas": [{}],
                    "ids": ["doc-1"],
                }
            )

            search_service.query_router.route_query = MagicMock(
                side_effect=lambda query, collection_override=None, enable_fallbacks=False: {
                    "collection_name": collection_override or "legal_unified"
                }
            )

            # Test search across multiple collections
            collections = ["visa_oracle", "kbli_unified", "legal_unified"]

            with patch.object(
                search_service.collection_manager, "get_collection", return_value=mock_vector_db
            ):
                for collection in collections:
                    result = await search_service.search(
                        "test query", user_level=1, limit=5, collection_override=collection
                    )
                    assert result is not None
                    assert "results" in result
                    assert result["collection_used"] == collection

    @pytest.mark.asyncio
    async def test_reranking_service(self, qdrant_client):
        """Test reranking service integration"""
        from backend.core.reranker import ReRanker

        reranker = ReRanker()

        # Test reranking
        documents = [
            {"text": "Document 1", "score": 0.9},
            {"text": "Document 2", "score": 0.8},
            {"text": "Document 3", "score": 0.7},
        ]

        query = "test query"

        # Mock reranking (if external service)
        reranked = await reranker.rerank(query, documents, top_k=2)

        assert reranked is not None
        assert len(reranked) <= len(documents)

    @pytest.mark.asyncio
    async def test_hybrid_search(self, qdrant_client):
        """Test hybrid search (vector + keyword)"""
        from backend.services.search.search_service import SearchService

        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            embedder = MagicMock()
            embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 1536)
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            search_service = SearchService()

            with (
                patch.object(
                    search_service,
                    "hybrid_search",
                    new_callable=AsyncMock,
                    return_value={"results": [{"text": "Doc", "score": 0.5}]},
                ),
                patch.object(
                    search_service,
                    "_init_reranker",
                    return_value=MagicMock(enabled=False),
                ),
            ):
                result = await search_service.hybrid_search_with_reranking(
                    "KITAS visa requirements",
                    user_level=1,
                    limit=10,
                )

            assert result is not None
            assert "results" in result
            assert result.get("pipeline") == "hybrid_bm25_rrf_zerank2"
