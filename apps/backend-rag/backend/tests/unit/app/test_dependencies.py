"""
Unit tests for app/dependencies.py
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.dependencies import (
    get_ai_client,
    get_cache,
    get_current_user,
    get_database_pool,
    get_intelligent_router,
    get_memory_service,
    get_search_service,
)


@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock(spec=Request)
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.state = MagicMock()
    return request


class TestDependencies:
    """Tests for dependency injection functions"""

    def test_get_search_service_success(self, mock_request):
        """Test getting search service successfully"""
        mock_service = MagicMock()
        mock_request.app.state.search_service = mock_service

        service = get_search_service(mock_request)
        assert service == mock_service

    def test_get_search_service_unavailable(self, mock_request):
        """Test getting search service when unavailable"""
        mock_request.app.state.search_service = None

        with pytest.raises(HTTPException) as exc_info:
            get_search_service(mock_request)
        assert exc_info.value.status_code == 503

    def test_get_ai_client_success(self, mock_request):
        """Test getting AI client successfully"""
        mock_client = MagicMock()
        mock_request.app.state.ai_client = mock_client

        client = get_ai_client(mock_request)
        assert client == mock_client

    def test_get_ai_client_unavailable(self, mock_request):
        """Test getting AI client when unavailable"""
        mock_request.app.state.ai_client = None

        with pytest.raises(HTTPException) as exc_info:
            get_ai_client(mock_request)
        assert exc_info.value.status_code == 503

    def test_get_intelligent_router_success(self, mock_request):
        """Test getting intelligent router successfully"""
        mock_router = MagicMock()
        mock_request.app.state.intelligent_router = mock_router

        router = get_intelligent_router(mock_request)
        assert router == mock_router

    def test_get_intelligent_router_unavailable(self, mock_request):
        """Test getting intelligent router when unavailable"""
        mock_request.app.state.intelligent_router = None

        with pytest.raises(HTTPException) as exc_info:
            get_intelligent_router(mock_request)
        assert exc_info.value.status_code == 503

    def test_get_memory_service_success(self, mock_request):
        """Test getting memory service successfully"""
        mock_service = MagicMock()
        mock_request.app.state.memory_service = mock_service

        service = get_memory_service(mock_request)
        assert service == mock_service

    def test_get_memory_service_unavailable(self, mock_request):
        """Test getting memory service when unavailable"""
        mock_request.app.state.memory_service = None

        with pytest.raises(HTTPException) as exc_info:
            get_memory_service(mock_request)
        assert exc_info.value.status_code == 503

    def test_get_database_pool_success(self, mock_request):
        """Test getting database pool successfully"""
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_request.app.state.db_pool = mock_pool

        pool = get_database_pool(mock_request)
        assert pool == mock_pool

    def test_get_database_pool_unavailable(self, mock_request):
        """Test getting database pool when unavailable"""
        mock_request.app.state.db_pool = None

        with pytest.raises(HTTPException) as exc_info:
            get_database_pool(mock_request)
        assert exc_info.value.status_code == 503

    def test_get_database_pool_no_acquire(self, mock_request):
        """Test getting database pool without acquire method"""
        # Create mock without acquire attribute
        mock_pool = MagicMock()
        del mock_pool.acquire  # Remove acquire attribute
        mock_request.app.state.db_pool = mock_pool

        with pytest.raises(HTTPException) as exc_info:
            get_database_pool(mock_request)
        assert exc_info.value.status_code == 503

    def test_get_database_pool_with_error(self, mock_request):
        """Test getting database pool with initialization error"""
        mock_request.app.state.db_pool = None
        mock_request.app.state.db_init_error = "Connection failed"

        with pytest.raises(HTTPException) as exc_info:
            get_database_pool(mock_request)
        assert exc_info.value.status_code == 503
        assert "Connection failed" in str(exc_info.value.detail)

    def test_get_current_user_from_middleware(self, mock_request):
        """Test getting current user from middleware"""
        mock_request.state.user = {
            "email": "test@example.com",
            "id": "123",
            "role": "admin"
        }

        user = get_current_user(mock_request, credentials=None)
        assert user["email"] == "test@example.com"
        assert user["user_id"] == "123"

    def test_get_current_user_from_token(self, mock_request):
        """Test getting current user from JWT token"""
        mock_request.state.user = None

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "valid_token"

        with patch("app.dependencies.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "email": "test@example.com",
                "user_id": "123",
                "role": "user"
            }

            user = get_current_user(mock_request, credentials=mock_credentials)
            assert user["email"] == "test@example.com"

    def test_get_current_user_no_credentials(self, mock_request):
        """Test getting current user without credentials"""
        mock_request.state.user = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_request, credentials=None)
        assert exc_info.value.status_code == 401

    def test_get_current_user_invalid_token(self, mock_request):
        """Test getting current user with invalid token"""
        mock_request.state.user = None

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "invalid_token"

        with patch("app.dependencies.jwt.decode") as mock_decode:
            from jose import JWTError
            mock_decode.side_effect = JWTError("Invalid token")

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_request, credentials=mock_credentials)
            assert exc_info.value.status_code == 401

    def test_get_current_user_missing_email(self, mock_request):
        """Test getting current user with token missing email"""
        mock_request.state.user = None

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "token"

        with patch("app.dependencies.jwt.decode") as mock_decode:
            mock_decode.return_value = {}  # No email, no sub

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_request, credentials=mock_credentials)
            assert exc_info.value.status_code == 401

    def test_get_cache_from_state(self, mock_request):
        """Test getting cache from app.state"""
        mock_cache = MagicMock()
        mock_request.app.state.cache_service = mock_cache

        cache = get_cache(mock_request)
        assert cache == mock_cache

    def test_get_cache_fallback(self, mock_request):
        """Test getting cache with fallback to singleton"""
        mock_request.app.state.cache_service = None

        with patch("app.dependencies.get_cache_service") as mock_get_cache:
            mock_get_cache.return_value = MagicMock()

            cache = get_cache(mock_request)
            assert cache is not None
            mock_get_cache.assert_called_once()

