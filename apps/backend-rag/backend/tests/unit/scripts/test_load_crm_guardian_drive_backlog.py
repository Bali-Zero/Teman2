from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.load_crm_guardian_drive_backlog import (
    bool_from_csv,
    build_load_plan,
    ensure_tables,
    priority_to_confidence,
    split_parent_ids,
)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_bool_from_csv() -> None:
    assert bool_from_csv("true") is True
    assert bool_from_csv("1") is True
    assert bool_from_csv("false") is False
    assert bool_from_csv("") is False


def test_split_parent_ids() -> None:
    assert split_parent_ids("a,b, c ,,") == ["a", "b", "c"]


def test_priority_to_confidence() -> None:
    assert priority_to_confidence("P0") == 0.9
    assert priority_to_confidence("P3") == 0.4
    assert priority_to_confidence("") is None


def test_build_load_plan_from_phase2_reports(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "phase2_valid_crm_drive_anchors.csv",
        [
            {
                "drive_id": "valid-1",
                "name": "Valid.pdf",
                "mime_type": "application/pdf",
                "owner": "antonellosiano@gmail.com",
                "owner_domain": "gmail.com",
                "drive_id_parent": "parent-1,parent-2",
                "driveId": "",
                "trashed": "false",
                "webViewLink": "https://drive/valid-1",
                "source_mix": "documents:1",
                "recommended_action": "external_owner_migration_review",
            }
        ],
    )
    write_csv(
        tmp_path / "phase2_db_link_error_backlog.csv",
        [
            {
                "priority": "P0",
                "drive_id": "missing-1",
                "status": "error_404",
                "error_status": "NOT_FOUND",
                "error_message": "File not found",
                "source_mix": "company_documents:1",
                "recommended_action": "owner_account_or_stale_id_review",
            }
        ],
    )
    write_csv(
        tmp_path / "phase2_external_owner_migration_backlog.csv",
        [
            {
                "priority": "P1",
                "drive_id": "valid-1",
                "name": "Valid.pdf",
                "owner": "antonellosiano@gmail.com",
                "owner_domain": "gmail.com",
                "source_mix": "documents:1",
                "recommended_action": "external_owner_migration_review",
            }
        ],
    )
    write_csv(
        tmp_path / "phase2_unlinked_visible_crm_items_backlog.csv",
        [
            {
                "priority": "P2",
                "id": "unlinked-1",
                "name": "Passport.jpg",
                "cluster": "BALI ZERO",
                "owner": "zero@balizero.com",
                "ownerDomain": "balizero.com",
                "recommended_action": "classify_and_match_to_client_company_practice",
            }
        ],
    )
    write_csv(
        tmp_path / "phase2_shortcut_resolution_backlog.csv",
        [
            {
                "id": "shortcut-1",
                "shortcutTargetId": "target-1",
                "shortcutTargetMimeType": "application/pdf",
                "path": "BALI ZERO / Shortcut",
                "cluster": "BALI ZERO",
                "owner": "zero@balizero.com",
                "ownerDomain": "balizero.com",
                "webViewLink": "https://drive/shortcut-1",
            }
        ],
    )

    plan = build_load_plan(tmp_path)

    assert len(plan.metadata_rows) == 2
    assert len(plan.backlog_rows) == 3
    assert len(plan.shortcut_rows) == 1
    assert plan.metadata_rows[0]["parent_ids"] == ["parent-1", "parent-2"]
    assert plan.shortcut_rows[0]["shortcut_id"] == "shortcut-1"


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchval(self, sql: str, *args: Any) -> str:
        self.calls.append((sql, args))
        return args[0]


@pytest.mark.asyncio
async def test_ensure_tables_casts_to_regclass_parameter() -> None:
    conn = FakeConnection()

    await ensure_tables(conn)  # type: ignore[arg-type]

    assert conn.calls
    assert all("to_regclass($1::text)" in sql for sql, _args in conn.calls)
