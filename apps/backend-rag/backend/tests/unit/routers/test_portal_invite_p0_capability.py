"""P0 account-takeover fix — PR A (2026-08-23).

Ground-verified chain this PR closes (see SPEC-p0-invite.md, section "PR A"):

1. `POST /api/portal/invite/resend/{client_id}` was guarded only by
   `is_human_team_member(current_user.get("role"))` — no client-access check,
   arbitrary `client_id`. Same for `send_invitation` and
   `get_client_invitations`.
2. The HTTP response carried the RAW token and the victim's email under
   `data`. Anyone who could reach #1 (including, before the widened-Subhi-era
   API-key/internal-role deny-list gap, non-human machine principals) got a
   working credential back in the response body.
3. `POST /api/portal/invite/complete` (public, no auth — it IS registration)
   consumes that token and overwrites `team_members.pin_hash`, reactivating
   ANY existing account for that client — including an already-ACTIVE one.
4. Login with the leaked email + chosen PIN → full portal session as that
   client.

This file covers A1 (no raw token/invite_url ever leaves the router) and A3
(client-level access gating on send/resend/history) at the router layer.
A2 (active-account guard) and A4's InviteService-level `deleted_at` filters
live in `backend/tests/services/portal/test_invite_service.py` — that is
where InviteService is already unit-tested with its own FakePool/FakeConnection
harness.

IMPORTANT — nothing here mocks `verify_client_access` itself (that would
prove nothing about the fix: patching the guard away runs no guard at all).
Every A3 test drives the REAL `verify_client_access`
(`backend.app.utils.crm_utils`), mocking only the asyncpg connection it reads
from — same harness as `test_crm_portal_mark_read_bola.py`
(`mock_db_pool._mock_conn.fetchrow`, the shared fixture in `conftest.py`).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.routers.portal_invite import (
    SendInviteRequest,
    _invitation_public_view,
    get_client_invitations,
    resend_invitation,
    send_invitation,
)

ADMIN_EMAIL = "asya@balizero.com"  # backend.app.utils.crm_utils.CRM_EXTRA_ADMIN_EMAILS

RAW_TOKEN = "super-secret-raw-invite-token"
RAW_INVITE_URL = f"/portal/register?token={RAW_TOKEN}"


class _StubInviteService:
    """Minimal async stand-in for InviteService — returns realistic payloads
    (including the raw token/invite_url) so the tests can prove the ROUTER,
    not the service, is what strips them."""

    async def create_invitation(
        self, *, client_id: int, email: str, created_by: str
    ) -> dict[str, Any]:
        return {
            "invitation_id": 1,
            "client_id": client_id,
            "client_name": "Stub Client",
            "email": email,
            "token": RAW_TOKEN,
            "expires_at": "2026-01-01T00:00:00+00:00",
            "invite_url": RAW_INVITE_URL,
        }

    async def get_client_invitations(self, client_id: int) -> list[dict[str, Any]]:
        return [{"id": 1, "email": "client@example.com", "status": "pending"}]

    async def resend_invitation(self, *, client_id: int, created_by: str) -> dict[str, Any]:
        return {
            "invitation_id": 2,
            "client_id": client_id,
            "client_name": "Stub Client",
            "email": "client@example.com",
            "token": RAW_TOKEN,
            "expires_at": "2026-01-01T00:00:00+00:00",
            "invite_url": RAW_INVITE_URL,
        }


def _client_row(*, assigned_to: str | None, created_by: str | None = None) -> dict[str, object]:
    return {
        "id": 1,
        "assigned_to": assigned_to,
        "created_by": created_by if created_by is not None else assigned_to,
    }


# ---------------------------------------------------------------------------
# A1 — the raw token/invite_url never leaves the process in a response body.
# ---------------------------------------------------------------------------


def test_invitation_public_view_strips_token_and_invite_url() -> None:
    """Direct unit test of the helper — the smallest possible discrimination
    surface. Mutate the helper to drop the exclusion set (or to exclude the
    wrong keys) and this fails immediately, independent of any router wiring.
    """
    result = {
        "invitation_id": 1,
        "client_id": 7,
        "client_name": "Kaiser Test",
        "email": "kaiser@example.com",
        "token": RAW_TOKEN,
        "expires_at": "2026-01-01T00:00:00+00:00",
        "invite_url": RAW_INVITE_URL,
    }

    view = _invitation_public_view(result)

    assert "token" not in view
    assert "invite_url" not in view
    # Everything else must survive untouched (spec: keep invitation_id,
    # client_id, client_name, email, expires_at).
    assert view == {
        "invitation_id": 1,
        "client_id": 7,
        "client_name": "Kaiser Test",
        "email": "kaiser@example.com",
        "expires_at": "2026-01-01T00:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_send_invitation_response_never_carries_token_or_any_link(
    monkeypatch: pytest.MonkeyPatch,
    mock_db_pool: MagicMock,
) -> None:
    """A1, wired end-to-end through send_invitation.

    Also pins the router-level deviation from the spec's literal text: the
    spec named only `token`/`invite_url` as the keys to strip, but
    `send_invitation` additionally computed `full_invite_url` (base_url +
    invite_url) and put THAT in the response too — which embeds the exact
    same raw token in a ready-to-click link. Stripping token/invite_url alone
    would not have closed the leak for this endpoint; `full_invite_url` must
    never be included in the response body either.
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to=ADMIN_EMAIL)
    monkeypatch.setattr(
        "backend.app.routers.portal_invite.settings.frontend_portal_url",
        "https://my.balizero.com",
    )

    with patch(
        "backend.app.routers.portal_invite.send_portal_invite_email",
        new=AsyncMock(),
    ):
        response = await send_invitation(
            SendInviteRequest(client_id=1, email="client@example.com"),
            current_user={"email": ADMIN_EMAIL, "role": "team"},
            invite_service=_StubInviteService(),  # type: ignore[arg-type]
            db_pool=mock_db_pool,
        )

    assert response["success"] is True
    data = response["data"]
    assert "token" not in data
    assert "invite_url" not in data
    assert "full_invite_url" not in data
    # Negative-content check too — RAW_TOKEN must not appear anywhere in the
    # serialized response, not just under the keys we know about today.
    assert RAW_TOKEN not in repr(response)


