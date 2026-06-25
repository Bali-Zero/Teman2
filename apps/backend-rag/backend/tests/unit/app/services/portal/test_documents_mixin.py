"""Unit tests for PortalService document mixin helpers and failure paths."""

import inspect
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.portal.portal_service import PortalService


class _AsyncCtx:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class UndefinedColumnError(Exception):
    sqlstate = "42703"


def _make_service_with_fetchrow(row: dict[str, Any] | None) -> tuple[PortalService, AsyncMock]:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = row
    mock_conn.transaction = MagicMock(return_value=_AsyncCtx())

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    return PortalService(mock_pool), mock_conn


def _close_spawn(awaitable: object) -> None:
    if inspect.iscoroutine(awaitable):
        awaitable.close()


def test_classify_document_category_keywords() -> None:
    assert PortalService._classify_document_category("kitas", "permit.pdf") == "immigration"
    assert PortalService._classify_document_category("passport", "scan.pdf") == "personal"
    assert PortalService._classify_document_category("company", "akta pendirian.pdf") == "pma"
    assert PortalService._classify_document_category("tax", "spt tahunan.pdf") == "tax"
    assert (
        PortalService._classify_document_category("family", "marriage certificate.pdf") == "family"
    )
    assert PortalService._classify_document_category("misc", "notes.txt") == "other"


def test_get_drive_folder_for_category() -> None:
    assert PortalService._get_drive_folder_for_category("IMMIGRATION") == "01_Immigration"
    assert PortalService._get_drive_folder_for_category("personal") == "00_Profile"
    assert PortalService._get_drive_folder_for_category("pma") == "02_Company"
    assert PortalService._get_drive_folder_for_category("tax") == "03_Tax"
    assert PortalService._get_drive_folder_for_category("family") == "04_Family"
    assert PortalService._get_drive_folder_for_category("unknown") == "99_Misc"
    assert PortalService._get_drive_folder_for_category("") == "99_Misc"


def test_extract_drive_file_id_variants() -> None:
    assert PortalService._extract_drive_file_id(None) is None
    assert (
        PortalService._extract_drive_file_id("https://drive.google.com/file/d/file_123/view")
        == "file_123"
    )
    assert (
        PortalService._extract_drive_file_id("https://drive.google.com/open?id=file_456")
        == "file_456"
    )
    assert PortalService._extract_drive_file_id("https://example.com/no-drive-id") is None


