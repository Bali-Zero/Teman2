"""Load CRM Guardian Drive Phase 2 CSV artifacts into staging tables.

Default mode is dry-run. Pass --apply to write to Postgres.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg

DEFAULT_REPORT_DIR = Path("/tmp/nuzantara-gws-phase1/reports")
SAFE_OWNER_DOMAINS = {"balizero.com", "nuzantara.iam.gserviceaccount.com"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadPlan:
    metadata_rows: list[dict[str, Any]]
    backlog_rows: list[dict[str, Any]]
    shortcut_rows: list[dict[str, Any]]

    @property
    def total_rows(self) -> int:
        return len(self.metadata_rows) + len(self.backlog_rows) + len(self.shortcut_rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def bool_from_csv(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"true", "t", "1", "yes", "y"}


def split_parent_ids(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def priority_to_confidence(priority: str | None) -> float | None:
    normalized = str(priority or "").upper()
    if normalized == "P0":
        return 0.9
    if normalized == "P1":
        return 0.75
    if normalized == "P2":
        return 0.6
    if normalized == "P3":
        return 0.4
    return None


def normalize_metadata_ok(row: dict[str, str]) -> dict[str, Any]:
    drive_id = row["drive_id"]
    owner_domain = row.get("owner_domain") or "unknown"
    return {
        "drive_id": drive_id,
        "name": row.get("name") or None,
        "mime_type": row.get("mime_type") or None,
        "owner_email": row.get("owner") or None,
        "owner_domain": owner_domain,
        "parent_ids": split_parent_ids(row.get("drive_id_parent")),
        "shared_drive_id": row.get("driveId") or None,
        "trashed": bool_from_csv(row.get("trashed")),
        "web_view_link": row.get("webViewLink") or None,
        "shortcut_target_id": None,
        "shortcut_target_mime_type": None,
        "can_copy": None,
        "can_download": None,
        "can_edit": None,
        "can_move_item_into_team_drive": None,
        "can_move_item_out_of_drive": None,
        "can_move_item_within_drive": None,
        "validation_status": "ok",
        "error_status": None,
        "error_message": None,
        "source_mix": row.get("source_mix") or None,
        "raw_metadata": {
            "source": "phase2_valid_crm_drive_anchors.csv",
            "recommended_action": row.get("recommended_action") or None,
        },
    }


def normalize_metadata_error(row: dict[str, str]) -> dict[str, Any]:
    return {
        "drive_id": row["drive_id"],
        "name": None,
        "mime_type": None,
        "owner_email": None,
        "owner_domain": "unknown",
        "parent_ids": [],
        "shared_drive_id": None,
        "trashed": False,
        "web_view_link": None,
        "shortcut_target_id": None,
        "shortcut_target_mime_type": None,
        "can_copy": None,
        "can_download": None,
        "can_edit": None,
        "can_move_item_into_team_drive": None,
        "can_move_item_out_of_drive": None,
        "can_move_item_within_drive": None,
        "validation_status": row.get("status") or "error",
        "error_status": row.get("error_status") or row.get("status") or "error",
        "error_message": row.get("error_message") or None,
        "source_mix": row.get("source_mix") or None,
        "raw_metadata": {
            "source": "phase2_db_link_error_backlog.csv",
            "recommended_action": row.get("recommended_action") or None,
        },
    }


def normalize_backlog(
    row: dict[str, str],
    *,
    backlog_type: str,
    default_action: str,
) -> dict[str, Any]:
    drive_id = row.get("drive_id") or row.get("id") or row.get("shortcutTargetId") or ""
    priority = row.get("priority") or "P2"
    evidence = {
        "source_row": row,
        "source": backlog_type,
    }
    return {
        "drive_id": drive_id,
        "backlog_type": backlog_type,
        "priority": priority,
        "owner_email": row.get("owner") or row.get("owner_email") or None,
        "owner_domain": row.get("ownerDomain") or row.get("owner_domain") or "unknown",
        "source_mix": row.get("source_mix") or row.get("cluster") or None,
        "recommended_action": row.get("recommended_action") or default_action,
        "confidence": priority_to_confidence(priority),
        "status": "open",
        "evidence": evidence,
    }


def normalize_shortcut(row: dict[str, str]) -> dict[str, Any]:
    evidence = {
        "name": row.get("name"),
        "webViewLink": row.get("webViewLink"),
        "source_row": row,
    }
    return {
        "shortcut_id": row["id"],
        "target_id": row["shortcutTargetId"],
        "target_mime_type": row.get("shortcutTargetMimeType") or None,
        "source_path": row.get("path") or None,
        "source_cluster": row.get("cluster") or None,
        "owner_email": row.get("owner") or None,
        "owner_domain": row.get("ownerDomain") or "unknown",
        "resolution_status": "pending",
        "evidence": evidence,
    }


def build_load_plan(report_dir: Path) -> LoadPlan:
    valid_rows = read_csv(report_dir / "phase2_valid_crm_drive_anchors.csv")
    error_rows = read_csv(report_dir / "phase2_db_link_error_backlog.csv")
    external_rows = read_csv(report_dir / "phase2_external_owner_migration_backlog.csv")
    unlinked_rows = read_csv(report_dir / "phase2_unlinked_visible_crm_items_backlog.csv")
    shortcut_rows = read_csv(report_dir / "phase2_shortcut_resolution_backlog.csv")

    metadata_by_id: dict[str, dict[str, Any]] = {}
    for row in valid_rows:
        drive_id = row.get("drive_id")
        if drive_id:
            metadata_by_id[drive_id] = normalize_metadata_ok(row)
    for row in error_rows:
        drive_id = row.get("drive_id")
        if drive_id:
            metadata_by_id[drive_id] = normalize_metadata_error(row)

    backlog_rows: list[dict[str, Any]] = []
    for row in external_rows:
        if (row.get("owner_domain") or row.get("ownerDomain")) in SAFE_OWNER_DOMAINS:
            continue
        backlog_rows.append(
            normalize_backlog(
                row,
                backlog_type="external_owner",
                default_action="external_owner_migration_review",
            )
        )
    for row in error_rows:
        backlog_rows.append(
            normalize_backlog(
                row,
                backlog_type="stale_link_candidate",
                default_action="owner_account_or_stale_id_review",
            )
        )
    for row in unlinked_rows:
        backlog_rows.append(
            normalize_backlog(
                row,
                backlog_type="unlinked_visible_crm_item",
                default_action="classify_and_match_to_client_company_practice",
            )
        )

    shortcuts = [
        normalize_shortcut(row)
        for row in shortcut_rows
        if row.get("id") and row.get("shortcutTargetId")
    ]
    return LoadPlan(
        metadata_rows=list(metadata_by_id.values()),
        backlog_rows=backlog_rows,
        shortcut_rows=shortcuts,
    )


async def ensure_tables(conn: asyncpg.Connection) -> None:
    required = [
        "crm_guardian_drive_metadata_snapshot",
        "crm_guardian_migration_backlog",
        "crm_guardian_shortcut_edges",
    ]
    for table_name in required:
        exists = await conn.fetchval("SELECT to_regclass($1::text)", f"public.{table_name}")
        if exists is None:
            raise RuntimeError(f"{table_name} is not migrated yet")


async def write_metadata(conn: asyncpg.Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    records = [
        (
            row["drive_id"],
            row["name"],
            row["mime_type"],
            row["owner_email"],
            row["owner_domain"],
            row["parent_ids"],
            row["shared_drive_id"],
            row["trashed"],
            row["web_view_link"],
            row["shortcut_target_id"],
            row["shortcut_target_mime_type"],
            row["can_copy"],
            row["can_download"],
            row["can_edit"],
            row["can_move_item_into_team_drive"],
            row["can_move_item_out_of_drive"],
            row["can_move_item_within_drive"],
            row["validation_status"],
            row["error_status"],
            row["error_message"],
            row["source_mix"],
            json.dumps(row["raw_metadata"]),
        )
        for row in rows
    ]
    await conn.executemany(
        """
        INSERT INTO crm_guardian_drive_metadata_snapshot (
            drive_id, name, mime_type, owner_email, owner_domain, parent_ids,
            shared_drive_id, trashed, web_view_link, shortcut_target_id,
            shortcut_target_mime_type, can_copy, can_download, can_edit,
            can_move_item_into_team_drive, can_move_item_out_of_drive,
            can_move_item_within_drive, validation_status, error_status,
            error_message, source_mix, raw_metadata, validated_at, updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6::text[], $7, $8, $9, $10, $11, $12,
            $13, $14, $15, $16, $17, $18, $19, $20, $21, $22::jsonb,
            NOW(), NOW()
        )
        ON CONFLICT (drive_id) DO UPDATE SET
            name = EXCLUDED.name,
            mime_type = EXCLUDED.mime_type,
            owner_email = EXCLUDED.owner_email,
            owner_domain = EXCLUDED.owner_domain,
            parent_ids = EXCLUDED.parent_ids,
            shared_drive_id = EXCLUDED.shared_drive_id,
            trashed = EXCLUDED.trashed,
            web_view_link = EXCLUDED.web_view_link,
            validation_status = EXCLUDED.validation_status,
            error_status = EXCLUDED.error_status,
            error_message = EXCLUDED.error_message,
            source_mix = EXCLUDED.source_mix,
            raw_metadata = EXCLUDED.raw_metadata,
            updated_at = NOW()
        """,
        records,
    )


async def write_backlog(conn: asyncpg.Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    records = [
        (
            row["drive_id"],
            row["backlog_type"],
            row["priority"],
            row["owner_email"],
            row["owner_domain"],
            row["source_mix"],
            row["recommended_action"],
            row["confidence"],
            row["status"],
            json.dumps(row["evidence"]),
        )
        for row in rows
    ]
    await conn.executemany(
        """
        INSERT INTO crm_guardian_migration_backlog (
            drive_id, backlog_type, priority, owner_email, owner_domain,
            source_mix, recommended_action, confidence, status, evidence
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
        """,
        records,
    )


async def write_shortcuts(conn: asyncpg.Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    records = [
        (
            row["shortcut_id"],
            row["target_id"],
            row["target_mime_type"],
            row["source_path"],
            row["source_cluster"],
            row["owner_email"],
            row["owner_domain"],
            row["resolution_status"],
            json.dumps(row["evidence"]),
        )
        for row in rows
    ]
    await conn.executemany(
        """
        INSERT INTO crm_guardian_shortcut_edges (
            shortcut_id, target_id, target_mime_type, source_path,
            source_cluster, owner_email, owner_domain, resolution_status,
            evidence, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
        ON CONFLICT (shortcut_id) DO UPDATE SET
            target_id = EXCLUDED.target_id,
            target_mime_type = EXCLUDED.target_mime_type,
            source_path = EXCLUDED.source_path,
            source_cluster = EXCLUDED.source_cluster,
            owner_email = EXCLUDED.owner_email,
            owner_domain = EXCLUDED.owner_domain,
            resolution_status = EXCLUDED.resolution_status,
            evidence = EXCLUDED.evidence,
            updated_at = NOW()
        """,
        records,
    )


async def apply_plan(database_url: str, plan: LoadPlan) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        await ensure_tables(conn)
        async with conn.transaction():
            await write_metadata(conn, plan.metadata_rows)
            await write_backlog(conn, plan.backlog_rows)
            await write_shortcuts(conn, plan.shortcut_rows)
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Directory containing phase2 CRM Guardian CSV reports.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write to DB. Without this flag, only prints a dry-run summary.",
    )
    return parser.parse_args()


async def main_async() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    plan = build_load_plan(args.report_dir)
    logger.info(
        "%s",
        json.dumps(
            {
                "report_dir": str(args.report_dir),
                "dry_run": not args.apply,
                "metadata_rows": len(plan.metadata_rows),
                "backlog_rows": len(plan.backlog_rows),
                "shortcut_rows": len(plan.shortcut_rows),
                "total_rows": plan.total_rows,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    if not args.apply:
        return 0
    if not args.database_url:
        raise RuntimeError("--database-url or DATABASE_URL is required with --apply")
    await apply_plan(args.database_url, plan)
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
