"""
Unit tests for session router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.session import router, get_session_service


@pytest.fixture
def mock_session_service():
    """Mock SessionService"""
    service = MagicMock()
    service.create_session = AsyncMock(return_value="session123")
    service.get_history = AsyncMock(return_value=[{"role": "user", "content": "Hello"}])
    service.update_history = AsyncMock(return_value=True)
    service.update_history_with_ttl = AsyncMock(return_value=True)
    service.extend_ttl = AsyncMock(return_value=True)
    service.delete_session = AsyncMock(return_value=True)
    return service


@pytest.fixture
def app(mock_session_service):
    """Create FastAPI app with router and dependency override"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session_service] = lambda: mock_session_service
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestSessionRouter:
    """Tests for session router"""

    def test_get_session_service(self):
        """Test getting session service"""
        # Reset global
        import app.routers.session as module
        module._session_service = None
        
        with patch("app.routers.session.SessionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            service = get_session_service()
            assert service == mock_service

    def test_create_session(self, client, mock_session_service):
        """Test creating a session"""
        response = client.post("/api/sessions/create")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "session_id" in data

    def test_create_session_error(self, app, client, mock_session_service):
        """Test creating session with error"""
        mock_session_service.create_session.side_effect = Exception("Service error")
        app.dependency_overrides[get_session_service] = lambda: mock_session_service
        
        response = client.post("/api/sessions/create")
        assert response.status_code == 500

    def test_get_session(self, client, mock_session_service):
        """Test getting a session"""
        response = client.get("/api/sessions/session123")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["session_id"] == "session123"
        assert "history" in data

    def test_get_session_not_found(self, app, client, mock_session_service):
        """Test getting non-existent session"""
        mock_session_service.get_history = AsyncMock(return_value=None)
        app.dependency_overrides[get_session_service] = lambda: mock_session_service
        
        response = client.get("/api/sessions/nonexistent")
        assert response.status_code == 404

    def test_update_session(self, client, mock_session_service):
        """Test updating a session"""
        response = client.put(
            "/api/sessions/session123",
            json={"history": [{"role": "user", "content": "Updated"}]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_session_service.update_history.assert_called_once()

    def test_update_session_failed(self, app, client, mock_session_service):
        """Test updating session that fails"""
        mock_session_service.update_history = AsyncMock(return_value=False)
        app.dependency_overrides[get_session_service] = lambda: mock_session_service
        
        response = client.put(
            "/api/sessions/session123",
            json={"history": [{"role": "user", "content": "Updated"}]}
        )
        assert response.status_code == 400

    def test_extend_session_ttl(self, client, mock_session_service):
        """Test extending session TTL"""
        response = client.put(
            "/api/sessions/session123/ttl",
            json={"history": [{"role": "user", "content": "Test"}], "ttl_hours": 24}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_session(self, client, mock_session_service):
        """Test deleting a session"""
        response = client.delete("/api/sessions/session123")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_session_service.delete_session.assert_called_once_with("session123")

