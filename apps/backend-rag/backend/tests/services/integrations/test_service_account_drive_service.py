from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from backend.services.integrations.service_account_drive_service import (
    DriveArchiveIntegrityError,
    ServiceAccountDriveService,
)


def test_constructor_honors_explicit_legal_archive_root_and_delegated_user() -> None:
    """A legal archive must not fall back to the generic CRM Drive root."""
    base_credentials = MagicMock()
    delegated_credentials = MagicMock()
    base_credentials.with_subject.return_value = delegated_credentials
    configured_settings = SimpleNamespace(
        google_credentials_json='{"type": "service_account"}',
        google_drive_root_folder_id="generic-root",
        gdrive_individuals_folder_id=None,
        gdrive_companies_folder_id=None,
    )

    with (
        patch(
            "backend.services.integrations.service_account_drive_service.settings",
            configured_settings,
        ),
        patch(
            "backend.services.integrations.service_account_drive_service.service_account"
            ".Credentials.from_service_account_info",
            return_value=base_credentials,
        ) as credential_factory,
        patch("backend.services.integrations.service_account_drive_service.build") as build_api,
        patch.object(ServiceAccountDriveService, "_validate_configured_folders"),
    ):
        service = ServiceAccountDriveService(
            root_folder_id="legal-root",
            delegated_user="legal-archive@example.com",
        )

    assert service.root_folder_id == "legal-root"
    assert service.delegated_user == "legal-archive@example.com"
    credential_factory.assert_called_once()
    base_credentials.with_subject.assert_called_once_with("legal-archive@example.com")
    build_api.assert_called_once_with("drive", "v3", credentials=delegated_credentials)


def _service_without_init(drive_api: Any) -> ServiceAccountDriveService:
    service = ServiceAccountDriveService.__new__(ServiceAccountDriveService)
    service.service = drive_api
    return service


async def test_get_file_metadata_detailed_requests_guardian_evidence_fields() -> None:
    request = MagicMock()
    request.execute.return_value = {
        "id": "file-123",
        "name": "Passport.pdf",
        "owners": [{"emailAddress": "zero@balizero.com"}],
    }
    files_resource = MagicMock()
    files_resource.get.return_value = request
    drive_api = MagicMock()
    drive_api.files.return_value = files_resource

    service = _service_without_init(drive_api)
    result = await service.get_file_metadata_detailed("file-123")

    assert result["id"] == "file-123"
    files_resource.get.assert_called_once()
    kwargs = files_resource.get.call_args.kwargs
    assert kwargs["fileId"] == "file-123"
    assert kwargs["supportsAllDrives"] is True
    fields = kwargs["fields"]
    for expected in (
        "id",
        "name",
        "mimeType",
        "owners(emailAddress,displayName)",
        "parents",
        "driveId",
        "shortcutDetails",
        "capabilities(canCopy,canDownload,canEdit,",
        "canMoveItemIntoTeamDrive",
        "canMoveItemOutOfDrive",
        "canMoveItemWithinDrive)",
    ):
        assert expected in fields


async def test_list_changes_since_returns_next_page_token_when_page_bound() -> None:
    first_request = MagicMock()
    first_request.execute.return_value = {
        "changes": [
            {
                "fileId": "file-1",
                "file": {"id": "file-1", "name": "passport.pdf"},
                "removed": False,
            }
        ],
        "nextPageToken": "page-2",
    }
    changes_resource = MagicMock()
    changes_resource.list.return_value = first_request
    drive_api = MagicMock()
    drive_api.changes.return_value = changes_resource

    service = _service_without_init(drive_api)
    result = await service.list_changes_since("page-1", max_pages=1, page_size=10)

    assert result["changes"][0]["fileId"] == "file-1"
    assert result["new_page_token"] == "page-2"
    assert result["more_pages"] is True
    assert result["pages_fetched"] == 1
    changes_resource.list.assert_called_once()
    assert changes_resource.list.call_args.kwargs["pageSize"] == 10


