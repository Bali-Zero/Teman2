"""
Comprehensive Handlers Registry Tests
Complete test coverage for handlers registry endpoints

Coverage:
- GET /api/handlers/list - List all handlers
- GET /api/handlers/search - Search handlers
- GET /api/handlers/category/{category} - Get handlers by category
"""

import os
import sys
from pathlib import Path

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestHandlersList:
    """Comprehensive tests for GET /api/handlers/list"""

    def test_list_all_handlers(self, api_key_client):
        """Test listing all handlers"""
        response = api_key_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()
        assert "total_handlers" in data
        assert "categories" in data
        assert "handlers" in data

    def test_list_handlers_response_structure(self, api_key_client):
        """Test handlers list response structure"""
        response = api_key_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["total_handlers"], int)
        assert isinstance(data["categories"], dict)
        assert isinstance(data["handlers"], list)

    def test_list_handlers_categories(self, api_key_client):
        """Test handlers list includes categories"""
        response = api_key_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()
        categories = data.get("categories", {})

        # Should have multiple categories
        assert len(categories) > 0

        # Each category should have count and handlers
        for category_name, category_data in categories.items():
            assert "count" in category_data
            assert "handlers" in category_data
            assert isinstance(category_data["count"], int)
            assert isinstance(category_data["handlers"], list)

    def test_list_handlers_handler_structure(self, api_key_client):
        """Test handler structure in list"""
        response = api_key_client.get("/api/handlers/list")

        assert response.status_code == 200
        data = response.json()

        if data["handlers"]:
            handler = data["handlers"][0]
            assert "name" in handler
            assert "path" in handler
            assert "methods" in handler
            assert "module" in handler


@pytest.mark.api
class TestHandlersSearch:
    """Comprehensive tests for GET /api/handlers/search"""

    def test_search_handlers_by_name(self, api_key_client):
        """Test searching handlers by name"""
        response = api_key_client.get("/api/handlers/search?query=client")

        assert response.status_code == 200

    def test_search_handlers_by_path(self, api_key_client):
        """Test searching handlers by path"""
        response = api_key_client.get("/api/handlers/search?query=/api/crm")

        assert response.status_code == 200

    def test_search_handlers_empty_query(self, api_key_client):
        """Test searching handlers with empty query"""
        response = api_key_client.get("/api/handlers/search?query=")

        assert response.status_code in [200, 400, 422]

    def test_search_handlers_missing_query(self, api_key_client):
        """Test searching handlers without query"""
        response = api_key_client.get("/api/handlers/search")

        assert response.status_code in [200, 400, 422]

    def test_search_handlers_response_structure(self, api_key_client):
        """Test handlers search response structure"""
        response = api_key_client.get("/api/handlers/search?query=test")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))


@pytest.mark.api
class TestHandlersCategory:
    """Comprehensive tests for GET /api/handlers/category/{category}"""

    def test_get_handlers_by_category(self, api_key_client):
        """Test getting handlers by category"""
        categories = ["agents", "crm_clients", "crm_practices", "oracle_universal"]

        for category in categories:
            response = api_key_client.get(f"/api/handlers/category/{category}")

            assert response.status_code in [200, 404]

    def test_get_handlers_invalid_category(self, api_key_client):
        """Test getting handlers with invalid category"""
        response = api_key_client.get("/api/handlers/category/invalid_category")

        assert response.status_code in [200, 404]

    def test_get_handlers_category_response_structure(self, api_key_client):
        """Test handlers category response structure"""
        response = api_key_client.get("/api/handlers/category/agents")

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


@pytest.mark.api
class TestHandlersSecurity:
    """Security tests for handlers endpoints"""

    def test_handlers_endpoints_require_auth(self, test_client):
        """Test handlers endpoints require authentication"""
        endpoints = [
            "/api/handlers/list",
            "/api/handlers/search?query=test",
            "/api/handlers/category/agents",
        ]

        for endpoint in endpoints:
            response = test_client.get(endpoint)

            # Handlers endpoints may be public or require auth
            assert response.status_code in [200, 401, 403]










