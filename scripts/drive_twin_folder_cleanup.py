"""Drive twin-folder cleanup for CRM clients.

Context (2026-06-11, PR #1308): before the `ensure_client_folder` chokepoint
fix, every client created from kita with a passport scan got TWO root folders
"{id}_{name}" in Drive — the linked one (clients.google_drive_folder_id,
usually WITHOUT the passport) and an orphan twin (often WITH the passport).

This script heals the existing population:

  report (default)  — census only, no mutation. Writes a JSONL report.
  apply             — for each twin: MERGE its contents into the linked
                      (keeper) folder, then move the EMPTY twin to trash.
                      Trash is reversible for 30 days. Nothing is ever
                      permanently deleted and the keeper is never modified
                      except by receiving files.

Merge policy (twins have at most root → category-subfolder → files):
  - twin child FILE          → moved to keeper root
  - twin child FOLDER whose name exists in keeper → its children moved into
    the keeper's same-name subfolder, then the (now empty) twin child folder
    is trashed
  - twin child FOLDER with no keeper counterpart → moved as-is to keeper root

Twins are matched conservatively: same exact folder name as the keeper, same
parent set (or any scanned client parent), different file id, not trashed.

Usage:
  PYTHONPATH=. python scripts/drive_twin_folder_cleanup.py            # report
  PYTHONPATH=. python scripts/drive_twin_folder_cleanup.py --apply    # heal

Credentials: GOOGLE_CREDENTIALS_JSON from apps/backend-rag/.env (service
account, domain-wide delegation to zero@balizero.com — same identity as the
backend ServiceAccountDriveService). DB: read-only DSN auto-discovered from
.mcp.json (nuzantara_readonly role).
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("twin-cleanup")

REPO_ROOT = Path(__file__).resolve().parent.parent
FOLDER_MIME = "application/vnd.google-apps.folder"
DELEGATED_USER = "zero@balizero.com"


def _load_env_value(key: str) -> str | None:
    # Environment first — on the Fly machine secrets are injected as env vars.
    import os

    if os.environ.get(key):
        return os.environ[key]
    for env_path in (
        REPO_ROOT / "apps" / "backend-rag" / ".env",
        Path.home() / "Desktop" / "nuzantara" / "apps" / "backend-rag" / ".env",
    ):
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                value = line.split("=", 1)[1].strip()
                return value.strip("'\"")
    return None


def _readonly_dsn() -> str:
    import os

    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    for candidate in (REPO_ROOT / ".mcp.json", Path.home() / "Desktop" / "nuzantara" / ".mcp.json"):
        if candidate.exists():
            match = re.search(r"postgres(?:ql)?://\S+?nuzantara_readonly\S+?/[\w-]+", candidate.read_text())
            if not match:
                match = re.search(r"postgres(?:ql)?://[^\s\"']+", candidate.read_text())
            if match:
                return match.group(0).rstrip("\\'\"")
    raise SystemExit("No Postgres DSN found (DATABASE_URL env or .mcp.json)")


def _drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_str = _load_env_value("GOOGLE_CREDENTIALS_JSON")
    if not creds_str:
        raise SystemExit("GOOGLE_CREDENTIALS_JSON not found in backend .env")
    info = None
    try:
        parsed = json.loads(creds_str)
        if parsed.get("type") == "service_account":
            info = parsed
    except json.JSONDecodeError:
        pass
    if info is None:
        info = json.loads(base64.b64decode(creds_str).decode("utf-8"))
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    ).with_subject(DELEGATED_USER)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


async def _fetch_linked_clients() -> list[dict[str, Any]]:
    import asyncpg

    conn = await asyncpg.connect(_readonly_dsn())
    try:
        rows = await conn.fetch(
            "SELECT id, google_drive_folder_id FROM clients "
            "WHERE google_drive_folder_id IS NOT NULL AND deleted_at IS NULL"
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def _get_meta(service, file_id: str) -> dict[str, Any] | None:
    try:
        return (
            service.files()
            .get(fileId=file_id, fields="id, name, parents, trashed", supportsAllDrives=True)
            .execute()
        )
    except Exception as e:
        logger.debug("meta fetch failed for %s: %s", file_id, e)
        return None


def _list_children(service, parent_id: str, folders_only: bool = False) -> list[dict[str, Any]]:
    q = f"'{parent_id}' in parents and trashed = false"
    if folders_only:
        q += f" and mimeType = '{FOLDER_MIME}'"
    items: list[dict[str, Any]] = []
    token = None
    while True:
        resp = (
            service.files()
            .list(
                q=q,
                fields="nextPageToken, files(id, name, mimeType, parents)",
                pageSize=1000,
                pageToken=token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        items.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return items


def _count_descendants(service, folder_id: str) -> int:
    """Count files (non-folders) up to 2 levels deep — twin structures are shallow."""
    total = 0
    children = _list_children(service, folder_id)
    for child in children:
        if child["mimeType"] == FOLDER_MIME:
            total += sum(
                1 for g in _list_children(service, child["id"]) if g["mimeType"] != FOLDER_MIME
            )
        else:
            total += 1
    return total


def _move(service, file_id: str, from_parent: str, to_parent: str) -> None:
    service.files().update(
        fileId=file_id,
        addParents=to_parent,
        removeParents=from_parent,
        supportsAllDrives=True,
        fields="id",
    ).execute()


def _trash(service, file_id: str) -> None:
    service.files().update(
        fileId=file_id, body={"trashed": True}, supportsAllDrives=True, fields="id"
    ).execute()


def _merge_twin_into_keeper(service, twin_id: str, keeper_id: str) -> dict[str, int]:
    """Move every child of twin into keeper (folder-aware), then trash empty twin."""
    stats = {"files_moved": 0, "folders_merged": 0, "folders_moved": 0, "subtrash": 0}
    keeper_subfolders = {
        f["name"]: f["id"] for f in _list_children(service, keeper_id, folders_only=True)
    }
    for child in _list_children(service, twin_id):
        if child["mimeType"] == FOLDER_MIME and child["name"] in keeper_subfolders:
            target = keeper_subfolders[child["name"]]
            for grand in _list_children(service, child["id"]):
                _move(service, grand["id"], child["id"], target)
                stats["files_moved"] += 1
            # child folder is now empty — verify then trash
            if not _list_children(service, child["id"]):
                _trash(service, child["id"])
                stats["subtrash"] += 1
            stats["folders_merged"] += 1
        elif child["mimeType"] == FOLDER_MIME:
            _move(service, child["id"], twin_id, keeper_id)
            stats["folders_moved"] += 1
        else:
            _move(service, child["id"], twin_id, keeper_id)
            stats["files_moved"] += 1
    leftovers = _list_children(service, twin_id)
    if leftovers:
        raise RuntimeError(f"twin {twin_id} not empty after merge: {len(leftovers)} items left")
    _trash(service, twin_id)
    return stats


def main() -> int:
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="merge twins + trash (default: report only)")
    parser.add_argument("--limit", type=int, default=0, help="max twins to process in apply mode (0 = all)")
    parser.add_argument(
        "--out",
        default=str(Path.home() / "logs" / f"drive-twin-cleanup-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"),
        help="JSONL report path",
    )
    args = parser.parse_args()

    service = _drive_service()
    clients = asyncio.run(_fetch_linked_clients())
    logger.info("clients with linked folder: %d", len(clients))

    # 1. metadata of every keeper (linked) folder
    keepers: dict[int, dict[str, Any]] = {}
    linked_missing: list[int] = []
    for i, row in enumerate(clients):
        meta = _get_meta(service, row["google_drive_folder_id"])
        if meta is None or meta.get("trashed"):
            linked_missing.append(row["id"])
            continue
        keepers[row["id"]] = meta
        if (i + 1) % 200 == 0:
            logger.info("keeper metadata: %d/%d", i + 1, len(clients))

    # 2. scan every distinct parent for client folders, group by name
    parents: set[str] = set()
    for meta in keepers.values():
        parents.update(meta.get("parents", []))
    logger.info("distinct parent folders: %d", len(parents))

    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for parent in parents:
        for folder in _list_children(service, parent, folders_only=True):
            by_name[folder["name"]].append(folder)

    # 3. twins = same name as keeper, different id
    twin_rows: list[dict[str, Any]] = []
    for client_id, keeper in keepers.items():
        for candidate in by_name.get(keeper["name"], []):
            if candidate["id"] != keeper["id"]:
                twin_rows.append(
                    {
                        "client_id": client_id,
                        "keeper_id": keeper["id"],
                        "twin_id": candidate["id"],
                        "name": keeper["name"],
                    }
                )

    # 4. enrich with file counts (report) / merge (apply)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    applied = 0
    errors = 0
    total_twin_files = 0
    with out_path.open("w") as fh:
        for row in twin_rows:
            try:
                row["twin_file_count"] = _count_descendants(service, row["twin_id"])
                total_twin_files += row["twin_file_count"]
                if args.apply and (not args.limit or applied < args.limit):
                    row["merge_stats"] = _merge_twin_into_keeper(
                        service, row["twin_id"], row["keeper_id"]
                    )
                    row["status"] = "merged_and_trashed"
                    applied += 1
                else:
                    row["status"] = "report_only"
            except Exception as e:
                row["status"] = "error"
                row["error"] = str(e)
                errors += 1
                logger.error("client %s twin %s: %s", row["client_id"], row["twin_id"], e)
            fh.write(json.dumps(row) + "\n")
        for client_id in linked_missing:
            fh.write(json.dumps({"client_id": client_id, "status": "linked_missing"}) + "\n")

    logger.info(
        "SUMMARY: keepers=%d linked_missing=%d twins=%d twin_files_total=%d applied=%d errors=%d report=%s",
        len(keepers),
        len(linked_missing),
        len(twin_rows),
        total_twin_files,
        applied,
        errors,
        out_path,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
