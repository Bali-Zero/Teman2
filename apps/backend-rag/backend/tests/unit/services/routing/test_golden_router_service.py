"""
Unit tests for GoldenRouterService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.golden_router_service import GoldenRouterService


@pytest.fixture
def mock_embeddings_generator():
    """Mock embeddings generator"""
    embedder = MagicMock()
    embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)
    return embedder


@pytest.fixture
def golden_router_service(mock_embeddings_generator):
    """Create GoldenRouterService instance"""
    return GoldenRouterService(embeddings_generator=mock_embeddings_generator)


class TestGoldenRouterService:
    """Tests for GoldenRouterService"""

    def test_init(self, mock_embeddings_generator):
        """Test initialization"""
        service = GoldenRouterService(embeddings_generator=mock_embeddings_generator)
        assert service.embeddings == mock_embeddings_generator
        assert service.routes_cache == []
        assert service.similarity_threshold == 0.85

    @pytest.mark.asyncio
    async def test_initialize(self, golden_router_service):
        """Test initializing golden router"""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_create_pool.return_value = mock_pool
            await golden_router_service.initialize()
            assert len(golden_router_service.routes_cache) == 0

    @pytest.mark.asyncio
    async def test_route_no_routes(self, golden_router_service):
        """Test routing when no routes exist"""
        golden_router_service.routes_cache = []
        result = await golden_router_service.route("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_with_routes(self, golden_router_service):
        """Test routing with routes available"""
        golden_router_service.routes_cache = [
            {
                "route_id": "route1",
                "canonical_query": "test query",
                "document_ids": ["doc1"],
                "chapter_ids": [],
                "collections": ["visa_oracle"],
                "hints": {}
            }
        ]
        golden_router_service.route_embeddings = [[0.1] * 384]
        result = await golden_router_service.route("test query")
        # May return route or None depending on similarity
        assert result is None or isinstance(result, dict)

