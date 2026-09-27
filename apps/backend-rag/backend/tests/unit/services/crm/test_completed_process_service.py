"""Unit tests for CompletedProcessService._upload_final_documents (2026-08-08).

Covers two things from the same change:

1. GUILT (double-count regression): _save_final_document_record used to run
   INSIDE the same try/except as the Drive upload call, writing to the
   never-provisioned `client_documents` table. When that DB write raised, a
   doc already appended to `uploaded` would ALSO land in `failed` via the
   outer except — double-counted in both lists. The write is gone now (the
   feature that would pass final_documents has zero live callers — see
   trigger_on_completed in crm_practices.py); the Drive-upload try/except is
   scoped to just the upload call, so a doc lands in exactly one of
   uploaded/failed, never both.

2. INNOCENCE: a successful Drive upload still lands in `uploaded` with the
   right shape, and no DB write is attempted (db_pool.acquire never called)
   — the dormant client_documents INSERT does not silently resurrect.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.crm.completed_process_service import CompletedProcessService


def _make_service() -> tuple[CompletedProcessService, MagicMock]:
    pool = MagicMock()
    # completed_process_service.py imports DriveFolderService eagerly at
    # module scope — patch the name bound in *this* module, not its origin
    # module, or the real DriveFolderService() constructor still runs.
    # (ZohoEmailService was removed 2026-09-27 — the Brevo→Zoho fallback
    # called it with the wrong keyword arguments since the call site was
    # first written, so it never actually worked; see TestSendWithBrevoFallback.)
    with patch("backend.services.crm.completed_process_service.DriveFolderService"):
        svc = CompletedProcessService(pool)
    svc.drive_service = AsyncMock()
    return svc, pool


@pytest.mark.asyncio
async def test_successful_upload_lands_in_uploaded_only_and_no_db_write() -> None:
    svc, pool = _make_service()
    svc.drive_service.upload_final_document.return_value = {
        "success": True,
        "file_id": "gd-1",
        "file_url": "https://drive.example/gd-1",
    }

    uploaded, failed = await svc._upload_final_documents(
        client_data={"id": 10, "drive_final_folder_id": "folder-1"},
        documents=[{"content": b"pdf", "filename": "doc.pdf"}],
    )

    assert uploaded == [{"filename": "doc.pdf", "file_url": "https://drive.example/gd-1"}]
    assert failed == []
    # No dormant client_documents write resurrected — the connection pool
    # is never touched by a successful upload.
    pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_upload_exception_lands_in_failed_only_not_also_uploaded() -> None:
    """GUILT: the exact double-count regression this change fixes. Before
    the fix, an exception raised past the Drive call (e.g. from the DB
    write that used to sit inside the same try block) would still find the
    doc already appended to `uploaded` from the line above it."""
    svc, _pool = _make_service()
    svc.drive_service.upload_final_document.side_effect = RuntimeError("drive down")

    uploaded, failed = await svc._upload_final_documents(
        client_data={"id": 10, "drive_final_folder_id": "folder-1"},
        documents=[{"content": b"pdf", "filename": "doc.pdf"}],
    )

    assert uploaded == []
    assert len(failed) == 1
    assert failed[0]["filename"] == "doc.pdf"
    assert "drive down" in failed[0]["reason"]


@pytest.mark.asyncio
async def test_drive_reports_failure_without_exception_lands_in_failed() -> None:
    svc, _pool = _make_service()
    svc.drive_service.upload_final_document.return_value = {
        "success": False,
        "error": "quota exceeded",
    }

    uploaded, failed = await svc._upload_final_documents(
        client_data={"id": 10, "drive_final_folder_id": "folder-1"},
        documents=[{"content": b"pdf", "filename": "doc.pdf"}],
    )

    assert uploaded == []
    assert failed == [{"filename": "doc.pdf", "reason": "drive_api: quota exceeded"}]


@pytest.mark.asyncio
async def test_no_final_folder_fails_all_documents_without_calling_drive() -> None:
    svc, _pool = _make_service()

    uploaded, failed = await svc._upload_final_documents(
        client_data={"id": 10, "drive_final_folder_id": None},
        documents=[{"content": b"pdf", "filename": "a.pdf"}, {"content": b"pdf", "filename": "b.pdf"}],
    )

    assert uploaded == []
    assert {f["filename"] for f in failed} == {"a.pdf", "b.pdf"}
    assert all(f["reason"] == "no_final_folder" for f in failed)
    svc.drive_service.upload_final_document.assert_not_called()


def test_save_final_document_record_no_longer_exists() -> None:
    """GUILT: the dormant client_documents INSERT must not be re-introduced
    under its old name — a future re-add should write to `documents` with
    an explicit column mapping, not silently resurrect this method."""
    assert not hasattr(CompletedProcessService, "_save_final_document_record")


# ---------------------------------------------------------------------------
# _send_with_brevo_fallback — Zoho fallback removal (2026-09-27)
# ---------------------------------------------------------------------------
#
# GUILT (the bug this fixes): the old "Zoho fallback" branch called
# ``ZohoEmailService.send_email(to_email=..., subject=..., body=...)`` —
# kwargs that never matched the real signature
# ``send_email(user_id, to, subject, content, ...)`` since the call site
# was first written (2026-02-22, before Brevo-primary even existed). Every
# double-failure was therefore recorded with ``provider="zoho"`` even
# though Zoho was never actually reachable through that call. The
# regression signal below is exactly that: a Brevo failure must now
# record ``provider="brevo"``, never ``"zoho"`` — a lone `create_autospec`
# on the (now-deleted) attribute can't express this anymore since the
# attribute itself is gone, which is the point: `test_no_zoho_attribute`
# guards against it coming back.


def test_no_zoho_attribute() -> None:
    """GUILT: ZohoEmailService must not be re-attached to this service —
    it was never a usable fallback (staff-personal OAuth mailbox, not a
    system identity) and every call site for it was broken since 2026-02-22."""
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
            "backend.services.crm.completed_process_service.get_email_client",
            AsyncMock(return_value=mock_client),
        ),
        patch(
            "backend.services.crm.completed_process_service.log_email_attempt",
            AsyncMock(return_value=42),
        ) ,
        patch(
            "backend.services.crm.completed_process_service.record_email_result",
            AsyncMock(),
        ) as mock_record,
        patch(
            "backend.services.crm.completed_process_service.notify_email_failure_critical",
            MagicMock(),
        ) as mock_notify,
        pytest.raises(RuntimeError, match="Brevo down"),
    ):
        await svc._send_with_brevo_fallback(
            "client@x.com",
            "Subject",
            "Body",
            email_type="completion_client",
            practice_id=1,
            client_id=10,
        )

    mock_record.assert_awaited_once()
    _args, kwargs = mock_record.call_args
    assert kwargs["status"] == "failed"
    assert kwargs["provider"] == "brevo"
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["email_type"] == "completion_client"


@pytest.mark.asyncio
async def test_brevo_success_records_sent_brevo_no_alert() -> None:
    svc, _pool = _make_service()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with (
        patch(
            "backend.services.crm.completed_process_service.get_email_client",
            AsyncMock(return_value=mock_client),
        ),
        patch(
            "backend.services.crm.completed_process_service.log_email_attempt",
            AsyncMock(return_value=42),
        ),
        patch(
            "backend.services.crm.completed_process_service.record_email_result",
            AsyncMock(),
        ) as mock_record,
        patch(
            "backend.services.crm.completed_process_service.notify_email_failure_critical",
            MagicMock(),
        ) as mock_notify,
    ):
        await svc._send_with_brevo_fallback(
            "client@x.com",
            "Subject",
            "Body",
            email_type="completion_client",
            practice_id=1,
            client_id=10,
        )

    mock_record.assert_awaited_once()
    _args, kwargs = mock_record.call_args
    assert kwargs["status"] == "sent"
    assert kwargs["provider"] == "brevo"
    mock_notify.assert_not_called()
