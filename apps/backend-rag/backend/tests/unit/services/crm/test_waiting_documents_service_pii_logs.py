"""PII log hygiene for WaitingDocumentsService._send_with_brevo_fallback —
C2 (PR #7385 gate follow-up, deadline 2026-10-03): the fresh gate on PR
#7438 found this file's "Email sent to %s via Brevo"/"...via Zoho
fallback"/"Brevo failed for %s..."/"Both Brevo and Zoho failed for %s: %s"
lines still logged `to_email` raw, and `completed_process_service.py`'s
sibling method logged the raw exception object directly. #7438 fixed
`router.py` and `email_audit.py`; this file's copy of the same
Brevo-then-Zoho pattern was named as C4's still-open third group.

Guilt: every branch of `_send_with_brevo_fallback` (Brevo success, Brevo
failure -> Zoho success, both fail) is exercised with an address-bearing
`to_email` and a provider exception whose own text echoes an address back
(the same "a bounce quotes the address" shape `email_audit.py`'s own
docstring names). Both halves are asserted: the raw text must be absent
AND its redacted stand-in must be present, so an emptied log line does not
pass as "fixed".

Innocence: the provider names ("Brevo"/"Zoho") and non-PII diagnostic
words survive the scrub untouched.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.crm.waiting_documents_service import WaitingDocumentsService

_LOGGER_NAME = "backend.services.crm.waiting_documents_service"
_ADDR = "waiting.docs.probe@example.com"


def _make_service() -> WaitingDocumentsService:
    pool = MagicMock()
    with patch("backend.services.crm.waiting_documents_service.ZohoEmailService"):
        svc = WaitingDocumentsService(pool)
    svc.zoho_email_service = AsyncMock()
    return svc


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def _patch_email_infra(brevo_client: object):
    """Patch the names bound in waiting_documents_service.py itself (not
    their origin modules) — the same convention test_completed_process_service.py
    documents: DB audit calls are stubbed out too, since this test targets
    the LOGGING behaviour, not the audit-write path (covered elsewhere)."""
    return (
        patch(
            "backend.services.crm.waiting_documents_service.get_email_client",
            new=AsyncMock(return_value=brevo_client),
        ),
        patch(
            "backend.services.crm.waiting_documents_service.log_email_attempt",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "backend.services.crm.waiting_documents_service.record_email_result",
            new=AsyncMock(),
        ),
        patch(
            "backend.services.crm.waiting_documents_service.notify_email_failure_critical",
            new=MagicMock(),
        ),
    )


# --- GUILT ---


@pytest.mark.asyncio
async def test_brevo_success_log_does_not_leak_the_recipient(caplog):
    svc = _make_service()
    client = AsyncMock()
    client.post = AsyncMock(return_value=_FakeResponse())
    p1, p2, p3, p4 = _patch_email_infra(client)
    with p1, p2, p3, p4, caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        await svc._send_with_brevo_fallback(_ADDR, "hi", "<p>x</p>", email_type="welcome")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "waiting.docs.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Brevo" in joined


@pytest.mark.asyncio
async def test_brevo_failure_then_zoho_success_never_logs_the_address_or_exception(caplog):
    svc = _make_service()
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError(f"550 mailbox {_ADDR} rejected"))
    svc.zoho_email_service.send_email = AsyncMock(return_value=None)
    p1, p2, p3, p4 = _patch_email_infra(client)
    with p1, p2, p3, p4, caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        await svc._send_with_brevo_fallback(_ADDR, "hi", "<p>x</p>", email_type="welcome")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "waiting.docs.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Brevo" in joined and "Zoho" in joined


@pytest.mark.asyncio
async def test_both_providers_failing_never_logs_the_address_or_exception_text(caplog):
    svc = _make_service()
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError(f"550 mailbox {_ADDR} rejected"))
    svc.zoho_email_service.send_email = AsyncMock(
        side_effect=RuntimeError(f"SMTP 421 {_ADDR} greylisted")
    )
    p1, p2, p3, p4 = _patch_email_infra(client)
    with (
        p1,
        p2,
        p3,
        p4,
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
        pytest.raises(RuntimeError),
    ):
        await svc._send_with_brevo_fallback(_ADDR, "hi", "<p>x</p>", email_type="welcome")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "waiting.docs.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Both Brevo and Zoho failed" in joined
    # Non-PII diagnostic text survives — only the address-shaped token in
    # the exception message is redacted, not the whole string.
    assert "greylisted" in joined


# --- INNOCENCE: non-PII diagnostic content survives ---


@pytest.mark.asyncio
async def test_innocence_brevo_failure_keeps_the_non_pii_diagnostic_text(caplog):
    svc = _make_service()
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError("connection reset by peer"))
    svc.zoho_email_service.send_email = AsyncMock(return_value=None)
    p1, p2, p3, p4 = _patch_email_infra(client)
    with p1, p2, p3, p4, caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        await svc._send_with_brevo_fallback(_ADDR, "hi", "<p>x</p>", email_type="welcome")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "connection reset by peer" in joined
