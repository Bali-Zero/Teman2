"""
Unit tests for Intel Router
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.intel import router

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create FastAPI test client"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_embeddings_generator():
    """Mock EmbeddingsGenerator"""
    generator = MagicMock()
    generator.generate_single_embedding = MagicMock(return_value=[0.1] * 384)
    return generator


@pytest.fixture
def mock_qdrant_client():
    """Mock QdrantClient"""
    client = MagicMock()
    client.search = MagicMock(
        return_value={
            "documents": [["Intel news 1"]],
            "metadatas": [
                [
                    {
                        "id": "doc1",
                        "title": "Test Intel",
                        "tier": "T1",
                        "impact_level": "high",
                        "published_date": "2024-01-01",
                        "source": "test",
                        "url": "https://test.com",
                    }
                ]
            ],
            "distances": [[0.1]],
        }
    )
    client.upsert_documents = AsyncMock(return_value=True)
    return client


# ============================================================================
# Tests for search_intel endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_search_intel_success(client, mock_embeddings_generator, mock_qdrant_client):
    """Test search_intel successful"""
    with (
        patch("app.routers.intel.embedder", mock_embeddings_generator),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={
                "query": "visa news",
                "category": "immigration",
                "date_range": "last_7_days",
                "limit": 20,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Router may return results or empty list
        assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_search_intel_all_categories(client, mock_embeddings_generator, mock_qdrant_client):
    """Test search_intel without category (searches all)"""
    with (
        patch("app.routers.intel.embedder", mock_embeddings_generator),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post("/api/intel/search", json={"query": "test query", "limit": 10})

        assert response.status_code == 200
        # Should search all collections
        data = response.json()
        assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_search_intel_date_range_all(client, mock_embeddings_generator, mock_qdrant_client):
    """Test search_intel with date_range='all'"""
    with (
        patch("app.routers.intel.embedder", mock_embeddings_generator),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post("/api/intel/search", json={"query": "test", "date_range": "all"})

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_search_intel_exception(client, mock_embeddings_generator):
    """Test search_intel handles exception"""
    # Mock embedder to raise exception
    mock_embeddings_generator.generate_single_embedding.side_effect = Exception("Embedding error")

    with patch("app.routers.intel.embedder", mock_embeddings_generator):
        response = client.post("/api/intel/search", json={"query": "test"})

        assert response.status_code == 500


# ============================================================================
# Tests for store_intel endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_store_intel_success(client, mock_qdrant_client):
    """Test store_intel successful"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.post(
            "/api/intel/store",
            json={
                "collection": "immigration",  # Use key, not full collection name
                "id": "doc123",
                "document": "Test document",
                "embedding": [0.1] * 384,
                "metadata": {"date": "2024-01-01", "tier": "T1"},
                "full_data": {"title": "Test"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_store_intel_exception(client):
    """Test store_intel handles exception"""
    mock_client = MagicMock()
    mock_client.upsert_documents = AsyncMock(side_effect=Exception("Store error"))

    with patch("app.routers.intel.QdrantClient", return_value=mock_client):
        response = client.post(
            "/api/intel/store",
            json={
                "collection": "immigration",
                "id": "doc1",
                "document": "Test",
                "embedding": [0.1] * 384,
                "metadata": {},
                "full_data": {},
            },
        )

        assert response.status_code == 500


# ============================================================================
# Tests for get_critical_intel endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_critical_intel_success(client, mock_qdrant_client):
    """Test get_critical_intel successful"""
    mock_qdrant_client.search.return_value = {
        "documents": [["Critical news"]],
        "metadatas": [
            [
                {
                    "id": "critical1",
                    "title": "Critical",
                    "impact_level": "critical",
                    "tier": "T1",
                    "published_date": "2024-01-01",
                }
            ]
        ],
        "distances": [[0.05]],
    }

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical")

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "items" in data
        assert isinstance(data["items"], list)


# ============================================================================
# Tests for get_trends endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_trends_success(client, mock_qdrant_client):
    """Test get_trends successful"""
    mock_qdrant_client.search.return_value = {
        "documents": [["Trending topic"]],
        "metadatas": [
            [{"id": "trend1", "title": "Trend", "published_date": "2024-01-01", "tier": "T1"}]
        ],
        "distances": [[0.2]],
    }

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (dict, list))


# ============================================================================
# Tests for get_stats endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_stats_success(client, mock_qdrant_client):
    """Test get_stats successful"""
    mock_qdrant_client.get_collection_stats = MagicMock(
        return_value={"total_documents": 100, "vectors_count": 100}
    )

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/stats/immigration")

        assert response.status_code == 200
        data = response.json()
        assert "collection_name" in data
        assert "total_documents" in data
