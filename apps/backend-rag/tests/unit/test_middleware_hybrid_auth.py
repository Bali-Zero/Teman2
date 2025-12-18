"""
Unit tests for Hybrid Auth Middleware
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from starlette.responses import Response

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.hybrid_auth import HybridAuthMiddleware, create_default_user_context


@pytest.fixture
def mock_settings():
    """Mock settings"""
    with patch("middleware.hybrid_auth.settings") as mock:
        mock.api_auth_enabled = True
        mock.api_auth_bypass_db = False
        yield mock


@pytest.fixture
def mock_api_key_auth():
    """Mock APIKeyAuth"""
    auth = MagicMock()
    auth.validate_api_key = MagicMock(return_value={"email": "test@example.com", "role": "admin"})
    auth.get_service_stats = MagicMock(return_value={})
    return auth


@pytest.fixture
def mock_app():
    """Mock FastAPI app"""
    app = MagicMock()
    return app


@pytest.fixture
def hybrid_auth_middleware(mock_app, mock_settings, mock_api_key_auth):
    """Create HybridAuthMiddleware instance"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        return middleware


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_success(mock_app, mock_settings, mock_api_key_auth):
    """Test middleware initialization"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        assert middleware.api_auth_enabled is True
        assert len(middleware.public_endpoints) > 0


# ============================================================================
# Tests for is_public_endpoint
# ============================================================================


def test_is_public_endpoint_health(mock_app, mock_settings, mock_api_key_auth):
    """Test public endpoint detection for health"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.url.path = "/health"

        assert middleware.is_public_endpoint(request) is True


def test_is_public_endpoint_docs(mock_app, mock_settings, mock_api_key_auth):
    """Test public endpoint detection for docs"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.url.path = "/docs"

        assert middleware.is_public_endpoint(request) is True


def test_is_public_endpoint_protected(mock_app, mock_settings, mock_api_key_auth):
    """Test protected endpoint detection"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.url.path = "/api/search"

        assert middleware.is_public_endpoint(request) is False


def test_is_public_endpoint_debug_config_not_public(mock_app, mock_settings, mock_api_key_auth):
    """SECURITY: Test that /debug/config is NOT public (requires authentication)"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.url.path = "/debug/config"

        # SECURITY: /debug/config should NOT be public
        assert middleware.is_public_endpoint(request) is False


# ============================================================================
# Tests for dispatch
# ============================================================================


@pytest.mark.asyncio
async def test_dispatch_public_endpoint(mock_app, mock_settings, mock_api_key_auth):
    """Test dispatch allows public endpoints"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.client.host = "127.0.0.1"

        response = MagicMock(spec=Response)
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        assert result == response
        assert result.headers["X-Auth-Type"] == "public"


@pytest.mark.asyncio
async def test_dispatch_api_key_auth(mock_app, mock_settings, mock_api_key_auth):
    """Test dispatch with API key authentication"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.url.path = "/api/search"
        request.client.host = "127.0.0.1"
        request.headers = {"X-API-Key": "test-key"}
        request.state = MagicMock()

        response = MagicMock(spec=Response)
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        assert result == response
        assert hasattr(request.state, "user")
        assert request.state.auth_type == "unknown"


@pytest.mark.asyncio
async def test_dispatch_no_auth_provided(mock_app, mock_settings, mock_api_key_auth):
    """Test dispatch returns 401 when no auth provided (fail-closed)"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.url.path = "/api/search"
        request.client.host = "127.0.0.1"
        request.headers = {}

        call_next = AsyncMock()

        # Fail-closed: returns JSONResponse with 401 instead of raising exception
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_dispatch_auth_disabled(mock_app, mock_api_key_auth):
    """Test dispatch when auth is disabled"""
    with patch("middleware.hybrid_auth.settings") as mock_settings:
        mock_settings.api_auth_enabled = False
        with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
            middleware = HybridAuthMiddleware(mock_app)
            request = MagicMock(spec=Request)
            request.url.path = "/api/search"
            request.client.host = "127.0.0.1"

            response = MagicMock(spec=Response)
            response.headers = {}
            call_next = AsyncMock(return_value=response)

            result = await middleware.dispatch(request, call_next)

            assert result == response


# ============================================================================
# Tests for authenticate_request
# ============================================================================