@pytest.mark.asyncio
async def test_get_documents_shapes_client_visible_rows() -> None:
    created_at = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    expiry_date = datetime(2027, 5, 1, tzinfo=timezone.utc)
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 10,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "received",
            "expiry_date": expiry_date,
            "file_url": None,
            "file_id": "drive_file_10",
            "file_size_kb": 42,
            "created_at": created_at,
            "practice_id": 3,
            "practice_name": "KITAS",
            "document_purpose": "Passport for KITAS renewal",
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.get_documents(
        client_id=1,
        document_type="passport",
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result == [
        {
            "id": 10,
            "type": "passport",
            "name": "passport.pdf",
            "status": "received",
            "expiry_date": expiry_date.isoformat(),
            "size_kb": 42,
            "practice_id": 3,
            "practice_name": "KITAS",
            "downloadable": True,
            "created_at": created_at.isoformat(),
            "purpose": "Passport for KITAS renewal",
        },
    ]
    # FASE 5: live documents only (soft-deleted hidden) + purpose surfaced
    assert "d.deleted_at IS NULL" in mock_conn.fetch.call_args.args[0]
    assert "d.document_purpose" in mock_conn.fetch.call_args.args[0]
    assert "d.document_type = $2" in mock_conn.fetch.call_args.args[0]
    assert mock_conn.fetch.call_args.args[1:] == (1, "passport")


@pytest.mark.asyncio
async def test_upload_document_success_stores_processed_document() -> None:
    service, mock_conn = _make_service_with_fetchrow(row=None)
    created_at = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    extracted_text = "Extracted passport text. " * 20
    mock_conn.fetchrow.side_effect = [
        None,
        {
            "email": "client@example.com",
            "full_name": "Client One",
            "assigned_to": "lead@example.com",
        },
        {
            "id": 88,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "received",
            "created_at": created_at,
            "expiry_date": None,
        },
    ]
    service._upload_to_drive = AsyncMock(
        return_value={
            "success": True,
            "file_id": "drive_file_88",
            "file_url": "https://drive.google.com/file/d/drive_file_88/view",
            "folder_path": "Zantara Portal Uploads/1_Client One/Passport",
        }
    )

    with (
        patch(
            "backend.services.portal._mixins.documents.DocumentOCR.extract_text",
            new=AsyncMock(return_value={"success": True, "text": extracted_text, "pages": 2}),
        ),
        patch(
            "backend.services.portal._mixins.documents.ExpiryDetector.detect_expiry",
            return_value={"expiry_date": "2027-05-10", "confidence": 0.8},
        ),
        patch(
            "backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder",
            return_value=object(),
        ),
        patch(
            "backend.services.portal._mixins.documents.spawn", side_effect=_close_spawn
        ) as spawn_mock,
    ):
        result = await service.upload_document(
            client_id=1,
            file_content=b"%PDF-1.4 clean passport",
            file_name="passport.pdf",
            document_type="passport",
            mime_type="application/pdf",
            current_user={"client_id": 1, "email": "client@example.com"},
        )

    assert result["id"] == 88
    assert result["type"] == "passport"
    assert result["name"] == "passport.pdf"
    assert result["expiry_date"] == "2027-05-10"
    assert result["processing"] == {
        "virus_clean": True,
        "ocr_pages": 2,
        "drive_uploaded": True,
    }
    assert result["extracted_text_preview"].endswith("...")
    assert service._metrics["uploads_total"] == 1
    assert service._metrics["drive_uploads"] == 1
    assert service._metrics["ocr_processed"] == 1
    assert spawn_mock.call_count == 2
    # doc_category is now second-to-last positional ($13); document_purpose is last ($14)
    assert mock_conn.fetchrow.call_args_list[2].args[-2] == "personal"
    assert mock_conn.fetchrow.call_args_list[2].args[-1] is None


@pytest.mark.asyncio
async def test_upload_document_persists_document_purpose() -> None:
    """FASE 5: a client-provided purpose note is stored as the last INSERT arg."""
    service, mock_conn = _make_service_with_fetchrow(row=None)
    created_at = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    mock_conn.fetchrow.side_effect = [
        None,
        {"email": "client@example.com", "full_name": "Client One", "assigned_to": None},
        {
            "id": 90,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "received",
            "created_at": created_at,
            "expiry_date": None,
        },
    ]
    service._upload_to_drive = AsyncMock(
        return_value={
            "success": True,
            "file_id": "drive_file_90",
            "file_url": "https://drive.google.com/file/d/drive_file_90/view",
            "folder_path": "Zantara Portal Uploads/1_Client One/Passport",
        }
    )

    with (
        patch(
            "backend.services.portal._mixins.documents.DocumentOCR.extract_text",
            new=AsyncMock(return_value={"success": True, "text": "txt", "pages": 1}),
        ),
        patch(
            "backend.services.portal._mixins.documents.ExpiryDetector.detect_expiry",
            return_value={"expiry_date": None, "confidence": 0.0},
        ),
        patch(
            "backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder",
            return_value=object(),
        ),
        patch("backend.services.portal._mixins.documents.spawn", side_effect=_close_spawn),
    ):
        result = await service.upload_document(
            client_id=1,
            file_content=b"%PDF-1.4 clean passport",
            file_name="passport.pdf",
            document_type="passport",
            mime_type="application/pdf",
            document_purpose="Required for KITAS renewal",
            current_user={"client_id": 1, "email": "client@example.com"},
        )

    assert result["id"] == 90
    # document_purpose is the last positional arg of the INSERT ($14)
    assert mock_conn.fetchrow.call_args_list[2].args[-1] == "Required for KITAS renewal"


@pytest.mark.asyncio
async def test_soft_delete_document_marks_deleted_and_returns_summary() -> None:
    """FASE 5: soft-delete sets deleted_at/deleted_by and records a timeline event."""
    service, mock_conn = _make_service_with_fetchrow(
        {"id": 10, "file_name": "passport.pdf", "document_type": "passport"}
    )

    result = await service.soft_delete_document(
        client_id=1,
        document_id=10,
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result == {
        "id": 10,
        "name": "passport.pdf",
        "type": "passport",
        "deleted": True,
    }
    update_sql = mock_conn.fetchrow.call_args.args[0]
    assert "UPDATE documents" in update_sql
    assert "deleted_at = NOW()" in update_sql
    assert "deleted_at IS NULL" in update_sql  # idempotent: only live rows
    # actor + ids passed through
    assert mock_conn.fetchrow.call_args.args[1:] == (10, 1, "client@example.com")
    # timeline event recorded with a CONSTRAINT-VALID event_type (Bug D).
    # 'document_removed' violates chk_timeline_event_type; must be 'status_change'.
    assert mock_conn.execute.await_count == 1
    assert "'status_change'" in mock_conn.execute.call_args.args[0]
    assert "document_removed" not in mock_conn.execute.call_args.args[0]


@pytest.mark.asyncio
async def test_soft_delete_document_returns_none_when_not_found() -> None:
    service, mock_conn = _make_service_with_fetchrow(row=None)

    result = await service.soft_delete_document(
        client_id=1,
        document_id=404,
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result is None
    # no timeline event when nothing was deleted
    assert mock_conn.execute.await_count == 0


@pytest.mark.asyncio
async def test_restore_document_clears_deleted_and_returns_summary() -> None:
    service, mock_conn = _make_service_with_fetchrow(
        {"id": 11, "file_name": "kitas.pdf", "document_type": "kitas"}
    )

    result = await service.restore_document(
        client_id=1,
        document_id=11,
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result == {
        "id": 11,
        "name": "kitas.pdf",
        "type": "kitas",
        "deleted": False,
    }
    update_sql = mock_conn.fetchrow.call_args.args[0]
    assert "deleted_at = NULL" in update_sql
    assert "deleted_at IS NOT NULL" in update_sql  # only restore actually-deleted rows
    assert mock_conn.fetchrow.call_args.args[1:] == (11, 1)
    assert mock_conn.execute.await_count == 1
    # Bug D: 'document_restored' violates chk_timeline_event_type; must be 'status_change'.
    assert "'status_change'" in mock_conn.execute.call_args.args[0]
    assert "document_restored" not in mock_conn.execute.call_args.args[0]


@pytest.mark.asyncio
async def test_restore_document_returns_none_when_not_deleted() -> None:
    service, mock_conn = _make_service_with_fetchrow(row=None)

    result = await service.restore_document(
        client_id=1,
        document_id=11,
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result is None
    assert mock_conn.execute.await_count == 0


@pytest.mark.asyncio
async def test_upload_document_rejects_recent_duplicate() -> None:
    service, mock_conn = _make_service_with_fetchrow(
        {
            "id": 10,
            "file_name": "passport.pdf",
            "created_at": datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
        }
    )

    with pytest.raises(ValueError, match="File already uploaded recently"):
        await service.upload_document(
            client_id=1,
            file_content=b"%PDF-1.4 clean passport",
            file_name="passport.pdf",
            document_type="passport",
            mime_type="application/pdf",
            current_user={"client_id": 1, "email": "client@example.com"},
        )

    assert mock_conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_upload_document_rejects_inaccessible_practice() -> None:
    service, mock_conn = _make_service_with_fetchrow(row=None)
    mock_conn.fetchrow.side_effect = [None, None]

    with pytest.raises(ValueError, match="Practice not found or not accessible"):
        await service.upload_document(
            client_id=1,
            file_content=b"%PDF-1.4 clean passport",
            file_name="passport.pdf",
            document_type="passport",
            mime_type="application/pdf",
            practice_id=99,
            current_user={"client_id": 1, "email": "client@example.com"},
        )


@pytest.mark.asyncio
async def test_upload_document_rejects_missing_client() -> None:
    service, mock_conn = _make_service_with_fetchrow(row=None)
    mock_conn.fetchrow.side_effect = [None, None]

    with pytest.raises(ValueError, match="Client 1 not found"):
        await service.upload_document(
            client_id=1,
            file_content=b"%PDF-1.4 clean passport",
            file_name="passport.pdf",
            document_type="passport",
            mime_type="application/pdf",
            current_user={"client_id": 1, "email": "client@example.com"},
        )


@pytest.mark.asyncio
async def test_upload_document_falls_back_when_insert_columns_are_missing() -> None:
    service, mock_conn = _make_service_with_fetchrow(row=None)
    created_at = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    mock_conn.fetchrow.side_effect = [
        None,
        {"email": "client@example.com", "full_name": "Client One", "assigned_to": None},
        UndefinedColumnError("document_category missing"),
        {
            "id": 89,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "received",
            "created_at": created_at,
            "expiry_date": None,
        },
    ]
    service._upload_to_drive = AsyncMock(
        return_value={
            "success": False,
            "file_id": None,
            "file_url": None,
            "folder_path": "",
        }
    )

    with (
        patch(
            "backend.services.portal._mixins.documents.DocumentOCR.extract_text",
            new=AsyncMock(
                return_value={"success": False, "text": "", "pages": 0, "error": "OCR disabled"}
            ),
        ),
        patch(
            "backend.services.portal._mixins.documents.ExpiryDetector.detect_expiry",
            return_value={"expiry_date": None, "confidence": 0.0},
        ),
        patch("backend.services.portal._mixins.documents.spawn", side_effect=_close_spawn),
    ):
        result = await service.upload_document(
            client_id=1,
            file_content=b"%PDF-1.4 clean passport",
            file_name="passport.pdf",
            document_type="passport",
            mime_type="application/pdf",
            current_user={"client_id": 1, "email": "client@example.com"},
        )

    assert result["id"] == 89
    assert result["processing"]["drive_uploaded"] is False
    assert service._metrics["uploads_total"] == 1
    assert service._metrics["drive_uploads"] == 0
    assert service._metrics["ocr_processed"] == 0


@pytest.mark.asyncio
async def test_download_document_returns_none_when_missing() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)

    result = await service.download_document(
        client_id=1,
        document_id=404,
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_download_document_returns_none_without_drive_file_id() -> None:
    service, _mock_conn = _make_service_with_fetchrow(
        {
            "id": 10,
            "file_name": "passport.pdf",
            "file_id": None,
            "file_url": "https://example.com/no-drive-id",
            "mime_type": "application/pdf",
            "status": "received",
        }
    )

    result = await service.download_document(
        client_id=1,
        document_id=10,
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_download_document_raises_when_drive_not_connected() -> None:
    service, _mock_conn = _make_service_with_fetchrow(
        {
            "id": 10,
            "file_name": "passport.pdf",
            "file_id": "drive_file_10",
            "file_url": None,
            "mime_type": "application/pdf",
            "status": "received",
        }
    )

    with patch(
        "backend.services.integrations.google_drive_service.GoogleDriveService"
    ) as drive_cls:
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="Google Drive is not connected"):
            await service.download_document(
                client_id=1,
                document_id=10,
                current_user={"client_id": 1, "email": "client@example.com"},
            )


@pytest.mark.asyncio
async def test_download_document_streams_drive_file() -> None:
    service, _mock_conn = _make_service_with_fetchrow(
        {
            "id": 10,
            "file_name": "passport.pdf",
            "file_id": "drive_file_10",
            "file_url": None,
            "mime_type": "application/pdf",
            "status": "received",
        }
    )
    meta_response = MagicMock(status_code=200)
    meta_response.json.return_value = {
        "name": "passport-renamed.pdf",
        "mimeType": "application/pdf",
    }
    download_response = MagicMock(status_code=200, content=b"PDF_BYTES")
    async_http = MagicMock()
    async_http.get = AsyncMock(side_effect=[meta_response, download_response])

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("httpx.AsyncClient") as client_cls,
    ):
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value="access-token")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=async_http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.download_document(
            client_id=1,
            document_id=10,
            current_user={"client_id": 1, "email": "client@example.com"},
        )

    assert result == {
        "content": b"PDF_BYTES",
        "file_name": "passport-renamed.pdf",
        "mime_type": "application/pdf",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("meta_status", "download_status", "expected_error"),
    [
        (404, None, None),
        (503, None, "Failed to fetch document metadata"),
        (200, 404, None),
        (200, 500, "Failed to download document"),
    ],
)
async def test_download_document_handles_drive_failures(
    meta_status: int,
    download_status: int | None,
    expected_error: str | None,
) -> None:
    service, _mock_conn = _make_service_with_fetchrow(
        {
            "id": 10,
            "file_name": "passport.pdf",
            "file_id": "drive_file_10",
            "file_url": None,
            "mime_type": "application/pdf",
            "status": "received",
        }
    )
    meta_response = MagicMock(status_code=meta_status)
    meta_response.json.return_value = {"name": "passport.pdf", "mimeType": "application/pdf"}
    responses = [meta_response]
    if download_status is not None:
        responses.append(MagicMock(status_code=download_status, content=b""))
    async_http = MagicMock()
    async_http.get = AsyncMock(side_effect=responses)

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("httpx.AsyncClient") as client_cls,
    ):
        drive_cls.SYSTEM_USER_ID = "SYSTEM"
        drive_cls.return_value.get_valid_token = AsyncMock(return_value="access-token")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=async_http)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        if expected_error:
            with pytest.raises(RuntimeError, match=expected_error):
                await service.download_document(
                    client_id=1,
                    document_id=10,
                    current_user={"client_id": 1, "email": "client@example.com"},
                )
        else:
            result = await service.download_document(
                client_id=1,
                document_id=10,
                current_user={"client_id": 1, "email": "client@example.com"},
            )
            assert result is None


@pytest.mark.asyncio
async def test_get_or_create_drive_folder_returns_existing_folder() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)
    drive_service = MagicMock()
    drive_service.list_files = AsyncMock(
        return_value={
            "files": [
                {
                    "id": "folder_1",
                    "name": "Client Folder",
                    "mimeType": "application/vnd.google-apps.folder",
                },
            ],
        }
    )

    result = await service._get_or_create_drive_folder(
        drive_service,
        user_id="SYSTEM",
        folder_name="Client Folder",
        parent_id="root",
    )

    assert result == "folder_1"
    drive_service.create_folder.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_drive_folder_creates_missing_folder() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)
    drive_service = MagicMock()
    drive_service.list_files = AsyncMock(return_value={"files": []})
    drive_service.create_folder = AsyncMock(return_value={"id": "folder_new"})

    result = await service._get_or_create_drive_folder(
        drive_service,
        user_id="SYSTEM",
        folder_name="Client Folder",
        parent_id="root",
    )

    assert result == "folder_new"
    drive_service.create_folder.assert_awaited_once_with(
        user_id="SYSTEM",
        name="Client Folder",
        parent_id="root",
    )


