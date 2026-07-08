from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

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


@pytest.mark.skip(reason="Auto-generated skeleton")
async def test_create_folder_skeleton():
    # TODO: Implement test logic for create_folder
    # result = await create_folder(...)
    assert True


@pytest.mark.skip(reason="Auto-generated skeleton")
async def test_get_folder_structure_skeleton():
    # TODO: Implement test logic for get_folder_structure
    # result = await get_folder_structure(...)
    assert True


@pytest.mark.skip(reason="Auto-generated skeleton")
async def test_upload_file_to_folder_skeleton():
    # TODO: Implement test logic for upload_file_to_folder
    # result = await upload_file_to_folder(...)
    assert True
