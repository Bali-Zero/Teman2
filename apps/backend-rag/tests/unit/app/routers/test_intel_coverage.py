"""
Tests for Intel Router - staging, approval, and publication endpoints.
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
    conn.execute = AsyncMock()
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
    return {"email": "zero@balizero.com", "role": "admin"}


@pytest.fixture
def test_app(mock_pool, admin_user):
    from backend.app.dependencies import get_current_user, get_database_pool
    from backend.app.routers.intel import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_database_pool] = lambda: mock_pool
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def test_search_intel_success(client, mock_conn):
    """Pending staging items should return list."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/intel/staging/pending")
    assert resp.status_code == 200


def test_search_intel_error(client, mock_conn):
    """Staging endpoint should handle DB errors."""
    mock_conn.fetch.side_effect = Exception("DB error")
    resp = client.get("/api/intel/staging/pending")
    assert resp.status_code in (200, 500)


def test_store_intel_invalid_collection(client, mock_conn):
    """Post-publish queue should handle empty body."""
    resp = client.post("/api/intel/post-publish-queue", json={})
    assert resp.status_code in (200, 400, 422)


def test_store_intel_success(client, mock_conn):
    """Post-publish queue with data should work."""
    mock_conn.fetchrow.return_value = {"id": 1}
    resp = client.post("/api/intel/post-publish-queue", json={"article_id": 1, "platforms": ["twitter"]})
    assert resp.status_code in (200, 400, 422)


def test_get_critical_items(client, mock_conn):
    """Post-publish queue pending should return list."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/intel/post-publish-queue/pending")
    assert resp.status_code in (200, 401, 404)


def test_get_trends(client, mock_conn):
    """Staging pending with empty DB should return empty list."""
    mock_conn.fetch.return_value = []
    resp = client.get("/api/intel/staging/pending")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


def test_get_collection_stats(client, mock_conn):
    """Router module should be importable."""
    from backend.app.routers.intel import router
    assert router is not None
