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
    _enforce_balizero_cc,
    send_direct_email,
)


class TestEnforceBalizeroCc:
    """Hard rule (Antonello 2026-06-17): a client never gets an email
    without a @balizero.com address copied in. Contextual CC:
    invoice → asya@ (accounting), else the assigned lead, else asya@.

    Superscar #3 discipline: every guard ships with an innocence test
    (does NOT fire on a legitimate neighbour) AND a guilt test (DOES
    fire on the real violation)."""

    # --- GUILT: external recipient, no balizero anywhere → inject CC ---
    def test_external_no_context_falls_back_to_accounting(self):
        # no email_type, no assigned → fallback asya@ (never silently void)
        assert _enforce_balizero_cc("alice@example.com", None, None) == [
            "asya@balizero.com"
        ]

    def test_invoice_forces_accounting_cc(self):
        out = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type="invoice_client"
        )
        assert out == ["asya@balizero.com"]

    def test_non_invoice_forces_assigned_lead(self):
        out = _enforce_balizero_cc(
            "alice@example.com",
            None,
            None,
            email_type="welcome",
            assigned_to="krisna@balizero.com",
        )
        assert out == ["krisna@balizero.com"]

    def test_non_invoice_no_assigned_falls_back_to_accounting(self):
        out = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type="waiting_docs_client"
        )
        assert out == ["asya@balizero.com"]

    def test_invoice_ignores_assigned_and_uses_accounting(self):
        # even with an assigned lead, an invoice goes to accounting
        out = _enforce_balizero_cc(
            "alice@example.com",
            None,
            None,
            email_type="invoice_client",
            assigned_to="krisna@balizero.com",
        )
        assert out == ["asya@balizero.com"]

    def test_external_with_other_cc_appends_balizero(self):
        out = _enforce_balizero_cc(
            "alice@example.com", ["bob@gmail.com"], None, email_type="welcome",
            assigned_to="krisna@balizero.com",
        )
        assert "krisna@balizero.com" in out
        assert "bob@gmail.com" in out

    # --- INNOCENCE: already compliant → leave untouched ---
    def test_intra_domain_recipient_untouched(self):
        # to is @balizero.com → intra-team, no injection
        assert _enforce_balizero_cc("bob@balizero.com", None, None) is None

    def test_existing_balizero_cc_untouched(self):
        # caller already copied a balizero address → respect their choice,
        # do NOT also add the contextual one
        cc = ["asya@balizero.com", "client@gmail.com"]
        assert (
            _enforce_balizero_cc(
                "alice@example.com", cc, None, email_type="welcome",
                assigned_to="krisna@balizero.com",
            )
            == cc
        )

    def test_balizero_in_bcc_counts_as_compliant(self):
        # team copied via BCC → rule satisfied, cc not mutated
        assert (
            _enforce_balizero_cc("alice@example.com", None, ["zero@balizero.com"])
            is None
        )

    def test_case_insensitive_domain_match(self):
        assert (
            _enforce_balizero_cc("alice@example.com", ["Asya@BaliZero.com"], None)
            == ["Asya@BaliZero.com"]
        )

    def test_no_bare_substring_false_match(self):
        # 'balizero.com.evil.com' must NOT be treated as a balizero address
        # → guard fires, injects the fallback accounting address
        out = _enforce_balizero_cc(
            "alice@example.com", ["x@balizero.com.evil.com"], None,
            email_type="invoice_client",
        )
        assert "asya@balizero.com" in out


@pytest.fixture
def req_external():
    return SendEmailRequest(
        to="alice@example.com",
        subject="hi",
        body="<p>x</p>",
    )


@pytest.fixture
def req_intra():
    return SendEmailRequest(
        to="bob@balizero.com",
        subject="hi",
        body="<p>x</p>",
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
