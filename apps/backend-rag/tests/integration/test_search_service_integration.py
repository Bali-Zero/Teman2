"""
Integration-style tests for SearchService with stubbed Qdrant and router.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.cache import invalidate_cache

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def stubbed_search_service():
    """Provide a SearchService wired to mocked dependencies."""
    with (
        patch("core.embeddings.create_embeddings_generator") as mock_embedder,
        patch("services.search_service.CollectionManager") as mock_collection_manager,
        patch(
            "services.query_router_integration.QueryRouterIntegration"
        ) as mock_router_integration,
        patch("services.search_service.ConflictResolver"),
        patch("services.cultural_insights_service.CulturalInsightsService"),
        patch("services.collection_health_service.CollectionHealthService"),
    ):
        embedder = MagicMock()
        embedder.generate_query_embedding.return_value = [0.4, 0.2]
        embedder.provider = "stub"
        embedder.dimensions = 2
        mock_embedder.return_value = embedder

        collection_manager = MagicMock()
        mock_collection_manager.return_value = collection_manager

        router = MagicMock()
        router.route_query.return_value = {"collection_name": "zantara_books"}
        mock_router_integration.return_value = router

        from services.search_service import SearchService

        service = SearchService()
        yield service, collection_manager, router


@pytest.fixture(autouse=True)
def clear_search_cache():
    invalidate_cache("zantara:rag_search:*")
    yield
    invalidate_cache("zantara:rag_search:*")


@pytest.mark.integration
class TestSearchServiceIntegration:
    def test_search_service_initialization(self):
        from services.search_service import SearchService

        service = SearchService()
        assert service.collection_manager is not None
        assert service.query_router is not None

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self, stubbed_search_service):
        service, collection_manager, router = stubbed_search_service
        router.route_query.return_value = {"collection_name": "visa_oracle"}

        vector_client = SimpleNamespace()
        vector_client.search = AsyncMock(
            return_value={
                "ids": ["doc-1"],
                "documents": ["Visa guidance"],
                "distances": [0.9],
                "metadatas": [{"book_title": "Visa"}],
            }
        )
        collection_manager.get_collection.side_effect = lambda name: vector_client

        result = await service.search("test", user_level=1)
        assert result["results"][0]["text"] == "Visa guidance"

    @pytest.mark.asyncio
    async def test_tier_filters_translated_to_qdrant(self, stubbed_search_service):
        from app.models import TierLevel

        service, collection_manager, router = stubbed_search_service
        router.route_query.return_value = {"collection_name": "zantara_books"}

        vector_client = SimpleNamespace()
        vector_client.search = AsyncMock(
            return_value={
                "ids": ["doc-2"],
                "documents": ["Tier doc"],
                "distances": [0.4],
                "metadatas": [{"tier": "S"}],
            }
        )
        collection_manager.get_collection.side_effect = lambda name: vector_client

        result = await service.search(
            "share wisdom",
            user_level=2,
            tier_filter=[TierLevel.S],
            limit=1,
            apply_filters=True,  # Enable filters for test
        )

        assert result["allowed_tiers"] == ["S"]
        _, kwargs = vector_client.search.call_args
        # Filters should be applied when apply_filters=True
        if kwargs.get("filter"):
            assert kwargs["filter"]["tier"] == {"$in": ["S"]}
            assert kwargs["filter"]["status_vigensi"] == {"$ne": "dicabut"}

    @pytest.mark.asyncio
    async def test_unknown_collection_falls_back_to_default(self, stubbed_search_service):
        service, collection_manager, router = stubbed_search_service
        router.route_query.return_value = {"collection_name": "unknown"}

        fallback_client = SimpleNamespace()
        fallback_client.search = AsyncMock(
            return_value={
                "ids": ["doc-3"],
                "documents": ["Fallback doc"],
                "distances": [0.3],
                "metadatas": [{}],
            }
        )

        def get_collection(name):
            if name == "unknown":
                return None
            if name == "visa_oracle":
                return fallback_client
            return None

        collection_manager.get_collection.side_effect = get_collection

        result = await service.search("fallback", user_level=0)

        assert result["collection_used"] == "visa_oracle"
        fallback_client.search.assert_awaited_once()

    def test_build_search_filter_excludes_repealed(self, stubbed_search_service):
        service, _, _ = stubbed_search_service
        combined = service._build_search_filter(
            tier_filter={"tier": {"$in": ["S"]}, "status_vigensi": {"$in": ["dicabut", "berlaku"]}}
        )
        assert combined["tier"] == {"$in": ["S"]}
        assert combined["status_vigensi"] == {"$in": ["berlaku"]}
