"""
Unit tests for Health Router
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

# Ensure backend is in path
backend_root = Path(__file__).parents[2]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.app.routers.health import (
    detailed_health,
    health_check,
    liveness_check,
    readiness_check,
)


@pytest.fixture
def mock_search_service():
    """Mock search service"""
    service = MagicMock()
    service.embedder = MagicMock()
    service.embedder.model = "text-embedding-3-small"
    service.embedder.dimensions = 1536
    service.embedder.provider = "openai"
    return service


@pytest.fixture
def mock_request(mock_search_service):
    """Mock Request with app.state configured"""
    request = MagicMock(spec=Request)
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.search_service = mock_search_service
    request.app.state.services_initialized = True
    return request


@pytest.fixture
def mock_request_no_service():
    """Mock Request with no search_service"""
    request = MagicMock(spec=Request)
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.search_service = None
    request.app.state.services_initialized = False
    return request


# ============================================================================
# Tests for health_check
# ============================================================================


@pytest.mark.asyncio
async def test_health_check_success(mock_request):
    """Test successful health check"""
    # Mocking get_qdrant_stats
    mock_stats = {"collections": 5, "total_documents": 1000}
    with patch("backend.app.routers.health.get_qdrant_stats", return_value=mock_stats):
        result = await health_check(request=mock_request)

    from backend.app.models import HealthResponse
    assert isinstance(result, HealthResponse)
    assert result.status == "healthy"
    assert result.database["collections"] == 5


@pytest.mark.asyncio
async def test_health_check_no_service(mock_request_no_service):
    """Test health check when search service is missing"""
    result = await health_check(request=mock_request_no_service)

    assert result.status == "initializing"


# ============================================================================
# Tests for detailed_health
# ============================================================================


@pytest.mark.asyncio
async def test_detailed_health_success(mock_request):
    """Test detailed health check"""
    # Mock database pool
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock()
    mock_pool.acquire.return_value.__aexit__ = AsyncMock()
    mock_pool.get_min_size.return_value = 2
    mock_pool.get_max_size.return_value = 10
    mock_pool.get_size.return_value = 5
    
    mock_request.app.state.db_pool = mock_pool

    # Mock qdrant stats
    mock_stats = {"status": "ok", "collections": []}

    with patch("backend.app.routers.health.get_qdrant_stats", return_value=mock_stats):
        result = await detailed_health(request=mock_request)

    assert result["status"] == "healthy"
    assert "services" in result
    assert result["services"]["search"]["status"] == "healthy"


# ============================================================================
# Tests for readiness_check
# ============================================================================


@pytest.mark.asyncio
async def test_readiness_check_ready(mock_request):
    """Test readiness check when ready"""
    mock_request.app.state.search_service = MagicMock()
    mock_request.app.state.ai_client = MagicMock()
    mock_request.app.state.services_initialized = True

    result = await readiness_check(request=mock_request)

    assert result["ready"] is True


@pytest.mark.asyncio
async def test_readiness_check_not_ready(mock_request_no_service):
    """Test readiness check when not ready"""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await readiness_check(request=mock_request_no_service)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["ready"] is False


# ============================================================================
# Tests for liveness_check
# ============================================================================


@pytest.mark.asyncio
async def test_liveness_check():
    """Test liveness check"""
    result = await liveness_check()
    assert result["alive"] is True
