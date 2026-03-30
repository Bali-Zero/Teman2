"""
Tests for CRM Enhanced Alerts Router.

Security test: verifies that the /expiry-alerts/summary endpoint
requires authentication (current_user dependency).
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool

# ============================================
# SECURITY TEST: auth on summary endpoint
# ============================================


def test_get_expiry_alerts_summary_has_current_user_param() -> None:
    """
    The /expiry-alerts/summary endpoint MUST require authentication.

    This test inspects the function signature of get_expiry_alerts_summary
    and asserts that it has a 'current_user' parameter with a Depends()
    annotation pointing to get_current_user.

    Without this, any unauthenticated caller can query aggregate alert
    counts (expired / red / yellow / green), leaking CRM data.
    """
    from backend.app.routers.crm_enhanced_alerts import get_expiry_alerts_summary

    sig = inspect.signature(get_expiry_alerts_summary)
    assert "current_user" in sig.parameters, (
        "get_expiry_alerts_summary is missing 'current_user' parameter — "
        "the endpoint is unauthenticated and leaks CRM data."
    )

    param = sig.parameters["current_user"]
    # The default should be a Depends() instance wrapping get_current_user
    assert isinstance(param.default, type(Depends(get_current_user))), (
        "'current_user' parameter must use Depends() as its default."
    )


def test_get_expiry_alerts_summary_current_user_depends_get_current_user() -> None:
    """
    Verifies the Depends() in current_user is bound to get_current_user
    (not some other callable).
    """
    from backend.app.routers.crm_enhanced_alerts import get_expiry_alerts_summary

    sig = inspect.signature(get_expiry_alerts_summary)
    param = sig.parameters["current_user"]
    dep = param.default
    assert dep.dependency is get_current_user, (
        f"current_user must Depend on get_current_user, got {dep.dependency!r}"
    )


# ============================================
# INTEGRATION: endpoint returns 401 when not authenticated
# ============================================


@pytest.fixture()
def mock_db_pool():
    """Minimal async pool mock."""
    from contextlib import asynccontextmanager

    pool = AsyncMock()
    conn = AsyncMock()

    row = MagicMock()
    row.__iter__ = MagicMock(return_value=iter([0, 0, 0, 0]))
    # fetchrow returns a record-like object
    conn.fetchrow = AsyncMock(return_value={"expired": 0, "red": 0, "yellow": 0, "green": 0})
    conn.fetch = AsyncMock(return_value=[])

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


@pytest.fixture()
def unauthenticated_app(mock_db_pool):
    """App WITHOUT current_user override — simulates unauthenticated caller."""
    from fastapi import FastAPI

    from backend.app.routers import crm_enhanced_alerts

    app = FastAPI()
    app.include_router(crm_enhanced_alerts.router)

    pool, _ = mock_db_pool
    app.dependency_overrides[get_database_pool] = lambda: pool
    # get_current_user is NOT overridden → FastAPI will call the real dep
    # which requires a valid JWT and returns 401/403 for anonymous requests.
    return app


@pytest.fixture()
def authenticated_app(mock_db_pool):
    """App WITH current_user override — simulates an authenticated admin."""
    from fastapi import FastAPI

    from backend.app.routers import crm_enhanced_alerts

    app = FastAPI()
    app.include_router(crm_enhanced_alerts.router)

    pool, _ = mock_db_pool

    def override_pool():
        return pool

    def override_user():
        return {"email": "admin@balizero.com", "role": "admin"}

    app.dependency_overrides[get_database_pool] = override_pool
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_summary_endpoint_reachable_when_authenticated(authenticated_app) -> None:
    """
    With a valid (mocked) user the endpoint should return 200 and
    the expected JSON shape.
    """
    client = TestClient(authenticated_app, raise_server_exceptions=True)
    response = client.get("/api/crm/expiry-alerts/summary")
    assert response.status_code == 200
    data = response.json()
    assert "counts" in data
    assert "urgent_alerts" in data
