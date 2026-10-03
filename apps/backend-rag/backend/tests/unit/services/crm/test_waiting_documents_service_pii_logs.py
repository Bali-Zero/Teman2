"""PII log hygiene for WaitingDocumentsService._send_with_brevo_fallback —
C2 (PR #7385 gate follow-up): the fresh gate on PR #7438 found this file's
"Email sent to %s via Brevo"/"...via Zoho fallback"/"Brevo failed for
%s..."/"Both Brevo and Zoho failed for %s: %s" lines still logged
`to_email` raw. #7438 fixed `router.py` and `email_audit.py`; this file's
copy of the same Brevo-then-Zoho pattern was named as C4's still-open
third group.

UPDATED 2026-09-27: the Zoho fallback itself was removed (it called
`ZohoEmailService.send_email` with kwargs that never matched its real
signature, so it never worked — see `_send_with_brevo_fallback`'s own
docstring). There is now exactly one failure path: Brevo fails -> log
(redacted) -> alert -> re-raise. The two former Zoho-branch guilt tests
collapse into one.

Guilt: Brevo success and Brevo failure are both exercised with an
address-bearing `to_email` and a provider exception whose own text echoes
an address back (the same "a bounce quotes the address" shape
`email_audit.py`'s own docstring names). Both halves are asserted: the raw
text must be absent AND its redacted stand-in must be present, so an
emptied log line does not pass as "fixed".

Innocence: the provider name ("Brevo") and non-PII diagnostic words
survive the scrub untouched.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.crm.waiting_documents_service import WaitingDocumentsService

_LOGGER_NAME = "backend.services.crm.waiting_documents_service"
_ADDR = "waiting.docs.probe@example.com"


# ---------------------------------------------------------------------------
# C2 (fresh gate on #7449, follow-up mandate): the fix above covers
# _send_with_brevo_fallback's own log lines. The CALLER,
# trigger_on_waiting_documents(), has its own independent success/except log
# lines that also print the raw client address today. Guilt+innocence here
# exercise the caller directly, mocking out its DB/email dependencies.
# ---------------------------------------------------------------------------


def _make_caller_service(client_data: dict, practice_data: dict) -> WaitingDocumentsService:
    svc = _make_service()
    svc._fetch_practice_data = AsyncMock(return_value=practice_data)
    svc._fetch_client_data = AsyncMock(return_value=client_data)
    svc._send_team_leader_notification = AsyncMock()
    return svc


_PRACTICE_NO_TEAM_LEADER = {"client_id": 1, "assigned_to": None, "created_by": None}


def _make_service() -> WaitingDocumentsService:
    pool = MagicMock()
    return WaitingDocumentsService(pool)


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
async def test_brevo_failure_never_logs_the_address_or_exception(caplog):
    svc = _make_service()
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError(f"550 mailbox {_ADDR} rejected"))
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
    assert "Brevo" in joined
    assert "no fallback provider" in joined


# --- INNOCENCE: non-PII diagnostic content survives ---


@pytest.mark.asyncio
async def test_innocence_brevo_failure_keeps_the_non_pii_diagnostic_text(caplog):
    svc = _make_service()
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError("connection reset by peer"))
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
    assert "connection reset by peer" in joined


# --- CALLER (trigger_on_waiting_documents) GUILT + INNOCENCE ---


@pytest.mark.asyncio
async def test_caller_success_log_does_not_leak_the_client_address(caplog):
    client_data = {"id": 1, "email": _ADDR, "full_name": "Alice"}
    svc = _make_caller_service(client_data, _PRACTICE_NO_TEAM_LEADER)
    svc._send_client_documents_request = AsyncMock(return_value=None)
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        result = await svc.trigger_on_waiting_documents(practice_id=99, triggered_by="staff@balizero.com")
    assert result["client_notified"] is True
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert redact_identifier_for_log(_ADDR) in joined


@pytest.mark.asyncio
async def test_caller_except_log_does_not_leak_the_address_or_raw_exception_text(caplog):
    client_data = {"id": 1, "email": _ADDR, "full_name": "Alice"}
    svc = _make_caller_service(client_data, _PRACTICE_NO_TEAM_LEADER)
    svc._send_client_documents_request = AsyncMock(
        side_effect=RuntimeError(f"550 mailbox {_ADDR} rejected")
    )
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        result = await svc.trigger_on_waiting_documents(practice_id=99, triggered_by="staff@balizero.com")
    assert result["client_notified"] is False
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "waiting.docs.probe" not in joined
    assert "rejected" in joined  # non-PII diagnostic text survives


@pytest.mark.asyncio
async def test_caller_innocence_keeps_the_non_pii_exception_text(caplog):
    client_data = {"id": 1, "email": _ADDR, "full_name": "Alice"}
    svc = _make_caller_service(client_data, _PRACTICE_NO_TEAM_LEADER)
    svc._send_client_documents_request = AsyncMock(
        side_effect=RuntimeError("connection reset by peer")
    )
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        await svc.trigger_on_waiting_documents(practice_id=99, triggered_by="staff@balizero.com")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "connection reset by peer" in joined