@pytest.mark.asyncio
async def test_get_or_create_drive_folder_returns_none_on_error() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)
    drive_service = MagicMock()
    drive_service.list_files = AsyncMock(side_effect=RuntimeError("drive down"))

    result = await service._get_or_create_drive_folder(
        drive_service,
        user_id="SYSTEM",
        folder_name="Client Folder",
        parent_id="root",
    )

    assert result is None


@pytest.mark.asyncio
async def test_upload_to_drive_returns_error_when_no_auth_available() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)
    result: dict[str, Any] = {}

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("backend.services.integrations.team_drive_service.TeamDriveService") as team_cls,
    ):
        drive_cls.return_value.is_configured.return_value = False
        team_cls.return_value.service_account_available = False

        result = await service._upload_to_drive(
            conn=AsyncMock(),
            client_id=1,
            client_name="Client One",
            document_type="passport",
            file_content=b"PDF",
            file_name="passport.pdf",
            mime_type="application/pdf",
        )

    assert result["success"] is False
    assert result["error"] == "No Drive authentication available"


@pytest.mark.asyncio
async def test_upload_to_drive_falls_back_when_oauth_token_missing() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("backend.services.integrations.team_drive_service.TeamDriveService") as team_cls,
    ):
        drive_cls.return_value.is_configured.return_value = True
        drive_cls.return_value.get_valid_token = AsyncMock(return_value=None)
        team_cls.return_value.service_account_available = False

        result = await service._upload_to_drive(
            conn=AsyncMock(),
            client_id=1,
            client_name="Client One",
            document_type="passport",
            file_content=b"PDF",
            file_name="passport.pdf",
            mime_type="application/pdf",
        )

    assert result["success"] is False
    assert result["error"] == "No Drive authentication available"