async def test_list_changes_since_uses_new_start_page_token_when_complete() -> None:
    first_request = MagicMock()
    first_request.execute.return_value = {
        "changes": [{"fileId": "file-1"}],
        "nextPageToken": "page-2",
    }
    second_request = MagicMock()
    second_request.execute.return_value = {
        "changes": [{"fileId": "file-2"}],
        "newStartPageToken": "fresh-start",
    }
    changes_resource = MagicMock()
    changes_resource.list.side_effect = [first_request, second_request]
    drive_api = MagicMock()
    drive_api.changes.return_value = changes_resource

    service = _service_without_init(drive_api)
    result = await service.list_changes_since("page-1", page_size=25)

    assert [change["fileId"] for change in result["changes"]] == ["file-1", "file-2"]
    assert result["new_page_token"] == "fresh-start"
    assert result["more_pages"] is False
    assert result["pages_fetched"] == 2


async def test_create_folder_uses_root_folder_when_parent_not_supplied() -> None:
    request = MagicMock()
    request.execute.return_value = {
        "id": "folder-1",
        "name": "Client",
        "webViewLink": "https://drive/folder-1",
    }
    files_resource = MagicMock()
    files_resource.create.return_value = request
    drive_api = MagicMock()
    drive_api.files.return_value = files_resource

    service = _service_without_init(drive_api)
    service.root_folder_id = "root-folder"

    result = await service.create_folder("Client")

    assert result["id"] == "folder-1"
    files_resource.create.assert_called_once_with(
        body={
            "name": "Client",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["root-folder"],
        },
        fields="id, name, webViewLink",
        supportsAllDrives=True,
    )


async def test_find_file_uses_an_exact_non_folder_query_and_requests_checksum() -> None:
    request = MagicMock()
    request.execute.return_value = {
        "files": [
            {
                "id": "perpres-43",
                "name": "Perpres_no_43_2011.pdf",
                "md5Checksum": "checksum",
            }
        ]
    }
    files_resource = MagicMock()
    files_resource.list.return_value = request
    drive_api = MagicMock()
    drive_api.files.return_value = files_resource
    service = _service_without_init(drive_api)

    result = await service.find_file("Perpres_no_43_2011.pdf", "legal-root")

    assert result is not None
    assert result["id"] == "perpres-43"
    kwargs = files_resource.list.call_args.kwargs
    assert "name = 'Perpres_no_43_2011.pdf'" in kwargs["q"]
    assert "mimeType != 'application/vnd.google-apps.folder'" in kwargs["q"]
    assert "'legal-root' in parents" in kwargs["q"]
    assert kwargs["fields"] == "files(id, name, webViewLink, size, md5Checksum)"


async def test_get_folder_structure_counts_subfolders_files_and_size() -> None:
    root_request = MagicMock()
    root_request.execute.return_value = {"id": "root", "name": "Root"}
    folders_request = MagicMock()
    folders_request.execute.return_value = {
        "files": [{"id": "sub-1", "name": "Subfolder"}],
    }
    files_request = MagicMock()
    files_request.execute.return_value = {
        "files": [{"id": "file-1", "size": "10"}, {"id": "file-2", "size": "15"}],
    }
    files_resource = MagicMock()
    files_resource.get.return_value = root_request
    files_resource.list.side_effect = [folders_request, files_request]
    drive_api = MagicMock()
    drive_api.files.return_value = files_resource

    service = _service_without_init(drive_api)
    result = await service.get_folder_structure("root")

    assert result == {
        "root_id": "root",
        "root_name": "Root",
        "folders": [{"id": "sub-1", "name": "Subfolder"}],
        "total_files": 2,
        "total_size_bytes": 25,
    }
    assert files_resource.list.call_count == 2


