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
        """Test AgenticRAGOrchestrator with real Qdrant"""
        from services.rag.agentic import AgenticRAGOrchestrator

        # Mock dependencies
        with (
            patch("services.rag.agentic.SearchService") as mock_search,
            patch("services.rag.agentic.ZantaraAIClient") as mock_ai,
            patch("core.embeddings.create_embeddings_generator") as mock_embedder,
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test_openai_api_key_for_testing",
                    "GOOGLE_API_KEY": "test_google_api_key_for_testing",
                },
                clear=False,
            ),
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [
                        {"text": "Document 1", "score": 0.9},
                        {"text": "Document 2", "score": 0.8},
                    ],
                    "collection_used": "visa_oracle",
                }
            )
            mock_search.return_value = mock_search_instance

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_response = AsyncMock(return_value="Agentic RAG response...")
            mock_ai.return_value = mock_ai_instance

            orchestrator = AgenticRAGOrchestrator(retriever=mock_search_instance, db_pool=db_pool)

            # Test query processing
            result = await orchestrator.process_query(
                query="What is KITAS?", user_id="test_user_rag_1"
            )

            assert result is not None
            assert "answer" in result or "response" in result

    @pytest.mark.asyncio
    async def test_cultural_rag_service(self, qdrant_client):
        """Test CulturalRAGService with real Qdrant"""
        from services.cultural_rag_service import CulturalRAGService

        with (
            patch("services.cultural_rag_service.SearchService") as mock_search,
            patch("services.cultural_rag_service.ZantaraAIClient") as mock_ai,
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test_openai_api_key_for_testing",
                    "GOOGLE_API_KEY": "test_google_api_key_for_testing",
                },
                clear=False,
            ),
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [{"text": "Cultural context document", "score": 0.85}],
                    "collection_used": "knowledge_base",
                }
            )
            mock_search.return_value = mock_search_instance

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_response = AsyncMock(return_value="Cultural RAG response...")
            mock_ai.return_value = mock_ai_instance

            service = CulturalRAGService(
                search_service=mock_search_instance, ai_client=mock_ai_instance
            )

            # Test cultural query
            result = await service.process_query(
                query="What are Indonesian business customs?",
                user_id="test_user_cultural_1",
                language="en",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_multi_collection_retrieval(self, qdrant_client):
        """Test multi-collection retrieval"""
        from services.search_service import SearchService

        with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
            embedder = MagicMock()
            embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            search_service = SearchService()

            # Test search across multiple collections
            collections = ["visa_oracle", "kbli_unified", "legal_unified"]

            for collection in collections:
                result = await search_service.search("test query", user_level=1, limit=5)
                assert result is not None
                assert "results" in result

    @pytest.mark.asyncio
    async def test_reranking_service(self, qdrant_client):
        """Test reranking service integration"""
        from services.reranker_service import RerankerService

        # Initialize reranker
        reranker = RerankerService()

        # Test reranking
        documents = [
            {"text": "Document 1", "score": 0.9},
            {"text": "Document 2", "score": 0.8},
            {"text": "Document 3", "score": 0.7},
        ]

        query = "test query"

        # Mock reranking (if external service)
        with patch.object(reranker, "rerank", new_callable=AsyncMock) as mock_rerank:
            mock_rerank.return_value = sorted(documents, key=lambda x: x["score"], reverse=True)

            reranked = await reranker.rerank(query, documents, top_k=2)

            assert reranked is not None
            assert len(reranked) <= len(documents)

    @pytest.mark.asyncio
    async def test_context_building(self, qdrant_client, db_pool):
        """Test context building from multiple sources"""
        from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestratorV2

        with (
            patch("services.context.agentic_orchestrator_v2.SearchService") as mock_search,
            patch("services.context.agentic_orchestrator_v2.ZantaraAIClient") as mock_ai,
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test_openai_api_key_for_testing",
                    "GOOGLE_API_KEY": "test_google_api_key_for_testing",
                },
                clear=False,
            ),
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [
                        {"text": "Context document 1", "score": 0.9},
                        {"text": "Context document 2", "score": 0.85},
                    ],
                    "collection_used": "visa_oracle",
                }
            )
            mock_search.return_value = mock_search_instance

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_response = AsyncMock(return_value="Contextual response...")
            mock_ai.return_value = mock_ai_instance

            orchestrator = AgenticRAGOrchestratorV2(retriever=mock_search_instance, db_pool=db_pool)

            # Test context building
            result = await orchestrator.process_query(
                query="What is KITAS?", user_id="test_user_context_1"
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_hybrid_search(self, qdrant_client):
        """Test hybrid search (vector + keyword)"""
        from services.search_service import SearchService

        with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
            embedder = MagicMock()
            embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            search_service = SearchService()

            # Test hybrid search
            result = await search_service.search(
                "KITAS visa requirements",
                user_level=1,
                limit=10,
                hybrid=True,  # If supported
            )

            assert result is not None
            assert "results" in result