@pytest.mark.asyncio
async def test_upload_to_drive_uses_service_account_fallback() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)
    expected = {"success": True, "method": "service_account"}
    service._upload_with_service_account = AsyncMock(return_value=expected)

    with (
        patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls,
        patch("backend.services.integrations.team_drive_service.TeamDriveService") as team_cls,
    ):
        drive_cls.return_value.is_configured.return_value = False
        team_cls.return_value.service_account_available = True

        result = await service._upload_to_drive(
            conn=AsyncMock(),
            client_id=1,
            client_name="Client One",
            document_type="passport",
            file_content=b"PDF",
            file_name="passport.pdf",
            mime_type="application/pdf",
        )

    assert result == expected
    service._upload_with_service_account.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_to_drive_oauth_success() -> None:
    service, _mock_conn = _make_service_with_fetchrow(row=None)
    drive_service = MagicMock()
    drive_service.is_configured.return_value = True
    drive_service.get_valid_token = AsyncMock(return_value="access-token")
    drive_service.upload_file_to_folder = AsyncMock(
        return_value={
            "id": "drive_file_10",
            "webViewLink": "https://drive.google.com/file/d/drive_file_10/view",
        }
    )
    service._get_or_create_drive_folder = AsyncMock(
        side_effect=["root_folder", "client_folder", "type_folder"],
    )

    with patch(
        "backend.services.integrations.google_drive_service.GoogleDriveService"
    ) as drive_cls:
        drive_cls.return_value = drive_service

        result = await service._upload_to_drive(
            conn=AsyncMock(),
            client_id=1,
            client_name="Client One!",
            document_type="passport_scan",
            file_content=b"PDF",
            file_name="passport.pdf",
            mime_type="application/pdf",
        )

    assert result["success"] is True
    assert result["file_id"] == "drive_file_10"
    assert result["file_url"] == "https://drive.google.com/file/d/drive_file_10/view"
    assert result["folder_path"] == "Zantara Portal Uploads/1_Client One/Passport Scan"
    drive_service.upload_file_to_folder.assert_awaited_once()
    assert drive_service.upload_file_to_folder.call_args.kwargs["folder_id"] == "type_folder"
    assert drive_service.upload_file_to_folder.call_args.kwargs["file_name"].endswith(
        "_passport.pdf"
    )


