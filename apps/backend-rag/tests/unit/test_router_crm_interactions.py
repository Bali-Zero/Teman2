"""
Unit tests for CRM Interactions Router
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_root = Path(__file__).parents[2]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.app.routers.crm_interactions import router


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool"""
    pool = MagicMock()
    conn = AsyncMock()
    
    # Configure default return values
    conn.fetchrow.return_value = None
    conn.fetch.return_value = []
    conn.execute.return_value = "INSERT 0 1"
    
    # Setup acquire context manager
    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=mock_acquire)
    
    return pool, conn


@pytest.fixture
def app(mock_db_pool):
    """Create FastAPI test app with mocked dependencies"""
    mock_pool, _ = mock_db_pool
    
    test_app = FastAPI()
    test_app.include_router(router)
    
    # Override dependencies
    from backend.app.dependencies import get_current_user, get_database_pool
    from backend.app.services.crm.audit_logger import audit_logger
    from backend.app.services.crm.metrics import metrics_collector

    # Initialize with mock pool
    audit_logger.initialize(mock_pool)
    metrics_collector.initialize(mock_pool)

    test_app.dependency_overrides[get_database_pool] = lambda: mock_pool
    test_app.dependency_overrides[get_current_user] = lambda: {
        "email": "admin@balizero.com",
        "role": "admin",
    }
    
    return test_app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_interaction_data():
    """Sample interaction data"""
    return {
        "id": 1,
        "client_id": 1,
        "practice_id": None,
        "interaction_type": "chat",
        "channel": "web_chat",
        "subject": "Test interaction",
        "summary": "Test summary",
        "team_member": "team@example.com",
        "direction": "inbound",
        "sentiment": "positive",
        "interaction_date": datetime.now(),
        "created_at": datetime.now(),
    }


# ============================================================================
# Tests for create_interaction
# ============================================================================


@pytest.mark.asyncio
async def test_create_interaction_success(client, mock_db_pool, sample_interaction_data):
    """Test successful interaction creation"""
    _, conn = mock_db_pool
    conn.fetchrow.return_value = sample_interaction_data

    payload = {
        "client_id": 1,
        "interaction_type": "chat",
        "channel": "web_chat",
        "team_member": "team@example.com",
        "summary": "Test summary",
    }

    response = client.post("/api/crm/interactions/", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["interaction_type"] == "chat"
    assert data["team_member"] == "team@example.com"


@pytest.mark.asyncio
async def test_create_interaction_database_error(client, mock_db_pool):
    """Test interaction creation with database error"""
    import asyncpg
    _, conn = mock_db_pool
    conn.fetchrow.side_effect = asyncpg.PostgresError("DB error")

    payload = {
        "client_id": 1,
        "interaction_type": "chat",
        "channel": "web_chat",
        "team_member": "team@example.com",
        "summary": "Test summary",
    }

    response = client.post("/api/crm/interactions/", json=payload)

    assert response.status_code == 503


# ============================================================================
# Tests for list_interactions
# ============================================================================


@pytest.mark.asyncio
async def test_get_interactions_success(client, mock_db_pool, sample_interaction_data):
    """Test listing interactions"""
    _, conn = mock_db_pool
    conn.fetch.return_value = [sample_interaction_data]

    response = client.get("/api/crm/interactions/", params={"limit": 10})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 1


# ============================================================================
# Tests for get_interaction
# ============================================================================


@pytest.mark.asyncio
async def test_get_interaction_success(client, mock_db_pool, sample_interaction_data):
    """Test getting single interaction"""
    _, conn = mock_db_pool
    conn.fetchrow.return_value = sample_interaction_data

    response = client.get("/api/crm/interactions/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1


@pytest.mark.asyncio
async def test_get_interaction_not_found(client, mock_db_pool):
    """Test getting non-existent interaction"""
    _, conn = mock_db_pool
    conn.fetchrow.return_value = None

    response = client.get("/api/crm/interactions/999")

    assert response.status_code == 404


# ============================================================================
# Tests for Timeline and History
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_timeline_success(client, mock_db_pool, sample_interaction_data):
    """Test getting client timeline"""
    _, conn = mock_db_pool
    conn.fetch.return_value = [sample_interaction_data]

    response = client.get("/api/crm/interactions/client/1/timeline")

    assert response.status_code == 200
    data = response.json()
    assert "timeline" in data
    assert len(data["timeline"]) == 1


@pytest.mark.asyncio
async def test_get_practice_history_success(client, mock_db_pool, sample_interaction_data):
    """Test getting practice history"""
    _, conn = mock_db_pool
    conn.fetch.return_value = [sample_interaction_data]

    response = client.get("/api/crm/interactions/practice/1/history")

    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert len(data["history"]) == 1


# ============================================================================
# Tests for delete_interaction
# ============================================================================


@pytest.mark.asyncio
async def test_delete_interaction_success(client, mock_db_pool):
    """Test deleting interaction"""
    _, conn = mock_db_pool
    conn.execute.return_value = "UPDATE 1"

    response = client.delete("/api/crm/interactions/1")

    assert response.status_code == 200
    assert response.json()["success"] is True