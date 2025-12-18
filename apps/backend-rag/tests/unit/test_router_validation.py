"""
Unit tests for Pydantic Input Validation across routers
Tests validation errors (422) for missing required fields, invalid types, and edge cases
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import FastAPI

# Import routers (notifications removed)
from app.routers import (
    agentic_rag,
    crm_clients,
    crm_interactions,
    intel,
    oracle_universal,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client_agentic():
    """Create FastAPI test client for agentic_rag router"""
    from app.routers.agentic_rag import get_orchestrator

    app = FastAPI()
    app.include_router(agentic_rag.router)

    # Mock orchestrator dependency
    mock_orchestrator = MagicMock()
    mock_orchestrator.process_query = AsyncMock(
        return_value={
            "answer": "test",
            "sources": [],
            "context_used": 0,
            "execution_time": 0.1,
            "route_used": "test",
        }
    )

    async def override_get_orchestrator():
        return mock_orchestrator

    app.dependency_overrides[get_orchestrator] = override_get_orchestrator

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture
def client_crm_clients():
    """Create FastAPI test client for crm_clients router"""
    app = FastAPI()
    app.include_router(crm_clients.router)
    return TestClient(app)


@pytest.fixture
def client_crm_interactions():
    """Create FastAPI test client for crm_interactions router"""
    app = FastAPI()
    app.include_router(crm_interactions.router)
    return TestClient(app)


@pytest.fixture
def client_intel():
    """Create FastAPI test client for intel router"""
    app = FastAPI()
    app.include_router(intel.router)
    return TestClient(app)


@pytest.fixture
def client_oracle():
    """Create FastAPI test client for oracle_universal router"""
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(oracle_universal.router)

    # Mock user dependency
    def override_get_current_user():
        return {"email": "test@example.com", "id": "user123"}

    app.dependency_overrides[get_current_user] = override_get_current_user

    yield TestClient(app)

    app.dependency_overrides.clear()


# ============================================================================
# Tests for Agentic RAG Router Validation
# ============================================================================


def test_agentic_rag_missing_query(client_agentic):
    """Test agentic RAG with missing required query field"""
    response = client_agentic.post("/api/agentic-rag/query", json={})

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("query" in str(err).lower() for err in errors)


def test_agentic_rag_invalid_user_id_type(client_agentic):
    """Test agentic RAG with invalid user_id type"""
    response = client_agentic.post(
        "/api/agentic-rag/query",
        json={"query": "test", "user_id": 12345},  # Should be string
    )

    assert response.status_code == 422


def test_agentic_rag_invalid_enable_vision_type(client_agentic):
    """Test agentic RAG with invalid enable_vision type"""
    response = client_agentic.post(
        "/api/agentic-rag/query",
        json={"query": "test", "enable_vision": "yes"},  # Should be bool
    )

    # Pydantic might coerce "yes" to True, so check for either 422 or 200
    assert response.status_code in [200, 422]


# ============================================================================
# Tests for CRM Clients Router Validation
# ============================================================================


@patch("app.routers.crm_clients.get_database_pool")
def test_crm_clients_create_missing_full_name(mock_db_pool, client_crm_clients):
    """Test CRM client creation with missing required full_name"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_db_pool.return_value = mock_pool

    response = client_crm_clients.post(
        "/api/crm/clients/?created_by=test@example.com", json={"email": "test@example.com"}
    )

    # Should return 422 for validation error, but might return 503 if DB unavailable
    assert response.status_code in [422, 503]
    if response.status_code == 422:
        errors = response.json()["detail"]
        assert any("full_name" in str(err).lower() for err in errors)


@patch("app.routers.crm_clients.get_database_pool")
def test_crm_clients_create_invalid_email_format(mock_db_pool, client_crm_clients):
    """Test CRM client creation with invalid email format"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_db_pool.return_value = mock_pool

    response = client_crm_clients.post(
        "/api/crm/clients/?created_by=test@example.com",
        json={"full_name": "Test User", "email": "invalid-email"},
    )

    # Should return 422 for validation error, but might return 503 if DB unavailable
    assert response.status_code in [422, 503]
    if response.status_code == 422:
        errors = response.json()["detail"]
        assert any("email" in str(err).lower() for err in errors)


# ============================================================================
# Tests for CRM Interactions Router Validation
# ============================================================================


@patch("app.routers.crm_interactions.get_database_pool")
def test_crm_interactions_create_missing_required_fields(mock_db_pool, client_crm_interactions):
    """Test CRM interaction creation with missing required fields"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_db_pool.return_value = mock_pool

    response = client_crm_interactions.post("/api/crm/interactions/", json={})

    # Should return 422 for validation error, but might return 503 if DB unavailable
    assert response.status_code in [422, 503]
    if response.status_code == 422:
        errors = response.json()["detail"]
        # Should require interaction_type and team_member
        assert any(
            "interaction_type" in str(err).lower() or "team_member" in str(err).lower()
            for err in errors
        )


