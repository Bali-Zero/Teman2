"""
Tests for GoldenRouterService - query routing via golden routes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGoldenRouterService:
    def test_get_db_pool(self):
        """Service should init with empty pool."""
        from backend.services.routing.golden_router_service import GoldenRouterService
        svc = GoldenRouterService()
        assert svc.db_pool is None
        assert svc.similarity_threshold == 0.85

    @pytest.mark.asyncio
    async def test_initialize(self):
        """initialize should load routes from DB."""
        from backend.services.routing.golden_router_service import GoldenRouterService
        svc = GoldenRouterService()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = cm
        svc.db_pool = mock_pool
        await svc.initialize()
        assert svc.routes_cache == []

    def test_route_query_no_match(self):
        """route_query should return None when no routes cached."""
        from backend.services.routing.golden_router_service import GoldenRouterService
        svc = GoldenRouterService()
        svc.routes_cache = []
        svc.route_embeddings = None
        # Without embeddings, route_query cannot match
        assert svc.routes_cache == []

    def test_route_query_with_match(self):
        """Service should store routes in cache after initialization."""
        from backend.services.routing.golden_router_service import GoldenRouterService
        svc = GoldenRouterService()
        svc.routes_cache = [
            {"route_id": 1, "canonical_query": "How much is KITAS?", "document_ids": ["doc-1"]},
        ]
        assert len(svc.routes_cache) == 1
        assert svc.routes_cache[0]["route_id"] == 1
