"""
Tests for zantara_media.indexer.drive_client

All Drive API calls are mocked — no real credentials required.
Uses pytest-asyncio (asyncio_mode = "auto" set in pyproject.toml).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zantara_media.indexer.drive_client import (
    GARUDA_SUBFOLDER_IDS,
    Change,
    DriveClient,
    DriveFile,
    _parse_change,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_file_data(
    file_id: str = "file1",
    name: str = "photo.jpg",
    trashed: bool = False,
    parents: list[str] | None = None,
) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": "image/jpeg",
        "parents": parents or ["parentFolder"],
        "size": "12345",
        "modifiedTime": "2026-01-15T10:00:00Z",
        "version": "3",
        "trashed": trashed,
    }


def _make_change_data(
    file_id: str = "file1",
    removed: bool = False,
    trashed: bool = False,
    parents: list[str] | None = None,
) -> dict:
    return {
        "type": "file",
        "fileId": file_id,
        "removed": removed,
        "file": _make_file_data(file_id=file_id, trashed=trashed, parents=parents),
    }


def _build_mock_service(pages: list[dict]) -> MagicMock:
    """
    Build a mock Drive service that returns *pages* sequentially when
    ``service.changes().list(...).execute()`` is called.
    """
    service = MagicMock()

    # getStartPageToken mock
    service.changes.return_value.getStartPageToken.return_value.execute.return_value = {
        "startPageToken": "abc123"
    }

    # list().execute() iterates through pages
    execute_mock = MagicMock(side_effect=pages)
    service.changes.return_value.list.return_value.execute = execute_mock

    return service


# ---------------------------------------------------------------------------
# Test 1 — get_start_page_token
# ---------------------------------------------------------------------------


async def test_get_start_page_token() -> None:
    """get_start_page_token() must return the token string from the API response."""
    service = MagicMock()
    service.changes.return_value.getStartPageToken.return_value.execute.return_value = {
        "startPageToken": "abc123"
    }

    client = DriveClient(service=service)
    token = await client.get_start_page_token()

    assert token == "abc123"
    service.changes.return_value.getStartPageToken.return_value.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2 — list_changes single page
# ---------------------------------------------------------------------------


async def test_list_changes_single_page() -> None:
    """A single-page response should yield exactly 2 Change objects."""
    page = {
        "newStartPageToken": "tok_next",
        "changes": [
            _make_change_data(file_id="f1"),
            _make_change_data(file_id="f2"),
        ],
    }

    service = _build_mock_service([page])
    client = DriveClient(service=service)

    results: list[Change] = []
    async for change in client.list_changes("tok_start"):
        results.append(change)

    assert len(results) == 2
    assert results[0].file_id == "f1"
    assert results[1].file_id == "f2"


# ---------------------------------------------------------------------------
# Test 3 — list_changes pagination (two pages)
# ---------------------------------------------------------------------------


async def test_list_changes_pagination() -> None:
    """Two pages should yield items from both pages (total 3)."""
    page1 = {
        "nextPageToken": "tok_page2",
        "changes": [
            _make_change_data(file_id="f1"),
            _make_change_data(file_id="f2"),
        ],
    }
    page2 = {
        "newStartPageToken": "tok_final",
        "changes": [
            _make_change_data(file_id="f3"),
        ],
    }

    service = _build_mock_service([page1, page2])
    client = DriveClient(service=service)

    results: list[Change] = []
    async for change in client.list_changes("tok_start"):
        results.append(change)

    assert len(results) == 3
    assert [c.file_id for c in results] == ["f1", "f2", "f3"]

    # Items from page1 carry page2 token; item from page2 carries final token.
    assert results[0].next_page_token == "tok_page2"
    assert results[1].next_page_token == "tok_page2"
    assert results[2].next_page_token == "tok_final"


# ---------------------------------------------------------------------------
# Test 4 — is_under_garuda: direct GARUDA subfolder parent → True
# ---------------------------------------------------------------------------


def test_is_under_garuda_direct() -> None:
    """A file whose parent is the photos subfolder ID must return True."""
    photos_id = "1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq"
    assert photos_id in GARUDA_SUBFOLDER_IDS  # sanity check
    assert DriveClient.is_under_garuda([photos_id]) is True


# ---------------------------------------------------------------------------
# Test 5 — is_under_garuda: random parent → False
# ---------------------------------------------------------------------------


def test_is_under_garuda_outside() -> None:
    """A file whose parent has no relation to GARUDA must return False."""
    random_id = "0B_totally_unrelated_folder_id"
    assert random_id not in GARUDA_SUBFOLDER_IDS
    assert DriveClient.is_under_garuda([random_id]) is False


# ---------------------------------------------------------------------------
# Test 6 — tombstone: removed=True → is_tombstone=True
# ---------------------------------------------------------------------------


def test_tombstone_removed() -> None:
    """A change with removed=True must have is_tombstone=True."""
    change_data = _make_change_data(file_id="deleted_file", removed=True, trashed=False)
    change = _parse_change(change_data)

    assert change.removed is True
    assert change.is_tombstone is True


# ---------------------------------------------------------------------------
# Test 7 — tombstone: file.trashed=True → is_tombstone=True
# ---------------------------------------------------------------------------


def test_tombstone_trashed() -> None:
    """A change whose file has trashed=True must have is_tombstone=True."""
    change_data = _make_change_data(file_id="trashed_file", removed=False, trashed=True)
    change = _parse_change(change_data)

    assert change.removed is False
    assert change.file is not None
    assert change.file.trashed is True
    assert change.is_tombstone is True
