"""
Extended integration tests for SearchService
Tests search functionality with various scenarios
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestSearchServiceExtendedIntegration:
    """Extended integration tests for SearchService"""

    @pytest.mark.asyncio
    async def test_search_service_initialization(self):
        """Test SearchService initialization"""
        with (
            patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder,
            patch("backend.services.collection_manager.CollectionManager") as mock_collection,
            patch(
                "backend.services.query_router_integration.QueryRouterIntegration"
            ) as mock_router,
        ):
            mock_embedder_instance = MagicMock()
            mock_embedder_instance.generate_query_embedding.return_value = [0.1] * 1536
            mock_embedder_instance.provider = "openai"
            mock_embedder_instance.dimensions = 1536
            mock_embedder.return_value = mock_embedder_instance

            mock_collection_instance = MagicMock()
            mock_collection.return_value = mock_collection_instance

            mock_router_instance = MagicMock()
            mock_router.return_value = mock_router_instance

            from backend.services.search_service import SearchService

            service = SearchService(
                collection_manager=mock_collection_instance, query_router=mock_router_instance
            )

            assert service is not None
            assert service.embedder is not None

    def test_search_service_level_to_tiers(self):
        """Test LEVEL_TO_TIERS mapping"""
        from backend.services.search_service import SearchService

        assert SearchService.LEVEL_TO_TIERS[0] == ["S"]
        assert SearchService.LEVEL_TO_TIERS[1] == ["S", "A"]
        assert SearchService.LEVEL_TO_TIERS[2] == ["S", "A", "B", "C"]
        assert SearchService.LEVEL_TO_TIERS[3] == ["S", "A", "B", "C", "D"]

    def test_build_search_filter(self):
        """Test _build_search_filter method"""
        with (
            patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder,
            patch("backend.services.collection_manager.CollectionManager") as mock_collection,
            patch(
                "backend.services.query_router_integration.QueryRouterIntegration"
            ) as mock_router,
        ):
            mock_collection_instance = MagicMock()
            mock_collection.return_value = mock_collection_instance

            mock_router_instance = MagicMock()
            mock_router.return_value = mock_router_instance

            from backend.services.search_service import SearchService

            service = SearchService(
                collection_manager=mock_collection_instance, query_router=mock_router_instance
            )

            # Test filter building
            filter_result = service._build_search_filter(tier_filter={"tier": {"$in": ["S"]}})
            assert isinstance(filter_result, dict)
