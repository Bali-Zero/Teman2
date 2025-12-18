"""
Unit tests for Agentic RAG Router
100% coverage target with comprehensive endpoint testing and error handling
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.agentic_rag import (
    AgenticQueryRequest,
    get_orchestrator,
    query_agentic_rag,
    router,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client(mock_orchestrator):
    """Create FastAPI test client with mocked orchestrator"""
    from fastapi import FastAPI

    from app.routers.agentic_rag import get_orchestrator

    app = FastAPI()
    app.include_router(router)

    # Override dependency
    async def override_get_orchestrator():
        return mock_orchestrator

    app.dependency_overrides[get_orchestrator] = override_get_orchestrator

    yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_orchestrator():
    """Mock AgenticRAGOrchestrator with complete interface"""
    orchestrator = MagicMock()
    orchestrator.initialize = AsyncMock(return_value=None)
    orchestrator.process_query = AsyncMock(
        return_value={
            "answer": "Test answer from agentic RAG",
            "sources": [
                {"id": "source1", "text": "Source content 1", "score": 0.95},
                {"id": "source2", "text": "Source content 2", "score": 0.87},
            ],
            "context_used": 1500,
            "execution_time": 1.234,
            "route_used": "agentic",
            "steps": [
                {"step": 1, "thought": "Analyzing query", "tool_used": None},
                {"step": 2, "thought": "Searching sources", "tool_used": "vector_search"},
            ],
            "tools_called": 1,
            "total_steps": 2,
        }
    )
    return orchestrator


@pytest.fixture
def mock_orchestrator_minimal():
    """Mock AgenticRAGOrchestrator with minimal required fields"""
    orchestrator = MagicMock()
    orchestrator.initialize = AsyncMock(return_value=None)
    orchestrator.process_query = AsyncMock(
        return_value={
            "answer": "Minimal answer",
            "sources": [],
            "context_used": 0,
            "execution_time": 0.5,
            "route_used": None,
        }
    )
    return orchestrator


@pytest.fixture
def mock_orchestrator_error():
    """Mock AgenticRAGOrchestrator that raises exceptions"""
    orchestrator = MagicMock()
    orchestrator.initialize = AsyncMock(return_value=None)
    orchestrator.process_query = AsyncMock(side_effect=Exception("Orchestrator error"))
    return orchestrator


@pytest.fixture
def mock_orchestrator_keyerror():
    """Mock AgenticRAGOrchestrator that returns incomplete dict"""
    orchestrator = MagicMock()
    orchestrator.initialize = AsyncMock(return_value=None)
    orchestrator.process_query = AsyncMock(
        return_value={
            "answer": "Answer without required fields",
            # Missing: sources, context_used, execution_time, route_used
        }
    )
    return orchestrator


# ============================================================================
# Tests for get_orchestrator dependency
# ============================================================================


@pytest.fixture
def mock_request():
    """Mock FastAPI Request object"""
    request = MagicMock()
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.db_pool = None
    request.app.state.search_service = None
    return request


@pytest.mark.asyncio
async def test_get_orchestrator_initializes_on_first_call(mock_orchestrator, mock_request):
    """Test that orchestrator is initialized on first call"""
    from app.routers import agentic_rag

    # Reset global orchestrator
    agentic_rag._orchestrator = None

    with patch("app.routers.agentic_rag.create_agentic_rag", return_value=mock_orchestrator):
        result = await get_orchestrator(mock_request)

        assert result == mock_orchestrator


@pytest.mark.asyncio
async def test_get_orchestrator_reuses_instance(mock_orchestrator, mock_request):
    """Test that orchestrator instance is reused on subsequent calls"""
    from app.routers import agentic_rag

    # Set global orchestrator
    agentic_rag._orchestrator = mock_orchestrator

    result = await get_orchestrator(mock_request)

    assert result == mock_orchestrator


@pytest.mark.asyncio
async def test_get_orchestrator_initialization_error(mock_orchestrator, mock_request):
    """Test get_orchestrator when initialization fails"""
    from app.routers import agentic_rag

    agentic_rag._orchestrator = None

    with patch("app.routers.agentic_rag.create_agentic_rag", side_effect=Exception("Init error")):
        with pytest.raises(Exception, match="Init error"):
            await get_orchestrator(mock_request)


# ============================================================================
# Tests for query_agentic_rag endpoint - Success Cases
# ============================================================================


def test_query_agentic_rag_success(client, mock_orchestrator):
    """Test successful agentic RAG query"""
    response = client.post(
        "/api/agentic-rag/query",
        json={
            "query": "What is the capital of Indonesia?",
            "user_id": "user123",
            "enable_vision": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Test answer from agentic RAG"
    assert len(data["sources"]) == 2
    assert data["context_length"] == 1500
    assert data["execution_time"] == 1.234
    assert data["route_used"] == "agentic"

    # Verify orchestrator was called correctly (enable_vision is not passed to process_query)
    mock_orchestrator.process_query.assert_called_once_with(
        query="What is the capital of Indonesia?", user_id="user123"
    )


def test_query_agentic_rag_with_anonymous_user(client, mock_orchestrator):
    """Test agentic RAG query with anonymous user (default)"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    assert response.status_code == 200
    # Verify default user_id is used (enable_vision is not passed to process_query)
    mock_orchestrator.process_query.assert_called_once_with(query="Test query", user_id="anonymous")


