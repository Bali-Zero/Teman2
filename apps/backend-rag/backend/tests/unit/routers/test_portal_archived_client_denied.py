"""
Tests for get_current_client — archived client cannot use the portal (M1, 2026-08-23).

SCAR CONTEXT: archiving a client in kita (crm_clients.py:1812 delete_client) sets
`clients.status='inactive', deleted_at=NOW()` but does NOT touch `team_members` at
all — the portal login row survives archiving intact. Before this fix, the normal
client path in `get_current_client` never queried `clients`: it read `team_members`
(id/role/active), checked `portal_access` + `linked_client_id`, and returned
`linked_client_id` as `client_id` — so an archived client's portal session kept
working indefinitely.

Owner ruling (Legge 5, 2026-08-23): fail-closed. Archiving in kita revokes the
portal login. `get_current_client` is the single choke point every client-facing
portal router depends on, so denying here closes the whole client surface at once.

These tests call `get_current_client` directly (not via TestClient) with a mocked
`Request`, matching the pattern in `backend/tests/unit/app/test_dependencies.py`.
The superuser impersonation path (lines ~145-213) is deliberately untouched by
this change and is not exercised here.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from backend.app.routers.portal import get_current_client

CLIENT_USER = {
    "id": "client-uuid-1",
    "email": "client@example.com",
    "role": "client",
}

TEAM_MEMBER_ROW = {
    "id": "client-uuid-1",
    "email": "client@example.com",
    "full_name": "Test Client",
    "linked_client_id": 42,
    "portal_access": True,
}


def _mock_request(user: dict) -> MagicMock:
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = user
    request.query_params = {}
    return request


class TestArchivedClientDenied:
    """GET-equivalent: exercises get_current_client's normal client path."""

    async def test_active_client_row_resolves_normally(self, mock_db_pool):
        """INNOCENCE: a live client (clients.deleted_at IS NULL) still logs in
        and gets back the expected client_id — the new gate must not turn into
        a blanket denial."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.side_effect = [
            TEAM_MEMBER_ROW,
            {"id": 42},  # clients row present -> not archived
        ]

        result = await get_current_client(_mock_request(CLIENT_USER), db_pool=mock_db_pool)

        assert result["client_id"] == 42
        assert result["impersonating"] is False
        assert conn.fetchrow.await_count == 2

    async def test_archived_client_row_denied_403(self, mock_db_pool):
        """GUILT: clients.deleted_at set on the linked client -> 403 with the
        contact-Bali-Zero wording, and no disclosure of the word 'archived'."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.side_effect = [
            TEAM_MEMBER_ROW,
            None,  # clients row filtered out by `deleted_at IS NULL`
        ]

        with pytest.raises(HTTPException) as exc_info:
            await get_current_client(_mock_request(CLIENT_USER), db_pool=mock_db_pool)

        assert exc_info.value.status_code == 403
        assert "Bali Zero" in exc_info.value.detail
        assert "archived" not in exc_info.value.detail.lower()

        # Second fetchrow call must be the clients lookup, scoped by the
        # linked_client_id and filtered by deleted_at IS NULL.
        assert conn.fetchrow.await_count == 2
        second_call = conn.fetchrow.await_args_list[1]
        assert "FROM clients" in second_call.args[0]
        assert "deleted_at IS NULL" in second_call.args[0]
        assert second_call.args[1] == 42

    async def test_inactive_team_member_still_403_no_deleted_at_filter_added(
        self, mock_db_pool
    ):
        """REGRESSION GUARD: the pre-existing team_members.active=false path is
        unaffected by this change, AND the team_members query text must NOT
        gain a `deleted_at` filter — that column does not exist on
        `team_members` and would 500 every client login."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = None  # team_members query returns nothing

        with pytest.raises(HTTPException) as exc_info:
            await get_current_client(_mock_request(CLIENT_USER), db_pool=mock_db_pool)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Client account not found or inactive"

        # Only the team_members query ran (the clients query is unreachable
        # once `row` is falsy) — and it must never reference deleted_at.
        conn.fetchrow.assert_awaited_once()
        team_members_sql = conn.fetchrow.await_args.args[0]
        assert "FROM team_members" in team_members_sql
        assert "deleted_at" not in team_members_sql
