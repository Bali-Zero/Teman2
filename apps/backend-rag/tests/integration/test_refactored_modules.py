"""
Integration Tests for Refactored Modules
Verifies that refactored modules work correctly after restructuring
"""

import sys
from pathlib import Path

import pytest

# Add backend to path for imports
backend_root = Path(__file__).parent.parent.parent / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi.testclient import TestClient

# Import app after path setup
try:
    from app.main_cloud import app
except ImportError as e:
    pytest.skip(f"Could not import app.main_cloud: {e}", allow_module_level=True)


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint is accessible"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "ZANTARA" in response.json()["message"]


def test_csrf_token_endpoint(client):
    """Test CSRF token endpoint"""
    response = client.get("/api/csrf-token")
    assert response.status_code == 200
    data = response.json()
    assert "csrfToken" in data
    assert "sessionId" in data
    assert len(data["csrfToken"]) == 64  # 32 bytes = 64 hex chars
    assert data["sessionId"].startswith("session_")

    # Check headers
    assert "X-CSRF-Token" in response.headers
    assert "X-Session-Id" in response.headers


def test_dashboard_stats_endpoint(client):
    """Test dashboard stats endpoint"""
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "active_agents" in data
    assert "system_health" in data
    assert "uptime_status" in data
    assert "knowledge_base" in data


def test_auth_validation_module_import():
    """Test that auth validation module can be imported"""
    from app.auth.validation import validate_api_key, validate_auth_mixed, validate_auth_token

    assert callable(validate_api_key)
    assert callable(validate_auth_token)
    assert callable(validate_auth_mixed)


def test_oracle_services_import():
    """Test that Oracle services can be imported"""
    from services.oracle_config import oracle_config
    from services.oracle_database import db_manager
    from services.oracle_google_services import google_services

    assert oracle_config is not None
    assert google_services is not None
    assert db_manager is not None


def test_state_helpers_import():
    """Test that state helpers can be imported"""
    from app.utils.state_helpers import get_app_state, get_request_state

    assert callable(get_app_state)
    assert callable(get_request_state)


def test_router_registration():
    """Test that routers are properly registered"""
    # Check that root router is included
    routes = [route.path for route in app.routes]
    assert "/" in routes
    assert "/api/csrf-token" in routes
    assert "/api/dashboard/stats" in routes


def test_health_endpoint(client):
    """Test health endpoint is accessible"""
    response = client.get("/health")
    assert response.status_code in [200, 503]  # 503 if services not initialized


@pytest.mark.asyncio
async def test_auth_validation_functions():
    """Test auth validation functions handle None inputs"""
    from app.auth.validation import validate_api_key, validate_auth_token

    # Test with None inputs
    result = await validate_api_key(None)
    assert result is None

    result = await validate_auth_token(None)
    assert result is None
