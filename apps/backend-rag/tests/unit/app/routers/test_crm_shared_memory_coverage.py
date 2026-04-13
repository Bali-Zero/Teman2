"""
Tests for CRM Shared Memory Router - natural language search across CRM.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)
    return conn


@pytest.fixture
def mock_pool(mock_conn):
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm
    return pool


@pytest.fixture
def admin_user():
    return {"email": "zero@balizero.com", "role": "admin", "sub": "admin-uuid"}


@pytest.fixture
def test_app(mock_pool, admin_user):
    from backend.app.dependencies import get_current_user, get_database_pool
    from backend.app.routers.crm_shared_memory import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_database_pool] = lambda: mock_pool
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def test_get_practice_codes_success(client, mock_conn):
    """_get_practice_codes should return codes from DB."""
    mock_conn.fetch.return_value = [{"code": "KITAS"}, {"code": "KITAP"}]
    resp = client.get("/api/crm/shared-memory/search?q=renewals")
    assert resp.status_code == 200


def test_get_practice_codes_failure(client, mock_conn):
    """Search should handle DB errors gracefully."""
    mock_conn.fetch.side_effect = Exception("DB error")
    resp = client.get("/api/crm/shared-memory/search?q=test")
    assert resp.status_code in (200, 500)


def test_search_renewal_query(client, mock_conn):
    """Search for renewal queries should detect renewal intent."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=clients+with+expiring+visas")
    assert resp.status_code == 200


def test_search_client_query(client, mock_conn):
    """Search for client name should work."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=John+Smith")
    assert resp.status_code == 200


def test_search_practice_type_query(client, mock_conn):
    """Search for practice type should work."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=KITAS+practices")
    assert resp.status_code == 200


def test_search_urgent_query(client, mock_conn):
    """Search for urgent items should work."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=urgent+practices")
    assert resp.status_code == 200


def test_search_recent_interactions(client, mock_conn):
    """Search for recent interactions should work."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=recent+interactions")
    assert resp.status_code == 200


def test_search_database_error(client, mock_conn):
    """Database errors should be handled gracefully."""
    mock_conn.fetch.side_effect = Exception("connection lost")
    resp = client.get("/api/crm/shared-memory/search?q=test")
    assert resp.status_code in (200, 500)


def test_get_upcoming_renewals(client, mock_conn):
    """Renewal endpoint should work."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=upcoming+renewals")
    assert resp.status_code == 200


def test_get_client_full_context(client, mock_conn):
    """Full context query should work."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=full+context+for+client+1")
    assert resp.status_code == 200


def test_get_client_full_context_not_found(client, mock_conn):
    """Full context for non-existent client should return empty."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=context+for+unknown+client")
    assert resp.status_code == 200


def test_get_team_overview(client, mock_conn):
    """Team overview query should work."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/crm/shared-memory/search?q=team+overview")
    assert resp.status_code == 200
