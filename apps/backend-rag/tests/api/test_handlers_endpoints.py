"""
API Tests for Handlers Registry Endpoint
Tests the handler discovery and listing system

Coverage:
- GET /api/handlers/list - List all handlers
- GET /api/handlers/search - Search handlers
- GET /api/handlers/category/{category} - Get handlers by category
"""

import os
import sys
from pathlib import Path

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures - Uses shared test_app from conftest.py
# ============================================================================


@pytest.fixture
def test_client(test_app):
    """Create FastAPI TestClient with API key auth for handlers tests."""
    from fastapi.testclient import TestClient

    # Use API key from environment
    api_key = os.environ.get("API_KEYS", "test_api_key_1").split(",")[0]

    with TestClient(test_app, raise_server_exceptions=False) as client:
        # Set API key header for all requests
        client.headers.update({"X-API-Key": api_key})
        yield client


# ============================================================================
# List All Handlers Tests
# ============================================================================


class TestHandlersList:
    """Tests for GET /api/handlers/list endpoint"""

    def test_list_all_handlers(self, test_client):
        """Test listing all available handlers"""
        response = test_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()

        assert "total_handlers" in data
        assert "categories" in data
        assert "handlers" in data
        assert "last_updated" in data

        # Should have multiple handlers
        assert data["total_handlers"] > 0
        assert len(data["handlers"]) > 0

    def test_list_handlers_has_categories(self, test_client):
        """Test handlers list includes categorized handlers"""
        response = test_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()

        # Should have category breakdown
        categories = data["categories"]
        assert len(categories) > 0

        # Each category should have count and handlers
        for cat_name, cat_data in categories.items():
            assert "count" in cat_data
            assert "handlers" in cat_data

    def test_list_handlers_format(self, test_client):
        """Test handler format includes expected fields"""
        response = test_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()

        # Check first handler has expected fields
        if data["handlers"]:
            handler = data["handlers"][0]
            assert "name" in handler
            assert "path" in handler
            assert "methods" in handler
            assert "module" in handler


# ============================================================================
# Search Handlers Tests
# ============================================================================


class TestHandlersSearch:
    """Tests for GET /api/handlers/search endpoint"""

    def test_search_handlers(self, test_client):
        """Test searching handlers by query"""
        response = test_client.get("/api/handlers/search?query=health")

        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert "matches" in data
        assert "handlers" in data
        assert data["query"] == "health"

    def test_search_handlers_no_results(self, test_client):
        """Test searching handlers with no matches"""
        response = test_client.get("/api/handlers/search?query=nonexistenthandler12345")

        assert response.status_code == 200
        data = response.json()

        assert data["matches"] == 0
        assert len(data["handlers"]) == 0

    def test_search_handlers_case_insensitive(self, test_client):
        """Test search is case-insensitive"""
        response_lower = test_client.get("/api/handlers/search?query=health")
        response_upper = test_client.get("/api/handlers/search?query=HEALTH")

        assert response_lower.status_code == 200
        assert response_upper.status_code == 200

        # Should return same results
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        assert data_lower["matches"] == data_upper["matches"]

    def test_search_handlers_missing_query(self, test_client):
        """Test search without query parameter"""
        response = test_client.get("/api/handlers/search")

        # Should return validation error
        assert response.status_code == 422


# ============================================================================
# Category Handlers Tests
# ============================================================================


class TestHandlersCategory:
    """Tests for GET /api/handlers/category/{category} endpoint"""

    def test_get_category_handlers(self, test_client):
        """Test getting handlers by category"""
        # First get list of categories
        list_response = test_client.get("/api/handlers/list")
        categories = list(list_response.json()["categories"].keys())

        if categories:
            # Get handlers for first category
            category = categories[0]
            response = test_client.get(f"/api/handlers/category/{category}")

            assert response.status_code == 200
            data = response.json()

            assert "count" in data
            assert "handlers" in data

    def test_get_category_not_found(self, test_client):
        """Test getting handlers for non-existent category"""
        response = test_client.get("/api/handlers/category/nonexistent_category")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_search_handlers_partial_match(self, test_client):
        """Test search handlers with partial query match"""
        response = test_client.get("/api/handlers/search?query=api")

        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        assert "handlers" in data

    def test_search_handlers_empty_query(self, test_client):
        """Test search handlers with empty query"""
        response = test_client.get("/api/handlers/search?query=")

        # Should either return all handlers or validation error
        assert response.status_code in [200, 422]

    def test_list_handlers_has_methods(self, test_client):
        """Test handlers include HTTP methods"""
        response = test_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()

        if data["handlers"]:
            handler = data["handlers"][0]
            assert "methods" in handler
            assert isinstance(handler["methods"], list)
            assert len(handler["methods"]) > 0

    def test_list_handlers_has_paths(self, test_client):
        """Test handlers include valid paths"""
        response = test_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()

        if data["handlers"]:
            for handler in data["handlers"]:
                assert "path" in handler
                assert isinstance(handler["path"], str)
                assert handler["path"].startswith("/")

    def test_search_handlers_multiple_words(self, test_client):
        """Test search handlers with multiple words"""
        response = test_client.get("/api/handlers/search?query=health check")

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "matches" in data

    def test_category_handlers_count_matches(self, test_client):
        """Test category handlers count matches list"""
        list_response = test_client.get("/api/handlers/list")
        categories = list(list_response.json()["categories"].keys())

        if categories:
            category = categories[0]
            category_response = test_client.get(f"/api/handlers/category/{category}")

            assert category_response.status_code == 200
            category_data = category_response.json()

            list_data = list_response.json()
            list_count = list_data["categories"][category]["count"]

            assert category_data["count"] == list_count

    def test_handlers_endpoints_require_auth(self, test_client):
        """Test handlers endpoints require authentication"""
        test_client.headers.pop("X-API-Key", None)
        test_client.headers.pop("Authorization", None)

        response = test_client.get("/api/handlers/list")
        # Handlers endpoints require authentication
        assert response.status_code == 401

        response = test_client.get("/api/handlers/search?query=test")
        assert response.status_code == 401
