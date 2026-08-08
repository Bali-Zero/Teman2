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
    # completed_process_service.py imports both classes eagerly at module
    # scope (unlike automation.py's ProcessAutomationService, which does a
    # lazy in-method import) — patch the names bound in *this* module, not
    # their origin modules, or the real DriveFolderService()/ZohoEmailService()
    # constructors still run.
    with (
        patch("backend.services.crm.completed_process_service.ZohoEmailService"),
        patch("backend.services.crm.completed_process_service.DriveFolderService"),
    ):
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
