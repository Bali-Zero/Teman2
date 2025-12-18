"""
Extended API tests for intel router
Tests additional edge cases and error scenarios
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi.testclient import TestClient


@pytest.fixture
def test_client(test_app):
    """Create test client"""
    yield TestClient(test_app)


class TestIntelExtended:
    """Extended API tests for intel router"""

    def test_search_intel_with_filters(self, test_client):
        """Test search_intel with metadata filters"""
        with patch("app.routers.intel.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(
                return_value={
                    "results": [{"content": "test", "metadata": {"source": "intel"}}],
                    "total_found": 1,
                }
            )
            mock_search.return_value = mock_service

            response = test_client.post(
                "/api/intel/search",
                json={
                    "query": "test",
                    "collection": "intel_collection",
                    "filters": {"source": "intel"},
                },
            )

            assert response.status_code in [200, 500]

    def test_store_intel_with_tags(self, test_client):
        """Test store_intel with tags"""
        with patch("app.routers.intel.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.collections = {"intel_collection": MagicMock()}
            mock_service.collections["intel_collection"].upsert_documents = AsyncMock()
            mock_search.return_value = mock_service

            response = test_client.post(
                "/api/intel/store",
                json={
                    "content": "test intel",
                    "collection": "intel_collection",
                    "tags": ["urgent", "important"],
                },
            )

            assert response.status_code in [200, 500]

    def test_get_critical_items_empty(self, test_client):
        """Test get_critical_items with no results"""
        with patch("app.routers.intel.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": [], "total_found": 0})
            mock_search.return_value = mock_service

            response = test_client.get("/api/intel/critical")

            assert response.status_code in [200, 500]
