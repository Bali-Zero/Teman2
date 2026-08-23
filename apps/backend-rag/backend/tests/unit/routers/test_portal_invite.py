"""Tests for the client portal invitation router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.routers.portal_invite import (
    SendInviteRequest,
    get_client_invitations,
    resend_invitation,
    send_invitation,
    send_portal_invite_email,
)


class FakeInviteService:
    """Small async fake for the portal invite service."""

    def __init__(self) -> None:
        self.created: dict[str, object] | None = None

    async def create_invitation(
        self,
        *,
        client_id: int,
        email: str,
        created_by: str,
    ) -> dict[str, object]:
        self.created = {
            "client_id": client_id,
            "email": email,
            "created_by": created_by,
        }
        return {
            "client_id": client_id,
            "client_name": "Test Client",
            "email": email,
            "invite_url": "/portal/invite?token=tok-123",
            "token": "tok-123",
        }


@pytest.mark.asyncio
async def test_send_portal_invite_email_uses_internal_brevo_adapter() -> None:
    db_pool = MagicMock()

    with patch(
        "backend.app.routers.portal_invite.send_internal_email",
        new=AsyncMock(),
    ) as mock_sender:
        await send_portal_invite_email(
            to="client@example.com",
            client_name='Test Client & "Demo"',
            invite_url="https://my.balizero.com/portal/invite?token=abc&x=1",
            db_pool=db_pool,
            client_id=11898,
        )

    assert mock_sender.await_count == 1
    kwargs = mock_sender.await_args.kwargs
    assert kwargs["to"] == "client@example.com"
    assert kwargs["subject"] == "Welcome to Bali Zero Client Portal"
    assert kwargs["raise_on_failure"] is True
    assert kwargs["email_type"] == "welcome"
    assert kwargs["pool"] is db_pool
    assert kwargs["client_id"] == 11898
    assert "Test Client &amp; &quot;Demo&quot;" in kwargs["body"]
    assert "token=abc&amp;x=1" in kwargs["body"]


@pytest.mark.asyncio
async def test_send_invitation_sends_email_through_internal_adapter(
    monkeypatch: pytest.MonkeyPatch,
    mock_db_pool: MagicMock,
) -> None:
    fake_service = FakeInviteService()
    db_pool = mock_db_pool
    # role="Founder" is admin via is_crm_admin's role check, so the A3
    # verify_client_access(write=True) gate passes regardless of assigned_to —
    # a row must still exist or verify_client_access 404s before we get here.
    db_pool._mock_conn.fetchrow.return_value = {
        "id": 11898,
        "assigned_to": None,
        "created_by": None,
    }
    monkeypatch.setattr(
        "backend.app.routers.portal_invite.settings.frontend_portal_url",
        "https://my.balizero.com",
    )

    with patch(
        "backend.app.routers.portal_invite.send_portal_invite_email",
        new=AsyncMock(),
    ) as mock_sender:
        response = await send_invitation(
            SendInviteRequest(
                client_id=11898,
                email="client@example.com",
            ),
            current_user={"email": "zero@balizero.com", "role": "Founder"},
            invite_service=fake_service,  # type: ignore[arg-type]
            db_pool=db_pool,
        )

    assert response["success"] is True
    assert response["email_sent"] is True
    assert response["email_error"] is None
    assert "email sent" in response["message"]
    assert fake_service.created == {
        "client_id": 11898,
        "email": "client@example.com",
        "created_by": "zero@balizero.com",
    }
    mock_sender.assert_awaited_once_with(
        to="client@example.com",
        client_name="Test Client",
        invite_url="https://my.balizero.com/portal/invite?token=tok-123",
        db_pool=db_pool,
        client_id=11898,
    )
    # A1 regression guard: the raw credential never reaches the response body.
    assert "token" not in response["data"]
    assert "invite_url" not in response["data"]
    assert "full_invite_url" not in response["data"]


@pytest.mark.asyncio
async def test_send_invitation_reports_email_failure(
    monkeypatch: pytest.MonkeyPatch,
    mock_db_pool: MagicMock,
) -> None:
    fake_service = FakeInviteService()
    mock_db_pool._mock_conn.fetchrow.return_value = {
        "id": 11898,
        "assigned_to": None,
        "created_by": None,
    }
    monkeypatch.setattr(
        "backend.app.routers.portal_invite.settings.frontend_portal_url",
        "https://my.balizero.com",
    )

    with patch(
        "backend.app.routers.portal_invite.send_portal_invite_email",
        new=AsyncMock(side_effect=RuntimeError("brevo unavailable")),
    ):
        response = await send_invitation(
            SendInviteRequest(
                client_id=11898,
                email="client@example.com",
            ),
            current_user={"email": "zero@balizero.com", "role": "Founder"},
            invite_service=fake_service,  # type: ignore[arg-type]
            db_pool=mock_db_pool,
        )

    assert response["success"] is True
    assert response["email_sent"] is False
    assert response["email_error"] == "brevo unavailable"
    assert "check email service" in response["message"]


@pytest.mark.asyncio
async def test_send_invitation_rejects_client_role() -> None:
    with pytest.raises(HTTPException) as exc:
        await send_invitation(
            SendInviteRequest(client_id=1, email="client@example.com"),
            current_user={"email": "client@example.com", "role": "client"},
            invite_service=FakeInviteService(),  # type: ignore[arg-type]
            db_pool=MagicMock(),
        )

    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Defect 2 (2026-08-19 audit): these three endpoints tested `role == "client"`
# instead of routing through service_accounts.is_human_team_member. A service
# account (e.g. the "monitoring" login-healthcheck probe) is not a client, but
# it is also not a colleague — it must not mint invite emails, view invitation
# history, or resend invitations either.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_invitation_rejects_monitoring_service_account() -> None:
    """Guilt: the probe must not be able to mint a live Brevo invitation email."""
    with pytest.raises(HTTPException) as exc:
        await send_invitation(
            SendInviteRequest(client_id=1, email="client@example.com"),
            current_user={"email": "probe@balizero.com", "role": "monitoring"},
            invite_service=FakeInviteService(),  # type: ignore[arg-type]
            db_pool=MagicMock(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_client_invitations_rejects_monitoring_service_account() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_client_invitations(
            client_id=1,
            current_user={"email": "probe@balizero.com", "role": "monitoring"},
            invite_service=FakeInviteService(),  # type: ignore[arg-type]
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_client_invitations_allows_a_realistic_free_text_role(
    mock_db_pool: MagicMock,
) -> None:
    """Innocence: a real, free-text team-role title must still pass through
    to the service call (this repo's roles are job titles, not an enum).

    "Board Member" is admin via is_crm_admin's role check (crm_utils.py), so
    the A3 verify_client_access(write=True) gate passes regardless of
    assigned_to — a client row must still exist or it 404s.
    """
    fake_service = FakeInviteService()
    mock_db_pool._mock_conn.fetchrow.return_value = {
        "id": 1,
        "assigned_to": None,
        "created_by": None,
    }

    async def _get_client_invitations(client_id: int) -> list[dict[str, object]]:
        return [{"client_id": client_id, "status": "pending"}]

    fake_service.get_client_invitations = _get_client_invitations  # type: ignore[assignment]

    response = await get_client_invitations(
        client_id=1,
        current_user={"email": "board@balizero.com", "role": "Board Member"},
        invite_service=fake_service,  # type: ignore[arg-type]
        db_pool=mock_db_pool,
    )

    assert response["success"] is True


@pytest.mark.asyncio
async def test_resend_invitation_rejects_monitoring_service_account() -> None:
    with pytest.raises(HTTPException) as exc:
        await resend_invitation(
            client_id=1,
            current_user={"email": "probe@balizero.com", "role": "monitoring"},
            invite_service=FakeInviteService(),  # type: ignore[arg-type]
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_resend_invitation_allows_a_realistic_free_text_role(
    mock_db_pool: MagicMock,
) -> None:
    """Innocence: a real, free-text team-role title must still pass through
    when the caller is assigned to (or created) the client — "Reception" is
    not an admin role, so the A3 verify_client_access(write=True) gate needs
    an ownership match, unlike the Board-Member case above.
    """
    fake_service = FakeInviteService()
    mock_db_pool._mock_conn.fetchrow.return_value = {
        "id": 1,
        "assigned_to": "reception@balizero.com",
        "created_by": "reception@balizero.com",
    }

    async def _resend_invitation(*, client_id: int, created_by: str) -> dict[str, object]:
        return {"client_id": client_id, "created_by": created_by}

    fake_service.resend_invitation = _resend_invitation  # type: ignore[assignment]

    response = await resend_invitation(
        client_id=1,
        current_user={"email": "reception@balizero.com", "role": "Reception"},
        invite_service=fake_service,  # type: ignore[arg-type]
        db_pool=mock_db_pool,
    )

    assert response["success"] is True