@pytest.mark.asyncio
async def test_resend_invitation_response_never_carries_token_or_url(
    mock_db_pool: MagicMock,
) -> None:
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to=ADMIN_EMAIL)

    response = await resend_invitation(
        client_id=1,
        current_user={"email": ADMIN_EMAIL, "role": "team"},
        invite_service=_StubInviteService(),  # type: ignore[arg-type]
        db_pool=mock_db_pool,
    )

    assert response["success"] is True
    data = response["data"]
    assert "token" not in data
    assert "invite_url" not in data
    assert RAW_TOKEN not in repr(response)


# ---------------------------------------------------------------------------
# A3 — minting/reading/resending an invitation requires client access.
# Guilt: non-assigned, non-admin human team member -> 403, never 500.
# Innocence: assigned team member -> allowed. Admin -> allowed regardless.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_invitation_non_assigned_non_admin_denied_403_not_500(
    mock_db_pool: MagicMock,
) -> None:
    """GUILT. Before A3, `is_human_team_member` was the ONLY gate — any human
    team-role login could mint a live Brevo invite for an arbitrary
    `client_id`. This drives the REAL `verify_client_access` write=True
    branch; nothing here mocks the guard away.
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="alice@balizero.com"
    )

    with pytest.raises(HTTPException) as exc_info:
        await send_invitation(
            SendInviteRequest(client_id=1, email="victim@example.com"),
            current_user={"email": "bob@balizero.com", "role": "team"},
            invite_service=MagicMock(),  # must never be reached
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.status_code != 500


@pytest.mark.asyncio
async def test_send_invitation_assigned_team_member_allowed(
    monkeypatch: pytest.MonkeyPatch,
    mock_db_pool: MagicMock,
) -> None:
    """INNOCENCE — assigned_to match."""
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")
    monkeypatch.setattr(
        "backend.app.routers.portal_invite.settings.frontend_portal_url",
        "https://my.balizero.com",
    )

    with patch(
        "backend.app.routers.portal_invite.send_portal_invite_email",
        new=AsyncMock(),
    ):
        response = await send_invitation(
            SendInviteRequest(client_id=1, email="client@example.com"),
            current_user={"email": "alice@balizero.com", "role": "team"},
            invite_service=_StubInviteService(),  # type: ignore[arg-type]
            db_pool=mock_db_pool,
        )

    assert response["success"] is True


@pytest.mark.asyncio
async def test_send_invitation_admin_allowed_regardless_of_assignment(
    monkeypatch: pytest.MonkeyPatch,
    mock_db_pool: MagicMock,
) -> None:
    """INNOCENCE — admin bypasses the ownership check entirely."""
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")
    monkeypatch.setattr(
        "backend.app.routers.portal_invite.settings.frontend_portal_url",
        "https://my.balizero.com",
    )

    with patch(
        "backend.app.routers.portal_invite.send_portal_invite_email",
        new=AsyncMock(),
    ):
        response = await send_invitation(
            SendInviteRequest(client_id=1, email="client@example.com"),
            current_user={"email": ADMIN_EMAIL, "role": "team"},
            invite_service=_StubInviteService(),  # type: ignore[arg-type]
            db_pool=mock_db_pool,
        )

    assert response["success"] is True


@pytest.mark.asyncio
async def test_get_client_invitations_non_assigned_non_admin_denied_403_not_500(
    mock_db_pool: MagicMock,
) -> None:
    """GUILT — history endpoint. Before A3 this had no `db_pool` dependency
    at all: any human team-role login could read any client's invitation
    history (id/email/status/expiry).
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="alice@balizero.com"
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_client_invitations(
            client_id=1,
            current_user={"email": "bob@balizero.com", "role": "team"},
            invite_service=MagicMock(),  # must never be reached
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.status_code != 500


@pytest.mark.asyncio
async def test_get_client_invitations_assigned_team_member_allowed(
    mock_db_pool: MagicMock,
) -> None:
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")

    response = await get_client_invitations(
        client_id=1,
        current_user={"email": "alice@balizero.com", "role": "team"},
        invite_service=_StubInviteService(),  # type: ignore[arg-type]
        db_pool=mock_db_pool,
    )

    assert response["success"] is True


@pytest.mark.asyncio
async def test_get_client_invitations_admin_allowed_regardless_of_assignment(
    mock_db_pool: MagicMock,
) -> None:
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")

    response = await get_client_invitations(
        client_id=1,
        current_user={"email": ADMIN_EMAIL, "role": "team"},
        invite_service=_StubInviteService(),  # type: ignore[arg-type]
        db_pool=mock_db_pool,
    )

    assert response["success"] is True


@pytest.mark.asyncio
async def test_resend_invitation_non_assigned_non_admin_denied_403_not_500(
    mock_db_pool: MagicMock,
) -> None:
    """GUILT — this is the exact endpoint named in the verified chain
    (`POST /api/portal/invite/resend/{client_id}`, portal_invite.py:271 in
    the spec's ground-truth read).
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="alice@balizero.com"
    )

    with pytest.raises(HTTPException) as exc_info:
        await resend_invitation(
            client_id=1,
            current_user={"email": "bob@balizero.com", "role": "team"},
            invite_service=MagicMock(),  # must never be reached
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.status_code != 500


@pytest.mark.asyncio
async def test_resend_invitation_assigned_team_member_allowed(
    mock_db_pool: MagicMock,
) -> None:
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")

    response = await resend_invitation(
        client_id=1,
        current_user={"email": "alice@balizero.com", "role": "team"},
        invite_service=_StubInviteService(),  # type: ignore[arg-type]
        db_pool=mock_db_pool,
    )

    assert response["success"] is True


@pytest.mark.asyncio
async def test_resend_invitation_admin_allowed_regardless_of_assignment(
    mock_db_pool: MagicMock,
) -> None:
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(assigned_to="alice@balizero.com")

    response = await resend_invitation(
        client_id=1,
        current_user={"email": ADMIN_EMAIL, "role": "team"},
        invite_service=_StubInviteService(),  # type: ignore[arg-type]
        db_pool=mock_db_pool,
    )

    assert response["success"] is True


# ---------------------------------------------------------------------------
# A3 also closes the API-key / machine-principal vector by construction:
# write=True requires the caller's email to match assigned_to/created_by or
# is_crm_admin, and a machine principal's email matches neither.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_invitation_api_key_principal_denied_403_not_500(
    mock_db_pool: MagicMock,
) -> None:
    """GUILT — an API-key-authenticated caller (role="user", per
    `app/services/api_key_auth.py`) passes `is_human_team_member` (it is a
    deny-list keyed on {"client","monitoring"}) but must still be denied by
    the write=True ownership check, since it owns/is-assigned-to nothing.
    """
    mock_db_pool._mock_conn.fetchrow.return_value = _client_row(
        assigned_to="alice@balizero.com", created_by="alice@balizero.com"
    )

    with pytest.raises(HTTPException) as exc_info:
        await send_invitation(
            SendInviteRequest(client_id=1, email="victim@example.com"),
            current_user={"email": "api-key-principal@balizero.com", "role": "user"},
            invite_service=MagicMock(),
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.status_code != 500


# ---------------------------------------------------------------------------
# A4 (router layer) — verify_client_access's own client lookup already
# filters `deleted_at IS NULL` (crm_utils.py), so an archived client 404s
# before send/resend ever reaches InviteService. The InviteService-level
# `deleted_at` filters (defense-in-depth for direct/non-router callers) are
# covered in test_invite_service.py.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_invitation_archived_client_denied_404_not_500(
    mock_db_pool: MagicMock,
) -> None:
    mock_db_pool._mock_conn.fetchrow.return_value = None  # deleted_at IS NULL excludes the row

    with pytest.raises(HTTPException) as exc_info:
        await send_invitation(
            SendInviteRequest(client_id=999999, email="client@example.com"),
            current_user={"email": ADMIN_EMAIL, "role": "team"},
            invite_service=MagicMock(),
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.status_code != 500


@pytest.mark.asyncio
async def test_resend_invitation_archived_client_denied_404_not_500(
    mock_db_pool: MagicMock,
) -> None:
    mock_db_pool._mock_conn.fetchrow.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await resend_invitation(
            client_id=999999,
            current_user={"email": ADMIN_EMAIL, "role": "team"},
            invite_service=MagicMock(),
            db_pool=mock_db_pool,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.status_code != 500