# =============================================================================
# BUG B REGRESSION — TeamDriveService.service_account_available (Bug-A worktree)
# =============================================================================


def test_team_drive_service_has_service_account_available_attribute() -> None:
    """TeamDriveService must expose service_account_available without raising.

    Before the fix, accessing team_drive.service_account_available raised
    AttributeError → the upload transaction was aborted → 500 on every request
    that fell through to the service-account path.
    """
    from unittest.mock import MagicMock

    from backend.services.integrations.team_drive_service import TeamDriveService

    # Constructing TeamDriveService requires a db_pool but we only test the
    # property, so we stub the internal managers to avoid real I/O.
    with patch(
        "backend.services.integrations.team_drive_service.DriveAuthManager"
    ) as auth_cls, patch(
        "backend.services.integrations.team_drive_service.DriveOperationsManager"
    ), patch(
        "backend.services.integrations.team_drive_service.DrivePermissionsManager"
    ), patch(
        "backend.services.integrations.team_drive_service.DriveAuditLogger"
    ), patch(
        "httpx.AsyncClient"
    ):
        service = TeamDriveService(db_pool=MagicMock())

        # Case 1: auth manager has no service_account_available attr → False
        auth_cls.return_value = MagicMock(spec=[])  # no extra attrs
        service.auth = auth_cls.return_value
        assert service.service_account_available is False

        # Case 2: auth manager exposes service_account_available = True
        auth_manager_with_sa = MagicMock()
        auth_manager_with_sa.service_account_available = True
        service.auth = auth_manager_with_sa
        assert service.service_account_available is True

        # Case 3: auth manager exposes service_account_available = False
        auth_manager_without_sa = MagicMock()
        auth_manager_without_sa.service_account_available = False
        service.auth = auth_manager_without_sa
        assert service.service_account_available is False

        # Case 4: auth is None → safe fallback
        service.auth = None
        assert service.service_account_available is False


