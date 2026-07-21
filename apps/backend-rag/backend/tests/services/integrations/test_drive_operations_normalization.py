"""Regression tests for Drive API v3 payload normalization (2026-07-19 audit find).

Google Drive v3 `files.list`/`files.get` return `mimeType` but NO `type` field,
and `size` as a STRING (absent entirely for folders and Google-native docs).
The team_drive router contract needs both: `FileItem.type` is a required str
(so `FileItem(**f)` on a raw payload 500s with a Pydantic ValidationError —
the exact live failure on GET /api/drive/files and /api/drive/search), and
the permission filter reads `f["type"]` directly (KeyError for non-admins).

These tests pin the normalization at the DriveOperationsManager layer so every
consumer receives router-contract-ready dicts. Mock pattern mirrors
test_drive_operations_mutations.py (no network).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations.drive.drive_operations import DriveOperationsManager

pytestmark = pytest.mark.asyncio

USER = "zero@balizero.com"

RAW_FOLDER = {
    "id": "folder-1",
    "name": "PERATURAN",
    "mimeType": "application/vnd.google-apps.folder",
    # Drive sends no `size` and no `type` for folders
    "modifiedTime": "2026-07-01T00:00:00.000Z",
}
RAW_FILE = {
    "id": "file-1",
    "name": "PP Nomor 28 Tahun 2025.pdf",
    "mimeType": "application/pdf",
    "size": "2048",  # Drive v3 returns size as a string
    "modifiedTime": "2026-07-02T00:00:00.000Z",
    "webViewLink": "https://drive.google.com/file/d/file-1/view",
}


def _resp(json_body: dict[str, Any] | list[Any] | None = None, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=json_body if json_body is not None else {})
    return r


def _manager(get_response: MagicMock) -> DriveOperationsManager:
    auth = MagicMock()
    auth.get_access_token = AsyncMock(return_value="tok-123")
    http = MagicMock()
    http.get = AsyncMock(return_value=get_response)
    return DriveOperationsManager(auth_manager=auth, http_client=http, audit=MagicMock())


async def test_list_files_normalizes_type_and_size():
    mgr = _manager(_resp({"files": [dict(RAW_FOLDER), dict(RAW_FILE)], "nextPageToken": "npt"}))
    out = await mgr.list_files(USER)

    folder, file = out["files"]
    assert folder["type"] == "folder"
    assert folder["size"] == 0
    assert file["type"] == "file"
    assert file["size"] == 2048  # int, not "2048"
    assert out["nextPageToken"] == "npt"  # passthrough untouched


async def test_search_files_normalizes_every_hit():
    mgr = _manager(_resp({"files": [dict(RAW_FILE), dict(RAW_FOLDER)]}))
    out = await mgr.search_files(USER, query="peraturan")

    assert [f["type"] for f in out] == ["file", "folder"]
    assert all(isinstance(f["size"], int) for f in out)


async def test_get_file_metadata_normalized():
    mgr = _manager(_resp(dict(RAW_FOLDER)))
    out = await mgr.get_file_metadata(USER, "folder-1")

    assert out["type"] == "folder"
    assert out["size"] == 0


async def test_normalized_payload_satisfies_router_fileitem_contract():
    """The live 500: FileItem(**raw_google_payload) → ValidationError (`type` missing).

    Build FileItem from the normalized manager output to pin the full contract.
    """
    from backend.app.routers.team_drive import FileItem

    mgr = _manager(_resp({"files": [dict(RAW_FOLDER), dict(RAW_FILE)]}))
    out = await mgr.list_files(USER)

    items = [FileItem(**f) for f in out["files"]]  # raises before the fix
    assert items[0].type == "folder"
    assert items[1].type == "file"
    assert items[1].size == 2048
