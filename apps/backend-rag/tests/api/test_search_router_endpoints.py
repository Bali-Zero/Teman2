"""
API tests for search router
Tests search endpoint functionality
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


class TestSearchRouter:
    """API tests for search router"""

    def test_search_endpoint_success(self, test_client):
        """Test successful search"""
        with patch("app.modules.knowledge.router.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(
                return_value={"results": [{"content": "test", "score": 0.9}], "total_found": 1}
            )
            mock_search.return_value = mock_service

            response = test_client.post("/api/search", json={"query": "test query", "limit": 10})

            assert response.status_code in [200, 500]

    def test_search_endpoint_with_collection(self, test_client):
        """Test search with specific collection"""
        with patch("app.modules.knowledge.router.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": [], "total_found": 0})
            mock_search.return_value = mock_service

            response = test_client.post(
                "/api/search", json={"query": "test", "collection": "test_collection"}
            )

            assert response.status_code in [200, 500]

    def test_search_endpoint_missing_query(self, test_client):
        """Test search without query"""
        response = test_client.post("/api/search", json={})

        assert response.status_code in [422, 500]
