"""Re-link CRM clients whose google_drive_folder_id points to a DEAD Drive folder.

Context (2026-06-12, follow-up to PR #1308): the twin-folder census found 17
clients whose `clients.google_drive_folder_id` resolves to a folder that no
longer exists (HTTP 404 notFound) or was trashed. This is a different defect
from the duplicate-twin one: the column is non-NULL but points to nothing, so
`ensure_client_folder` would happily return it as "already exists" without
ever noticing it is dead.

This script heals them. For each target client, INSIDE a per-client pg
advisory lock (same class as ServiceAccountDriveService, so it can't race a
live ensure/create):

  1. re-read google_drive_folder_id and CONFIRM it is still one of the known
     dead ids passed via --dead-ids (refuses otherwise — guards against a
     concurrent repair / a folder that came back)
  2. verify the folder is REALLY dead right now (404 / trashed). If it turns
     out alive (403-style permission flake healed, or restored from trash) →
     SKIP, do not touch.
  3. reuse a live "{id}_{name}" folder found by name under the type parent
     (heals the case where a folder exists but the column drifted), else
     create a fresh root + the 16 standard subfolders
  4. UPDATE clients.google_drive_folder_id + repopulate client_drive_subfolders

Standalone (does NOT import backend code) because the ensure_client_folder fix
is not deployed to Fly yet — it replicates the same folder layout.

Usage (on the Fly rag machine, secrets in env):
  # dry-run — prints the plan, mutates nothing:
  python scripts/drive_relink_missing_folders.py --client-ids 168,251,...
  # apply:
  python scripts/drive_relink_missing_folders.py --client-ids 168,251,... --apply

Credentials + DSN: same discovery as drive_twin_folder_cleanup (env-first,
GOOGLE_CREDENTIALS_JSON + DATABASE_URL).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/tmp")  # Fly: helper colocated in /tmp

from drive_twin_folder_cleanup import (  # noqa: E402
    FOLDER_MIME,
    _drive_service,
    _list_children,
    _load_env_value,
    _readonly_dsn,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("relink-missing")

# Advisory-lock class — MUST match ServiceAccountDriveService.DRIVE_FOLDER_LOCK_CLASS
DRIVE_FOLDER_LOCK_CLASS = 742001

STANDARD_SUBFOLDERS = [
    "00_Profile",
    "01_Immigration",
    "01_Immigration/Actual Visa",
    "01_Immigration/Previous Visa",
    "02_Company",
    "02_Company/AKTA",
    "02_Company/NIB",
    "02_Company/NPWP",
    "02_Company/Profile Perseroan",
    "03_Tax",
    "03_Tax/SPT company",
    "03_Tax/SPT personal",
    "03_Tax/LKPM reports",
    "03_Tax/NPWP personal",
    "04_Family",
    "99_Misc",
]


def _write_dsn() -> str:
    """Prefer a writable DSN (DATABASE_URL) over the read-only MCP one."""
    import os

    for key in ("DATABASE_URL", "DATABASE_URL_FLY", "DATABASE_URL_LOCAL"):
        if os.environ.get(key):
            return os.environ[key]
    # Fall back to whatever drive_twin_folder_cleanup finds (may be read-only —
    # the UPDATE will then fail loudly, which is the correct safe behavior).
    return _readonly_dsn()


def _parent_for_type(client_type: str) -> str:
    if client_type == "individual":
        pid = _load_env_value("GDRIVE_INDIVIDUALS_FOLDER_ID")
    elif client_type == "company":
        pid = _load_env_value("GDRIVE_COMPANIES_FOLDER_ID")
    else:
        pid = None
    return pid or _load_env_value("GOOGLE_DRIVE_ROOT_FOLDER_ID")


def _folder_state(service, folder_id: str) -> str:
    """alive | trashed | dead (404) | error:<reason>."""
    try:
        meta = (
            service.files()
            .get(fileId=folder_id, fields="id, trashed", supportsAllDrives=True)
            .execute()
        )
        return "trashed" if meta.get("trashed") else "alive"
    except Exception as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        if status == 404:
            return "dead"
        return f"error:{status or type(e).__name__}"


def _find_by_name(service, name: str, parent_id: str) -> dict[str, Any] | None:
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")
    q = (
        f"name = '{escaped}' and mimeType = '{FOLDER_MIME}' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    resp = (
        service.files()
        .list(
            q=q,
            fields="files(id, name, webViewLink)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=2,
        )
        .execute()
    )
    files = resp.get("files", [])
    return files[0] if files else None


def _create_folder(service, name: str, parent_id: str) -> dict[str, Any]:
    return (
        service.files()
        .create(
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )


def _build_subfolders(service, root_id: str) -> dict[str, str]:
    cache = {"": root_id}
    out: dict[str, str] = {}
    for path in STANDARD_SUBFOLDERS:
        parts = path.split("/")
        if len(parts) == 1:
            parent, name = root_id, parts[0]
        else:
            parent, name = cache.get(parts[0], root_id), parts[1]
        try:
            sub = _create_folder(service, name, parent)
            out[path] = sub["id"]
            if len(parts) == 1:
                cache[name] = sub["id"]
        except Exception as e:
            logger.error("subfolder %s failed: %s", path, e)
    return out


def main() -> int:
    import asyncio

    import asyncpg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-ids", required=True, help="comma-separated client ids")
    parser.add_argument(
        "--dead-ids",
        default="",
        help="optional comma-separated folder ids confirmed dead; if set, a client whose "
        "current folder id is NOT in this set is skipped (race guard)",
    )
    parser.add_argument("--apply", action="store_true", help="mutate (default: dry-run)")
    parser.add_argument(
        "--out",
        default=str(Path.home() / "logs" / f"drive-relink-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"),
    )
    args = parser.parse_args()

    client_ids = [int(x) for x in args.client_ids.split(",") if x.strip()]
    dead_ids = {x.strip() for x in args.dead_ids.split(",") if x.strip()}
    service = _drive_service()

    async def run() -> list[dict[str, Any]]:
        conn = await asyncpg.connect(_write_dsn())
        results: list[dict[str, Any]] = []
        try:
            for cid in client_ids:
                row: dict[str, Any] = {"client_id": cid}
                await conn.execute("SELECT pg_advisory_lock($1, $2)", DRIVE_FOLDER_LOCK_CLASS, cid)
                try:
                    rec = await conn.fetchrow(
                        "SELECT full_name, client_type, google_drive_folder_id "
                        "FROM clients WHERE id = $1 AND deleted_at IS NULL",
                        cid,
                    )
                    if rec is None:
                        row["status"] = "client_not_found"
                        continue
                    current = rec["google_drive_folder_id"]
                    row["old_folder_id"] = current
                    if dead_ids and current not in dead_ids:
                        row["status"] = "skip_not_in_dead_set"
                        continue

                    state = _folder_state(service, current) if current else "dead"
                    row["observed_state"] = state
                    if state not in ("dead", "trashed"):
                        # alive or transient error → do NOT touch
                        row["status"] = "skip_folder_alive_or_error"
                        continue

                    name = rec["full_name"] or f"client_{cid}"
                    ctype = rec["client_type"] or "individual"
                    folder_name = f"{cid}_{name}"
                    parent = _parent_for_type(ctype)
                    row["folder_name"] = folder_name
                    row["client_type"] = ctype

                    if not args.apply:
                        row["status"] = "dry_run_would_relink"
                        continue

                    existing = _find_by_name(service, folder_name, parent)
                    if existing:
                        new_id = existing["id"]
                        row["reused"] = True
                        subfolders: dict[str, str] = {}
                    else:
                        created = _create_folder(service, folder_name, parent)
                        new_id = created["id"]
                        row["reused"] = False
                        subfolders = _build_subfolders(service, new_id)

                    await conn.execute(
                        "UPDATE clients SET google_drive_folder_id = $1 WHERE id = $2",
                        new_id,
                        cid,
                    )
                    for path, sid in subfolders.items():
                        if "/" not in path:
                            await conn.execute(
                                """INSERT INTO client_drive_subfolders
                                   (client_id, subfolder_name, subfolder_id, created_at)
                                   VALUES ($1, $2, $3, NOW()) ON CONFLICT DO NOTHING""",
                                cid,
                                path,
                                sid,
                            )
                    row["new_folder_id"] = new_id
                    row["subfolder_count"] = len(subfolders)
                    row["status"] = "relinked"
                    logger.info("client %s relinked -> %s (reused=%s)", cid, new_id, row.get("reused"))
                finally:
                    await conn.execute(
                        "SELECT pg_advisory_unlock($1, $2)", DRIVE_FOLDER_LOCK_CLASS, cid
                    )
                    results.append(row)
        finally:
            await conn.close()
        return results

    results = asyncio.run(run())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")

    from collections import Counter

    summary = Counter(r["status"] for r in results)
    logger.info("SUMMARY apply=%s %s report=%s", args.apply, dict(summary), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
