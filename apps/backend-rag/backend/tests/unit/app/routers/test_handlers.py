"""
Unit tests for handlers router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.handlers import router, extract_handlers_from_router


@pytest.fixture
def app():
    """Create FastAPI app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestHandlersRouter:
    """Tests for handlers router"""

    def test_extract_handlers_from_router(self):
        """Test extracting handlers from router module"""
        mock_module = MagicMock()
        mock_route = MagicMock()
        mock_route.name = "test_handler"
        mock_route.path = "/test"
        mock_route.methods = {"GET", "POST"}
        mock_route.endpoint.__doc__ = "Test handler"
        
        mock_module.router.routes = [mock_route]
        mock_module.__name__ = "test_module"
        
        handlers = extract_handlers_from_router(mock_module)
        assert len(handlers) == 1
        assert handlers[0]["name"] == "test_handler"
        assert handlers[0]["path"] == "/test"
        assert "GET" in handlers[0]["methods"]

    def test_extract_handlers_no_router(self):
        """Test extracting handlers from module without router"""
        mock_module = MagicMock()
        del mock_module.router
        
        handlers = extract_handlers_from_router(mock_module)
        assert handlers == []

    def test_list_all_handlers(self, client):
        """Test listing all handlers"""
        response = client.get("/api/handlers/list")
        assert response.status_code == 200
        data = response.json()
        assert "total_handlers" in data
        assert "categories" in data
        assert "handlers" in data
        assert isinstance(data["handlers"], list)

    def test_search_handlers(self, client):
        """Test searching handlers"""
        response = client.get("/api/handlers/search?query=health")
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "matches" in data
        assert "handlers" in data
        assert data["query"] == "health"

    def test_search_handlers_no_match(self, client):
        """Test searching handlers with no matches"""
        response = client.get("/api/handlers/search?query=nonexistent_handler_xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["matches"] == 0
        assert len(data["handlers"]) == 0

    def test_get_handlers_by_category(self, client):
        """Test getting handlers by category"""
        # First get list to find a category
        list_response = client.get("/api/handlers/list")
        categories = list_response.json()["categories"]
        
        if categories:
            category_name = list(categories.keys())[0]
            response = client.get(f"/api/handlers/category/{category_name}")
            assert response.status_code == 200
            data = response.json()
            assert "count" in data
            assert "handlers" in data

    def test_get_handlers_by_category_not_found(self, client):
        """Test getting handlers by non-existent category"""
        response = client.get("/api/handlers/category/nonexistent")
        assert response.status_code == 404

