"""Tests for team.py::get_team_members — the LIVE, registered GET /api/team/members.

2026-08-19 audit context: this endpoint applied ZERO role filtering. A fix for
service-account exclusion (#4353) had instead been applied to
routers/team_members.py, a disabled duplicate that is never registered and
serves no traffic. These tests exercise the real, live endpoint end-to-end
(through a fake connection that actually honors the WHERE clause) across all
three visibility branches, so a regression here fails loudly instead of
passing silently on the dead twin.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from backend.app.routers.team import get_team_members

# A fixed roster covering all three shapes that must be told apart: a real
# person (free-text job title, not an enum), a client, and the "monitoring"
# service account (the login-healthcheck probe).
ALL_MEMBERS: list[dict[str, Any]] = [
    {
        "id": "1",
        "email": "surya@balizero.com",
        "name": "Surya",
        "full_name": "Surya",
        "role": "Tax Care",
        "department": "tax",
        "active": True,
        "avatar": None,
    },
    {
        "id": "2",
        "email": "client@example.com",
        "name": "Client",
        "full_name": "Client Example",
        "role": "client",
        "department": "tax",
        "active": True,
        "avatar": None,
    },
    {
        "id": "3",
        "email": "probe@balizero.com",
        "name": "Probe",
        "full_name": "Login Healthcheck Probe",
        "role": "monitoring",
        "department": "tax",
        "active": True,
        "avatar": None,
    },
]


class FakeConn:
    """A minimal asyncpg-connection stand-in that actually honors the WHERE
    clauses the router issues, instead of just recording call args.

    This is deliberate: a test that only asserts "the query STRING contains
    role <> ALL(" would pass even if the SQL were wired to the wrong bind
    parameter. Simulating the filter against a fixed roster and asserting on
    the RESPONSE is what makes this a real guilt+innocence test rather than a
    string-match that could pass vacuously.
    """

    def __init__(self, viewer: dict[str, Any] | None, visibility_rules: list[dict[str, Any]]):
        self._viewer = viewer
        self._visibility_rules = visibility_rules
        self.member_query_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, _query: str, *_params: Any) -> dict[str, Any] | None:
        return self._viewer

    async def fetch(self, query: str, *params: Any) -> list[dict[str, Any]]:
        if "team_member_visibility_rules" in query:
            return self._visibility_rules

        self.member_query_calls.append((query, params))
        rows = list(ALL_MEMBERS)

        if "role <> ALL(" in query:
            excluded = {r.lower() for r in params[-1]}
            rows = [r for r in rows if r["role"].lower() not in excluded]

        if "email = ANY(" in query:
            allowed_emails = set(params[0])
            rows = [r for r in rows if r["email"] in allowed_emails]
        elif "department = $1" in query:
            dept = params[0]
            rows = [r for r in rows if r["department"] == dept]

        return rows


def _pool_for(conn: FakeConn) -> Any:
    class _Pool:
        def acquire(self):
            @asynccontextmanager
            async def _acquire():
                yield conn

            return _acquire()

    return _Pool()


@pytest.mark.asyncio
async def test_board_branch_excludes_service_accounts_and_clients() -> None:
    """Guilt (service account) + guilt (client) + innocence (real role), board branch."""
    conn = FakeConn(viewer={"department": "board", "role": "founder"}, visibility_rules=[])
    result = await get_team_members(
        current_user={"email": "zero@balizero.com"}, pool=_pool_for(conn)
    )

    emails = {m.email for m in result}
    assert "probe@balizero.com" not in emails, "service account (monitoring) must be excluded"
    assert "client@example.com" not in emails, "client must be excluded"
    assert "surya@balizero.com" in emails, "a real team member must still appear"
    assert conn.member_query_calls, "the members query must have run"
    assert "role <> ALL(" in conn.member_query_calls[0][0]


@pytest.mark.asyncio
async def test_department_default_branch_excludes_service_accounts_and_clients() -> None:
    """Guilt + innocence, default (same-department) branch."""
    conn = FakeConn(
        viewer={"department": "tax", "role": "Tax Care"},
        visibility_rules=[],
    )
    result = await get_team_members(
        current_user={"email": "surya@balizero.com"}, pool=_pool_for(conn)
    )

    emails = {m.email for m in result}
    assert "probe@balizero.com" not in emails
    assert "client@example.com" not in emails
    assert "surya@balizero.com" in emails


@pytest.mark.asyncio
async def test_visibility_rules_branch_excludes_service_accounts_and_clients() -> None:
    """Guilt + innocence, user-specific visibility-rules branch.

    Even if an operator's visibility rule names the probe or a client
    explicitly, the roster must not surface them.
    """
    conn = FakeConn(
        viewer={"department": "tax", "role": "Tax Care"},
        visibility_rules=[
            {"visible_member_email": "surya@balizero.com"},
            {"visible_member_email": "client@example.com"},
            {"visible_member_email": "probe@balizero.com"},
        ],
    )
    result = await get_team_members(
        current_user={"email": "zero@balizero.com"}, pool=_pool_for(conn)
    )

    emails = {m.email for m in result}
    assert "probe@balizero.com" not in emails
    assert "client@example.com" not in emails
    assert "surya@balizero.com" in emails


@pytest.mark.asyncio
async def test_probe_cannot_be_the_innocence_case() -> None:
    """Sanity check on the fixture itself: the fake DB actually distinguishes
    the three role shapes rather than filtering everything or nothing."""
    assert {m["role"] for m in ALL_MEMBERS} == {"Tax Care", "client", "monitoring"}