@pytest.mark.asyncio
async def test_authenticate_request_api_key_success(mock_app, mock_settings, mock_api_key_auth):
    """Test API key authentication success"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.headers = {"X-API-Key": "valid-key"}
        request.client.host = "127.0.0.1"

        result = await middleware.authenticate_request(request)

        assert result is not None
        assert result["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_request_api_key_invalid(mock_app, mock_settings, mock_api_key_auth):
    """Test API key authentication failure"""
    mock_api_key_auth.validate_api_key = MagicMock(return_value=None)

    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        middleware = HybridAuthMiddleware(mock_app)
        request = MagicMock(spec=Request)
        request.headers = {"X-API-Key": "invalid-key"}
        request.client.host = "127.0.0.1"

        result = await middleware.authenticate_request(request)

        assert result is None


@pytest.mark.asyncio
async def test_authenticate_request_jwt_success(mock_app, mock_settings, mock_api_key_auth):
    """Test JWT authentication success via Authorization header (Priority 3)"""
    mock_user = {
        "id": "user-123",
        "email": "user@example.com",
        "role": "user",
        "name": "Test User",
        "auth_method": "jwt_stateless",
        "status": "active",
    }

    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        # Mock cookie functions to return None (no cookie auth)
        with patch("middleware.hybrid_auth.get_jwt_from_cookie", return_value=None):
            middleware = HybridAuthMiddleware(mock_app)

            # Mock authenticate_jwt directly to return valid user
            middleware.authenticate_jwt = AsyncMock(return_value=mock_user)

            request = MagicMock(spec=Request)
            request.headers = {"Authorization": "Bearer valid-jwt-token"}
            request.client.host = "127.0.0.1"

            result = await middleware.authenticate_request(request)

            assert result is not None
            assert result["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_authenticate_request_cookie_jwt_success(mock_app, mock_settings, mock_api_key_auth):
    """Test Cookie JWT authentication success (Priority 2)"""
    mock_user = {
        "id": "user-456",
        "email": "cookie@example.com",
        "role": "member",
    }

    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        # Mock cookie functions - cookie JWT present with valid CSRF
        with patch("middleware.hybrid_auth.get_jwt_from_cookie", return_value="valid-cookie-jwt"):
            with patch("middleware.hybrid_auth.validate_csrf", return_value=True):
                with patch("middleware.hybrid_auth.is_csrf_exempt", return_value=False):
                    middleware = HybridAuthMiddleware(mock_app)

                    # Mock authenticate_jwt_token to return valid user
                    middleware.authenticate_jwt_token = AsyncMock(return_value=mock_user)

                    request = MagicMock(spec=Request)
                    request.headers = {}  # No Authorization header
                    request.method = "POST"  # State-changing request requires CSRF
                    request.client.host = "127.0.0.1"

                    result = await middleware.authenticate_request(request)

                    assert result is not None
                    assert result["email"] == "cookie@example.com"
                    assert result["auth_method"] == "jwt_cookie"


@pytest.mark.asyncio
async def test_authenticate_request_cookie_jwt_csrf_fail(
    mock_app, mock_settings, mock_api_key_auth
):
    """Test Cookie JWT fails when CSRF validation fails"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        # Mock cookie present but CSRF fails
        with patch("middleware.hybrid_auth.get_jwt_from_cookie", return_value="valid-cookie-jwt"):
            with patch("middleware.hybrid_auth.validate_csrf", return_value=False):
                with patch("middleware.hybrid_auth.is_csrf_exempt", return_value=False):
                    middleware = HybridAuthMiddleware(mock_app)

                    request = MagicMock(spec=Request)
                    request.headers = {}
                    request.method = "POST"
                    request.url.path = "/api/test"
                    request.client.host = "127.0.0.1"

                    result = await middleware.authenticate_request(request)

                    # Should fail due to CSRF validation
                    assert result is None


@pytest.mark.asyncio
async def test_authenticate_request_no_auth(mock_app, mock_settings, mock_api_key_auth):
    """Test authentication when no auth provided"""
    with patch("middleware.hybrid_auth.APIKeyAuth", return_value=mock_api_key_auth):
        with patch("middleware.hybrid_auth.get_jwt_from_cookie", return_value=None):
            middleware = HybridAuthMiddleware(mock_app)
            request = MagicMock(spec=Request)
            request.headers = {}
            request.url.path = "/api/search"

            result = await middleware.authenticate_request(request)

            assert result is None


# ============================================================================
# Tests for create_default_user_context
# ============================================================================


def test_create_default_user_context():
    """Test creating default user context"""
    context = create_default_user_context()

    assert context["id"] == "public_user"
    assert context["email"] == "public@zantara.dev"
    assert context["role"] == "public"
    assert context["auth_method"] == "public"
    assert "permissions" in context
