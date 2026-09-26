"""PII log hygiene for CompletedProcessService._send_with_brevo_fallback —
C2 (PR #7385 gate follow-up, deadline 2026-10-03), sibling of
test_waiting_documents_service_pii_logs.py. See that file's module
docstring for the full context (PR #7438's gate found this file's copy of
the same Brevo-then-Zoho pattern still open under C4).

This file's `except Exception as brevo_error:` block had an EXTRA defect
its sibling did not: it logged the raw exception OBJECT directly (`%s` on
`brevo_error`, i.e. `str(brevo_error)`) BEFORE `format_send_error` even
ran, so there was no formatted/scrubbed text to log in the first place —
covered by `test_brevo_failure_then_zoho_success_never_logs_the_address_or_exception`
below with an exception whose `str()` itself carries the address.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.crm.completed_process_service import CompletedProcessService

_LOGGER_NAME = "backend.services.crm.completed_process_service"
_ADDR = "completed.process.probe@example.com"


def _make_service() -> CompletedProcessService:
    pool = MagicMock()
    with (
        patch("backend.services.crm.completed_process_service.ZohoEmailService"),
        patch("backend.services.crm.completed_process_service.DriveFolderService"),
    ):
        svc = CompletedProcessService(pool)
    svc.zoho_email_service = AsyncMock()
    return svc


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def _patch_email_infra(brevo_client: object):
    return (
        patch(
            "backend.services.crm.completed_process_service.get_email_client",
            new=AsyncMock(return_value=brevo_client),
        ),
        patch(
            "backend.services.crm.completed_process_service.log_email_attempt",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "backend.services.crm.completed_process_service.record_email_result",
            new=AsyncMock(),
        ),
        patch(
            "backend.services.crm.completed_process_service.notify_email_failure_critical",
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
    assert "completed.process.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Brevo" in joined


@pytest.mark.asyncio
async def test_brevo_failure_then_zoho_success_never_logs_the_address_or_exception(caplog):
    """The raw-exception-object defect this file had (see module
    docstring): the exception's `str()` itself carries the address, and
    the old code logged it before any formatting/scrubbing ran."""
    svc = _make_service()
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError(f"550 mailbox {_ADDR} rejected"))
    svc.zoho_email_service.send_email = AsyncMock(return_value=None)
    p1, p2, p3, p4 = _patch_email_infra(client)
    with p1, p2, p3, p4, caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        await svc._send_with_brevo_fallback(_ADDR, "hi", "<p>x</p>", email_type="welcome")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _ADDR not in joined
    assert "completed.process.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Brevo" in joined and "Zoho" in joined


@pytest.mark.asyncio
async def test_both_providers_failing_never_logs_the_address(caplog):
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
    assert "completed.process.probe" not in joined
    assert redact_identifier_for_log(_ADDR) in joined
    assert "Both Brevo and Zoho failed" in joined
    assert "greylisted" in joined  # non-PII diagnostic text survives


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