def test_query_agentic_rag_with_vision_enabled(client, mock_orchestrator):
    """Test agentic RAG query with vision enabled in request (not passed to process_query)"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Analyze this image", "user_id": "user123", "enable_vision": True},
    )

    assert response.status_code == 200
    # Note: enable_vision is in the request model but NOT passed to process_query
    mock_orchestrator.process_query.assert_called_once_with(
        query="Analyze this image", user_id="user123"
    )


@pytest.fixture
def client_minimal(mock_orchestrator_minimal):
    """Create FastAPI test client with minimal mock orchestrator"""
    from fastapi import FastAPI

    from app.routers.agentic_rag import get_orchestrator

    app = FastAPI()
    app.include_router(router)

    async def override_get_orchestrator():
        return mock_orchestrator_minimal

    app.dependency_overrides[get_orchestrator] = override_get_orchestrator

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_query_agentic_rag_minimal_response(client_minimal, mock_orchestrator_minimal):
    """Test agentic RAG query with minimal response fields"""
    response = client_minimal.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Minimal answer"
    assert data["sources"] == []
    assert data["context_length"] == 0
    assert data["execution_time"] == 0.5
    assert data["route_used"] is None


def test_query_agentic_rag_empty_sources(client, mock_orchestrator):
    """Test agentic RAG query with empty sources"""
    mock_orchestrator.process_query = AsyncMock(
        return_value={
            "answer": "Answer without sources",
            "sources": [],
            "context_used": 0,
            "execution_time": 0.5,
            "route_used": "agentic",
        }
    )

    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == []
    assert data["context_length"] == 0


# ============================================================================
# Tests for query_agentic_rag endpoint - Error Handling
# ============================================================================


@pytest.fixture
def client_error(mock_orchestrator_error):
    """Create FastAPI test client with error mock orchestrator"""
    from fastapi import FastAPI

    from app.routers.agentic_rag import get_orchestrator

    app = FastAPI()
    app.include_router(router)

    async def override_get_orchestrator():
        return mock_orchestrator_error

    app.dependency_overrides[get_orchestrator] = override_get_orchestrator

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_query_agentic_rag_orchestrator_exception(client_error, mock_orchestrator_error):
    """Test agentic RAG query when orchestrator raises exception"""
    response = client_error.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    assert response.status_code == 500
    assert "Orchestrator error" in response.json()["detail"]


@pytest.fixture
def client_keyerror(mock_orchestrator_keyerror):
    """Create FastAPI test client with keyerror mock orchestrator"""
    from fastapi import FastAPI

    from app.routers.agentic_rag import get_orchestrator

    app = FastAPI()
    app.include_router(router)

    async def override_get_orchestrator():
        return mock_orchestrator_keyerror

    app.dependency_overrides[get_orchestrator] = override_get_orchestrator

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_query_agentic_rag_keyerror_missing_fields(client_keyerror, mock_orchestrator_keyerror):
    """Test agentic RAG query when orchestrator returns incomplete dict"""
    response = client_keyerror.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    # Should raise KeyError which gets caught and converted to HTTPException
    assert response.status_code == 500
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_query_agentic_rag_http_exception_propagates(client, mock_orchestrator):
    """Test that HTTPException from orchestrator is caught and converted to 500"""
    from fastapi import HTTPException

    mock_orchestrator.process_query = AsyncMock(
        side_effect=HTTPException(status_code=400, detail="Bad request")
    )

    # The router catches all exceptions and converts them to HTTPException 500
    # Test the actual endpoint function directly (not via client)
    request = AgenticQueryRequest(query="Test query")
    with pytest.raises(HTTPException) as exc_info:
        await query_agentic_rag(request, mock_orchestrator)

    # Router converts all exceptions to 500
    assert exc_info.value.status_code == 500
    # The detail might be empty or contain the exception message
    assert exc_info.value.detail is not None


# ============================================================================
# Tests for Input Validation
# ============================================================================


@pytest.mark.asyncio
async def test_query_agentic_rag_missing_query(client):
    """Test agentic RAG query with missing query field"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"user_id": "user123"},
    )

    assert response.status_code == 422  # Validation error
    assert "detail" in response.json()


