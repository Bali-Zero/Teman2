"""
Unit tests for HybridAuthMiddleware
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from starlette.responses import Response

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.hybrid_auth import (
    HybridAuthMiddleware,
    _allowed_origins,
    _get_correlation_id,
    create_default_user_context,
)


@pytest.fixture
def mock_app():
    return MagicMock()


@pytest.fixture
def middleware(mock_app):
    return HybridAuthMiddleware(app=mock_app)


@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.headers = {}
    req.cookies = {}
    req.state = MagicMock()
    req.state.correlation_id = "test-correlation-id"
    req.url.path = "/api/protected"
    req.method = "GET"
    req.client.host = "127.0.0.1"
    return req


# ============================================================================
# TESTS: Helper Functions
# ============================================================================
def test_get_correlation_id():
    req = MagicMock()
    req.state.correlation_id = "123"
    assert _get_correlation_id(req) == "123"

    req.state.correlation_id = None
    req.state.request_id = "456"
    assert _get_correlation_id(req) == "456"

    req.state.request_id = None
    assert _get_correlation_id(req) == "unknown"


def test_allowed_origins():
    with (
        patch("app.core.config.settings.zantara_allowed_origins", "https://custom.com"),
        patch("app.core.config.settings.dev_origins", "http://dev.com"),
    ):
        origins = _allowed_origins()
        assert "https://custom.com" in origins
        assert "http://dev.com" in origins
        assert "http://localhost:3000" in origins


def test_create_default_user_context():
    ctx = create_default_user_context()
    assert ctx["id"] == "public_user"
    assert ctx["role"] == "public"


# ============================================================================
# TESTS: Middleware Methods
# ============================================================================
def test_is_public_endpoint(middleware, mock_request):
    mock_request.url.path = "/health"
    assert middleware.is_public_endpoint(mock_request) is True

    mock_request.url.path = "/api/protected"
    assert middleware.is_public_endpoint(mock_request) is False


def test_cors_headers_for_request(middleware, mock_request):
    with patch("middleware.hybrid_auth._allowed_origins", return_value={"https://allowed.com"}):
        mock_request.headers = {"origin": "https://allowed.com"}
        headers = middleware._cors_headers_for_request(mock_request)
        assert headers["access-control-allow-origin"] == "https://allowed.com"

        mock_request.headers = {"origin": "https://blocked.com"}
        headers = middleware._cors_headers_for_request(mock_request)
        assert headers == {}


def test_get_auth_stats(middleware):
    stats = middleware.get_auth_stats()
    assert "api_auth_enabled" in stats
    assert "timestamp" in stats


# ============================================================================
# TESTS: dispatch
# ============================================================================
@pytest.mark.asyncio
async def test_dispatch_options(middleware, mock_request):
    mock_request.method = "OPTIONS"
    call_next = AsyncMock(return_value=Response("OK"))

    response = await middleware.dispatch(mock_request, call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_public(middleware, mock_request):
    mock_request.url.path = "/health"
    call_next = AsyncMock(return_value=Response("OK"))

    response = await middleware.dispatch(mock_request, call_next)
    assert response.headers["X-Auth-Type"] == "public"


@pytest.mark.asyncio
async def test_dispatch_auth_success(middleware, mock_request):
    mock_request.url.path = "/api/protected"
    with patch.object(
        middleware,
        "authenticate_request",
        return_value={"email": "test@test.com", "auth_method": "jwt"},
    ):
        call_next = AsyncMock(return_value=Response("OK"))

        response = await middleware.dispatch(mock_request, call_next)
        assert response.headers["X-Auth-Type"] == "jwt"
        assert mock_request.state.user["email"] == "test@test.com"


@pytest.mark.asyncio
async def test_dispatch_auth_fail(middleware, mock_request):
    mock_request.url.path = "/api/protected"
    with patch.object(middleware, "authenticate_request", return_value=None):
        response = await middleware.dispatch(mock_request, AsyncMock())
        assert response.status_code == 401
        assert "Authentication required" in str(response.body)  # or detail check logic


@pytest.mark.asyncio
async def test_dispatch_http_exception(middleware, mock_request):
    mock_request.url.path = "/api/protected"
    # Authenticate successfully but call_next raises HTTPException
    with patch.object(middleware, "authenticate_request", return_value={"email": "test"}):
        call_next = AsyncMock(side_effect=HTTPException(status_code=400, detail="Bad Request"))
        response = await middleware.dispatch(mock_request, call_next)
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_dispatch_http_exception_complex_detail(middleware, mock_request):
    mock_request.url.path = "/api/protected"
    # Detail is a dict with non-serializable object?
    # Middleware sanitizes it.
    detail = {"msg": "Error", "obj": object()}
    with patch.object(middleware, "authenticate_request", return_value={"email": "test"}):
        call_next = AsyncMock(side_effect=HTTPException(status_code=400, detail=detail))
        response = await middleware.dispatch(mock_request, call_next)
        assert response.status_code == 400
        # Ensure serialization didn't crash


@pytest.mark.asyncio
async def test_dispatch_unhandled_exception(middleware, mock_request):
    mock_request.url.path = "/api/protected"
    with patch.object(middleware, "authenticate_request", side_effect=ValueError("System Error")):
        response = await middleware.dispatch(mock_request, AsyncMock())
        assert response.status_code == 503
        assert "Authentication service temporarily unavailable" in str(response.body)


@pytest.mark.asyncio
async def test_dispatch_db_pool_exception(middleware, mock_request):
    mock_request.url.path = "/api/protected"
    # Simulate an error that mentions "Pool" or "asyncpg"
    with patch.object(
        middleware, "authenticate_request", side_effect=Exception("asyncpg connection failed")
    ):
        response = await middleware.dispatch(mock_request, AsyncMock())
        assert response.status_code == 503
        # Should sanitize error message
        # Need to check response content but it's bytes.
        # Assuming JSONResponse


# ============================================================================
# TESTS: authenticate_request
# ============================================================================
@pytest.mark.asyncio
async def test_auth_api_key_valid(middleware, mock_request):
    mock_request.headers = {"X-API-Key": "valid-key"}
    middleware.api_key_auth.validate_api_key = MagicMock(return_value={"role": "service"})

    user = await middleware.authenticate_request(mock_request)
    assert user["role"] == "service"


@pytest.mark.asyncio
async def test_auth_api_key_invalid(middleware, mock_request):
    mock_request.headers = {"X-API-Key": "invalid-key"}
    middleware.api_key_auth.validate_api_key = MagicMock(return_value=None)

    user = await middleware.authenticate_request(mock_request)
    assert user is None


@pytest.mark.asyncio
async def test_auth_cookie_valid(middleware, mock_request):
    mock_request.headers = {}
    mock_request.cookies = {"nz_access_token": "valid-jwt"}

    with (
        patch("middleware.hybrid_auth.validate_csrf", return_value=True),
        patch.object(middleware, "authenticate_jwt_token", return_value={"email": "test"}),
    ):
        user = await middleware.authenticate_request(mock_request)
        assert user["email"] == "test"
        assert user["auth_method"] == "jwt_cookie"


@pytest.mark.asyncio
async def test_auth_cookie_csrf_fail(middleware, mock_request):
    mock_request.cookies = {"nz_access_token": "valid-jwt"}
    mock_request.method = "POST"  # State changing

    with patch("middleware.hybrid_auth.validate_csrf", return_value=False):
        user = await middleware.authenticate_request(mock_request)
        assert user is None


@pytest.mark.asyncio
async def test_auth_cookie_invalid(middleware, mock_request):
    mock_request.cookies = {"nz_access_token": "invalid-jwt"}

    with (
        patch("middleware.hybrid_auth.validate_csrf", return_value=True),
        patch.object(middleware, "authenticate_jwt_token", return_value=None),
    ):
        user = await middleware.authenticate_request(mock_request)
        assert user is None


@pytest.mark.asyncio
async def test_auth_header_valid(middleware, mock_request):
    mock_request.headers = {"Authorization": "Bearer valid-jwt"}
    middleware.api_auth_bypass_db = False

    with patch.object(middleware, "authenticate_jwt", return_value={"email": "test"}):
        user = await middleware.authenticate_request(mock_request)
        assert user["email"] == "test"
        assert user["auth_method"] == "jwt_header"


@pytest.mark.asyncio
async def test_auth_header_bypass_db(middleware, mock_request):
    mock_request.headers = {"Authorization": "Bearer valid-jwt"}
    middleware.api_auth_bypass_db = True

    user = await middleware.authenticate_request(mock_request)
    assert user is None


@pytest.mark.asyncio
async def test_auth_none(middleware, mock_request):
    user = await middleware.authenticate_request(mock_request)
    assert user is None


# ============================================================================
# TESTS: JWT Validation
# ============================================================================
@pytest.mark.asyncio
async def test_authenticate_jwt_token_valid(middleware):
    with patch("jose.jwt.decode", return_value={"sub": "1", "email": "a@b.com", "role": "admin"}):
        user = await middleware.authenticate_jwt_token("token")
        assert user["email"] == "a@b.com"


@pytest.mark.asyncio
async def test_authenticate_jwt_token_missing_claims(middleware):
    with patch("jose.jwt.decode", return_value={"sub": "1"}):  # Missing email
        user = await middleware.authenticate_jwt_token("token")
        assert user is None


@pytest.mark.asyncio
async def test_authenticate_jwt_token_error(middleware):
    with patch("jose.jwt.decode", side_effect=Exception("Decode fail")):
        user = await middleware.authenticate_jwt_token("token")
        assert user is None


@pytest.mark.asyncio
async def test_authenticate_jwt_valid(middleware, mock_request):
    mock_request.headers = {"Authorization": "Bearer token"}
    with patch("jose.jwt.decode", return_value={"sub": "1", "email": "a@b.com"}):
        user = await middleware.authenticate_jwt(mock_request)
        assert user["email"] == "a@b.com"


@pytest.mark.asyncio
async def test_authenticate_jwt_invalid_header(middleware, mock_request):
    mock_request.headers = {"Authorization": "Basic token"}
    user = await middleware.authenticate_jwt(mock_request)
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_jwt_error(middleware, mock_request):
    mock_request.headers = {"Authorization": "Bearer token"}
    with patch("jose.jwt.decode", side_effect=Exception("Fail")):
        user = await middleware.authenticate_jwt(mock_request)
        assert user is None