@pytest.mark.asyncio
async def test_upload_to_drive_no_auth_does_not_raise_attribute_error() -> None:
    """_upload_to_drive must return an error dict, never raise AttributeError.

    The AttributeError was triggered by accessing team_drive.service_account_available
    before the property was added.  This test guards against the regression.
    """
    service, _mock_conn = _make_service_with_fetchrow(row=None)

    with (
        patch(
            "backend.services.integrations.google_drive_service.GoogleDriveService"
        ) as drive_cls,
        patch(
            "backend.services.integrations.team_drive_service.TeamDriveService"
        ) as team_cls,
    ):
        drive_cls.return_value.is_configured.return_value = False
        # Critically: ensure service_account_available is defined and False
        team_cls.return_value.service_account_available = False

        # Must NOT raise — must return a well-formed error dict
        result = await service._upload_to_drive(
            conn=AsyncMock(),
            client_id=1,
            client_name="Client One",
            document_type="passport",
            file_content=b"PDF",
            file_name="passport.pdf",
            mime_type="application/pdf",
        )

    assert result["success"] is False
    assert result["error"] == "No Drive authentication available"
    assert result["file_id"] is None
    assert result["file_url"] is None


# ---------------------------------------------------------------------------
# Bug D — soft-delete must NOT share a transaction with the timeline INSERT, and
# the timeline event_type must be a value allowed by chk_timeline_event_type.
# Previously soft_delete_document INSERTed event_type='document_removed' inside the
# SAME conn.transaction() as the UPDATE; the CHECK violation aborted the txn and
# silently rolled the soft-delete back while returning 200 "deleted: true".
# ---------------------------------------------------------------------------


