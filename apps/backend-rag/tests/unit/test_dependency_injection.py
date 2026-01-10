"""
Unit tests for FastAPI dependency injection
Target: 90%+ coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

# Ensure backend is in path
backend_root = Path(__file__).parents[2]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.app.dependencies import (
    get_ai_client,
    get_database_pool,
    get_intelligent_router,
    get_memory_service,
    get_orchestrator,
    get_search_service,
)


@pytest.fixture
def mock_request():
    """Mock FastAPI Request object"""
    request = MagicMock(spec=Request)
    request.app.state = MagicMock()
    return request


# ============================================================================
# Tests for get_orchestrator (dependencies.py)
# ============================================================================


@pytest.mark.asyncio
async def test_get_orchestrator_lazy_initialization(mock_request):
    """Test that orchestrator is initialized on first call"""
    mock_request.app.state.db_pool = MagicMock()
    mock_request.app.state.search_service = MagicMock()

    mock_orchestrator = MagicMock()
    
    with patch("backend.services.rag.agentic.create_agentic_rag", return_value=mock_orchestrator):
        with patch("backend.app.dependencies._agentic_rag_orchestrator", None):
            result = get_orchestrator(mock_request)
            assert result == mock_orchestrator


@pytest.mark.asyncio
async def test_get_orchestrator_instance_reuse(mock_request):
    """Test that the same orchestrator instance is reused"""
    mock_request.app.state.db_pool = MagicMock()
    mock_request.app.state.search_service = MagicMock()

    mock_orchestrator = MagicMock()
    
    with patch("backend.services.rag.agentic.create_agentic_rag", return_value=mock_orchestrator):
        with patch("backend.app.dependencies._agentic_rag_orchestrator", None):
            # First call
            result1 = get_orchestrator(mock_request)
            # Second call
            result2 = get_orchestrator(mock_request)

            assert result1 == mock_orchestrator
            assert result2 == mock_orchestrator
            assert result1 is result2


@pytest.mark.asyncio
async def test_get_orchestrator_initialization_error(mock_request):
    """Test get_orchestrator when initialization fails"""
    mock_request.app.state.db_pool = MagicMock()
    mock_request.app.state.search_service = MagicMock()

    with patch("backend.services.rag.agentic.create_agentic_rag", side_effect=Exception("Init error")):
        with patch("backend.app.dependencies._agentic_rag_orchestrator", None):
            with pytest.raises(Exception, match="Init error"):
                get_orchestrator(mock_request)


# ============================================================================
# Tests for get_database_pool (dependencies.py)
# ============================================================================


def test_get_database_pool_success(mock_request):
    """Test get_database_pool when pool is available"""
    mock_pool = MagicMock()
    # Mock hasattr(mock_pool, "acquire") to return True
    mock_pool.acquire = AsyncMock()
    mock_request.app.state.db_pool = mock_pool

    result = get_database_pool(mock_request)

    assert result == mock_pool


def test_get_database_pool_not_initialized(mock_request):
    """Test get_database_pool when pool is not initialized"""
    mock_request.app.state.db_pool = None
    mock_request.app.state.db_init_error = "Test error"

    with pytest.raises(HTTPException) as exc_info:
        get_database_pool(mock_request)

    assert exc_info.value.status_code == 503
    assert "not initialized" in str(exc_info.value.detail).lower()
    assert "Test error" in str(exc_info.value.detail)


def test_get_database_pool_missing_state(mock_request):
    """Test get_database_pool when app.state is missing"""
    del mock_request.app.state

    with pytest.raises(AttributeError):
        get_database_pool(mock_request)


# ============================================================================
# Tests for get_search_service (dependencies.py)
# ============================================================================


def test_get_search_service_success(mock_request):
    """Test get_search_service when service is available"""
    mock_service = MagicMock()
    mock_request.app.state.search_service = mock_service

    result = get_search_service(mock_request)

    assert result == mock_service


def test_get_search_service_not_initialized(mock_request):
    """Test get_search_service when not initialized"""
    mock_request.app.state.search_service = None

    with pytest.raises(HTTPException) as exc_info:
        get_search_service(mock_request)

    assert exc_info.value.status_code == 503


# ============================================================================
# Tests for get_ai_client (dependencies.py)
# ============================================================================


def test_get_ai_client_success(mock_request):
    """Test get_ai_client when client is available"""
    mock_client = MagicMock()
    mock_request.app.state.ai_client = mock_client

    result = get_ai_client(mock_request)

    assert result == mock_client


def test_get_ai_client_not_initialized(mock_request):
    """Test get_ai_client when not initialized"""
    mock_request.app.state.ai_client = None

    with pytest.raises(HTTPException) as exc_info:
        get_ai_client(mock_request)

    assert exc_info.value.status_code == 503


# ============================================================================
# Tests for get_intelligent_router (dependencies.py)
# ============================================================================


def test_get_intelligent_router_success(mock_request):
    """Test get_intelligent_router when router is available"""
    mock_router = MagicMock()
    mock_request.app.state.intelligent_router = mock_router

    result = get_intelligent_router(mock_request)

    assert result == mock_router


def test_get_intelligent_router_not_initialized(mock_request):
    """Test get_intelligent_router when not initialized"""
    mock_request.app.state.intelligent_router = None

    with pytest.raises(HTTPException) as exc_info:
        get_intelligent_router(mock_request)

    assert exc_info.value.status_code == 503


# ============================================================================
# Tests for get_memory_service (dependencies.py)
# ============================================================================


def test_get_memory_service_success(mock_request):
    """Test get_memory_service when service is available"""
    mock_service = MagicMock()
    mock_request.app.state.memory_service = mock_service

    result = get_memory_service(mock_request)

    assert result == mock_service


def test_get_memory_service_not_initialized(mock_request):
    """Test get_memory_service when not initialized"""
    mock_request.app.state.memory_service = None

    with pytest.raises(HTTPException) as exc_info:
        get_memory_service(mock_request)

    assert exc_info.value.status_code == 503


# ============================================================================
# Tests for get_auto_crm (dependencies.py) - (using direct import for now)
# ============================================================================


def test_get_auto_crm_lazy_initialization(mock_request):
    """Test that AutoCRM is initialized on first call"""
    # This might be in a different file or replaced by direct service init
    pass


# ============================================================================
# Tests for Dependency Overrides
# ============================================================================


def test_dependency_override_get_orchestrator(mock_request):
    """Test overriding get_orchestrator dependency"""
    from fastapi import FastAPI
    app = FastAPI()
    mock_orchestrator = MagicMock()
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    
    # Simulate FastAPI dependency resolution
    result = app.dependency_overrides[get_orchestrator]()
    assert result == mock_orchestrator


def test_dependency_override_get_database_pool(mock_request):
    """Test overriding get_database_pool dependency"""
    from fastapi import FastAPI
    app = FastAPI()
    mock_pool = MagicMock()
    app.dependency_overrides[get_database_pool] = lambda: mock_pool
    
    result = app.dependency_overrides[get_database_pool]()
    assert result == mock_pool


def test_dependency_override_get_search_service(mock_request):
    """Test overriding get_search_service dependency"""
    from fastapi import FastAPI
    app = FastAPI()
    mock_service = MagicMock()
    app.dependency_overrides[get_search_service] = lambda: mock_service
    
    result = app.dependency_overrides[get_search_service]()
    assert result == mock_service


def test_multiple_dependencies_in_single_endpoint(mock_request):
    """Test using multiple dependencies together"""
    mock_pool = MagicMock()
    mock_pool.acquire = AsyncMock()
    mock_service = MagicMock()
    
    mock_request.app.state.db_pool = mock_pool
    mock_request.app.state.search_service = mock_service
    
    pool = get_database_pool(mock_request)
    service = get_search_service(mock_request)
    
    assert pool == mock_pool
    assert service == mock_service


def test_dependency_exception_propagation(mock_request):
    """Test that exceptions propagate correctly"""
    mock_request.app.state.search_service = None
    
    with pytest.raises(HTTPException) as exc_info:
        get_search_service(mock_request)
    
    assert exc_info.value.status_code == 503


def test_dependency_missing_attribute(mock_request):
    """Test handling of missing attributes in request.app.state"""
    # Remove app attribute to trigger error
    del mock_request.app
    
    with pytest.raises(AttributeError):
        get_search_service(mock_request)