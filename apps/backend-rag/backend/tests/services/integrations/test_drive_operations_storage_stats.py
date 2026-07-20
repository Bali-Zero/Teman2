"""Regression tests for DriveOperationsManager.get_storage_stats (lever #5 residual,
2026-07-19 KB audit — GET /api/drive/stats had never existed as a backend route,
despite the `get_drive_storage_stats` MCP tool calling it since inception. The 404
fired silently: `error_monitoring.py` explicitly suppresses all `/api/drive/` 404s
as "Deleted Drive folders", so nothing ever paged on it.

Design: total storage used comes from a single `about.get(fields=storageQuota)`
call (exact, independent of any enumeration). files/folders count, storage-by-type,
and largest-files come from a paginated `files.list` walk, capped at `max_pages`
(default 20 * pageSize 1000 = up to 20k files) — if the cap is hit before
`nextPageToken` runs out, the response says so explicitly (`truncated: True`,
`scanned_pages`) rather than silently reporting a partial count as if it were
the total (modus "no silent caps" discipline).

Mock pattern mirrors test_drive_operations_normalization.py / _mutations.py
(no network; AsyncMock side_effect drives the sequential about.get + N-page walk).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations.drive.drive_operations import DriveOperationsManager

pytestmark = pytest.mark.asyncio

USER = "zero@balizero.com"

ABOUT_RESP = {
    "storageQuota": {
        "limit": "32985348833280",  # 30TB, matches the /status quota_info string
        "usage": "1048576000",  # 1000 MB
        "usageInDrive": "1048576000",
        "usageInDriveTrash": "0",
    }
}


def _resp(json_body: dict[str, Any]) -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=json_body)
    return r


def _file(id_: str, name: str, mime: str, size: str | None) -> dict[str, Any]:
    f = {"id": id_, "name": name, "mimeType": mime}
    if size is not None:
        f["size"] = size
    return f


def _manager(responses: list[MagicMock]) -> DriveOperationsManager:
    auth = MagicMock()
    auth.get_access_token = AsyncMock(return_value="tok-123")
    http = MagicMock()
    http.get = AsyncMock(side_effect=responses)
    return DriveOperationsManager(auth_manager=auth, http_client=http, audit=MagicMock())


async def test_get_storage_stats_reports_exact_total_from_about_endpoint():
    """Total storage used is NOT derived from the file walk — it's the exact,
    single-call `about.get` value, independent of any pagination cap."""
    mgr = _manager(
        [
            _resp(ABOUT_RESP),
            _resp({"files": []}),  # empty drive, no pagination
        ]
    )
    out = await mgr.get_storage_stats(USER)

    assert out["storage_used_bytes"] == 1048576000
    assert out["storage_limit_bytes"] == 32985348833280
    assert out["files_count"] == 0
    assert out["folders_count"] == 0


async def test_get_storage_stats_counts_files_and_folders():
    mgr = _manager(
        [
            _resp(ABOUT_RESP),
            _resp(
                {
                    "files": [
                        _file("f1", "report.pdf", "application/pdf", "2048"),
                        _file("f2", "notes.pdf", "application/pdf", "1024"),
                        _file("d1", "Archive", "application/vnd.google-apps.folder", None),
                    ]
                }
            ),
        ]
    )
    out = await mgr.get_storage_stats(USER)

    assert out["files_count"] == 2
    assert out["folders_count"] == 1


async def test_get_storage_stats_handles_google_native_doc_without_size():
    """Pins a real edge case (Codex/Kimi adversarial review, 2026-07-20):
    Google-native docs (Sheets/Docs/Slides) are non-folder items that carry
    NO `size` field at all — unlike folders they DO enter the files_count/
    storage_by_type/largest_files accumulation, so a naive `f["size"]` would
    KeyError/TypeError if `_normalize_drive_file` ever stopped defaulting
    absent size to 0. It currently does (`int(f.get("size") or 0)`,
    drive_operations.py) — this test pins that contract so a future change
    to the normalizer can't silently reintroduce the crash."""
    mgr = _manager(
        [
            _resp(ABOUT_RESP),
            _resp({"files": [_file("doc1", "Q3 Report", "application/vnd.google-apps.document", None)]}),
        ]
    )
    out = await mgr.get_storage_stats(USER)

    assert out["files_count"] == 1
    assert out["folders_count"] == 0
    assert out["storage_by_type"] == {"application/vnd.google-apps.document": 0}
    assert out["largest_files"] == [{"id": "doc1", "name": "Q3 Report", "size": 0}]


async def test_get_storage_stats_sums_bytes_by_mime_type():
    mgr = _manager(
        [
            _resp(ABOUT_RESP),
            _resp(
                {
                    "files": [
                        _file("f1", "a.pdf", "application/pdf", "1000"),
                        _file("f2", "b.pdf", "application/pdf", "500"),
                        _file("f3", "c.jpg", "image/jpeg", "300"),
                    ]
                }
            ),
        ]
    )
    out = await mgr.get_storage_stats(USER)

    assert out["storage_by_type"] == {"application/pdf": 1500, "image/jpeg": 300}
    # Folders never contribute bytes to the type breakdown (they carry no size).


async def test_get_storage_stats_returns_top_10_largest_files_sorted_desc():
    files = [_file(f"f{i}", f"file{i}.bin", "application/octet-stream", str(i * 100)) for i in range(15)]
    mgr = _manager([_resp(ABOUT_RESP), _resp({"files": files})])
    out = await mgr.get_storage_stats(USER)

    assert len(out["largest_files"]) == 10
    sizes = [f["size"] for f in out["largest_files"]]
    assert sizes == sorted(sizes, reverse=True)
    assert sizes[0] == 1400  # f14 = 14*100


async def test_get_storage_stats_walks_multiple_pages_until_no_next_token():
    page1 = _resp(
        {
            "files": [_file("f1", "a.pdf", "application/pdf", "100")],
            "nextPageToken": "tok-2",
        }
    )
    page2 = _resp({"files": [_file("f2", "b.pdf", "application/pdf", "200")]})
    mgr = _manager([_resp(ABOUT_RESP), page1, page2])

    out = await mgr.get_storage_stats(USER)

    assert out["files_count"] == 2
    assert out["scanned_pages"] == 2
    assert out["truncated"] is False


async def test_get_storage_stats_honestly_flags_truncation_when_cap_hit():
    """Guilt: if the drive has MORE pages than max_pages allows, the response
    must say so explicitly — never present a partial count silently as final."""
    page_with_more = _resp(
        {
            "files": [_file("f1", "a.pdf", "application/pdf", "100")],
            "nextPageToken": "still-more",
        }
    )
    # 2 pages available, but cap the walk at 1 page.
    mgr = _manager([_resp(ABOUT_RESP), page_with_more])

    out = await mgr.get_storage_stats(USER, max_pages=1)

    assert out["truncated"] is True
    assert out["scanned_pages"] == 1
    assert out["files_count"] == 1  # honest partial count, not silently hidden


async def test_get_storage_stats_does_not_falsely_flag_truncation_under_cap():
    """Innocence-of-the-detector: a drive that finishes within the cap must NOT
    be reported truncated — proves test above is measuring the cap, not a bug
    that always sets truncated=True."""
    mgr = _manager([_resp(ABOUT_RESP), _resp({"files": []})])

    out = await mgr.get_storage_stats(USER, max_pages=1)

    assert out["truncated"] is False
    assert out["scanned_pages"] == 1
