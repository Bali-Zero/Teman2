"""PR 2a — the CRM upload refuses a file the client already has.

Shape decided by Antonello (email 24 Sep 2026, GO once PR 7967 merged):
- a duplicate is the SAME FILE CONTENT (``content_hash``) for the SAME
  ``client_id`` — not name+size, not one document per document_type;
- the check runs BEFORE the Drive upload, so a refused file leaves no orphan;
- an active duplicate answers 409 with the id of the document already there;
- "active" is the same predicate as PR 7967 (``admin_document_not_deleted_clause``),
  so a document deleted by the team or by the client may be uploaded again.

Index 074 stays non-unique (application check; two simultaneous uploads of
the same file are an accepted race for now). The 61 duplicate rows already in
production are not touched here.
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from backend.services.crm.admin_document_visibility import admin_document_not_deleted_clause

FILE_B64 = "ZmlsZQ=="  # b"file"
FILE_MD5 = hashlib.md5(b"file").hexdigest()


class _Tx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _pool(dedup_hit, insert_id=701):
    """A pool whose fetchval answers the dedup SELECT, then the documents INSERT."""
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_Tx())
    conn.fetchrow.side_effect = [
        {
            "id": 1,
            "full_name": "Client One",
            "google_drive_folder_id": "root",
            "client_type": "individual",
            "phone": None,
            "phone_normalized": None,
        }
    ]

    async def fetchval(sql, *args):
        if "INSERT INTO documents" in sql:
            return insert_id
        if "content_hash" in sql:
            return dedup_hit
        raise AssertionError(f"unexpected fetchval: {sql[:80]}")

    conn.fetchval.side_effect = fetchval
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


def _drive():
    drive = AsyncMock()
    drive.get_folder_structure.return_value = {"folders": [{"id": "p", "name": "00_Profile"}]}
    drive.upload_file_to_folder.return_value = {"id": "drive-file", "webViewLink": "https://d/x"}
    return drive


async def _upload(pool, drive):
    from backend.app.routers.crm_enhanced_documents import (
        DocumentUploadBase64,
        upload_document_base64,
    )

    with (
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
        patch(
            "backend.app.routers.crm_enhanced_documents.ServiceAccountDriveService",
            return_value=drive,
        ) as drive_cls,
    ):
        try:
            return await upload_document_base64(
                client_id=1,
                data=DocumentUploadBase64(
                    file=FILE_B64,
                    file_name="scan.pdf",
                    document_type="passport",
                    document_category="personal",
                ),
                pool=pool,
                current_user={"email": "staff@example.test", "role": "admin"},
                background_tasks=BackgroundTasks(),
                access_already_verified=True,
            )
        finally:
            _upload.drive_cls = drive_cls


def _dedup_calls(conn):
    return [
        c
        for c in conn.fetchval.await_args_list
        if "content_hash" in c.args[0] and "INSERT INTO documents" not in c.args[0]
    ]


@pytest.mark.asyncio
async def test_upload_dedup_guilt_same_file_same_client_is_409_with_existing_id():
    pool, conn = _pool(dedup_hit=555)
    drive = _drive()

    with pytest.raises(HTTPException) as exc:
        await _upload(pool, drive)

    assert exc.value.status_code == 409
    assert "555" in str(exc.value.detail)
    # Refused BEFORE any Drive work: no service built, no file uploaded.
    _upload.drive_cls.assert_not_called()
    drive.upload_file_to_folder.assert_not_awaited()
    assert not any("INSERT INTO documents" in c.args[0] for c in conn.fetchval.await_args_list)


@pytest.mark.asyncio
async def test_upload_dedup_innocence_new_file_uploads_as_before():
    pool, conn = _pool(dedup_hit=None)
    drive = _drive()

    result = await _upload(pool, drive)

    assert result["success"] is True
    assert result["document_id"] == 701
    drive.upload_file_to_folder.assert_awaited_once()
    # Positive control: the dedup query really ran on this path.
    assert len(_dedup_calls(conn)) == 1


@pytest.mark.asyncio
async def test_upload_dedup_query_is_client_and_hash_scoped_and_skips_deleted_rows():
    pool, conn = _pool(dedup_hit=None)

    await _upload(pool, _drive())

    (call,) = _dedup_calls(conn)
    sql, args = call.args[0], call.args[1:]
    assert args == (1, FILE_MD5)
    assert "client_id = $1" in sql and "content_hash = $2" in sql
    # Same "active" predicate as PR 7967: a deleted document can be re-uploaded.
    assert admin_document_not_deleted_clause("d") in sql


def test_upload_dedup_predicate_positive_control():
    """The predicate the dedup reuses hides both deletions (status and deleted_at)."""
    clause = admin_document_not_deleted_clause("d")
    assert "d.deleted_at IS NULL" in clause
    assert "<> 'deleted'" in clause
