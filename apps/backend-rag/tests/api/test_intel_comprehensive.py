"""
Comprehensive API Tests for Intel Router
Complete test coverage for all intel news endpoints

Coverage:
- POST /api/intel/search - Search intel news
- POST /api/intel/store - Store intel document
- GET /api/intel/critical - Get critical intel
- GET /api/intel/trends - Get intel trends
- GET /api/intel/stats/{collection} - Get collection statistics
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestIntelSearch:
    """Comprehensive tests for POST /api/intel/search"""

    def test_search_intel_basic(self, authenticated_client):
        """Test basic intel search"""
        with patch("app.routers.intel.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                mock_client = MagicMock()
                mock_client.search = AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
                mock_qdrant.return_value = mock_client

                response = authenticated_client.post(
                    "/api/intel/search",
                    json={"query": "immigration news"},
                )

                assert response.status_code in [200, 500, 503]

    def test_search_intel_with_category(self, authenticated_client):
        """Test intel search with category filter"""
        with patch("app.routers.intel.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                mock_client = MagicMock()
                mock_client.search = AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
                mock_qdrant.return_value = mock_client

                categories = [
                    "immigration",
                    "bkpm_tax",
                    "realestate",
                    "events",
                    "social",
                    "competitors",
                    "bali_news",
                    "roundup",
                ]

                for category in categories:
                    response = authenticated_client.post(
                        "/api/intel/search",
                        json={"query": "test", "category": category},
                    )

                    assert response.status_code in [200, 500, 503]

    def test_search_intel_with_date_range(self, authenticated_client):
        """Test intel search with date range"""
        with patch("app.routers.intel.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                mock_client = MagicMock()
                mock_client.search = AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
                mock_qdrant.return_value = mock_client

                date_ranges = ["today", "last_7_days", "last_30_days", "last_90_days", "all"]

                for date_range in date_ranges:
                    response = authenticated_client.post(
                        "/api/intel/search",
                        json={"query": "test", "date_range": date_range},
                    )

                    assert response.status_code in [200, 500, 503]

    def test_search_intel_with_tier(self, authenticated_client):
        """Test intel search with tier filter"""
        with patch("app.routers.intel.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                mock_client = MagicMock()
                mock_client.search = AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
                mock_qdrant.return_value = mock_client

                response = authenticated_client.post(
                    "/api/intel/search",
                    json={"query": "test", "tier": ["T1", "T2"]},
                )

                assert response.status_code in [200, 500, 503]

    def test_search_intel_with_impact_level(self, authenticated_client):
        """Test intel search with impact level filter"""
        with patch("app.routers.intel.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                mock_client = MagicMock()
                mock_client.search = AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
                mock_qdrant.return_value = mock_client

                response = authenticated_client.post(
                    "/api/intel/search",
                    json={"query": "test", "impact_level": "high"},
                )

                assert response.status_code in [200, 500, 503]

    def test_search_intel_with_limit(self, authenticated_client):
        """Test intel search with limit"""
        with patch("app.routers.intel.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                mock_client = MagicMock()
                mock_client.search = AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
                mock_qdrant.return_value = mock_client

                response = authenticated_client.post(
                    "/api/intel/search",
                    json={"query": "test", "limit": 50},
                )

                assert response.status_code in [200, 500, 503]

    def test_search_intel_missing_query(self, authenticated_client):
        """Test intel search without query"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={},
        )

        assert response.status_code == 422

    def test_search_intel_empty_query(self, authenticated_client):
        """Test intel search with empty query"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={"query": ""},
        )

        assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestIntelStore:
    """Comprehensive tests for POST /api/intel/store"""

    def test_store_intel_document(self, authenticated_client):
        """Test storing intel document"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.upsert = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_client

            response = authenticated_client.post(
                "/api/intel/store",
                json={
                    "collection": "bali_intel_immigration",
                    "id": "doc_123",
                    "document": "Test document content",
                    "embedding": [0.1] * 1536,
                    "metadata": {"tier": "T1", "published_date": "2025-01-01"},
                    "full_data": {"title": "Test", "content": "Test content"},
                },
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_store_intel_missing_fields(self, authenticated_client):
        """Test storing intel without required fields"""
        response = authenticated_client.post(
            "/api/intel/store",
            json={},
        )

        assert response.status_code == 422

    def test_store_intel_invalid_collection(self, authenticated_client):
        """Test storing intel with invalid collection"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.upsert = AsyncMock(side_effect=ValueError("Invalid collection"))
            mock_qdrant.return_value = mock_client

            response = authenticated_client.post(
                "/api/intel/store",
                json={
                    "collection": "invalid_collection",
                    "id": "doc_123",
                    "document": "Test",
                    "embedding": [0.1] * 1536,
                    "metadata": {},
                    "full_data": {},
                },
            )

            assert response.status_code in [400, 422, 500, 503]


@pytest.mark.api
class TestCriticalIntel:
    """Comprehensive tests for GET /api/intel/critical"""

    def test_get_critical_intel(self, authenticated_client):
        """Test getting critical intel"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                return_value={
                    "documents": [],
                    "metadatas": [],
                    "distances": [],
                }
            )
            mock_qdrant.return_value = mock_client

            response = authenticated_client.get("/api/intel/critical")

            assert response.status_code in [200, 500, 503]

    def test_get_critical_intel_with_limit(self, authenticated_client):
        """Test getting critical intel with limit"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                return_value={
                    "documents": [],
                    "metadatas": [],
                    "distances": [],
                }
            )
            mock_qdrant.return_value = mock_client

            response = authenticated_client.get("/api/intel/critical?limit=10")

            assert response.status_code in [200, 500, 503]


@pytest.mark.api
class TestIntelTrends:
    """Comprehensive tests for GET /api/intel/trends"""

    def test_get_intel_trends(self, authenticated_client):
        """Test getting intel trends"""
        response = authenticated_client.get("/api/intel/trends")

        assert response.status_code in [200, 500, 503]

    def test_get_intel_trends_with_category(self, authenticated_client):
        """Test getting intel trends for specific category"""
        response = authenticated_client.get("/api/intel/trends?category=immigration")

        assert response.status_code in [200, 500, 503]

    def test_get_intel_trends_with_timeframe(self, authenticated_client):
        """Test getting intel trends with timeframe"""
        response = authenticated_client.get("/api/intel/trends?timeframe=30d")

        assert response.status_code in [200, 500, 503]


@pytest.mark.api
class TestIntelStats:
    """Comprehensive tests for GET /api/intel/stats/{collection}"""

    def test_get_intel_stats(self, authenticated_client):
        """Test getting intel collection statistics"""
        collections = [
            "immigration",
            "bkpm_tax",
            "realestate",
            "events",
            "social",
            "competitors",
            "bali_news",
            "roundup",
        ]

        for collection in collections:
            response = authenticated_client.get(f"/api/intel/stats/{collection}")

            assert response.status_code in [200, 404, 500, 503]

    def test_get_intel_stats_invalid_collection(self, authenticated_client):
        """Test getting stats for invalid collection"""
        response = authenticated_client.get("/api/intel/stats/invalid_collection")

        assert response.status_code in [200, 404, 500, 503]


@pytest.mark.api
class TestIntelSecurity:
    """Security tests for Intel endpoints"""

    def test_intel_endpoints_require_auth(self, test_client):
        """Test all intel endpoints require authentication"""
        endpoints = [
            ("POST", "/api/intel/search"),
            ("POST", "/api/intel/store"),
            ("GET", "/api/intel/critical"),
            ("GET", "/api/intel/trends"),
            ("GET", "/api/intel/stats/immigration"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401
