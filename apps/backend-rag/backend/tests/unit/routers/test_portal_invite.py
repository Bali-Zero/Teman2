"""Tests for the client portal invitation router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.routers.portal_invite import (
    SendInviteRequest,
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
            "client_name": "Kaiser Test",
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
            to="kaiser@example.com",
            client_name='Kaiser & "Demo"',
            invite_url="https://my.balizero.com/portal/invite?token=abc&x=1",
            db_pool=db_pool,
            client_id=11898,
        )

    assert mock_sender.await_count == 1
    kwargs = mock_sender.await_args.kwargs
    assert kwargs["to"] == "kaiser@example.com"
    assert kwargs["subject"] == "Welcome to Bali Zero Client Portal"
    assert kwargs["raise_on_failure"] is True
    assert kwargs["email_type"] == "welcome"
    assert kwargs["pool"] is db_pool
    assert kwargs["client_id"] == 11898
    assert "Kaiser &amp; &quot;Demo&quot;" in kwargs["body"]
    assert "token=abc&amp;x=1" in kwargs["body"]


@pytest.mark.asyncio
async def test_send_invitation_sends_email_through_internal_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeInviteService()
    db_pool = MagicMock()
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
                email="kaiser198719871987@gmail.com",
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
        "email": "kaiser198719871987@gmail.com",
        "created_by": "zero@balizero.com",
    }
    mock_sender.assert_awaited_once_with(
        to="kaiser198719871987@gmail.com",
        client_name="Kaiser Test",
        invite_url="https://my.balizero.com/portal/invite?token=tok-123",
        db_pool=db_pool,
        client_id=11898,
    )


@pytest.mark.asyncio
async def test_send_invitation_reports_email_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeInviteService()
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
                email="kaiser198719871987@gmail.com",
            ),
            current_user={"email": "zero@balizero.com", "role": "Founder"},
            invite_service=fake_service,  # type: ignore[arg-type]
            db_pool=MagicMock(),
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
