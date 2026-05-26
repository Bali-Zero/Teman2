from __future__ import annotations

from typing import Any

import pytest

from backend.services.crm_guardian.drive_metadata_snapshot import (
    CRMDriveLink,
    CRMGuardianDriveMetadataSnapshotService,
    error_to_snapshot,
    extract_drive_id,
    fetch_crm_drive_links,
    metadata_to_snapshot,
    summarize_snapshots,
    unique_drive_ids,
)


class _FakeDriveService:
    def __init__(self, responses: dict[str, dict[str, Any] | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def get_file_metadata_detailed(self, file_id: str) -> dict[str, Any]:
        self.calls.append(file_id)
        response = self.responses[file_id]
        if isinstance(response, Exception):
            raise response
        return response


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        assert "FROM clients" in query
        return self.rows


def _crm_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source_table": "documents",
        "link_kind": "client_document",
        "entity_type": "client",
        "entity_id": "client-1",
        "parent_entity_id": "doc-1",
        "entity_label": "Passport.pdf",
        "document_type": "passport",
        "file_name": "Passport.pdf",
        "raw_drive_id": "",
        "raw_url": None,
        "crm_status": "active",
        "crm_updated_at": "2026-05-25T00:00:00",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("raw_drive_id", "raw_url", "expected"),
    [
        ("1AbCdEfGhIjK", None, "1AbCdEfGhIjK"),
        (None, "https://drive.google.com/file/d/1AbCdEfGhIjK/view", "1AbCdEfGhIjK"),
        (None, "https://drive.google.com/drive/folders/1FolderId_123", "1FolderId_123"),
        (None, "https://drive.google.com/open?id=1OpenId_123", "1OpenId_123"),
        ("", "not a drive url", None),
    ],
)
def test_extract_drive_id(
    raw_drive_id: str | None,
    raw_url: str | None,
    expected: str | None,
) -> None:
    assert extract_drive_id(raw_drive_id, raw_url) == expected


def test_metadata_to_snapshot_normalizes_drive_metadata() -> None:
    snapshot = metadata_to_snapshot(
        "file-1",
        {
            "name": "Passport.pdf",
            "mimeType": "application/pdf",
            "owners": [{"emailAddress": "Zero@BaliZero.com"}],
            "parents": ["parent-1", None, "parent-2"],
            "driveId": "shared-drive-1",
            "trashed": True,
            "webViewLink": "https://drive.google.com/file/d/file-1/view",
            "shortcutDetails": {
                "targetId": "target-1",
                "targetMimeType": "application/vnd.google-apps.folder",
            },
            "capabilities": {
                "canCopy": True,
                "canDownload": False,
                "canEdit": True,
                "canMoveItemIntoTeamDrive": False,
                "canMoveItemOutOfDrive": True,
                "canMoveItemWithinDrive": False,
            },
        },
    )

    assert snapshot.validation_status == "ok"
    assert snapshot.owner_email == "Zero@BaliZero.com"
    assert snapshot.owner_domain == "balizero.com"
    assert snapshot.parent_ids == ("parent-1", "parent-2")
    assert snapshot.shared_drive_id == "shared-drive-1"
    assert snapshot.trashed is True
    assert snapshot.shortcut_target_id == "target-1"
    assert snapshot.can_copy is True
    assert snapshot.can_download is False
    assert snapshot.can_move_item_out_of_drive is True


def test_error_to_snapshot_preserves_drive_id_and_error_message() -> None:
    snapshot = error_to_snapshot("file-1", RuntimeError("drive unavailable"))

    assert snapshot.drive_id == "file-1"
    assert snapshot.validation_status == "error"
    assert snapshot.error_status == "error"
    assert snapshot.error_message == "drive unavailable"
    assert snapshot.owner_domain == "unknown"


async def test_fetch_crm_drive_links_extracts_ids_from_rows() -> None:
    conn = _FakeConn(
        [
            _crm_row(raw_drive_id="direct-drive-id"),
            _crm_row(
                entity_id="client-2",
                raw_url="https://drive.google.com/file/d/url-drive-id-123/view",
            ),
            _crm_row(entity_id="client-3", raw_drive_id="", raw_url="not a drive url"),
        ],
    )

    links = await fetch_crm_drive_links(conn)

    assert [link.drive_id for link in links] == ["direct-drive-id", "url-drive-id-123"]
    assert links[0].entity_id == "client-1"
    assert links[1].entity_id == "client-2"


def test_unique_drive_ids_preserves_first_seen_order() -> None:
    links = [
        _link("drive-a"),
        _link("drive-b"),
        _link("drive-a"),
    ]

    assert unique_drive_ids(links) == ["drive-a", "drive-b"]


async def test_validate_drive_ids_converts_successes_and_errors() -> None:
    drive_service = _FakeDriveService(
        {
            "ok-file": {"name": "OK", "mimeType": "application/pdf"},
            "bad-file": RuntimeError("not reachable"),
        },
    )
    service = CRMGuardianDriveMetadataSnapshotService(drive_service, concurrency=2)

    snapshots = await service.validate_drive_ids(["ok-file", "bad-file"])

    assert [snapshot.drive_id for snapshot in snapshots] == ["ok-file", "bad-file"]
    assert [snapshot.validation_status for snapshot in snapshots] == ["ok", "error"]
    assert drive_service.calls == ["ok-file", "bad-file"]


async def test_validate_db_links_applies_limit_after_deduplication() -> None:
    conn = _FakeConn(
        [
            _crm_row(raw_drive_id="drive-a"),
            _crm_row(raw_drive_id="drive-b"),
            _crm_row(raw_drive_id="drive-a"),
        ],
    )
    drive_service = _FakeDriveService(
        {
            "drive-a": {"name": "A"},
            "drive-b": {"name": "B"},
        },
    )
    service = CRMGuardianDriveMetadataSnapshotService(drive_service)

    links, snapshots = await service.validate_db_links(conn, limit=1)

    assert len(links) == 3
    assert [snapshot.drive_id for snapshot in snapshots] == ["drive-a"]
    assert drive_service.calls == ["drive-a"]


def test_summarize_snapshots_counts_status_owner_and_mime() -> None:
    snapshots = [
        metadata_to_snapshot(
            "file-1",
            {
                "name": "Passport.pdf",
                "mimeType": "application/pdf",
                "owners": [{"emailAddress": "zero@balizero.com"}],
            },
        ),
        error_to_snapshot("file-2", RuntimeError("missing")),
    ]

    summary = summarize_snapshots(snapshots)

    assert summary == {
        "total": 2,
        "ok": 1,
        "errors": 1,
        "status_counts": {"ok": 1, "error": 1},
        "owner_domain_counts": {"balizero.com": 1},
        "mime_type_counts": {"application/pdf": 1},
    }


def _link(drive_id: str) -> CRMDriveLink:
    return CRMDriveLink(
        source_table="documents",
        link_kind="client_document",
        entity_type="client",
        entity_id="client-1",
        parent_entity_id=None,
        entity_label=None,
        document_type=None,
        file_name=None,
        drive_id=drive_id,
        raw_url=None,
        crm_status=None,
        crm_updated_at=None,
    )
