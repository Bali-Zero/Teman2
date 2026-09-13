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


def _cc_of(*args, **kwargs):
    """The CC half of `_enforce_balizero_cc`'s ``(cc, bcc)`` pair.

    The function grew a second return value when credential deliveries had
    to be stripped of bcc as well as cc (a bcc'd login link leaks exactly as
    much as a cc'd one). The assertions in `TestEnforceBalizeroCc` below are
    about the CC half and are UNCHANGED from when the function returned it
    alone -- this helper keeps them that way instead of restating them.
    Tests that care about the bcc half call the real function directly.
    """
    return _enforce_balizero_cc(*args, **kwargs)[0]


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
        assert _cc_of("alice@example.com", None, None) == [
            "asya@balizero.com"
        ]

    def test_invoice_forces_accounting_cc(self):
        out = _cc_of(
            "alice@example.com", None, None, email_type="invoice_client"
        )
        assert out == ["asya@balizero.com"]

    def test_non_invoice_forces_assigned_lead(self):
        out = _cc_of(
            "alice@example.com",
            None,
            None,
            email_type="welcome",
            assigned_to="krisna@balizero.com",
        )
        assert out == ["krisna@balizero.com"]

    def test_non_invoice_no_assigned_falls_back_to_accounting(self):
        out = _cc_of(
            "alice@example.com", None, None, email_type="waiting_docs_client"
        )
        assert out == ["asya@balizero.com"]

    def test_invoice_ignores_assigned_and_uses_accounting(self):
        # even with an assigned lead, an invoice goes to accounting
        out = _cc_of(
            "alice@example.com",
            None,
            None,
            email_type="invoice_client",
            assigned_to="krisna@balizero.com",
        )
        assert out == ["asya@balizero.com"]

    def test_external_with_other_cc_appends_balizero(self):
        out = _cc_of(
            "alice@example.com", ["bob@gmail.com"], None, email_type="welcome",
            assigned_to="krisna@balizero.com",
        )
        assert "krisna@balizero.com" in out
        assert "bob@gmail.com" in out

    # --- INNOCENCE: already compliant → leave untouched ---
    def test_intra_domain_recipient_untouched(self):
        # to is @balizero.com → intra-team, no injection
        assert _cc_of("bob@balizero.com", None, None) is None

    def test_existing_balizero_cc_untouched(self):
        # caller already copied a balizero address → respect their choice,
        # do NOT also add the contextual one
        cc = ["asya@balizero.com", "client@gmail.com"]
        assert (
            _cc_of(
                "alice@example.com", cc, None, email_type="welcome",
                assigned_to="krisna@balizero.com",
            )
            == cc
        )

    def test_balizero_in_bcc_counts_as_compliant(self):
        # team copied via BCC → rule satisfied, cc not mutated
        assert (
            _cc_of("alice@example.com", None, ["zero@balizero.com"])
            is None
        )

    def test_case_insensitive_domain_match(self):
        assert (
            _cc_of("alice@example.com", ["Asya@BaliZero.com"], None)
            == ["Asya@BaliZero.com"]
        )

    def test_no_bare_substring_false_match(self):
        # 'balizero.com.evil.com' must NOT be treated as a balizero address
        # → guard fires, injects the fallback accounting address
        out = _cc_of(
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


class TestGarudaVoaStandingCc:
    """RULED by Antonello 2026-09-02: "in cc questi 3 solo per le pratiche
    del garuda voa". A STANDING list scoped to one email family -- unlike
    every other rule here, which picks ONE contextual reader.

    Superscar #3 discipline: guilt AND innocence, and the innocence cases
    are the ones that keep this from becoming an over-match."""

    THREE = ["surya@balizero.com", "vino@balizero.com", "zero@balizero.com"]

    # --- GUILT ---
    def test_voa_practice_mail_copies_all_three(self):
        cc, bcc = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type="garuda_voa_order_confirmed"
        )
        assert cc == self.THREE
        assert bcc is None

    def test_bare_family_name_also_matches(self):
        cc, _ = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type="garuda_voa"
        )
        assert cc == self.THREE

    def test_case_and_whitespace_do_not_defeat_it(self):
        cc, _ = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type="  GARUDA_VOA_Status  "
        )
        assert cc == self.THREE

    def test_standing_list_is_added_even_when_someone_is_already_copied(self):
        # Deliberately DIFFERENT from the generic rule, which leaves an
        # already-compliant mail untouched. "In cc vanno questi tre" is not
        # "in cc va qualcuno".
        cc, _ = _enforce_balizero_cc(
            "alice@example.com",
            ["krisna@balizero.com"],
            None,
            email_type="garuda_voa_status",
        )
        assert cc[0] == "krisna@balizero.com"
        for addr in self.THREE:
            assert addr in cc

    def test_no_duplicate_when_one_is_already_there(self):
        cc, _ = _enforce_balizero_cc(
            "alice@example.com", ["zero@balizero.com"], None, email_type="garuda_voa"
        )
        assert cc.count("zero@balizero.com") == 1
        assert len(cc) == 3

    # --- INNOCENCE ---
    def test_a_neighbouring_email_type_does_NOT_get_the_three(self):
        # The classifier is a PREFIX on a controlled field, not a substring
        # search: a type that merely CONTAINS the family name is not it.
        cc, _ = _enforce_balizero_cc(
            "alice@example.com",
            None,
            None,
            email_type="not_garuda_voa",
            assigned_to="krisna@balizero.com",
        )
        assert cc == ["krisna@balizero.com"]

    def test_ordinary_practice_mail_is_unchanged_by_this_rule(self):
        cc, _ = _enforce_balizero_cc(
            "alice@example.com",
            None,
            None,
            email_type="welcome",
            assigned_to="krisna@balizero.com",
        )
        assert cc == ["krisna@balizero.com"]
        assert "surya@balizero.com" not in cc

    def test_intra_team_voa_mail_gets_nothing_forced(self):
        cc, bcc = _enforce_balizero_cc(
            "bob@balizero.com", None, None, email_type="garuda_voa_status"
        )
        assert cc is None and bcc is None


