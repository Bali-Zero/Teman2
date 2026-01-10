"""
Unit tests for Golden Router Service
Target: >99% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.routing.golden_router_service import GoldenRouterService


class TestGoldenRouterService:
    """Tests for GoldenRouterService"""

    def test_init(self):
        """Test initialization"""
        service = GoldenRouterService()
        assert service.embeddings is None
        assert service.golden_answer_service is None
        assert service.search_service is None
        assert service.db_pool is None
        assert service.routes_cache == []
        assert service.route_embeddings is None
        assert service.similarity_threshold == 0.85

    def test_init_with_params(self):
        """Test initialization with parameters"""
        mock_embeddings = MagicMock()
        mock_golden_answer = MagicMock()
        mock_search = MagicMock()

        service = GoldenRouterService(
            embeddings_generator=mock_embeddings,
            golden_answer_service=mock_golden_answer,
            search_service=mock_search,
        )
        assert service.embeddings == mock_embeddings
        assert service.golden_answer_service == mock_golden_answer
        assert service.search_service == mock_search

    @pytest.mark.asyncio
    @patch("backend.services.routing.golden_router_service.asyncpg.create_pool")
    @patch("backend.app.core.config.settings")
    async def test_get_db_pool(self, mock_settings, mock_create_pool):
        """Test getting database pool"""
        mock_settings.database_url = "postgresql://test"
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        service = GoldenRouterService()
        pool = await service._get_db_pool()

        assert pool == mock_pool
        mock_create_pool.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.services.routing.golden_router_service.asyncpg.create_pool")
    @patch("backend.app.core.config.settings")
    async def test_get_db_pool_cached(self, mock_settings, mock_create_pool):
        """Test getting database pool uses cache"""
        mock_settings.database_url = "postgresql://test"
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        service = GoldenRouterService()
        pool1 = await service._get_db_pool()
        pool2 = await service._get_db_pool()

        assert pool1 == pool2
        mock_create_pool.assert_called_once()  # Only called once

    @pytest.mark.asyncio
    @patch("backend.services.routing.golden_router_service.asyncpg.create_pool")
    @patch("backend.app.core.config.settings")
    async def test_get_db_pool_error(self, mock_settings, mock_create_pool):
        """Test getting database pool handles errors"""
        mock_settings.database_url = "postgresql://test"
        mock_create_pool.side_effect = Exception("Connection failed")

        service = GoldenRouterService()

        with pytest.raises(Exception, match="Connection failed"):
            await service._get_db_pool()

    @pytest.mark.asyncio
    @patch.object(GoldenRouterService, "_get_db_pool")
    async def test_initialize_empty_routes(self, mock_get_pool):
        """Test initialization with no routes in database"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        service = GoldenRouterService()
        await service.initialize()

        assert service.routes_cache == []
        assert service.route_embeddings is None
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(GoldenRouterService, "_get_db_pool")
    @patch("backend.services.routing.golden_router_service.asyncio.create_task")
    async def test_initialize_with_routes(self, mock_create_task, mock_get_pool):
        """Test initialization with routes in database"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            "route_id": "route1",
            "canonical_query": "test query",
            "document_ids": ["doc1"],
            "chapter_ids": ["ch1"],
            "collections": ["collection1"],
            "routing_hints": '{"hint": "value"}',
        }[key]
        mock_conn.fetch.return_value = [mock_row]

        mock_get_pool.return_value = mock_pool

        service = GoldenRouterService()
        await service.initialize()

        assert len(service.routes_cache) == 1
        assert service.routes_cache[0]["route_id"] == "route1"
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_no_routes(self):
        """Test routing with no routes cached"""
        service = GoldenRouterService()
        service.routes_cache = []
        service.route_embeddings = None

        result = await service.route("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_no_embeddings(self):
        """Test routing with routes but no embeddings"""
        service = GoldenRouterService()
        service.routes_cache = [{"route_id": "route1"}]
        service.route_embeddings = None
        service.embeddings = None

        result = await service.route("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_with_golden_answer_service(self):
        """Test routing using golden_answer_service"""
        mock_golden_answer = AsyncMock()
        mock_golden_answer.find_similar.return_value = {
            "answer": "test answer",
            "similarity": 0.90,
        }

        service = GoldenRouterService(golden_answer_service=mock_golden_answer)
        result = await service.route("test query", user_id="user1")

        assert result is not None
        assert result["answer"] == "test answer"
        assert result["similarity"] == 0.90
        mock_golden_answer.find_similar.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_route_with_golden_answer_service_low_similarity(self):
        """Test routing with golden_answer_service but low similarity"""
        mock_golden_answer = AsyncMock()
        mock_golden_answer.find_similar.return_value = {
            "answer": "test answer",
            "similarity": 0.50,  # Below threshold 0.85
        }

        service = GoldenRouterService(golden_answer_service=mock_golden_answer)
        service.routes_cache = []
        service.route_embeddings = None

        result = await service.route("test query")
        assert result is None

    @pytest.mark.asyncio
    @patch.object(GoldenRouterService, "_get_db_pool")
    async def test_update_usage_stats(self, mock_get_pool):
        """Test updating route usage statistics"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        service = GoldenRouterService()
        await service._update_usage_stats("route1")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "UPDATE golden_routes" in call_args[0][0]
        assert call_args[0][1] == "route1"

    @pytest.mark.asyncio
    @patch.object(GoldenRouterService, "_get_db_pool")
    async def test_update_usage_stats_error(self, mock_get_pool):
        """Test updating route usage stats handles errors"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute.side_effect = Exception("DB error")
        mock_get_pool.return_value = mock_pool

        service = GoldenRouterService()
        # Should not raise, just log warning
        await service._update_usage_stats("route1")

    @pytest.mark.asyncio
    @patch.object(GoldenRouterService, "initialize")
    @patch.object(GoldenRouterService, "_get_db_pool")
    async def test_add_route(self, mock_get_pool, mock_initialize):
        """Test adding a new route"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        service = GoldenRouterService()
        route_id = await service.add_route(
            canonical_query="test query",
            document_ids=["doc1"],
            chapter_ids=["ch1"],
            collections=["collection1"],
        )

        assert route_id.startswith("route_")
        assert len(route_id) > 6  # route_ + 8 hex chars
        mock_conn.execute.assert_called_once()
        mock_initialize.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(GoldenRouterService, "initialize")
    @patch.object(GoldenRouterService, "_get_db_pool")
    async def test_add_route_with_defaults(self, mock_get_pool, mock_initialize):
        """Test adding route with default collections"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        service = GoldenRouterService()
        route_id = await service.add_route(
            canonical_query="test query",
            document_ids=["doc1"],
        )

        assert route_id.startswith("route_")
        call_args = mock_conn.execute.call_args
        # Should use default collection "legal_unified"
        assert call_args[0][4] == ["legal_unified"]

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing the service"""
        mock_pool = AsyncMock()
        service = GoldenRouterService()
        service.db_pool = mock_pool

        await service.close()

        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_pool(self):
        """Test closing when no pool exists"""
        service = GoldenRouterService()
        service.db_pool = None

        # Should not raise
        await service.close()
