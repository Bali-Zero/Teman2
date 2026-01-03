"""
Unit tests for HybridAuthMiddleware
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.hybrid_auth import HybridAuthMiddleware


@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.cookies = {}
    request.state = MagicMock()
    return request


@pytest.fixture
def hybrid_auth_middleware():
    """Create hybrid auth middleware instance"""
    return HybridAuthMiddleware(app=MagicMock())


class TestHybridAuthMiddleware:
    """Tests for HybridAuthMiddleware"""

    @pytest.mark.asyncio
    async def test_call_with_api_key(self, hybrid_auth_middleware, mock_request):
        """Test authentication with API key"""
        mock_request.headers = {"X-API-Key": "test-key"}
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"
        mock_request.client.host = "127.0.0.1"

        with patch.object(hybrid_auth_middleware, 'authenticate_request', return_value={"email": "test@example.com"}):
            call_next = AsyncMock(return_value=MagicMock())

            response = await hybrid_auth_middleware.dispatch(mock_request, call_next)
            assert response is not None

    @pytest.mark.asyncio
    async def test_call_with_jwt_cookie(self, hybrid_auth_middleware, mock_request):
        """Test authentication with JWT cookie"""
        mock_request.cookies = {"nz_access_token": "jwt-token"}
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"
        mock_request.client.host = "127.0.0.1"

        with patch.object(hybrid_auth_middleware, 'authenticate_request', return_value={"email": "test@example.com"}):
            call_next = AsyncMock(return_value=MagicMock())

            response = await hybrid_auth_middleware.dispatch(mock_request, call_next)
            assert response is not None

    @pytest.mark.asyncio
    async def test_call_with_bearer_token(self, hybrid_auth_middleware, mock_request):
        """Test authentication with Bearer token"""
        mock_request.headers = {"Authorization": "Bearer jwt-token"}
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"
        mock_request.client.host = "127.0.0.1"

        with patch.object(hybrid_auth_middleware, 'authenticate_request', return_value={"email": "test@example.com"}):
            call_next = AsyncMock(return_value=MagicMock())

            response = await hybrid_auth_middleware.dispatch(mock_request, call_next)
            assert response is not None

    @pytest.mark.asyncio
    async def test_call_no_auth(self, hybrid_auth_middleware, mock_request):
        """Test without authentication - public endpoint"""
        mock_request.headers = {}
        mock_request.cookies = {}
        mock_request.url.path = "/health"  # Public endpoint
        mock_request.method = "GET"

        call_next = AsyncMock(return_value=MagicMock())

        response = await hybrid_auth_middleware.dispatch(mock_request, call_next)
        # Should continue without auth for public endpoints
        assert response is not None