class TestCredentialDeliveryIsNeverCopied:
    """A magic link's body IS the recipient's key to their own account, so a
    copy is not an audit trail -- it is a second person able to sign in as
    the customer. Before 2026-09-02 the magic-link sender passed no
    email_type at all, so it fell through to the accounting fallback and
    every customer login link was copied to a staff mailbox."""

    LINK = "garuda_magic_link"

    # --- GUILT ---
    def test_no_address_is_injected(self):
        cc, bcc = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type=self.LINK
        )
        assert cc is None
        assert bcc is None

    def test_a_caller_supplied_cc_is_STRIPPED_not_merely_left_alone(self):
        cc, bcc = _enforce_balizero_cc(
            "alice@example.com",
            ["asya@balizero.com", "someone@example.com"],
            None,
            email_type=self.LINK,
        )
        assert cc is None and bcc is None

    def test_bcc_is_stripped_too(self):
        # A bcc'd login link leaks exactly as much as a cc'd one; the
        # function returns both halves precisely so this is expressible.
        cc, bcc = _enforce_balizero_cc(
            "alice@example.com", None, ["zero@balizero.com"], email_type=self.LINK
        )
        assert cc is None and bcc is None

    def test_the_assigned_lead_does_not_override_it(self):
        cc, bcc = _enforce_balizero_cc(
            "alice@example.com",
            None,
            None,
            email_type=self.LINK,
            assigned_to="krisna@balizero.com",
        )
        assert cc is None and bcc is None

    # --- INNOCENCE: the exemption must not widen ---
    def test_an_unknown_email_type_is_NOT_exempt(self):
        # The failure mode of a typo must be an unwanted copy, never a
        # leaked credential. `_CREDENTIAL_DELIVERY_EMAIL_TYPES` is a fixed
        # membership list, not a pattern.
        cc, _ = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type="garuda_magic_lnk"
        )
        assert cc == ["asya@balizero.com"]

    def test_a_type_merely_containing_the_name_is_NOT_exempt(self):
        cc, _ = _enforce_balizero_cc(
            "alice@example.com", None, None, email_type="about_garuda_magic_link"
        )
        assert cc == ["asya@balizero.com"]

    def test_absent_email_type_is_NOT_exempt(self):
        cc, _ = _enforce_balizero_cc("alice@example.com", None, None)
        assert cc == ["asya@balizero.com"]
