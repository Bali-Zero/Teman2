"""Guilt/innocence for the team gate on ``GET /api/team/members``.

Loop loop-20260906-partner-gate-followups, task T3: at baseline a partner JWT
received 200 with an empty list here (the partner's ``team_members`` row has no
staff department, so the department-default branch matched nothing). No
partner-portal page consumes this endpoint — it feeds the staff workspace's
``useTeamMembers`` — so the correct follow-up is the team gate, not a partner
view: partner/client/service-account JWTs now get 403 BEFORE the database is
touched, while a staff role still gets 200 with a non-empty roster.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers import team

_NON_TEAM_PRINCIPALS: list[dict[str, Any]] = [
    {"email": "partner@example.com", "user_id": "partner@example.com", "role": "partner"},
    {"email": "client@example.com", "user_id": "client@example.com", "role": "client"},
    {"email": "probe@balizero.com", "user_id": "probe@balizero.com", "role": "monitoring"},
]

_STAFF: dict[str, Any] = {
    "email": "surya@balizero.com",
    "user_id": "surya@balizero.com",
    "role": "Tax Care",
}

_STAFF_ROW: dict[str, Any] = {
    "id": "1",
    "email": "surya@balizero.com",
    "name": "Surya",
    "full_name": "Surya",
    "role": "Tax Care",
    "department": "tax",
    "active": True,
    "avatar": None,
}

_DB_TOUCHED = "the gate must refuse before the database is touched"


class _UntouchablePool:
    """Any attribute access is a test failure: the gate must fire first."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        raise AssertionError(f"{_DB_TOUCHED}: pool.{name}")


class _StaffConn:
    """Minimal asyncpg stand-in returning a one-person roster for staff."""

    async def fetchrow(self, _query: str, *_params: Any) -> dict[str, Any] | None:
        return {"department": "tax", "role": "Tax Care"}

    async def fetch(self, query: str, *_params: Any) -> list[dict[str, Any]]:
        if "team_member_visibility_rules" in query:
            return []
        return [_STAFF_ROW]


class _StaffPool:
    def acquire(self) -> Any:
        @asynccontextmanager
        async def _acquire() -> Any:
            yield _StaffConn()

        return _acquire()


def _app_for(principal: dict[str, Any], pool: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(team.router)
    app.dependency_overrides[get_current_user] = lambda: principal
    app.dependency_overrides[get_database_pool] = lambda: pool
    return app


@pytest.mark.parametrize("principal", _NON_TEAM_PRINCIPALS, ids=lambda p: p["role"])
def test_non_team_jwt_gets_403_before_the_database_is_touched(
    principal: dict[str, Any],
) -> None:
    """Guilt: at the baseline a partner JWT passed with 200 and an empty list."""
    client = TestClient(_app_for(principal, _UntouchablePool()))
    response = client.get("/api/team/members")
    assert response.status_code == 403, response.text
    assert "team members" in response.json()["detail"]


def test_staff_jwt_gets_200_with_a_non_empty_roster() -> None:
    """Innocence: a real free-text staff role passes the gate and is served."""
    client = TestClient(_app_for(_STAFF, _StaffPool()))
    response = client.get("/api/team/members")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [m["email"] for m in body] == ["surya@balizero.com"]