def _make_two_conn_service(row: dict[str, Any] | None):
    """Service whose pool hands out a DISTINCT conn on each acquire(), so we can
    assert the UPDATE and the timeline INSERT run on SEPARATE connections."""
    update_conn = AsyncMock()
    update_conn.fetchrow.return_value = row
    update_conn.transaction = MagicMock(return_value=_AsyncCtx())

    audit_conn = AsyncMock()
    audit_conn.transaction = MagicMock(return_value=_AsyncCtx())

    conns = iter([update_conn, audit_conn])

    def _acquire(*_a: object, **_k: object):
        ctx = MagicMock()
        chosen = next(conns)
        ctx.__aenter__ = AsyncMock(return_value=chosen)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    mock_pool = MagicMock()
    mock_pool.acquire.side_effect = _acquire
    return PortalService(mock_pool), update_conn, audit_conn


@pytest.mark.asyncio
async def test_soft_delete_uses_valid_event_type_on_separate_conn() -> None:
    row = {"id": 7, "file_name": "akta.pdf", "document_type": "company"}
    service, update_conn, audit_conn = _make_two_conn_service(row)

    result = await service.soft_delete_document(
        client_id=1, document_id=7, current_user={"client_id": 1, "email": "c@x.com"}
    )

    assert result is not None and result["deleted"] is True
    # The UPDATE ran inside a transaction on the first connection.
    update_conn.transaction.assert_called_once()
    # The timeline INSERT ran on a DIFFERENT connection (audit_conn) and was NOT
    # wrapped in update_conn's transaction — so it can never roll back the delete.
    audit_conn.execute.assert_awaited_once()
    sql = audit_conn.execute.call_args.args[0]
    assert "'status_change'" in sql, "timeline event_type must be the allowed value"
    assert "document_removed" not in sql, "must not use the constraint-violating value"
    # The delete connection must NOT have run the timeline INSERT.
    for call in update_conn.execute.await_args_list:
        assert "timeline_events" not in (call.args[0] if call.args else "")


@pytest.mark.asyncio
async def test_restore_uses_valid_event_type_on_separate_conn() -> None:
    row = {"id": 7, "file_name": "akta.pdf", "document_type": "company"}
    service, update_conn, audit_conn = _make_two_conn_service(row)

    result = await service.restore_document(
        client_id=1, document_id=7, current_user={"client_id": 1, "email": "c@x.com"}
    )

    assert result is not None and result["deleted"] is False
    audit_conn.execute.assert_awaited_once()
    sql = audit_conn.execute.call_args.args[0]
    assert "'status_change'" in sql
    assert "document_restored" not in sql


@pytest.mark.asyncio
async def test_timeline_failure_does_not_break_soft_delete() -> None:
    """If the audit-log INSERT fails, the soft-delete result still succeeds —
    proving the audit log can no longer roll back the mutation."""
    row = {"id": 7, "file_name": "akta.pdf", "document_type": "company"}
    service, _update_conn, audit_conn = _make_two_conn_service(row)
    audit_conn.execute.side_effect = RuntimeError("timeline boom")

    result = await service.soft_delete_document(
        client_id=1, document_id=7, current_user={"client_id": 1, "email": "c@x.com"}
    )

    assert result is not None and result["deleted"] is True
