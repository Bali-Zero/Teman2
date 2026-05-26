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
