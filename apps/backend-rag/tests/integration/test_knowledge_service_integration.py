"""
Integration-style tests for KnowledgeService with stubbed dependencies.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.cache import invalidate_cache

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def stubbed_knowledge_service():
    """Provision a KnowledgeService with embeddings/router/Qdrant all stubbed."""
    with (
        patch("core.embeddings.create_embeddings_generator") as mock_embedder,
        patch("app.modules.knowledge.service.QdrantClient") as mock_qdrant,
        patch("app.modules.knowledge.service.QueryRouter") as mock_router,
    ):
        embedder = MagicMock()
        embedder.generate_query_embedding.return_value = [0.1, 0.2, 0.3]
        embedder.provider = "stub"
        embedder.dimensions = 3
        mock_embedder.return_value = embedder

        router_instance = MagicMock()
        router_instance.route.return_value = "zantara_books"
        mock_router.return_value = router_instance

        mock_qdrant.return_value = MagicMock()

        from app.modules.knowledge.service import KnowledgeService

        service = KnowledgeService()
        yield service, embedder, router_instance


@pytest.fixture(autouse=True)
def clear_cached_results():
    """Ensure cached decorator does not short-circuit consecutive tests."""
    invalidate_cache("zantara:rag_search:*")
    yield
    invalidate_cache("zantara:rag_search:*")


@pytest.mark.integration
class TestKnowledgeServiceIntegration:
    @pytest.mark.asyncio
    async def test_knowledge_service_search_returns_formatted_results(
        self, stubbed_knowledge_service
    ):
        service, _, router = stubbed_knowledge_service
        router.route.return_value = "zantara_books"

        vector_client = MagicMock()
        vector_client.search = AsyncMock(
            return_value={
                "ids": ["doc-1"],
                "documents": ["Test document"],
                "distances": [0.1],
                "metadatas": [{"book_title": "Test Book"}],
            }
        )
        service.collections["zantara_books"] = vector_client

        result = await service.search("test query", user_level=2, limit=1)

        assert result["collection_used"] == "zantara_books"
        assert result["results"][0]["text"] == "Test document"
        vector_client.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pricing_keyword_routes_to_pricing_collection(self, stubbed_knowledge_service):
        service, _, router = stubbed_knowledge_service
        router.route.return_value = "zantara_books"

        pricing_client = MagicMock()
        pricing_client.search = AsyncMock(
            return_value={
                "ids": ["price-1"],
                "documents": ["Pricing sheet"],
                "distances": [0.5],
                "metadatas": [{"source": "official"}],
            }
        )
        service.collections["bali_zero_pricing"] = pricing_client

        result = await service.search("how much does it cost?", user_level=1)

        assert result["collection_used"] == "bali_zero_pricing"
        assert result["results"][0]["metadata"]["pricing_priority"] == "high"
        pricing_client.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_collection_falls_back_to_visa_oracle(self, stubbed_knowledge_service):
        service, _, _ = stubbed_knowledge_service

        fallback_client = MagicMock()
        fallback_client.search = AsyncMock(
            return_value={
                "ids": ["visa-1"],
                "documents": ["Visa info"],
                "distances": [0.2],
                "metadatas": [{"source": "visa_oracle"}],
            }
        )
        service.collections = {"visa_oracle": fallback_client}

        result = await service.search(
            "Explain requirements", user_level=0, collection_override="unknown_collection"
        )

        assert result["collection_used"] == "visa_oracle"
        fallback_client.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tier_filter_applied_for_zantara_books(self, stubbed_knowledge_service):
        from app.models import TierLevel

        service, _, _ = stubbed_knowledge_service
        zantara_client = MagicMock()
        zantara_client.search = AsyncMock(
            return_value={
                "ids": ["doc-3"],
                "documents": ["Tier-specific doc"],
                "distances": [0.3],
                "metadatas": [{"tier": "B"}],
            }
        )
        service.collections["zantara_books"] = zantara_client

        result = await service.search(
            "share wisdom",
            user_level=3,
            tier_filter=[TierLevel.S, TierLevel.B],
            collection_override="zantara_books",
        )

        assert result["allowed_tiers"] == ["S", "B"]
        _, kwargs = zantara_client.search.call_args
        assert kwargs["filter"] == {"tier": {"$in": ["S", "B"]}}
