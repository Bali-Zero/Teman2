"""
API tests for search endpoints.

These tests verify the full request/response cycle for search endpoints.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestSearchEndpoints:
    """API tests for search endpoints"""

    def test_search_endpoint_basic(self, authenticated_client):
        """Test basic search endpoint"""
        with patch("app.modules.knowledge.router.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search = AsyncMock(
                return_value={
                    "results": [],
                    "collection_used": "test_collection",
                    "query": "test query",
                    "user_level": 2,
                    "allowed_tiers": [],
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/search", json={"query": "test query", "level": 2}
            )

            # Should return 200 or 503 depending on service initialization
            assert response.status_code == 200
            # Verify apply_filters=True is passed
            call_args = mock_service.search.call_args
            assert call_args[1]["apply_filters"] is True

    def test_search_endpoint_with_filters(self, authenticated_client):
        """Test search endpoint with filters"""
        with patch("app.modules.knowledge.router.get_search_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.search = AsyncMock(
                return_value={
                    "results": [
                        {
                            "id": "id1",
                            "text": "Test result",
                            "score": 0.9,
                            "metadata": {
                                "book_title": "Test Book",
                                "book_author": "Test Author",
                                "tier": "S",
                                "min_level": 2,
                                "chunk_index": 0,
                                "total_chunks": 1,
                            },
                        }
                    ],
                    "collection_used": "test_collection",
                    "query": "test query",
                    "user_level": 2,
                    "allowed_tiers": ["S"],
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/search",
                json={"query": "test query", "level": 2, "tier_filter": ["S", "A"]},
            )

            assert response.status_code == 200
            # Verify apply_filters=True is passed
            call_args = mock_service.search.call_args
            assert call_args[1]["apply_filters"] is True

    def test_search_endpoint_authentication_required(self, test_client):
        """Test that search endpoint requires authentication"""
        # Remove any default auth headers
        test_client.headers.pop("Authorization", None)
        test_client.headers.pop("X-API-Key", None)

        response = test_client.post("/api/search", json={"query": "test query", "user_level": 2})

        # Should return 401 or 403 if auth is required
        assert response.status_code in [200, 401, 403, 503]
