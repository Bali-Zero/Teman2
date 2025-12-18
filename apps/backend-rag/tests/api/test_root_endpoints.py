"""
API Tests for Root Endpoints Router
Tests root-level endpoints including health check, CSRF token, and dashboard stats

Coverage:
- GET / - Root endpoint
- GET /api/csrf-token - CSRF token generation
- GET /api/dashboard/stats - Dashboard statistics
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
class TestRootEndpoint:
    """Tests for GET / root endpoint"""

    def test_root_endpoint(self, api_key_client):
        """Test GET / - root health check"""
        response = api_key_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0

    def test_root_endpoint_requires_auth(self, test_client):
        """Test root endpoint requires authentication"""
        # Clear any auth headers
        test_client.headers.pop("Authorization", None)
        test_client.headers.pop("X-API-Key", None)

        response = test_client.get("/")
        assert response.status_code == 401


@pytest.mark.api
class TestCsrfTokenEndpoint:
    """Tests for GET /api/csrf-token endpoint (requires auth) and /api/auth/csrf-token (public)"""

    def test_get_csrf_token_requires_auth(self, api_key_client):
        """Test GET /api/csrf-token - requires authentication"""
        response = api_key_client.get("/api/csrf-token")

        assert response.status_code == 200
        data = response.json()
        assert "csrfToken" in data
        assert "sessionId" in data

        # Validate CSRF token format (64 hex chars = 32 bytes)
        assert len(data["csrfToken"]) == 64
        assert all(c in "0123456789abcdef" for c in data["csrfToken"])

        # Validate session ID format
        assert data["sessionId"].startswith("session_")
        assert len(data["sessionId"]) > len("session_")

    def test_get_csrf_token_public_endpoint(self, test_client, test_app):
        """Test GET /api/auth/csrf-token - public endpoint (no auth required)"""
        from fastapi.testclient import TestClient

        with TestClient(test_app, raise_server_exceptions=False) as client:
            client.headers.clear()
            response = client.get("/api/auth/csrf-token")

            assert response.status_code == 200
            data = response.json()
            assert "csrfToken" in data
            assert "sessionId" in data

    def test_csrf_token_uniqueness(self, api_key_client):
        """Test CSRF tokens are unique on each request"""
        response1 = api_key_client.get("/api/csrf-token")
        response2 = api_key_client.get("/api/csrf-token")

        assert response1.status_code == 200
        assert response2.status_code == 200

        token1 = response1.json()["csrfToken"]
        token2 = response2.json()["csrfToken"]

        assert token1 != token2, "CSRF tokens should be unique"

    def test_csrf_token_requires_auth(self, test_client):
        """Test /api/csrf-token endpoint requires authentication"""
        test_client.headers.clear()
        response = test_client.get("/api/csrf-token")
        assert response.status_code == 401


@pytest.mark.api
class TestDashboardStatsEndpoint:
    """Tests for GET /api/dashboard/stats endpoint"""

    def test_get_dashboard_stats(self, api_key_client):
        """Test GET /api/dashboard/stats - returns dashboard statistics"""
        response = api_key_client.get("/api/dashboard/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate expected fields
        assert "active_agents" in data
        assert "system_health" in data
        assert "uptime_status" in data
        assert "knowledge_base" in data

        # Validate knowledge_base structure
        assert isinstance(data["knowledge_base"], dict)
        assert "vectors" in data["knowledge_base"]
        assert "status" in data["knowledge_base"]

    def test_dashboard_stats_format(self, api_key_client):
        """Test dashboard stats have correct data types"""
        response = api_key_client.get("/api/dashboard/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate data types
        assert isinstance(data["active_agents"], str)
        assert isinstance(data["system_health"], str)
        assert isinstance(data["uptime_status"], str)
        assert isinstance(data["knowledge_base"], dict)

    def test_dashboard_stats_requires_auth(self, test_client):
        """Test dashboard stats endpoint requires authentication"""
        test_client.headers.pop("Authorization", None)
        test_client.headers.pop("X-API-Key", None)

        response = test_client.get("/api/dashboard/stats")
        assert response.status_code == 401

    def test_dashboard_stats_consistency(self, api_key_client):
        """Test dashboard stats are consistent across requests"""
        response1 = api_key_client.get("/api/dashboard/stats")
        response2 = api_key_client.get("/api/dashboard/stats")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Structure should be consistent
        assert set(data1.keys()) == set(data2.keys())
        assert set(data1["knowledge_base"].keys()) == set(data2["knowledge_base"].keys())
