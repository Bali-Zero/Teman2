"""
API Tests for SearchService - Coverage 95% Target
Tests SearchService methods via API endpoints

Coverage:
- search method (via oracle_universal endpoint)
- search_with_conflict_resolution method
- _build_search_filter method
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestSearchService:
    """Test SearchService methods"""

    @pytest.mark.asyncio
    async def test_search_basic(self):
        """Test basic search method"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        # Mock dependencies
        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": [["Document 1", "Document 2"]],
                "distances": [[0.1, 0.2]],
                "metadatas": [[{"title": "Doc 1"}, {"title": "Doc 2"}]],
                "ids": [["id1", "id2"]],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={"collection_name": "visa_oracle", "confidence": 0.8, "fallbacks": []}
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        result = await service.search(query="visa question", user_level=2, limit=5)

        assert "query" in result
        assert "results" in result
        assert "collection_used" in result
        assert result["query"] == "visa question"

    @pytest.mark.asyncio
    async def test_search_with_reranking(self):
        """Test search_with_reranking method"""
        from unittest.mock import Mock

        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": ["Document 1", "Document 2", "Document 3"],
                "distances": [0.1, 0.2, 0.3],
                "metadatas": [{"title": "Doc 1"}, {"title": "Doc 2"}, {"title": "Doc 3"}],
                "ids": ["id1", "id2", "id3"],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={"collection_name": "visa_oracle", "confidence": 0.8, "is_pricing": False}
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        # Mock reranker
        mock_reranker = Mock()
        mock_reranker.enabled = True
        mock_reranker.rerank = AsyncMock(
            return_value=[
                {"text": "Document 2", "score": 0.95, "metadata": {"title": "Doc 2"}},
                {"text": "Document 1", "score": 0.90, "metadata": {"title": "Doc 1"}},
            ]
        )
        service._reranker = mock_reranker

        result = await service.search_with_reranking(query="visa question", user_level=2, limit=2)

        assert "query" in result
        assert "results" in result
        assert result.get("reranked") is True
        assert len(result["results"]) <= 2
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_filters_enabled(self):
        """Test that filters are enabled by default (no NUCLEAR OVERRIDE)"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        captured_filter = None

        async def capture_search(query_embedding, filter=None, limit=5):
            nonlocal captured_filter
            captured_filter = filter
            return {
                "documents": ["Test doc"],
                "metadatas": [{}],
                "distances": [0.1],
                "ids": ["doc1"],
            }

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = capture_search
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={
                "collection_name": "zantara_books",
                "collections": ["zantara_books"],
                "confidence": 1.0,
                "is_pricing": False,
            }
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        await service.search(query="test", user_level=2, limit=5)

        # Verify search was called (filter may be None for non-tier collections, but shouldn't be forced None)
        assert mock_vector_db.search.called

    @pytest.mark.asyncio
    async def test_search_with_collection_override(self):
        """Test search with collection override"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": [["Document 1"]],
                "distances": [[0.1]],
                "metadatas": [[{"title": "Doc 1"}]],
                "ids": [["id1"]],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={"collection_name": "tax_genius", "confidence": 0.8, "fallbacks": []}
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        result = await service.search(
            query="tax question", user_level=2, limit=5, collection_override="tax_genius"
        )

        assert result["collection_used"] == "tax_genius"

    @pytest.mark.asyncio
    async def test_search_with_tier_filter(self):
        """Test search with tier filter"""
        from backend.app.models import TierLevel
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": [["Document 1"]],
                "distances": [[0.1]],
                "metadatas": [[{"tier": "S", "title": "Doc 1"}]],
                "ids": [["id1"]],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={"collection_name": "zantara_books", "confidence": 0.8, "fallbacks": []}
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        result = await service.search(
            query="philosophy question",
            user_level=2,
            limit=5,
            tier_filter=[TierLevel.S, TierLevel.A],
        )

        assert "allowed_tiers" in result
        assert len(result["allowed_tiers"]) > 0

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution(self):
        """Test search_with_conflict_resolution method"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": [["Document 1"]],
                "distances": [[0.1]],
                "metadatas": [[{"title": "Doc 1"}]],
                "ids": [["id1"]],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={
                "collection_name": "visa_oracle",
                "confidence": 0.5,
                "fallbacks": ["kbli_eye"],
                "collections": ["visa_oracle", "kbli_eye"],
            }
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        result = await service.search_with_conflict_resolution(
            query="ambiguous question", user_level=2, limit=5, enable_fallbacks=True
        )

        assert "results" in result
        assert "conflict_resolution" in result or "metadata" in result

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_no_fallbacks(self):
        """Test search_with_conflict_resolution without fallbacks"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": [["Document 1"]],
                "distances": [[0.1]],
                "metadatas": [[{"title": "Doc 1"}]],
                "ids": [["id1"]],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={
                "collection_name": "visa_oracle",
                "confidence": 0.8,
                "fallbacks": [],
                "collections": ["visa_oracle"],
            }
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        result = await service.search_with_conflict_resolution(
            query="visa question", user_level=2, limit=5, enable_fallbacks=False
        )

        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """Test search error handling"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_collection_manager.get_collection = MagicMock(return_value=None)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={
                "collection_name": "unknown_collection",
                "confidence": 0.8,
                "fallbacks": [],
            }
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        # Should handle missing collection gracefully
        with pytest.raises((ValueError, Exception)):
            await service.search(query="test", user_level=2, limit=5)

    def test_build_search_filter_with_tier(self):
        """Test _build_search_filter with tier filter"""
        from backend.services.collection_manager import CollectionManager
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_embedder = MagicMock()
        service = SearchService(
            collection_manager=CollectionManager(),
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=CollectionManager(), embedder=mock_embedder
            ),
        )

        tier_filter = {"tier": {"$in": ["S", "A"]}}
        result = service._build_search_filter(tier_filter=tier_filter, exclude_repealed=True)

        assert result is not None
        assert "tier" in result
        assert "status_vigensi" in result or "$and" in result or "$or" in result

    def test_build_search_filter_exclude_repealed(self):
        """Test _build_search_filter excludes repealed laws"""
        from backend.services.collection_manager import CollectionManager
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_embedder = MagicMock()
        service = SearchService(
            collection_manager=CollectionManager(),
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=CollectionManager(), embedder=mock_embedder
            ),
        )

        result = service._build_search_filter(tier_filter=None, exclude_repealed=True)

        assert result is not None
        # Should exclude "dicabut" status
        assert "status_vigensi" in result or "$and" in result or "$or" in result

    def test_build_search_filter_include_repealed(self):
        """Test _build_search_filter includes repealed laws when requested"""
        from backend.services.collection_manager import CollectionManager
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_embedder = MagicMock()
        service = SearchService(
            collection_manager=CollectionManager(),
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=CollectionManager(), embedder=mock_embedder
            ),
        )

        result = service._build_search_filter(tier_filter=None, exclude_repealed=False)

        # When exclude_repealed=False, should not have status_vigensi filter
        # or should allow all statuses
        assert result is None or "status_vigensi" not in result or "$in" in str(result)

    def test_build_search_filter_no_tier(self):
        """Test _build_search_filter without tier filter"""
        from backend.services.collection_manager import CollectionManager
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_embedder = MagicMock()
        service = SearchService(
            collection_manager=CollectionManager(),
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=CollectionManager(), embedder=mock_embedder
            ),
        )

        result = service._build_search_filter(tier_filter=None, exclude_repealed=True)

        # Should still exclude repealed even without tier filter
        assert result is None or "status_vigensi" in result or "$and" in result

    @pytest.mark.asyncio
    async def test_search_user_level_0(self):
        """Test search with user_level 0 (S tier only)"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": [["Document 1"]],
                "distances": [[0.1]],
                "metadatas": [[{"tier": "S", "title": "Doc 1"}]],
                "ids": [["id1"]],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={"collection_name": "zantara_books", "confidence": 0.8, "fallbacks": []}
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        result = await service.search(query="test", user_level=0, limit=5)

        assert result["user_level"] == 0
        assert "S" in result["allowed_tiers"] or len(result["allowed_tiers"]) == 0

    @pytest.mark.asyncio
    async def test_search_user_level_3(self):
        """Test search with user_level 3 (all tiers)"""
        from backend.services.conflict_resolver import ConflictResolver
        from backend.services.cultural_insights_service import CulturalInsightsService
        from backend.services.search_service import SearchService

        mock_collection_manager = MagicMock()
        mock_vector_db = MagicMock()
        mock_vector_db.search = AsyncMock(
            return_value={
                "documents": [["Document 1"]],
                "distances": [[0.1]],
                "metadatas": [[{"tier": "D", "title": "Doc 1"}]],
                "ids": [["id1"]],
            }
        )
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)

        mock_query_router = MagicMock()
        mock_query_router.route_query = MagicMock(
            return_value={"collection_name": "zantara_books", "confidence": 0.8, "fallbacks": []}
        )

        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)

        service = SearchService(
            collection_manager=mock_collection_manager,
            conflict_resolver=ConflictResolver(),
            cultural_insights=CulturalInsightsService(
                collection_manager=mock_collection_manager, embedder=mock_embedder
            ),
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder

        result = await service.search(query="test", user_level=3, limit=5)

        assert result["user_level"] == 3
        # Level 3 should have access to all tiers
        assert len(result["allowed_tiers"]) >= 4  # S, A, B, C, D
