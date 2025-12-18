"""
Comprehensive tests for GoldenRouterService
Target: 100% coverage
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGoldenRouterService:
    """Tests for GoldenRouterService class"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        with patch("services.golden_router_service.settings") as mock:
            mock.database_url = "postgresql://test:test@localhost/test"
            yield mock

    @pytest.fixture
    def service(self, mock_settings):
        """Create GoldenRouterService instance"""
        from services.golden_router_service import GoldenRouterService

        return GoldenRouterService()

    @pytest.fixture
    def service_with_deps(self, mock_settings):
        """Create service with dependencies"""
        from services.golden_router_service import GoldenRouterService

        mock_embeddings = MagicMock()
        mock_golden = MagicMock()
        mock_search = MagicMock()
        return GoldenRouterService(
            embeddings_generator=mock_embeddings,
            golden_answer_service=mock_golden,
            search_service=mock_search,
        )

    def test_init_default(self, service):
        """Test default initialization"""
        assert service.embeddings is None
        assert service.golden_answer_service is None
        assert service.search_service is None
        assert service.db_pool is None
        assert service.routes_cache == []
        assert service.route_embeddings is None
        assert service.similarity_threshold == 0.85

    def test_init_with_deps(self, service_with_deps):
        """Test initialization with dependencies"""
        assert service_with_deps.embeddings is not None
        assert service_with_deps.golden_answer_service is not None
        assert service_with_deps.search_service is not None

    @pytest.mark.asyncio
    async def test_get_db_pool_creates_pool(self, service, mock_settings):
        """Test getting/creating database pool"""
        mock_pool = MagicMock()

        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool

            pool = await service._get_db_pool()

            assert pool == mock_pool
            assert service.db_pool == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_returns_existing(self, service):
        """Test returns existing pool"""
        mock_pool = MagicMock()
        service.db_pool = mock_pool

        pool = await service._get_db_pool()

        assert pool == mock_pool

    @pytest.mark.asyncio
    async def test_get_db_pool_failure(self, service, mock_settings):
        """Test pool creation failure"""
        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await service._get_db_pool()

    @pytest.mark.asyncio
    async def test_initialize_with_routes(self, service, mock_settings):
        """Test initializing with routes from database"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "route_id": "route_123",
                    "canonical_query": "What is KITAS?",
                    "document_ids": ["doc1", "doc2"],
                    "chapter_ids": ["ch1"],
                    "collections": ["visa_oracle"],
                    "routing_hints": json.dumps({"priority": "high"}),
                }
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_pool

            with patch("asyncio.create_task"):
                await service.initialize()

        assert len(service.routes_cache) == 1
        assert service.routes_cache[0]["route_id"] == "route_123"

    @pytest.mark.asyncio
    async def test_initialize_with_dict_hints(self, service, mock_settings):
        """Test initializing with already-parsed routing hints"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "route_id": "route_123",
                    "canonical_query": "What is KITAS?",
                    "document_ids": ["doc1"],
                    "chapter_ids": [],
                    "collections": ["visa_oracle"],
                    "routing_hints": {"priority": "high"},  # Already dict
                }
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_pool

            with patch("asyncio.create_task"):
                await service.initialize()

        assert service.routes_cache[0]["hints"] == {"priority": "high"}

    @pytest.mark.asyncio
    async def test_initialize_no_routes(self, service, mock_settings):
        """Test initializing with no routes"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_pool

            await service.initialize()

        assert service.routes_cache == []
        assert service.route_embeddings is None

    @pytest.mark.asyncio
    async def test_generate_embeddings_background_from_cache(self, service):
        """Test loading embeddings from cache"""

        import numpy as np

        queries = ["Query 1", "Query 2"]
        cached_embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()) as mock_open:
                mock_open.return_value.__enter__.return_value.read = MagicMock()

                with patch("pickle.load") as mock_pickle:
                    mock_pickle.return_value = cached_embeddings

                    await service._generate_embeddings_background(queries)

        assert service.route_embeddings is not None

    @pytest.mark.asyncio
    async def test_generate_embeddings_background_cache_mismatch(self, service):
        """Test regenerating when cache count differs"""
        import numpy as np

        queries = ["Query 1", "Query 2", "Query 3"]
        cached_embeddings = np.array([[0.1, 0.2]])  # Only 1 embedding

        mock_embeddings = MagicMock()
        mock_embeddings.generate_embeddings_async = AsyncMock(return_value=[[0.1], [0.2], [0.3]])
        service.embeddings = mock_embeddings

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("pickle.load", return_value=cached_embeddings):
                    with patch("pickle.dump"):
                        await service._generate_embeddings_background(queries)

    @pytest.mark.asyncio
    async def test_generate_embeddings_background_fresh(self, service):
        """Test generating fresh embeddings"""

        queries = ["Query 1", "Query 2"]
        mock_embeddings = MagicMock()
        mock_embeddings.generate_embeddings_async = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
        service.embeddings = mock_embeddings

        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", MagicMock()):
                with patch("pickle.dump"):
                    await service._generate_embeddings_background(queries)

        assert service.route_embeddings is not None

    @pytest.mark.asyncio
    async def test_generate_embeddings_background_sync_fallback(self, service):
        """Test fallback to sync embedding generation"""

        queries = ["Query 1"]
        mock_embeddings = MagicMock()
        mock_embeddings.generate_embeddings_async = AsyncMock(return_value=[])  # Returns empty
        mock_embeddings.generate_embeddings = MagicMock(return_value=[[0.1, 0.2]])
        service.embeddings = mock_embeddings

        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", MagicMock()):
                with patch("pickle.dump"):
                    await service._generate_embeddings_background(queries)

    @pytest.mark.asyncio
    async def test_generate_embeddings_background_exception(self, service):
        """Test exception handling in embedding generation"""
        queries = ["Query 1"]
        mock_embeddings = MagicMock()
        mock_embeddings.generate_embeddings_async = AsyncMock(side_effect=Exception("Error"))
        service.embeddings = mock_embeddings

        with patch("os.path.exists", return_value=False):
            await service._generate_embeddings_background(queries)  # Should not raise

    @pytest.mark.asyncio
    async def test_route_with_golden_answer_service(self, service_with_deps):
        """Test routing using golden answer service"""
        service_with_deps.golden_answer_service.find_similar = AsyncMock(
            return_value={"answer": "KITAS is...", "similarity": 0.9}
        )

        result = await service_with_deps.route("What is KITAS?")

        assert result is not None
        assert result["answer"] == "KITAS is..."
        assert result["similarity"] == 0.9

    @pytest.mark.asyncio
    async def test_route_golden_answer_below_threshold(self, service_with_deps):
        """Test routing when golden answer below threshold"""
        service_with_deps.golden_answer_service.find_similar = AsyncMock(
            return_value={
                "answer": "Some answer",
                "similarity": 0.5,  # Below 0.85 threshold
            }
        )

        result = await service_with_deps.route("Random query")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_golden_answer_exception(self, service_with_deps):
        """Test routing when golden answer service fails"""
        service_with_deps.golden_answer_service.find_similar = AsyncMock(
            side_effect=Exception("Service error")
        )

        result = await service_with_deps.route("Query")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_no_cache(self, service):
        """Test routing with empty cache"""
        service.routes_cache = []

        result = await service.route("Query")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_no_embeddings(self, service):
        """Test routing with no embeddings"""
        service.routes_cache = [{"route_id": "1"}]
        service.route_embeddings = None

        result = await service.route("Query")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_no_embeddings_generator(self, service):
        """Test routing without embeddings generator"""
        import numpy as np

        service.routes_cache = [{"route_id": "1"}]
        service.route_embeddings = np.array([[0.1, 0.2]])
        service.embeddings = None

        result = await service.route("Query")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_match_found(self, service, mock_settings):
        """Test successful route match"""
        import numpy as np

        service.routes_cache = [
            {
                "route_id": "route_123",
                "canonical_query": "What is KITAS?",
                "document_ids": ["doc1"],
                "chapter_ids": ["ch1"],
                "collections": ["visa"],
                "hints": {"priority": "high"},
            }
        ]
        service.route_embeddings = np.array([[0.1, 0.2, 0.3]])

        mock_embeddings = MagicMock()
        mock_embeddings.generate_query_embedding = MagicMock(return_value=[0.1, 0.2, 0.3])
        service.embeddings = mock_embeddings

        with patch("services.golden_router_service.cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.9]])

            with patch.object(service, "_update_usage_stats", new_callable=AsyncMock):
                result = await service.route("What is KITAS?")

        assert result is not None
        assert result["route_id"] == "route_123"
        assert result["score"] == 0.9

    @pytest.mark.asyncio
    async def test_route_below_threshold(self, service):
        """Test no match when below threshold"""
        import numpy as np

        service.routes_cache = [{"route_id": "1"}]
        service.route_embeddings = np.array([[0.1, 0.2]])

        mock_embeddings = MagicMock()
        mock_embeddings.generate_query_embedding = MagicMock(return_value=[0.9, 0.9])
        service.embeddings = mock_embeddings

        with patch("services.golden_router_service.cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.5]])  # Below 0.85 threshold

            result = await service.route("Different query")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_usage_stats_success(self, service, mock_settings):
        """Test updating usage statistics"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool

            await service._update_usage_stats("route_123")

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_usage_stats_exception(self, service, mock_settings):
        """Test exception handling in update stats"""
        with patch.object(service, "_get_db_pool", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("DB error")

            await service._update_usage_stats("route_123")  # Should not raise

    @pytest.mark.asyncio
    async def test_add_route(self, service, mock_settings):
        """Test adding a new route"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool

            with patch.object(service, "initialize", new_callable=AsyncMock):
                route_id = await service.add_route(
                    canonical_query="New query?", document_ids=["doc1", "doc2"]
                )

        assert route_id.startswith("route_")
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_route_with_optional_params(self, service, mock_settings):
        """Test adding route with optional parameters"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_router_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool

            with patch.object(service, "initialize", new_callable=AsyncMock):
                route_id = await service.add_route(
                    canonical_query="New query?",
                    document_ids=["doc1"],
                    chapter_ids=["ch1", "ch2"],
                    collections=["custom_collection"],
                )

        assert route_id.startswith("route_")

    @pytest.mark.asyncio
    async def test_close_with_pool(self, service):
        """Test closing with existing pool"""
        mock_pool = AsyncMock()
        service.db_pool = mock_pool

        await service.close()

        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_pool(self, service):
        """Test closing without pool"""
        service.db_pool = None

        await service.close()  # Should not raise
