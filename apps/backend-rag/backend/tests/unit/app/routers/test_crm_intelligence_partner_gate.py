"""Guilt/innocence for the team gate on ``/api/crm/intelligence/*``.

Ledger row L88 (opened 2026-08-19): ``require_team_member`` was a two-entry
denylist (``client``, ``monitoring``), so a JWT carrying the role the platform
itself issues to external partners — ``partner``, which
``routers/auth.py::_redirect_for_role`` sends to ``/portal/partner`` and
``routers/partners.py::_is_partner_role`` defines as "not internal team" — was
granted team-level authority on the six CRM-intelligence routes, none of which
re-checks the role in its body. These tests pin the gate at the HTTP boundary,
on the real router, with a database pool that refuses to be touched: a 403
therefore proves the gate fired BEFORE any client data could be read.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.deps.auth import get_current_user, require_team_member
from backend.app.deps.database import get_database_pool
from backend.app.routers import crm_intelligence

_PARTNER: dict[str, Any] = {
    "email": "partner@example.com",
    "user_id": "partner@example.com",
    "role": "partner",
    "permissions": [],
}
_STAFF: dict[str, Any] = {
    "email": "staff@balizero.com",
    "user_id": "staff@balizero.com",
    "role": "Reception",
    "permissions": [],
}

_DB_TOUCHED = "the gate must refuse before the database is touched"


class _UntouchablePool:
    """Any attribute access is a test failure: the gate must fire first."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        raise AssertionError(f"{_DB_TOUCHED}: pool.{name}")


def _app_for(principal: dict[str, Any]) -> FastAPI:
    app = FastAPI()
    app.include_router(crm_intelligence.router)
    app.dependency_overrides[get_current_user] = lambda: principal
    app.dependency_overrides[get_database_pool] = lambda: _UntouchablePool()
    return app


_ROUTES = [
    ("GET", "/api/crm/intelligence/evidence-dossiers", None),
    ("POST", "/api/crm/intelligence/workspace-ai-snapshots", {}),
    ("GET", "/api/crm/intelligence/workspace-ai-snapshots/review", None),
    ("POST", "/api/crm/intelligence/workspace-ai-snapshots/auto-approve", {}),
    ("POST", "/api/crm/intelligence/workspace-ai-snapshots/1/approve", {}),
    ("POST", "/api/crm/intelligence/1/query", {}),
]


def test_every_intelligence_route_is_behind_the_team_gate() -> None:
    """Wiring: the six routes exist and each one declares require_team_member."""
    paths = sorted(route.path for route in crm_intelligence.router.routes)
    assert paths == [
        "/api/crm/intelligence/evidence-dossiers",
        "/api/crm/intelligence/workspace-ai-snapshots",
        "/api/crm/intelligence/workspace-ai-snapshots/auto-approve",
        "/api/crm/intelligence/workspace-ai-snapshots/review",
        "/api/crm/intelligence/workspace-ai-snapshots/{snapshot_id}/approve",
        "/api/crm/intelligence/{client_id}/query",
    ], paths
    unguarded = [
        route.path
        for route in crm_intelligence.router.routes
        if not any(dep.call is require_team_member for dep in route.dependant.dependencies)
    ]
    assert unguarded == [], unguarded


@pytest.mark.parametrize(("method", "path", "body"), _ROUTES)
def test_partner_gets_403_before_any_client_data_is_read(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Guilt: at the baseline this returned anything but 403."""
    client = TestClient(_app_for(_PARTNER))
    response = client.request(method, path, json=body)
    assert response.status_code == 403, response.text
    assert "team members" in response.json()["detail"]


def test_staff_passes_the_gate_and_reaches_the_data_layer() -> None:
    """Innocence: a real free-text staff role is let through — the request
    dies on the untouchable pool, i.e. AFTER the gate."""
    client = TestClient(_app_for(_STAFF))
    with pytest.raises(AssertionError, match=_DB_TOUCHED):
        client.get("/api/crm/intelligence/evidence-dossiers")
