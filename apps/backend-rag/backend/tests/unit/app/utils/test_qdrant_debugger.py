"""
Unit tests for app/utils/qdrant_debugger.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.utils.qdrant_debugger import (
    CollectionHealth,
    QdrantDebugger,
    QueryPerformance,
)


class TestCollectionHealth:
    """Tests for CollectionHealth dataclass"""

    def test_init(self):
        """Test CollectionHealth initialization"""
        health = CollectionHealth(
            name="test_collection",
            points_count=100,
            vectors_count=100,
            indexed=True,
            status="green",
        )
        assert health.name == "test_collection"
        assert health.points_count == 100
        assert health.vectors_count == 100
        assert health.indexed is True
        assert health.status == "green"
        assert health.error is None

    def test_init_with_error(self):
        """Test CollectionHealth with error"""
        health = CollectionHealth(
            name="test",
            points_count=0,
            vectors_count=0,
            indexed=False,
            status="error",
            error="Connection failed",
        )
        assert health.error == "Connection failed"


class TestQueryPerformance:
    """Tests for QueryPerformance dataclass"""

    def test_init(self):
        """Test QueryPerformance initialization"""
        perf = QueryPerformance(
            collection="test_collection", query="test query", duration_ms=10.5, results_count=5
        )
        assert perf.collection == "test_collection"
        assert perf.query == "test query"
        assert perf.duration_ms == 10.5
        assert perf.results_count == 5
        assert perf.error is None

    def test_init_with_error(self):
        """Test QueryPerformance with error"""
        perf = QueryPerformance(
            collection="test", query="test", duration_ms=0.0, results_count=0, error="Query failed"
        )
        assert perf.error == "Query failed"


class TestQdrantDebugger:
    """Tests for QdrantDebugger"""

    def test_init_default(self):
        """Test QdrantDebugger initialization with defaults"""
        with patch("backend.app.utils.qdrant_debugger.settings") as mock_settings:
            mock_settings.qdrant_url = "http://localhost:6333"
            mock_settings.qdrant_api_key = None

            debugger = QdrantDebugger()

            assert debugger.qdrant_url == "http://localhost:6333"
            assert debugger.api_key is None
            assert debugger.headers == {}

    def test_init_custom(self):
        """Test QdrantDebugger initialization with custom values"""
        debugger = QdrantDebugger(qdrant_url="http://custom:6333", api_key="test-key")

        assert debugger.qdrant_url == "http://custom:6333"
        assert debugger.api_key == "test-key"
        assert debugger.headers["api-key"] == "test-key"

    @pytest.mark.asyncio
    async def test_get_collection_health_success(self):
        """Test getting collection health successfully"""
        debugger = QdrantDebugger(qdrant_url="http://localhost:6333")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "points_count": 100,
                "vectors_count": 100,
                "config": {"params": {"vectors": {"on_disk": True}}},
                "status": "green",
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            health = await debugger.get_collection_health("test_collection")

            assert health.name == "test_collection"
            assert health.points_count == 100
            assert health.status == "green"

    @pytest.mark.asyncio
    async def test_get_collection_health_error(self):
        """Test getting collection health with error"""
        debugger = QdrantDebugger(qdrant_url="http://localhost:6333")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client.return_value = mock_client_instance

            health = await debugger.get_collection_health("test_collection")

            assert health.status == "error"
            assert health.error is not None

    @pytest.mark.asyncio
    async def test_get_all_collections_health(self):
        """Test getting all collections health"""
        debugger = QdrantDebugger(qdrant_url="http://localhost:6333")

        mock_collections_response = MagicMock()
        mock_collections_response.json.return_value = {
            "result": {"collections": [{"name": "coll1"}, {"name": "coll2"}]}
        }
        mock_collections_response.raise_for_status = MagicMock()

        mock_health_response = MagicMock()
        mock_health_response.json.return_value = {
            "result": {
                "points_count": 10,
                "vectors_count": 10,
                "config": {"params": {"vectors": {"on_disk": False}}},
                "status": "green",
            }
        }
        mock_health_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.get = AsyncMock(
                side_effect=[mock_collections_response, mock_health_response, mock_health_response]
            )
            mock_client.return_value = mock_client_instance

            health_list = await debugger.get_all_collections_health()

            assert len(health_list) == 2

    @pytest.mark.asyncio
    async def test_analyze_query_performance(self):
        """Test analyzing query performance"""
        debugger = QdrantDebugger(qdrant_url="http://localhost:6333")

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [{"id": 1}, {"id": 2}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client, patch("time.time", side_effect=[0.0, 0.01]):
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            perf = await debugger.analyze_query_performance(
                collection="test", query_vector=[0.1] * 1536, limit=10
            )

            assert perf.collection == "test"
            assert perf.results_count == 2
            assert perf.duration_ms > 0

    @pytest.mark.asyncio
    async def test_get_collection_stats(self):
        """Test getting collection statistics"""
        debugger = QdrantDebugger(qdrant_url="http://localhost:6333")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "points_count": 100,
                "config": {"params": {"vectors": {"size": 1536, "distance": "Cosine"}}},
                "status": "green",
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            stats = await debugger.get_collection_stats("test_collection")

            # get_collection_stats returns name, points_count, vectors_count, status, config
            assert stats["points_count"] == 100
            assert stats["name"] == "test_collection"
            assert stats["status"] == "green"
            assert "config" in stats