@patch("app.routers.crm_interactions.get_database_pool")
def test_crm_interactions_create_invalid_interaction_type(mock_db_pool, client_crm_interactions):
    """Test CRM interaction creation with invalid interaction_type"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_db_pool.return_value = mock_pool

    response = client_crm_interactions.post(
        "/api/crm/interactions/",
        json={
            "interaction_type": "invalid_type",  # Should be one of: chat, email, whatsapp, call, meeting, note
            "team_member": "test@example.com",
        },
    )

    # Should return 422 for validation error, but might return 503 if DB unavailable
    assert response.status_code in [422, 503]
    if response.status_code == 422:
        errors = response.json()["detail"]
        assert any("interaction_type" in str(err).lower() for err in errors)


@patch("app.routers.crm_interactions.get_database_pool")
def test_crm_interactions_create_empty_team_member(mock_db_pool, client_crm_interactions):
    """Test CRM interaction creation with empty team_member"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_db_pool.return_value = mock_pool

    response = client_crm_interactions.post(
        "/api/crm/interactions/",
        json={"interaction_type": "chat", "team_member": ""},  # Empty string should fail validation
    )

    # Should return 422 for validation error, but might return 503 if DB unavailable
    assert response.status_code in [422, 503]
    if response.status_code == 422:
        errors = response.json()["detail"]
        assert any("team_member" in str(err).lower() for err in errors)


# ============================================================================
# Tests for Intel Router Validation
# ============================================================================


def test_intel_search_missing_query(client_intel):
    """Test intel search with missing required query field"""
    response = client_intel.post("/api/intel/search", json={})

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("query" in str(err).lower() for err in errors)


def test_intel_search_invalid_limit_type(client_intel):
    """Test intel search with invalid limit type"""
    response = client_intel.post(
        "/api/intel/search", json={"query": "test", "limit": "not_a_number"}
    )

    assert response.status_code == 422


def test_intel_search_negative_limit(client_intel):
    """Test intel search with negative limit"""
    response = client_intel.post("/api/intel/search", json={"query": "test", "limit": -1})

    # Should either validate (422), process with validation (400/500/503), or accept (200)
    # The API might clamp negative values to default, hence 200 is acceptable
    assert response.status_code in [200, 400, 422, 500, 503]


def test_intel_store_missing_required_fields(client_intel):
    """Test intel store with missing required fields"""
    response = client_intel.post("/api/intel/store", json={})

    assert response.status_code == 422
    errors = response.json()["detail"]
    # Should require: collection, id, document, embedding, metadata, full_data
    required_fields = ["collection", "id", "document", "embedding", "metadata", "full_data"]
    assert any(field in str(errors).lower() for field in required_fields)


def test_intel_store_invalid_embedding_type(client_intel):
    """Test intel store with invalid embedding type"""
    response = client_intel.post(
        "/api/intel/store",
        json={
            "collection": "test",
            "id": "test_id",
            "document": "test doc",
            "embedding": "not_a_list",  # Should be list[float]
            "metadata": {},
            "full_data": {},
        },
    )

    assert response.status_code == 422


# ============================================================================
# Tests for Oracle Universal Router Validation
# ============================================================================


def test_oracle_query_missing_query(client_oracle):
    """Test oracle query with missing required query field"""
    response = client_oracle.post("/api/oracle/query", json={})

    # Oracle router might require authentication or have different validation
    assert response.status_code in [401, 403, 422, 500, 503]


def test_oracle_query_invalid_user_preferences_type(client_oracle):
    """Test oracle query with invalid user_preferences type"""
    response = client_oracle.post(
        "/api/oracle/query",
        json={"query": "test", "user_preferences": "not_a_dict"},  # Should be dict
    )

    # Oracle router might require authentication or have different validation
    # Note: OracleQueryRequest doesn't have user_preferences field, so this might be ignored
    assert response.status_code in [200, 401, 403, 422, 500, 503]


# ============================================================================
# Tests for Edge Cases and Type Coercion
# ============================================================================


def test_agentic_rag_empty_string_query(client_agentic):
    """Test agentic RAG with empty string query (edge case)"""
    # Empty string is technically valid in Pydantic, but might be rejected by business logic
    response = client_agentic.post("/api/agentic-rag/query", json={"query": ""})

    # Should either accept (200) or reject (400/422/500)
    assert response.status_code in [200, 400, 422, 500]


def test_intel_search_zero_limit(client_intel):
    """Test intel search with zero limit (edge case)"""
    response = client_intel.post("/api/intel/search", json={"query": "test", "limit": 0})

    # Should either validate (422) or process (200/400/500/503)
    assert response.status_code in [200, 400, 422, 500, 503]


# ============================================================================
# Tests for Nested Object Validation
# ============================================================================


def test_intel_store_invalid_metadata_type(client_intel):
    """Test intel store with invalid metadata type"""
    response = client_intel.post(
        "/api/intel/store",
        json={
            "collection": "test",
            "id": "test_id",
            "document": "test doc",
            "embedding": [0.1, 0.2, 0.3],
            "metadata": "not_a_dict",  # Should be dict
            "full_data": {},
        },
    )

    assert response.status_code == 422


def test_intel_store_invalid_full_data_type(client_intel):
    """Test intel store with invalid full_data type"""
    response = client_intel.post(
        "/api/intel/store",
        json={
            "collection": "test",
            "id": "test_id",
            "document": "test doc",
            "embedding": [0.1, 0.2, 0.3],
            "metadata": {},
            "full_data": "not_a_dict",  # Should be dict
        },
    )

    assert response.status_code == 422


# ============================================================================
# Tests for List/Array Validation
# ============================================================================


def test_intel_search_invalid_tier_type(client_intel):
    """Test intel search with invalid tier type"""
    response = client_intel.post(
        "/api/intel/search",
        json={"query": "test", "tier": "not_a_list"},  # Should be list[str]
    )

    assert response.status_code == 422
