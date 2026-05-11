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
    assert PortalService._classify_document_category("family", "marriage certificate.pdf") == "family"
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
    assert PortalService._extract_drive_file_id("https://drive.google.com/open?id=file_456") == "file_456"
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
        },
    ]
    assert "d.document_type = $2" in mock_conn.fetch.call_args.args[0]
    assert mock_conn.fetch.call_args.args[1:] == (1, "passport")


@pytest.mark.asyncio
async def test_upload_document_success_stores_processed_document() -> None:
    service, mock_conn = _make_service_with_fetchrow(row=None)
    created_at = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    extracted_text = "Extracted passport text. " * 20
    mock_conn.fetchrow.side_effect = [
        None,
        {"email": "client@example.com", "full_name": "Client One", "assigned_to": "lead@example.com"},
        {
            "id": 88,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "received",
            "created_at": created_at,
            "expiry_date": None,
        },
    ]
    service._upload_to_drive = AsyncMock(return_value={
        "success": True,
        "file_id": "drive_file_88",
        "file_url": "https://drive.google.com/file/d/drive_file_88/view",
        "folder_path": "Zantara Portal Uploads/1_Client One/Passport",
    })

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
        patch("backend.services.portal._mixins.documents.spawn", side_effect=_close_spawn) as spawn_mock,
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
    assert mock_conn.fetchrow.call_args_list[2].args[-1] == "personal"


@pytest.mark.asyncio
async def test_upload_document_rejects_recent_duplicate() -> None:
    service, mock_conn = _make_service_with_fetchrow({
        "id": 10,
        "file_name": "passport.pdf",
        "created_at": datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
    })

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
    service._upload_to_drive = AsyncMock(return_value={
        "success": False,
        "file_id": None,
        "file_url": None,
        "folder_path": "",
    })

    with (
        patch(
            "backend.services.portal._mixins.documents.DocumentOCR.extract_text",
            new=AsyncMock(return_value={"success": False, "text": "", "pages": 0, "error": "OCR disabled"}),
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
    service, _mock_conn = _make_service_with_fetchrow({
        "id": 10,
        "file_name": "passport.pdf",
        "file_id": None,
        "file_url": "https://example.com/no-drive-id",
        "mime_type": "application/pdf",
        "status": "received",
    })

    result = await service.download_document(
        client_id=1,
        document_id=10,
        current_user={"client_id": 1, "email": "client@example.com"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_download_document_raises_when_drive_not_connected() -> None:
    service, _mock_conn = _make_service_with_fetchrow({
        "id": 10,
        "file_name": "passport.pdf",
        "file_id": "drive_file_10",
        "file_url": None,
        "mime_type": "application/pdf",
        "status": "received",
    })

    with patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls:
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
    service, _mock_conn = _make_service_with_fetchrow({
        "id": 10,
        "file_name": "passport.pdf",
        "file_id": "drive_file_10",
        "file_url": None,
        "mime_type": "application/pdf",
        "status": "received",
    })
    meta_response = MagicMock(status_code=200)
    meta_response.json.return_value = {"name": "passport-renamed.pdf", "mimeType": "application/pdf"}
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
    service, _mock_conn = _make_service_with_fetchrow({
        "id": 10,
        "file_name": "passport.pdf",
        "file_id": "drive_file_10",
        "file_url": None,
        "mime_type": "application/pdf",
        "status": "received",
    })
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
    drive_service.list_files = AsyncMock(return_value={
        "files": [
            {
                "id": "folder_1",
                "name": "Client Folder",
                "mimeType": "application/vnd.google-apps.folder",
            },
        ],
    })

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
    drive_service.upload_file_to_folder = AsyncMock(return_value={
        "id": "drive_file_10",
        "webViewLink": "https://drive.google.com/file/d/drive_file_10/view",
    })
    service._get_or_create_drive_folder = AsyncMock(
        side_effect=["root_folder", "client_folder", "type_folder"],
    )

    with patch("backend.services.integrations.google_drive_service.GoogleDriveService") as drive_cls:
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
    assert drive_service.upload_file_to_folder.call_args.kwargs["file_name"].endswith("_passport.pdf")
