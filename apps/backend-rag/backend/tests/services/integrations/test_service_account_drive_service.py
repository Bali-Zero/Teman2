from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from backend.services.integrations.service_account_drive_service import (
    ServiceAccountDriveService,
)


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
    assert kwargs["fields"] == "id, name, webViewLink, size"
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["media_body"].mimetype() == "application/pdf"
