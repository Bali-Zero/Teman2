"""Regression: get_current_portal_client must resolve clients from team_members,
NOT user_profiles.

Live incident 2026-07-10: real clients (role='client') hitting /api/portal/taxes
and /api/portal/visa got HTTP 500 because the resolver did
`JOIN user_profiles up ON up.linked_client_id = c.id WHERE up.role = 'client'`
but user_profiles has NEITHER `role` NOR `linked_client_id` columns
(asyncpg UndefinedColumnError). Client accounts actually live in team_members
(role='client', linked_client_id -> clients.id). Superuser impersonation
(?as_client=<id>) masked the bug because it never hit this branch.

These tests pin the team_members lookup, the client_id mapping
(linked_client_id -> returned id), and that failures are 403 (auth), never 500.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException


def _make_request(user: dict | None, query_params: dict | None = None):
    """Mock Request whose .state.user is `user`."""
    request = MagicMock()
    request.state.user = user
    request.query_params = query_params or {}
    return request


@pytest.mark.asyncio
async def test_client_resolved_from_team_members(mock_db_pool):
    """Happy path: a real client (role='client') is resolved via team_members and
    the returned id is the linked_client_id (the clients.id), not the account id."""
    from backend.app.deps.auth import get_current_portal_client

    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {
        "id": "acct-uuid-abc",
        "email": "e2e-portal-client@test.balizero.com",
        "full_name": "E2E Portal Client",
        "linked_client_id": 12087,
        "portal_access": True,
    }
    request = _make_request(
        {"user_id": "acct-uuid-abc", "email": "e2e-portal-client@test.balizero.com", "role": "client"}
    )

    result = await get_current_portal_client(request, db_pool=pool)

    assert result["id"] == 12087, "must return linked_client_id (clients.id), not the account id"
    assert result["email"] == "e2e-portal-client@test.balizero.com"
    assert result["impersonating"] is False

    # GUILT: the query must target team_members, never user_profiles.
    sql = conn.fetchrow.await_args.args[0]
    assert "team_members" in sql
    assert "user_profiles" not in sql
    assert "role = 'client'" in sql


@pytest.mark.asyncio
async def test_no_row_is_403_not_500(mock_db_pool):
    """No matching team_members row -> 403 (auth failure), NEVER a 500."""
    from backend.app.deps.auth import get_current_portal_client

    pool, conn = mock_db_pool
    conn.fetchrow.return_value = None
    request = _make_request({"user_id": "ghost", "email": "ghost@test.balizero.com", "role": "client"})

    with pytest.raises(HTTPException) as exc:
        await get_current_portal_client(request, db_pool=pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_portal_access_disabled_is_403(mock_db_pool):
    from backend.app.deps.auth import get_current_portal_client

    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {
        "id": "acct", "email": "c@test.balizero.com", "full_name": "C",
        "linked_client_id": 999, "portal_access": False,
    }
    request = _make_request({"user_id": "acct", "email": "c@test.balizero.com", "role": "client"})

    with pytest.raises(HTTPException) as exc:
        await get_current_portal_client(request, db_pool=pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_unlinked_account_is_403(mock_db_pool):
    from backend.app.deps.auth import get_current_portal_client

    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {
        "id": "acct", "email": "c@test.balizero.com", "full_name": "C",
        "linked_client_id": None, "portal_access": True,
    }
    request = _make_request({"user_id": "acct", "email": "c@test.balizero.com", "role": "client"})

    with pytest.raises(HTTPException) as exc:
        await get_current_portal_client(request, db_pool=pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_non_client_role_is_403(mock_db_pool):
    """A team member without role='client' must not reach the client data path."""
    from backend.app.deps.auth import get_current_portal_client

    pool, conn = mock_db_pool
    request = _make_request({"user_id": "staff", "email": "staff@balizero.com", "role": "staff"})

    with pytest.raises(HTTPException) as exc:
        await get_current_portal_client(request, db_pool=pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_user_is_401(mock_db_pool):
    from backend.app.deps.auth import get_current_portal_client

    pool, _ = mock_db_pool
    request = _make_request(None)

    with pytest.raises(HTTPException) as exc:
        await get_current_portal_client(request, db_pool=pool)
    assert exc.value.status_code == 401
