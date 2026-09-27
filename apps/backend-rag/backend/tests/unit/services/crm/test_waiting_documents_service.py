"""Unit tests for WaitingDocumentsService._send_with_brevo_fallback (2026-09-27).

GUILT (the bug this fixes): the "Zoho fallback" branch called
``ZohoEmailService.send_email(to_email=..., subject=..., body=...)`` — kwargs
that never matched the real signature
``send_email(user_id, to, subject, content, ...)`` since this call site was
first written. Every double-failure was recorded with
``provider="zoho"`` even though Zoho was never actually reachable through
that call — Brevo failing here silently lost the email while looking
"handled". The fix removes the dead fallback: a Brevo failure now records
``provider="brevo"`` and pages the owner immediately.

No test file existed for this service before this change (confirmed via
`grep -rl waiting_documents_service backend/tests` on main — only
test_automation.py referenced the class name in a comment about a *removed*
duplicate).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.crm.waiting_documents_service import WaitingDocumentsService


def _make_service() -> tuple[WaitingDocumentsService, MagicMock]:
    pool = MagicMock()
    svc = WaitingDocumentsService(pool)
    return svc, pool


def test_no_zoho_attribute() -> None:
    """GUILT: ZohoEmailService must not be re-attached to this service —
    it was never a usable fallback (staff-personal OAuth mailbox, not a
    system identity) and the call site for it was broken from the start."""
    svc, _pool = _make_service()
    assert not hasattr(svc, "zoho_email_service")


@pytest.mark.asyncio
async def test_brevo_failure_records_failed_brevo_and_alerts() -> None:
    """GUILT: before the fix this row would land as
    ``status='failed', provider='zoho'`` (a wasted, always-broken Zoho
    attempt) instead of ``provider='brevo'`` with an immediate alert."""
    svc, _pool = _make_service()

    mock_client = AsyncMock()
    mock_client.post.side_effect = RuntimeError("Brevo down")

    with (
        patch(
            "backend.services.crm.waiting_documents_service.get_email_client",
            AsyncMock(return_value=mock_client),
        ),
        patch(
            "backend.services.crm.waiting_documents_service.log_email_attempt",
            AsyncMock(return_value=42),
        ),
        patch(
            "backend.services.crm.waiting_documents_service.record_email_result",
            AsyncMock(),
        ) as mock_record,
        patch(
            "backend.services.crm.waiting_documents_service.notify_email_failure_critical",
            MagicMock(),
        ) as mock_notify,
        pytest.raises(RuntimeError, match="Brevo down"),
    ):
        await svc._send_with_brevo_fallback(
            "client@x.com",
            "Subject",
            "Body",
            email_type="waiting_docs_client",
            practice_id=1,
            client_id=10,
        )

    mock_record.assert_awaited_once()
    _args, kwargs = mock_record.call_args
    assert kwargs["status"] == "failed"
    assert kwargs["provider"] == "brevo"
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["email_type"] == "waiting_docs_client"


@pytest.mark.asyncio
async def test_brevo_success_records_sent_brevo_no_alert() -> None:
    svc, _pool = _make_service()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with (
        patch(
            "backend.services.crm.waiting_documents_service.get_email_client",
            AsyncMock(return_value=mock_client),
        ),
        patch(
            "backend.services.crm.waiting_documents_service.log_email_attempt",
            AsyncMock(return_value=42),
        ),
        patch(
            "backend.services.crm.waiting_documents_service.record_email_result",
            AsyncMock(),
        ) as mock_record,
        patch(
            "backend.services.crm.waiting_documents_service.notify_email_failure_critical",
            MagicMock(),
        ) as mock_notify,
    ):
        await svc._send_with_brevo_fallback(
            "client@x.com",
            "Subject",
            "Body",
            email_type="waiting_docs_client",
            practice_id=1,
            client_id=10,
        )

    mock_record.assert_awaited_once()
    _args, kwargs = mock_record.call_args
    assert kwargs["status"] == "sent"
    assert kwargs["provider"] == "brevo"
    mock_notify.assert_not_called()