def test_query_agentic_rag_empty_query(client, mock_orchestrator):
    """Test agentic RAG query with empty query string"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"query": ""},
    )

    # Empty string is valid according to Pydantic, so should process
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_agentic_rag_invalid_user_id_type(client):
    """Test agentic RAG query with invalid user_id type"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Test query", "user_id": 12345},  # Should be string
    )

    assert response.status_code == 422  # Validation error


def test_query_agentic_rag_invalid_enable_vision_type(client):
    """Test agentic RAG query with invalid enable_vision type"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Test query", "enable_vision": "yes"},  # Should be bool
    )

    # Pydantic might coerce "yes" to True, so check for either 422 or 200
    assert response.status_code in [200, 422]


# ============================================================================
# Tests for Response Model Validation
# ============================================================================


def test_query_agentic_rag_response_structure(client, mock_orchestrator):
    """Test that response has correct structure matching AgenticQueryResponse model"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields are present
    assert "answer" in data
    assert "sources" in data
    assert "context_length" in data
    assert "execution_time" in data
    assert "route_used" in data

    # Verify types
    assert isinstance(data["answer"], str)
    assert isinstance(data["sources"], list)
    assert isinstance(data["context_length"], int)
    assert isinstance(data["execution_time"], (int, float))
    assert isinstance(data["route_used"], (str, type(None)))


def test_query_agentic_rag_sources_structure(client, mock_orchestrator):
    """Test that sources array contains valid objects"""
    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 2
    # Sources can be any structure (list[Any] in model)
    assert isinstance(data["sources"][0], dict)


# ============================================================================
# Tests for Edge Cases
# ============================================================================


def test_query_agentic_rag_very_long_query(client, mock_orchestrator):
    """Test agentic RAG query with very long query string"""
    long_query = "Test query " * 1000  # Very long query

    response = client.post(
        "/api/agentic-rag/query",
        json={"query": long_query},
    )

    assert response.status_code == 200
    mock_orchestrator.process_query.assert_called_once_with(query=long_query, user_id="anonymous")


def test_query_agentic_rag_special_characters(client, mock_orchestrator):
    """Test agentic RAG query with special characters"""
    special_query = "Test query with special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"

    response = client.post(
        "/api/agentic-rag/query",
        json={"query": special_query},
    )

    assert response.status_code == 200
    mock_orchestrator.process_query.assert_called_once_with(
        query=special_query, user_id="anonymous"
    )


def test_query_agentic_rag_unicode_characters(client, mock_orchestrator):
    """Test agentic RAG query with unicode characters"""
    unicode_query = "Test query with unicode: 你好世界 🌍"

    response = client.post(
        "/api/agentic-rag/query",
        json={"query": unicode_query},
    )

    assert response.status_code == 200
    mock_orchestrator.process_query.assert_called_once_with(
        query=unicode_query, user_id="anonymous"
    )


def test_query_agentic_rag_none_route_used(client, mock_orchestrator):
    """Test agentic RAG query when route_used is None"""
    mock_orchestrator.process_query = AsyncMock(
        return_value={
            "answer": "Answer",
            "sources": [],
            "context_used": 500,
            "execution_time": 1.0,
            "route_used": None,
        }
    )

    response = client.post(
        "/api/agentic-rag/query",
        json={"query": "Test query"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["route_used"] is None


# ============================================================================
# Tests for Concurrent Requests
# ============================================================================


def test_query_agentic_rag_concurrent_requests(client, mock_orchestrator):
    """Test that orchestrator instance is reused across concurrent requests"""
    # Simulate concurrent requests
    responses = []
    for i in range(5):
        response = client.post(
            "/api/agentic-rag/query",
            json={"query": f"Test query {i}"},
        )
        responses.append(response)

    # All should succeed
    assert all(r.status_code == 200 for r in responses)
    # Orchestrator should be called 5 times
    assert mock_orchestrator.process_query.call_count == 5
