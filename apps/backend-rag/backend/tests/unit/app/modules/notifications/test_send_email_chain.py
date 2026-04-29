"""Provider-chain tests for ``POST /api/notifications/send-email``.

NB-E (2026-04-29) extends the chain to:

    intra-domain:  Zoho SMTP  → Brevo
    external:      Brevo → Resend → Zoho SMTP

These tests exercise the chain order without going to the network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.modules.notifications.router import (
    SendEmailRequest,
    send_direct_email,
)


@pytest.fixture
def req_external():
    return SendEmailRequest(
        to="alice@example.com", subject="hi", body="<p>x</p>",
    )


@pytest.fixture
def req_intra():
    return SendEmailRequest(
        to="bob@balizero.com", subject="hi", body="<p>x</p>",
    )


@pytest.mark.asyncio
async def test_external_brevo_succeeds_no_fallback(req_external):
    """When Brevo (primary for externals) succeeds, Resend and Zoho must NOT be called."""
    with (
        patch(
            "backend.app.modules.notifications.router._send_via_brevo",
            new=AsyncMock(return_value=True),
        ) as brevo,
        patch(
            "backend.app.modules.notifications.router._send_via_resend",
            new=AsyncMock(return_value=True),
        ) as resend,
        patch(
            "backend.app.modules.notifications.router._send_via_zoho_smtp",
            new=AsyncMock(return_value=True),
        ) as zoho,
    ):
        resp = await send_direct_email(req_external, _auth={})
    assert resp.success is True
    assert "brevo" in resp.message
    brevo.assert_called_once()
    resend.assert_not_called()
    zoho.assert_not_called()


@pytest.mark.asyncio
async def test_external_brevo_fail_resend_succeeds(req_external):
    """Brevo failure must fall through to Resend (the new NB-E layer) before Zoho."""
    with (
        patch(
            "backend.app.modules.notifications.router._send_via_brevo",
            new=AsyncMock(return_value=False),
        ) as brevo,
        patch(
            "backend.app.modules.notifications.router._send_via_resend",
            new=AsyncMock(return_value=True),
        ) as resend,
        patch(
            "backend.app.modules.notifications.router._send_via_zoho_smtp",
            new=AsyncMock(return_value=True),
        ) as zoho,
    ):
        resp = await send_direct_email(req_external, _auth={})
    assert resp.success is True
    assert "resend" in resp.message
    brevo.assert_called_once()
    resend.assert_called_once()
    zoho.assert_not_called()


@pytest.mark.asyncio
async def test_external_brevo_and_resend_fail_zoho_last_resort(req_external):
    """If both Brevo and Resend fail, Zoho SMTP is the last resort."""
    with (
        patch(
            "backend.app.modules.notifications.router._send_via_brevo",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "backend.app.modules.notifications.router._send_via_resend",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "backend.app.modules.notifications.router._send_via_zoho_smtp",
            new=AsyncMock(return_value=True),
        ) as zoho,
    ):
        resp = await send_direct_email(req_external, _auth={})
    assert resp.success is True
    assert "zoho" in resp.message
    zoho.assert_called_once()


@pytest.mark.asyncio
async def test_external_all_three_fail(req_external):
    with (
        patch(
            "backend.app.modules.notifications.router._send_via_brevo",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "backend.app.modules.notifications.router._send_via_resend",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "backend.app.modules.notifications.router._send_via_zoho_smtp",
            new=AsyncMock(return_value=False),
        ),
    ):
        resp = await send_direct_email(req_external, _auth={})
    assert resp.success is False
    # All three providers should be named in the failure message.
    assert "brevo" in resp.message
    assert "resend" in resp.message
    assert "zoho" in resp.message


@pytest.mark.asyncio
async def test_intra_domain_does_not_use_resend(req_intra):
    """Resend must NOT appear in the intra-domain chain — Zoho is primary,
    Brevo is the only fallback. Adding Resend on @balizero.com would
    cross domains needlessly."""
    with (
        patch(
            "backend.app.modules.notifications.router._send_via_zoho_smtp",
            new=AsyncMock(return_value=False),
        ) as zoho,
        patch(
            "backend.app.modules.notifications.router._send_via_brevo",
            new=AsyncMock(return_value=True),
        ) as brevo,
        patch(
            "backend.app.modules.notifications.router._send_via_resend",
            new=AsyncMock(return_value=True),
        ) as resend,
    ):
        resp = await send_direct_email(req_intra, _auth={})
    assert resp.success is True
    zoho.assert_called_once()
    brevo.assert_called_once()
    resend.assert_not_called()
