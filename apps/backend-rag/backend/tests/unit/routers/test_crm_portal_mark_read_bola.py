"""Tests for the `mark_client_message_read` team-side BOLA fix (2026-08-23, round 2).

Ground-verified this session: `crm_portal_integration.py::mark_client_message_read`
(`POST /api/crm/portal/clients/{client_id}/messages/{message_id}/read`) performs
`UPDATE portal_messages SET read_at = NOW() ...` — a WRITE. The round-1 pass added
`verify_client_access(client_id, current_user, conn, allow_assigned=True)` but left
`write` at its default `False`. In that mode `verify_client_access` (crm_utils.py
lines 234-238) grants access to **every authenticated team member**, per its own
docstring: "All authenticated team members can view any client ... Unassigned
clients must be accessible so team members can self-assign." So the round-1 diff
gated nothing — any staff member could still mark any client's message read.

The round-2 fix passes `write=True`:
`verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)`.
With `write=True` (crm_utils.py lines 212-232), a non-admin caller is granted
access only if their email matches the client's `assigned_to` OR `created_by`;
anyone else gets `HTTPException(403)`. Admins (crm_utils.py lines 208-210) always
pass, before the write check ever runs.

The handler's bare `except Exception` at the bottom of the try block would
otherwise convert that HTTPException(403) — or the HTTPException(404) for a
missing/soft-deleted client — into an opaque 500. The `except HTTPException:
raise` added just above it is what lets the real status code reach the caller;
several tests below pin that explicitly (403/404, never 500).

IMPORTANT — nothing in this file mocks `verify_client_access` itself (that would
assert nothing about the fix: patching the guard away runs no guard at all). Every
test here drives the REAL `verify_client_access`, mocking only the asyncpg
connection it reads from (`mock_db_pool._mock_conn.fetchrow`, the shared fixture
in `conftest.py`, same harness as `test_crm_clients_coverage.py::test_delete_client_*`).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.routers.crm_portal_integration import mark_client_message_read

ADMIN_EMAIL = "asya@balizero.com"  # backend.app.utils.crm_utils.CRM_EXTRA_ADMIN_EMAILS


def _client_row(*, assigned_to: str | None, created_by: str | None = None) -> dict[str, object]:
    return {
        "id": 1,
        "assigned_to": assigned_to,
        "created_by": created_by if created_by is not None else assigned_to,
    }


@pytest.mark.asyncio
async def test_assigned_team_member_marks_own_clients_message_succeeds(mock_db_pool) -> None:
    """Team member whose email == the client's assigned_to → 200, UPDATE executed."""
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")
    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    current_user = {"email": "alice@balizero.com", "role": "team"}

    result = await mark_client_message_read(
        client_id=1,
        message_id=10,
        current_user=current_user,
        db_pool=mock_db_pool,
    )

    assert result == {"success": True, "message": "Message marked as read"}
    mock_db_pool._mock_conn.execute.assert_awaited_once()
    args, _kwargs = mock_db_pool._mock_conn.execute.await_args
    assert args[1:] == (10, 1)  # (message_id, client_id) bind params


@pytest.mark.asyncio
async def test_created_by_team_member_marks_message_succeeds(mock_db_pool) -> None:
    """Non-assigned team member who IS the client's created_by → 200.

    write=True's owner check (crm_utils.py:212-219) accepts assigned_to OR
    created_by — this pins the created_by half of that OR, which the assigned_to
    test above cannot exercise on its own.
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="carol@balizero.com"
    )
    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    current_user = {"email": "carol@balizero.com", "role": "team"}

    result = await mark_client_message_read(
        client_id=1,
        message_id=11,
        current_user=current_user,
        db_pool=mock_db_pool,
    )

    assert result == {"success": True, "message": "Message marked as read"}
    mock_db_pool._mock_conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_marks_any_clients_message_succeeds(mock_db_pool) -> None:
    """Admin keeps full access regardless of assignment (CLAUDE.md §13)."""
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="bob@balizero.com")
    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    current_user = {"email": ADMIN_EMAIL, "role": "team"}

    result = await mark_client_message_read(
        client_id=1,
        message_id=99,
        current_user=current_user,
        db_pool=mock_db_pool,
    )

    assert result == {"success": True, "message": "Message marked as read"}
    mock_db_pool._mock_conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_assigned_non_admin_team_member_denied_403_not_500(mock_db_pool) -> None:
    """GUILT — the case the round-1 fix silently failed to gate.

    A non-admin team member who is neither `assigned_to` nor `created_by` for
    this client must be denied with 403 (not 500), and the UPDATE must never
    run. This drives the REAL `verify_client_access` write=True branch
    (crm_utils.py:212-232) — nothing here mocks the guard. Before the round-2
    fix (i.e. with the round-1 call, which omits `write=True`), this exact
    setup returns 200 instead of raising: `write=False` grants access to any
    authenticated team member regardless of assignment (crm_utils.py:234-238).
    So this test fails without `write=True` — that is what makes it a real
    guard test rather than a tautology.
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="alice@balizero.com"
    )

    # not admin, not assigned, not creator
    current_user = {"email": "bob@balizero.com", "role": "team"}

    with pytest.raises(HTTPException) as exc_info:
        await mark_client_message_read(
            client_id=1,
            message_id=10,
            current_user=current_user,
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.status_code != 500
    mock_db_pool._mock_conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_nonexistent_client_returns_404_not_500(mock_db_pool) -> None:
    """Client that does not exist or is soft-deleted → 404, not 500; UPDATE never runs."""
    # no row => 404 inside verify_client_access
    mock_db_pool._mock_conn.fetchrow.return_value = None

    current_user = {"email": "alice@balizero.com", "role": "team"}

    with pytest.raises(HTTPException) as exc_info:
        await mark_client_message_read(
            client_id=999999,
            message_id=10,
            current_user=current_user,
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.status_code != 500
    mock_db_pool._mock_conn.execute.assert_not_awaited()
