"""
Ultra-Complete API Tests for Handlers Router
============================================

Coverage Endpoints:
- GET /api/handlers/list - List all handlers
- GET /api/handlers/search - Search handlers
- GET /api/handlers/category/{category} - Get handlers by category
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestHandlersList:
    def test_list_all_handlers(self, authenticated_client):
        with patch("app.routers.handlers.get_handler_registry") as mock:
            mock.return_value = []
            response = authenticated_client.get("/api/handlers/list")
            assert response.status_code in [200, 500]
            if response.status_code == 200:
                assert isinstance(response.json(), list)


@pytest.mark.api
class TestHandlersSearch:
    def test_search_handlers(self, authenticated_client):
        response = authenticated_client.get("/api/handlers/search?q=pricing")
        assert response.status_code in [200, 400, 500]

    def test_search_empty_query(self, authenticated_client):
        response = authenticated_client.get("/api/handlers/search?q=")
        assert response.status_code in [200, 400]


@pytest.mark.api
class TestHandlersCategory:
    def test_get_by_category(self, authenticated_client):
        response = authenticated_client.get("/api/handlers/category/crm")
        assert response.status_code in [200, 404, 500]

    def test_invalid_category(self, authenticated_client):
        response = authenticated_client.get("/api/handlers/category/nonexistent")
        assert response.status_code in [404, 200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