async def test_upload_file_to_folder_infers_pdf_mime_type() -> None:
    request = MagicMock()
    request.execute.return_value = {
        "id": "file-1",
        "name": "passport.pdf",
        "webViewLink": "https://drive/file-1",
        "size": "7",
    }
    files_resource = MagicMock()
    files_resource.create.return_value = request
    drive_api = MagicMock()
    drive_api.files.return_value = files_resource

    service = _service_without_init(drive_api)
    result = await service.upload_file_to_folder(
        folder_id="folder-1",
        file_content=b"content",
        file_name="passport.pdf",
    )

    assert result["id"] == "file-1"
    kwargs = files_resource.create.call_args.kwargs
    assert kwargs["body"] == {"name": "passport.pdf", "parents": ["folder-1"]}
    assert kwargs["fields"] == "id, name, webViewLink, size, md5Checksum"
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["media_body"].mimetype() == "application/pdf"


async def test_archive_file_idempotent_holds_distributed_name_lock() -> None:
    service = _service_without_init(MagicMock())
    checksum = "098f6bcd4621d373cade4e832627b4f6"
    service.find_file = AsyncMock(
        return_value={"id": "existing", "md5Checksum": checksum}
    )
    service.upload_file_to_folder = AsyncMock()
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    result, status = await service.archive_file_idempotent(
        folder_id="legal-root",
        file_content=b"test",
        file_name="instrument.pdf",
        mime_type="application/pdf",
        db_pool=pool,
        require_distributed_lock=True,
    )

    assert result["id"] == "existing"
    assert status == "reused"
    lock_key = service._archive_lock_key("legal-root", "instrument.pdf")
    conn.execute.assert_has_awaits(
        [
            call(
                "SELECT pg_advisory_lock($1, $2)",
                service.DRIVE_ARCHIVE_LOCK_CLASS,
                lock_key,
            ),
            call(
                "SELECT pg_advisory_unlock($1, $2)",
                service.DRIVE_ARCHIVE_LOCK_CLASS,
                lock_key,
            ),
        ]
    )
    service.upload_file_to_folder.assert_not_awaited()


async def test_archive_file_idempotent_rejects_same_name_different_content() -> None:
    service = _service_without_init(MagicMock())
    service.find_file = AsyncMock(
        return_value={"id": "other", "md5Checksum": "different"}
    )
    service.upload_file_to_folder = AsyncMock()

    with pytest.raises(DriveArchiveIntegrityError, match="name collision"):
        await service.archive_file_idempotent(
            folder_id="legal-root",
            file_content=b"test",
            file_name="instrument.pdf",
            mime_type="application/pdf",
            db_pool=None,
        )

    service.upload_file_to_folder.assert_not_awaited()


async def test_historical_archive_requires_distributed_lock() -> None:
    service = _service_without_init(MagicMock())

    with pytest.raises(DriveArchiveIntegrityError, match="Distributed archive lock"):
        await service.archive_file_idempotent(
            folder_id="legal-root",
            file_content=b"test",
            file_name="instrument.pdf",
            mime_type="application/pdf",
            db_pool=None,
            require_distributed_lock=True,
        )


async def test_process_lock_prevents_duplicate_upload_when_database_is_unavailable() -> None:
    service = _service_without_init(MagicMock())
    archived: dict[str, Any] | None = None
    uploads = 0

    async def find_file(*, name: str, parent_id: str) -> dict[str, Any] | None:
        del name, parent_id
        return archived

    async def upload_file_to_folder(**kwargs: Any) -> dict[str, Any]:
        nonlocal archived, uploads
        await asyncio.sleep(0)
        uploads += 1
        archived = {
            "id": "single-upload",
            "md5Checksum": hashlib.md5(kwargs["file_content"]).hexdigest(),
        }
        return archived

    service.find_file = AsyncMock(side_effect=find_file)
    service.upload_file_to_folder = AsyncMock(side_effect=upload_file_to_folder)
    args = {
        "folder_id": "local-lock-root",
        "file_content": b"same-content",
        "file_name": "same-name.pdf",
        "mime_type": "application/pdf",
        "db_pool": None,
    }

    results = await asyncio.gather(
        service.archive_file_idempotent(**args),
        service.archive_file_idempotent(**args),
    )

    assert uploads == 1
    assert sorted(status for _, status in results) == ["reused", "uploaded"]
