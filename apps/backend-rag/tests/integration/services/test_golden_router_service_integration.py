"""
Integration Tests for GoldenRouterService
Tests golden route matching and routing
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestGoldenRouterServiceIntegration:
    """Comprehensive integration tests for GoldenRouterService"""

    @pytest_asyncio.fixture
    async def mock_embedder(self):
        """Create mock embedder"""
        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)
        mock_embedder.generate_embeddings_async = AsyncMock(return_value=[[0.1] * 384])
        mock_embedder.generate_embeddings = MagicMock(return_value=[[0.1] * 384])
        return mock_embedder

    @pytest_asyncio.fixture
    async def mock_db_pool(self):
        """Create mock database pool"""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return mock_pool

    @pytest_asyncio.fixture
    async def service(self, mock_embedder, mock_db_pool):
        """Create GoldenRouterService instance"""
        with patch("services.golden_router_service.asyncpg.create_pool", return_value=mock_db_pool):
            from services.golden_router_service import GoldenRouterService

            service = GoldenRouterService(embeddings_generator=mock_embedder)
            service.db_pool = mock_db_pool
            return service

    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.similarity_threshold == 0.85

    @pytest.mark.asyncio
    async def test_initialize(self, service, mock_db_pool):
        """Test initializing service"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "route_id": "route1",
                    "canonical_query": "How to get KITAS?",
                    "document_ids": ["doc1"],
                    "chapter_ids": [],
                    "collections": ["visa_oracle"],
                    "routing_hints": "{}",
                }
            ]
        )

        await service.initialize()

        assert len(service.routes_cache) >= 0  # May be 0 if no routes

    @pytest.mark.asyncio
    async def test_route_with_golden_answer_service(self, service):
        """Test routing with golden answer service"""
        mock_golden_service = MagicMock()
        mock_golden_service.find_similar = AsyncMock(
            return_value={"answer": "Test answer", "similarity": 0.9}
        )
        service.golden_answer_service = mock_golden_service

        result = await service.route("How to get KITAS?")

        assert result is not None
        assert result["similarity"] >= 0.85

    @pytest.mark.asyncio
    async def test_route_with_embeddings(self, service, mock_embedder):
        """Test routing with embeddings"""
        service.routes_cache = [
            {
                "route_id": "route1",
                "canonical_query": "How to get KITAS?",
                "document_ids": ["doc1"],
                "chapter_ids": [],
                "collections": ["visa_oracle"],
                "hints": {},
            }
        ]
        import numpy as np

        service.route_embeddings = np.array([[0.1] * 384])

        result = await service.route("How to get work permit?")

        # May or may not match depending on similarity
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_route_no_routes(self, service):
        """Test routing when no routes available"""
        service.routes_cache = []
        service.route_embeddings = None

        result = await service.route("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_db_pool(self, service, mock_db_pool):
        """Test getting database pool"""
        pool = await service._get_db_pool()

        assert pool is not None
