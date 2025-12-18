"""
Unit tests for FastAPI dependency injection functions.

Tests that dependencies are correctly retrieved from app.state via the Request object.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException, Request

from app import dependencies

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object with app.state"""
    request = Mock(spec=Request)
    request.app = Mock()
    request.app.state = Mock()
    # Initialize state attributes to None by default
    request.app.state.search_service = None
    request.app.state.intelligent_router = None
    request.app.state.memory_service = None
    request.app.state.db_pool = None
    request.app.state.ai_client = None
    request.app.state.cache_service = None
    return request


# ============================================================================
# Test get_search_service
# ============================================================================


class TestGetSearchService:
    """Tests for get_search_service dependency."""

    def test_returns_service_when_available(self, mock_request):
        """Test that service is returned when available in app.state."""
        mock_service = MagicMock()
        mock_request.app.state.search_service = mock_service

        result = dependencies.get_search_service(mock_request)
        assert result == mock_service

    def test_raises_503_when_unavailable(self, mock_request):
        """Test that HTTPException 503 is raised when service unavailable."""
        mock_request.app.state.search_service = None

        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_search_service(mock_request)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["error"] == "SearchService unavailable"
        assert "retry_after" in exc_info.value.detail
        assert exc_info.value.detail["service"] == "search"
        assert "troubleshooting" in exc_info.value.detail

    def test_error_includes_troubleshooting_hints(self, mock_request):
        """Test that error response includes troubleshooting hints."""
        mock_request.app.state.search_service = None

        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_search_service(mock_request)

        hints = exc_info.value.detail["troubleshooting"]
        assert len(hints) > 0
        assert any("Qdrant" in hint for hint in hints)


# ============================================================================
# Test get_intelligent_router
# ============================================================================


class TestGetIntelligentRouter:
    """Tests for get_intelligent_router dependency."""

    def test_returns_router_when_available(self, mock_request):
        """Test that router is returned when available in app.state."""
        mock_router = MagicMock()
        mock_request.app.state.intelligent_router = mock_router

        result = dependencies.get_intelligent_router(mock_request)
        assert result == mock_router

    def test_raises_503_when_unavailable(self, mock_request):
        """Test that HTTPException 503 is raised when router unavailable."""
        mock_request.app.state.intelligent_router = None

        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_intelligent_router(mock_request)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["error"] == "Router unavailable"
        assert exc_info.value.detail["service"] == "router"

    def test_error_includes_troubleshooting(self, mock_request):
        """Test that error response includes troubleshooting hints."""
        mock_request.app.state.intelligent_router = None

        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_intelligent_router(mock_request)

        assert "troubleshooting" in exc_info.value.detail
        hints = exc_info.value.detail["troubleshooting"]
        assert len(hints) > 0


# ============================================================================
# Test get_memory_service
# ============================================================================


class TestGetMemoryService:
    """Tests for get_memory_service dependency."""

    def test_returns_service_when_available(self, mock_request):
        """Test that service is returned when available in app.state."""
        mock_service = MagicMock()
        mock_request.app.state.memory_service = mock_service

        result = dependencies.get_memory_service(mock_request)
        assert result == mock_service

    def test_raises_503_when_unavailable(self, mock_request):
        """Test that HTTPException 503 is raised when service unavailable."""
        mock_request.app.state.memory_service = None

        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_memory_service(mock_request)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["error"] == "Memory service unavailable"


# ============================================================================
# Test get_database_pool
# ============================================================================


class TestGetDatabasePool:
    """Tests for get_database_pool dependency."""

    def test_returns_pool_when_available(self, mock_request):
        """Test that pool is returned when available in app.state."""
        mock_pool = MagicMock()
        mock_request.app.state.db_pool = mock_pool

        result = dependencies.get_database_pool(mock_request)
        assert result == mock_pool

    def test_raises_503_when_unavailable(self, mock_request):
        """Test that HTTPException 503 is raised when pool unavailable."""
        mock_request.app.state.db_pool = None

        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_database_pool(mock_request)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["error"] == "Database unavailable"


# ============================================================================
# Test get_ai_client
# ============================================================================


class TestGetAIClient:
    """Tests for get_ai_client dependency."""

    def test_returns_client_when_available(self, mock_request):
        """Test that client is returned when available in app.state."""
        mock_client = MagicMock()
        mock_request.app.state.ai_client = mock_client

        result = dependencies.get_ai_client(mock_request)
        assert result == mock_client

    def test_raises_503_when_unavailable(self, mock_request):
        """Test that HTTPException 503 is raised when client unavailable."""
        mock_request.app.state.ai_client = None

        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_ai_client(mock_request)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["error"] == "AI service unavailable"


# ============================================================================
# Test get_cache
# ============================================================================


class TestGetCache:
    """Tests for get_cache dependency."""

    def test_returns_cache_from_state(self, mock_request):
        """Test that cache is returned from app.state if available."""
        mock_cache = MagicMock()
        mock_request.app.state.cache_service = mock_cache

        result = dependencies.get_cache(mock_request)
        assert result == mock_cache

    def test_returns_singleton_fallback(self, mock_request):
        """Test that singleton fallback is used if not in state."""
        mock_request.app.state.cache_service = None

        # We need to mock get_cache_service since it's imported in the module
        with patch("app.dependencies.get_cache_service") as mock_get_cache:
            mock_singleton = MagicMock()
            mock_get_cache.return_value = mock_singleton

            result = dependencies.get_cache(mock_request)
            assert result == mock_singleton
