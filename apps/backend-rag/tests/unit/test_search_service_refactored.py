"""
Unit tests for refactored SearchService

Tests SearchService with mocked dependencies to verify core search logic.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.collection_manager import CollectionManager
from services.conflict_resolver import ConflictResolver
from services.cultural_insights_service import CulturalInsightsService
from services.query_router_integration import QueryRouterIntegration
from services.search_service import SearchService


class TestSearchServiceRefactored:
    """Test refactored SearchService with dependency injection"""

    @pytest.fixture
    def mock_collection_manager(self):
        """Mock CollectionManager"""
        manager = Mock(spec=CollectionManager)
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "documents": ["Test document"],
                "metadatas": [{"tier": "A"}],
                "distances": [0.3],
                "ids": ["doc_1"],
            }
        )
        manager.get_collection.return_value = mock_client
        return manager

    @pytest.fixture
    def mock_conflict_resolver(self):
        """Mock ConflictResolver"""
        resolver = Mock(spec=ConflictResolver)
        resolver.detect_conflicts.return_value = []
        resolver.resolve_conflicts.return_value = ([], [])
        resolver.get_stats.return_value = {
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
        }
        return resolver

    @pytest.fixture
    def mock_cultural_insights(self):
        """Mock CulturalInsightsService"""
        service = Mock(spec=CulturalInsightsService)
        service.add_insight = AsyncMock(return_value=True)
        service.query_insights = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def mock_query_router(self):
        """Mock QueryRouterIntegration"""
        router = Mock(spec=QueryRouterIntegration)
        router.route_query.return_value = {
            "collection_name": "visa_oracle",
            "collections": ["visa_oracle"],
            "confidence": 1.0,
            "is_pricing": False,
        }
        return router

    @pytest.fixture
    def mock_embedder(self):
        """Mock EmbeddingsGenerator"""
        embedder = Mock()
        embedder.generate_query_embedding.return_value = [0.1] * 1536
        embedder.provider = "openai"
        embedder.dimensions = 1536
        return embedder

    @pytest.fixture
    def mock_health_monitor(self):
        """Mock CollectionHealthService"""
        monitor = Mock()
        monitor.record_query = Mock()
        monitor.get_collection_health = Mock(return_value=Mock())
        monitor.get_all_collection_health = Mock(return_value={})
        monitor.get_dashboard_summary = Mock(return_value={})
        monitor.get_health_report = Mock(return_value="Health report")
        return monitor

    @pytest.fixture
    def search_service(
        self,
        mock_collection_manager,
        mock_conflict_resolver,
        mock_cultural_insights,
        mock_query_router,
        mock_embedder,
    ):
        """Create SearchService with mocked dependencies"""
        with patch("core.embeddings.create_embeddings_generator", return_value=mock_embedder):
            with patch(
                "services.collection_health_service.CollectionHealthService",
                return_value=Mock(),
            ):
                service = SearchService(
                    collection_manager=mock_collection_manager,
                    conflict_resolver=mock_conflict_resolver,
                    cultural_insights=mock_cultural_insights,
                    query_router=mock_query_router,
                )
                # Replace health monitor with mock
                service.health_monitor = Mock()
                service.health_monitor.record_query = Mock()
                return service

    def test_initialization_with_dependencies(self, search_service):
        """Test SearchService initialization with injected dependencies"""
        assert search_service is not None
        assert search_service.collection_manager is not None
        assert search_service.conflict_resolver is not None
        assert search_service.cultural_insights is not None
        assert search_service.query_router is not None

    def test_initialization_without_dependencies(self):
        """Test SearchService creates dependencies if not provided"""
        with patch("services.search_service.settings") as mock_settings:
            mock_settings.qdrant_url = "http://test:6333"
            with patch("core.embeddings.create_embeddings_generator") as mock_create:
                mock_embedder = Mock()
                mock_embedder.provider = "openai"
                mock_embedder.dimensions = 1536
                mock_create.return_value = mock_embedder
                with patch("services.collection_health_service.CollectionHealthService"):
                    service = SearchService()
                    assert service.collection_manager is not None
                    assert service.conflict_resolver is not None

    @pytest.mark.asyncio
    async def test_search_basic(self, search_service, mock_collection_manager):
        """Test basic search functionality"""
        result = await search_service.search(query="test query", user_level=3, limit=5)

        assert result is not None
        assert "query" in result
        assert "results" in result
        assert result["query"] == "test query"
        mock_collection_manager.get_collection.assert_called()

    @pytest.mark.asyncio
    async def test_search_with_collection_override(
        self, search_service, mock_collection_manager, mock_query_router
    ):
        """Test search with collection override"""

        # Mock query router to respect collection_override
        def route_query_side_effect(query, collection_override=None, enable_fallbacks=False):
            if collection_override:
                return {
                    "collection_name": collection_override,
                    "collections": [collection_override],
                    "confidence": 1.0,
                    "is_pricing": False,
                }
            return {
                "collection_name": "visa_oracle",
                "collections": ["visa_oracle"],
                "confidence": 1.0,
                "is_pricing": False,
            }

        mock_query_router.route_query.side_effect = route_query_side_effect

        result = await search_service.search(
            query="test", user_level=3, collection_override="tax_genius"
        )

        assert result["collection_used"] == "tax_genius"
        mock_collection_manager.get_collection.assert_called_with("tax_genius")

    @pytest.mark.asyncio
    async def test_search_pricing_query(self, search_service, mock_query_router):
        """Test that pricing queries route correctly"""
        mock_query_router.route_query.return_value = {
            "collection_name": "bali_zero_pricing",
            "collections": ["bali_zero_pricing"],
            "confidence": 1.0,
            "is_pricing": True,
        }

        result = await search_service.search(query="What is the price?", user_level=3)

        assert result["collection_used"] == "bali_zero_pricing"
        mock_query_router.route_query.assert_called()

    @pytest.mark.asyncio
    async def test_search_with_tier_filter(self, search_service):
        """Test search with tier filter"""
        from app.models import TierLevel

        result = await search_service.search(
            query="test", user_level=2, tier_filter=[TierLevel.S, TierLevel.A]
        )

        assert "allowed_tiers" in result

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution(self, search_service, mock_conflict_resolver):
        """Test search with conflict resolution"""
        mock_conflict_resolver.detect_conflicts.return_value = []
        mock_conflict_resolver.resolve_conflicts.return_value = ([], [])

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=3, enable_fallbacks=True
        )

        assert result is not None
        assert "conflicts_detected" in result
        mock_conflict_resolver.detect_conflicts.assert_called()

    def test_cultural_insights_property(self, search_service, mock_cultural_insights):
        """Test that cultural_insights property exposes CulturalInsightsService"""
        assert search_service.cultural_insights is mock_cultural_insights

    @pytest.mark.asyncio
    async def test_cultural_insights_direct_access(self, search_service, mock_cultural_insights):
        """Test direct access to cultural_insights service"""
        mock_cultural_insights.add_insight.return_value = True
        result = await search_service.cultural_insights.add_insight(
            text="Test insight", metadata={"topic": "greeting"}
        )

        assert result is True
        mock_cultural_insights.add_insight.assert_called_once_with(
            text="Test insight", metadata={"topic": "greeting"}
        )

    def test_get_conflict_stats_delegation(self, search_service, mock_conflict_resolver):
        """Test that get_conflict_stats delegates to ConflictResolver"""
        stats = search_service.get_conflict_stats()

        assert "conflicts_detected" in stats
        mock_conflict_resolver.get_stats.assert_called()

    @pytest.mark.asyncio
    async def test_search_collection_direct(self, search_service, mock_collection_manager):
        """Test direct collection search"""
        result = await search_service.search_collection(
            query="test", collection_name="visa_oracle", limit=5
        )

        assert result is not None
        assert "results" in result
        mock_collection_manager.get_collection.assert_called_with("visa_oracle")

    @pytest.mark.asyncio
    async def test_warmup_service_access(self, search_service):
        """Test that warmup_service is accessible"""
        assert hasattr(search_service, "warmup_service")
        assert search_service.warmup_service is not None

    @pytest.mark.asyncio
    async def test_search_with_reranking(self, search_service, mock_collection_manager):
        """Test search_with_reranking method"""
        # Mock reranker
        mock_reranker = Mock()
        mock_reranker.enabled = True
        mock_reranker.rerank = AsyncMock(
            return_value=[
                {"text": "Reranked doc 1", "score": 0.95, "metadata": {}},
                {"text": "Reranked doc 2", "score": 0.90, "metadata": {}},
            ]
        )
        search_service._reranker = mock_reranker

        result = await search_service.search_with_reranking(
            query="test query", user_level=3, limit=2
        )

        assert result is not None
        assert "results" in result
        assert result.get("reranked") is True
        assert len(result["results"]) <= 2
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_reranking_disabled(self, search_service, mock_collection_manager):
        """Test search_with_reranking when reranker is disabled"""
        # Mock reranker as disabled
        mock_reranker = Mock()
        mock_reranker.enabled = False
        search_service._reranker = mock_reranker

        result = await search_service.search_with_reranking(
            query="test query", user_level=3, limit=2
        )

        assert result is not None
        assert result.get("reranked") is False
        assert len(result["results"]) <= 2

    @pytest.mark.asyncio
    async def test_search_filters_enabled_by_default(self, search_service, mock_collection_manager):
        """Test that filters are enabled by default (apply_filters=None means enabled)"""
        # Mock vector DB to capture filter
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

        mock_client = AsyncMock()
        mock_client.search = capture_search
        mock_collection_manager.get_collection.return_value = mock_client

        # Route to zantara_books to trigger tier filter
        search_service.query_router.route_query.return_value = {
            "collection_name": "zantara_books",
            "collections": ["zantara_books"],
            "confidence": 1.0,
            "is_pricing": False,
        }

        # Default behavior: filters enabled (apply_filters=None)
        await search_service.search(query="test", user_level=2, limit=5)

        # Filter should be applied (not None) for zantara_books with tier
        # Note: filter might be None if no tier matches, but should not be forced None
        # The key is that we're not forcing chroma_filter = None anymore
        assert (
            captured_filter is not None
            or search_service.query_router.route_query.return_value["collection_name"]
            != "zantara_books"
        )

    @pytest.mark.asyncio
    async def test_search_filters_explicitly_enabled(self, search_service, mock_collection_manager):
        """Test that filters are applied when apply_filters=True"""
        captured_filter = None

        async def capture_search(query_embedding, filter=None, limit=5):
            nonlocal captured_filter
            captured_filter = filter
            return {
                "documents": ["Test doc"],
                "metadatas": [{"tier": "A"}],
                "distances": [0.1],
                "ids": ["doc1"],
            }

        mock_client = AsyncMock()
        mock_client.search = capture_search
        mock_collection_manager.get_collection.return_value = mock_client

        search_service.query_router.route_query.return_value = {
            "collection_name": "zantara_books",
            "collections": ["zantara_books"],
            "confidence": 1.0,
            "is_pricing": False,
        }

        await search_service.search(query="test", user_level=2, limit=5, apply_filters=True)

        # Filters should be enabled (not forced to None)
        # For zantara_books with user_level=2, tier filter should be built
        assert captured_filter is not None

    @pytest.mark.asyncio
    async def test_search_filters_explicitly_disabled(
        self, search_service, mock_collection_manager
    ):
        """Test that filters are disabled when apply_filters=False"""
        captured_filter = "not_none_initially"

        async def capture_search(query_embedding, filter=None, limit=5):
            nonlocal captured_filter
            captured_filter = filter
            return {
                "documents": ["Test doc"],
                "metadatas": [{}],
                "distances": [0.1],
                "ids": ["doc1"],
            }

        mock_client = AsyncMock()
        mock_client.search = capture_search
        mock_collection_manager.get_collection.return_value = mock_client

        search_service.query_router.route_query.return_value = {
            "collection_name": "zantara_books",
            "collections": ["zantara_books"],
            "confidence": 1.0,
            "is_pricing": False,
        }

        await search_service.search(query="test", user_level=2, limit=5, apply_filters=False)

        # Filters should be disabled (forced to None)
        assert captured_filter is None
