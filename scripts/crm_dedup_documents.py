"""De-duplicate CRM documents that are byte-identical re-uploads.

Context (2026-06-12, follow-up to the Drive cleanup): 158 (client_id,
content_hash) groups hold 192 extra rows — the SAME file (identical md5
content_hash) uploaded multiple times for the same client, each landing as a
DISTINCT Drive file (so the upload-with-retry / double-trigger created real
duplicate Drive blobs, not just duplicate DB rows).

Policy per group (client_id, content_hash, status != deleted):
  - keeper = the row to KEEP = lowest id (oldest). Never touched.
  - losers = every other row in the group.
      * DB: status -> 'deleted' (soft-delete, reversible)
      * Drive: trash the loser's file_id, but ONLY after proving it is
        (a) different from the keeper's file_id, and
        (b) not referenced by ANY other non-deleted document row.
        If either guard fails, the Drive file is left alone (DB row still
        soft-deleted) and the case is flagged. Trash is reversible 30 days.

Safety:
  - content_hash is md5 of file bytes; same client + same md5 = same document.
  - keeper selection is deterministic (min id) so re-runs are idempotent.
  - dry-run by default; --apply required to mutate.

Usage (Fly rag machine, secrets in env; colocate drive_twin_folder_cleanup.py
in the same dir):
  python scripts/crm_dedup_documents.py            # report
  python scripts/crm_dedup_documents.py --apply     # soft-delete + trash
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from drive_twin_folder_cleanup import _drive_service, _load_env_value  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dedup-docs")


def _write_dsn() -> str:
    import os

    for key in ("DATABASE_URL", "DATABASE_URL_FLY", "DATABASE_URL_LOCAL"):
        if os.environ.get(key):
            return os.environ[key]
    # last resort: whatever the helper resolves (may be read-only → UPDATE fails loudly)
    from drive_twin_folder_cleanup import _readonly_dsn

    return _readonly_dsn()


def _trash(service, file_id: str) -> None:
    service.files().update(
        fileId=file_id, body={"trashed": True}, supportsAllDrives=True, fields="id"
    ).execute()


def main() -> int:
    import asyncio

    import asyncpg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="mutate (default dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="max loser rows to process (0=all)")
    parser.add_argument(
        "--out",
        default=str(Path.home() / "logs" / f"crm-dedup-docs-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"),
    )
    args = parser.parse_args()
    service = _drive_service()

    async def run() -> list[dict[str, Any]]:
        conn = await asyncpg.connect(_write_dsn())
        rows_out: list[dict[str, Any]] = []
        processed = 0
        try:
            groups = await conn.fetch(
                """
                SELECT client_id, content_hash,
                       array_agg(id ORDER BY id) AS ids,
                       array_agg(COALESCE(file_id,'') ORDER BY id) AS file_ids
                FROM documents
                WHERE status <> 'deleted' AND content_hash IS NOT NULL
                GROUP BY client_id, content_hash
                HAVING count(*) > 1
                ORDER BY client_id
                """
            )
            for g in groups:
                ids = list(g["ids"])
                file_ids = list(g["file_ids"])
                keeper_id, keeper_file = ids[0], file_ids[0]
                for loser_id, loser_file in zip(ids[1:], file_ids[1:]):
                    if args.limit and processed >= args.limit:
                        break
                    rec: dict[str, Any] = {
                        "client_id": g["client_id"],
                        "keeper_id": keeper_id,
                        "loser_id": loser_id,
                        "loser_file_id": loser_file or None,
                    }
                    # Drive-trash guards
                    trash_ok = bool(loser_file) and loser_file != keeper_file
                    if trash_ok:
                        other = await conn.fetchval(
                            "SELECT count(*) FROM documents "
                            "WHERE file_id = $1 AND status <> 'deleted' AND id <> $2",
                            loser_file,
                            loser_id,
                        )
                        if other and other > 0:
                            trash_ok = False
                            rec["drive_skip_reason"] = f"file_id shared by {other} other live docs"
                    elif loser_file == keeper_file and loser_file:
                        rec["drive_skip_reason"] = "same file_id as keeper"
                    else:
                        rec["drive_skip_reason"] = "no file_id"

                    if not args.apply:
                        rec["status"] = "dry_run"
                        rec["would_trash_drive"] = trash_ok
                        rows_out.append(rec)
                        processed += 1
                        continue

                    # 1) soft-delete the DB row
                    await conn.execute(
                        "UPDATE documents SET status='deleted', updated_at=NOW() WHERE id=$1",
                        loser_id,
                    )
                    # 2) trash the Drive blob if guards passed
                    if trash_ok:
                        try:
                            _trash(service, loser_file)
                            rec["drive_trashed"] = True
                        except Exception as e:
                            rec["drive_trashed"] = False
                            rec["drive_error"] = str(e)[:160]
                    else:
                        rec["drive_trashed"] = False
                    rec["status"] = "deduped"
                    rows_out.append(rec)
                    processed += 1
        finally:
            await conn.close()
        return rows_out

    rows = asyncio.run(run())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    summary = Counter(r["status"] for r in rows)
    drive_trashed = sum(1 for r in rows if r.get("drive_trashed"))
    drive_skipped = sum(1 for r in rows if not r.get("would_trash_drive", r.get("drive_trashed")))
    logger.info(
        "SUMMARY apply=%s rows=%d %s drive_trashed=%d drive_skipped=%d report=%s",
        args.apply,
        len(rows),
        dict(summary),
        drive_trashed,
        drive_skipped,
        out_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
