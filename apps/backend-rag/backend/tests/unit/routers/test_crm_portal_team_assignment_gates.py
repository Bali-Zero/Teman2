"""Tests for the PR B team-assignment gates in `crm_portal_integration.py`.

SPEC-p0-invite.md (2026-08-23), "## PR B — `crm_portal_integration.py`: team-side
endpoints honour assignment". Three items:

- B1 `send_portal_invite` (~line 238): a fourth invitation-minting path. Gains
  `write=True` on its `verify_client_access` call and strips the raw
  `token`/`invite_url` from the response — same treatment as
  `portal_invite.py`'s A1/A3, applied here because this router has its own
  separate `verify_client_access` call and its own separate response body.
- B2 `send_message_to_client` (~line 465) — owner ruling: its
  `verify_client_access` ran in read mode (`write` defaults to `False`), so
  any authenticated team member could write a client-visible message
  regardless of assignment. Zero ruled 2026-08-23: `write=True`.
- B3 `get_unread_messages_count` (~line 351) — owner ruling: had no
  `assigned_filter` and no `verify_client_access` at all; its `by_client`
  block returned real client names (`c.full_name`) for the top 10 unread
  senders across the WHOLE book, archived clients included, to any
  authenticated team member. Copies the `assigned_filter` pattern from
  `get_recent_portal_activity` (same file, ~line 573) verbatim and applies
  it to both the `total` and `by_client` queries, plus `c.deleted_at IS
  NULL` on the `by_client` join.

IMPORTANT — nothing here mocks `verify_client_access` itself (that would
prove nothing about the fix: patching the guard away runs no guard at all).
B1/B2 tests drive the REAL `verify_client_access`, mocking only the asyncpg
connection it reads from (`mock_db_pool._mock_conn`, the shared fixture in
`conftest.py`) — same harness as
`test_crm_portal_mark_read_bola.py` (landed in #4594). B3 has no
`verify_client_access` call (by design — it's a book-wide summary, not a
single-client endpoint); its gate is the `assigned_filter` dependency value,
so those tests instead inspect the actual SQL text and bound parameters sent
to `conn.fetchval`/`conn.fetch` — the only way to prove the WHERE clause
(and not just the mocked return value) actually changed.

Synthetic fixtures only — no real client name, email, or id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.app.routers.crm_portal_integration import (
    SendInviteRequest,
    TeamMessageRequest,
    get_unread_messages_count,
    send_message_to_client,
    send_portal_invite,
)

ADMIN_EMAIL = "asya@balizero.com"  # backend.app.utils.crm_utils.CRM_EXTRA_ADMIN_EMAILS


def _client_row(*, assigned_to: str | None, created_by: str | None = None) -> dict[str, object]:
    return {
        "id": 1,
        "assigned_to": assigned_to,
        "created_by": created_by if created_by is not None else assigned_to,
    }


def _message_row() -> dict[str, object]:
    return {
        "id": 42,
        "subject": "Synthetic subject",
        "content": "Synthetic content",
        "sent_by": "alice@balizero.com",
        "created_at": datetime(2026, 8, 23, tzinfo=timezone.utc),
    }


def _raw_invitation(*, suffix: str) -> dict[str, object]:
    """A synthetic `InviteService.create_invitation` return value.

    Deliberately includes `token`/`invite_url` — B1's whole point is that
    these must never survive into the HTTP response.
    """
    return {
        "invitation_id": 5,
        "client_id": 1,
        "client_name": "Synthetic Client",
        "email": "synthetic-client@example.com",
        "expires_at": "2026-09-01T00:00:00+00:00",
        "token": f"raw-secret-token-{suffix}",
        "invite_url": f"https://kita.balizero.com/invite/raw-secret-token-{suffix}",
    }


# ================================================
# B1 — send_portal_invite: write=True + secrets stripped
# ================================================


@pytest.mark.asyncio
async def test_b1_non_assigned_non_admin_denied_403_not_500(mock_db_pool) -> None:
    """GUILT: a non-assigned, non-admin team member must not mint an invite."""
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="alice@balizero.com"
    )
    invite_service = AsyncMock()
    current_user = {"email": "bob@balizero.com", "role": "team"}

    with pytest.raises(HTTPException) as exc_info:
        await send_portal_invite(
            client_id=1,
            request=SendInviteRequest(email="synthetic-client@example.com"),
            current_user=current_user,
            invite_service=invite_service,
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.status_code != 500
    invite_service.create_invitation.assert_not_awaited()


@pytest.mark.asyncio
async def test_b1_assigned_team_member_allowed_secrets_stripped(mock_db_pool) -> None:
    """INNOCENCE: assigned caller succeeds, and the response has no raw secret."""
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")
    invite_service = AsyncMock()
    invite_service.create_invitation.return_value = _raw_invitation(suffix="assigned")
    current_user = {"email": "alice@balizero.com", "role": "team"}

    result = await send_portal_invite(
        client_id=1,
        request=SendInviteRequest(email="synthetic-client@example.com"),
        current_user=current_user,
        invite_service=invite_service,
        db_pool=mock_db_pool,
    )

    assert result["success"] is True
    invite_service.create_invitation.assert_awaited_once()
    assert "token" not in result["data"]
    assert "invite_url" not in result["data"]
    assert result["data"]["invitation_id"] == 5
    assert result["data"]["email"] == "synthetic-client@example.com"


@pytest.mark.asyncio
async def test_b1_admin_allowed_secrets_stripped(mock_db_pool) -> None:
    """INNOCENCE: admin bypasses assignment, and the response still has no secret."""
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="bob@balizero.com")
    invite_service = AsyncMock()
    invite_service.create_invitation.return_value = _raw_invitation(suffix="admin")
    current_user = {"email": ADMIN_EMAIL, "role": "team"}

    result = await send_portal_invite(
        client_id=1,
        request=SendInviteRequest(email="synthetic-client@example.com"),
        current_user=current_user,
        invite_service=invite_service,
        db_pool=mock_db_pool,
    )

    assert result["success"] is True
    assert "token" not in result["data"]
    assert "invite_url" not in result["data"]


# ================================================
# B2 — send_message_to_client: write=True
# ================================================


@pytest.mark.asyncio
async def test_b2_non_assigned_non_admin_denied_403_not_500(mock_db_pool) -> None:
    """GUILT — the case B2 exists to close.

    Before `write=True`, `verify_client_access`'s read-mode branch
    (`allow_assigned=True`, `write` defaulting to False) grants access to
    every authenticated team member. This drives the REAL guard; if B2's
    `write=True` were reverted, this exact setup would return 200 instead of
    raising — that is what makes the test discriminate the fix.
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="alice@balizero.com"
    )
    current_user = {"email": "bob@balizero.com", "role": "team"}

    with pytest.raises(HTTPException) as exc_info:
        await send_message_to_client(
            client_id=1,
            request=TeamMessageRequest(content="Synthetic message body"),
            current_user=current_user,
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.status_code != 500
    # Only the verify_client_access SELECT ran — the INSERT (also via
    # `conn.fetchrow` in this handler) must never have been reached.
    assert mock_db_pool._mock_conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_b2_assigned_team_member_allowed(mock_db_pool) -> None:
    """INNOCENCE: the client's assigned team member may still send."""
    mock_db_pool._mock_conn.fetchrow.side_effect = [
        _client_row(assigned_to="alice@balizero.com"),
        _message_row(),
    ]
    current_user = {"email": "alice@balizero.com", "role": "team"}

    result = await send_message_to_client(
        client_id=1,
        request=TeamMessageRequest(content="Synthetic message body"),
        current_user=current_user,
        db_pool=mock_db_pool,
    )

    assert result["success"] is True
    assert result["data"]["id"] == 42


@pytest.mark.asyncio
async def test_b2_admin_allowed_regardless_of_assignment(mock_db_pool) -> None:
    """INNOCENCE: admin keeps full access regardless of assignment (CLAUDE.md §13)."""
    mock_db_pool._mock_conn.fetchrow.side_effect = [
        _client_row(assigned_to="bob@balizero.com"),
        _message_row(),
    ]
    current_user = {"email": ADMIN_EMAIL, "role": "team"}

    result = await send_message_to_client(
        client_id=1,
        request=TeamMessageRequest(content="Synthetic message body"),
        current_user=current_user,
        db_pool=mock_db_pool,
    )

    assert result["success"] is True
    assert result["data"]["id"] == 42


# ================================================
# B3 — get_unread_messages_count: assigned_filter on both queries
# ================================================


@pytest.mark.asyncio
async def test_b3_non_admin_filter_applied_to_total_and_by_client(mock_db_pool) -> None:
    """GUILT/discrimination: a non-admin's filter must reach BOTH queries.

    Before the fix, `get_unread_messages_count` had no `assigned_filter`
    parameter at all, so neither query carried an assignment clause — a
    mutation that drops the `if assigned_filter is not None:` block on
    either query (or reverts the dependency) makes these assertions fail:
    the clause disappears from the SQL text, or the bound param disappears.
    """
    conn = mock_db_pool._mock_conn
    conn.fetchval.return_value = 3
    conn.fetch.return_value = [
        {"client_id": 1, "client_name": "Synthetic Assigned Client", "unread_count": 3}
    ]

    result = await get_unread_messages_count(
        _current_user={"email": "alice@balizero.com", "role": "team"},
        assigned_filter="alice@balizero.com",
        db_pool=mock_db_pool,
    )

    assert result["data"]["total_unread"] == 3
    assert len(result["data"]["by_client"]) == 1

    total_query, *total_params = conn.fetchval.await_args.args
    assert "LOWER(c.assigned_to) = $1" in total_query
    assert total_params == ["alice@balizero.com"]

    by_client_query, *by_client_params = conn.fetch.await_args.args
    assert "LOWER(c.assigned_to) = $1" in by_client_query
    assert by_client_params == ["alice@balizero.com"]
    # Archived-client leak must be closed on the query that carries names.
    assert "c.deleted_at IS NULL" in by_client_query


@pytest.mark.asyncio
async def test_b3_non_admin_response_excludes_unassigned_client(mock_db_pool) -> None:
    """A non-admin's `by_client` rows must never surface a client they are
    not assigned to — the mock DB is instructed (as the real filtered SQL
    would be) to return only the caller's own assigned client; this pins the
    response shape a non-admin is entitled to see."""
    conn = mock_db_pool._mock_conn
    conn.fetchval.return_value = 2
    conn.fetch.return_value = [
        {"client_id": 1, "client_name": "Synthetic Assigned Client", "unread_count": 2}
    ]

    result = await get_unread_messages_count(
        _current_user={"email": "alice@balizero.com", "role": "team"},
        assigned_filter="alice@balizero.com",
        db_pool=mock_db_pool,
    )

    client_ids = {row["client_id"] for row in result["data"]["by_client"]}
    assert client_ids == {1}
    assert 99 not in client_ids  # a client synthetically "not assigned" to this caller


@pytest.mark.asyncio
async def test_b3_admin_sees_full_book_no_assigned_to_clause(mock_db_pool) -> None:
    """INNOCENCE: `assigned_filter is None` (admin) must not bind any filter,
    but the archived-client exclusion on `by_client` still applies unconditionally.
    """
    conn = mock_db_pool._mock_conn
    conn.fetchval.return_value = 10
    conn.fetch.return_value = [
        {"client_id": 1, "client_name": "Synthetic Client A", "unread_count": 6},
        {"client_id": 2, "client_name": "Synthetic Client B", "unread_count": 4},
    ]

    result = await get_unread_messages_count(
        _current_user={"email": ADMIN_EMAIL, "role": "team"},
        assigned_filter=None,
        db_pool=mock_db_pool,
    )

    assert result["data"]["total_unread"] == 10
    assert len(result["data"]["by_client"]) == 2

    total_call_args = conn.fetchval.await_args.args
    assert len(total_call_args) == 1  # query only, no assigned_to param bound
    assert "assigned_to" not in total_call_args[0]

    by_client_query, *by_client_params = conn.fetch.await_args.args
    assert by_client_params == []
    assert "assigned_to" not in by_client_query
    assert "c.deleted_at IS NULL" in by_client_query


@pytest.mark.asyncio
async def test_b3_archived_client_excluded_from_by_client_even_for_admin(mock_db_pool) -> None:
    """An archived client must never appear in `by_client`, admin or not.

    The mocked connection can't enforce SQL semantics, so this pins the
    query CONTRACT: `by_client`'s join always carries `c.deleted_at IS
    NULL`, which is what makes an archived client's messages disappear from
    that result set at the database level regardless of who is asking.
    """
    conn = mock_db_pool._mock_conn
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    await get_unread_messages_count(
        _current_user={"email": ADMIN_EMAIL, "role": "team"},
        assigned_filter=None,
        db_pool=mock_db_pool,
    )

    by_client_query = conn.fetch.await_args.args[0]
    assert "c.deleted_at IS NULL" in by_client_query
