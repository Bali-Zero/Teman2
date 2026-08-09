"""Client-boundary contract tests for portal response projections."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.app.routers import portal_drive
from backend.services.portal._mixins.documents import PortalDocumentsMixin

_FORBIDDEN_NORMALIZED_KEYS = {
    "driveid",
    "driveurl",
    "extractedtextpreview",
    "fileid",
    "folderid",
    "id",
    "ocrpages",
    "ocrpreview",
    "processing",
    "rootid",
    "sourcetrace",
    "virusclean",
    "webcontentlink",
    "webviewlink",
}
_DRIVE_URL_PATTERN = re.compile(r"https?://(?:drive|docs)\.google\.com", re.IGNORECASE)


def _nested_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nested_keys(child)


def _normalized_keys(value: Any) -> set[str]:
    return {re.sub(r"[^a-z0-9]", "", key.lower()) for key in _nested_keys(value)}


@pytest.mark.asyncio
async def test_drive_files_response_is_allowlisted_for_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw Drive identifiers, URLs, and backstage fields never reach the response."""
    raw_root_id = "root_1A2b3C4d5E6f7G8h9I"
    raw_folder_id = "folder_9I8h7G6f5E4d3C2b1A"
    raw_file_id = "file_0A1b2C3d4E5f6G7h8I"
    raw_drive_url = f"https://drive.google.com/file/d/{raw_file_id}/view"

    async def fake_list(
        pool: object,
        drive_service: object,
        client_id: int,
    ) -> dict[str, Any]:
        assert client_id == 42
        return {
            "root_id": raw_root_id,
            "root_name": "Client documents",
            "folders": [
                {
                    "id": raw_folder_id,
                    "name": "Corporate",
                    "webViewLink": raw_drive_url,
                }
            ],
            "files": [
                {
                    "id": raw_file_id,
                    "name": "Registration.pdf",
                    "drive_url": raw_drive_url,
                    "ocr_preview": "backstage text",
                    "source_trace": {"provider": "drive"},
                }
            ],
            "total_files": 1,
            "total_size_bytes": 4096,
        }

    monkeypatch.setattr(portal_drive, "_list_client_drive_files", fake_list)

    response = await portal_drive.list_drive_files(
        client={"client_id": 42},
        db_pool=MagicMock(),
        drive_service=MagicMock(),
    )

    assert response == {
        "success": True,
        "data": {
            "root_name": "Client documents",
            "files": [],
            "folders": [{"name": "Corporate"}],
            "total_files": 1,
            "total_size_bytes": 4096,
        },
    }
    assert _normalized_keys(response).isdisjoint(_FORBIDDEN_NORMALIZED_KEYS)

    serialized = json.dumps(response)
    assert _DRIVE_URL_PATTERN.search(serialized) is None
    for raw_identifier in (raw_root_id, raw_folder_id, raw_file_id):
        assert raw_identifier not in serialized


def test_upload_response_projection_removes_backstage_fields() -> None:
    """Upload responses retain document state without exposing OCR or orchestration data."""
    raw_drive_url = "https://drive.google.com/file/d/file_0A1b2C3d4E5f6G7h8I/view"
    result = PortalDocumentsMixin._client_safe_upload_response(
        {
            "id": 88,
            "type": "passport",
            "name": "passport.pdf",
            "status": "received",
            "size_kb": 42,
            "created_at": "2026-08-04T00:00:00+00:00",
            "expiry_date": "2027-08-04",
            "extracted_text_preview": "backstage OCR text",
            "processing": {
                "virus_clean": True,
                "ocr_pages": 2,
                "drive_uploaded": True,
            },
            "drive_id": "file_0A1b2C3d4E5f6G7h8I",
            "drive_url": raw_drive_url,
            "source_trace": {"provider": "drive", "operation": "upload"},
        }
    )

    assert result == {
        "id": 88,
        "type": "passport",
        "name": "passport.pdf",
        "status": "received",
        "size_kb": 42,
        "created_at": "2026-08-04T00:00:00+00:00",
        "expiry_date": "2027-08-04",
    }
    assert _normalized_keys(result).isdisjoint(_FORBIDDEN_NORMALIZED_KEYS - {"id"})
    assert _DRIVE_URL_PATTERN.search(json.dumps(result)) is None


@pytest.mark.asyncio
async def test_drive_files_response_retains_safe_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projection keeps the client-facing empty-state contract intact."""

    async def fake_list(
        pool: object,
        drive_service: object,
        client_id: int,
    ) -> dict[str, Any]:
        return {
            "files": [],
            "folders": [],
            "total_files": 0,
            "message": "No client Drive folder is configured",
        }

    monkeypatch.setattr(portal_drive, "_list_client_drive_files", fake_list)

    response = await portal_drive.list_drive_files(
        client={"client_id": 42},
        db_pool=MagicMock(),
        drive_service=MagicMock(),
    )

    assert response == {
        "success": True,
        "data": {
            "files": [],
            "folders": [],
            "total_files": 0,
            "message": "No client Drive folder is configured",
        },
    }
