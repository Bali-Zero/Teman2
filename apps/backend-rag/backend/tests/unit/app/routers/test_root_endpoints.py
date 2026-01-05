"""
Unit tests for root endpoints
Target: >95% coverage
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.root_endpoints import router


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


class TestRootEndpoints:
    """Tests for root endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()
        assert "ZANTARA" in response.json()["message"]

    def test_get_csrf_token(self, client):
        """Test CSRF token generation"""
        response = client.get("/api/csrf-token")
        assert response.status_code == 200
        data = response.json()
        assert "csrfToken" in data
        assert "sessionId" in data
        assert len(data["csrfToken"]) == 64  # 32 bytes = 64 hex chars
        assert "session_" in data["sessionId"]

        # Check headers
        assert "X-CSRF-Token" in response.headers
        assert "X-Session-Id" in response.headers

    def test_get_csrf_token_unique(self, client):
        """Test that CSRF tokens are unique"""
        response1 = client.get("/api/csrf-token")
        response2 = client.get("/api/csrf-token")

        assert response1.json()["csrfToken"] != response2.json()["csrfToken"]
        assert response1.json()["sessionId"] != response2.json()["sessionId"]

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_with_db(self, app):
        """Test dashboard stats with database"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[10, 1000])  # active_conversations, kb_documents

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.acquire = acquire

        app.state.db_pool = mock_pool

        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active_agents" in data
        assert "system_health" in data
        assert "uptime_status" in data
        assert "knowledge_base" in data

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_no_db(self, app):
        """Test dashboard stats without database"""
        app.state.db_pool = None

        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["system_health"] == "unknown"
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_db_error(self, app):
        """Test dashboard stats with database error"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("DB error"))

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.acquire = acquire

        app.state.db_pool = mock_pool

        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["system_health"] == "error"
        assert "error" in data

