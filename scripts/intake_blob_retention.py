"""Intake blob retention — reclaim disk by deleting BYTES of terminal blobs.

Runs ON the Pro (LaunchAgent com.nuzantara.intake-blob-retention, daily):
the Drive/WhatsApp intake pipeline downloads every client file under
INTAKE_BLOB_ROOT (~/.nuzantara/intake-blobs) and NEVER deletes it — the
pipeline has a writer (drive_adapter), a queue (intake_queue) and a consumer
(intake-worker) but NO organ of death. Without this job the blob store grows
unbounded (79 GB / 94k files as of 2026-06-23 → 20% of the Pro SSD).

What it does (and what it deliberately does NOT do):
- Selects intake_queue rows in a TERMINAL status whose blob has been on disk
  longer than the TTL, and `unlink()`s the blob FILE only.
- It NEVER deletes the document_instances or intake_queue ROW. Those are the
  immutable dedup registry (document_instances is `ON DELETE RESTRICT`); the
  blob_hash row keeps de-duplicating future Drive changes so a re-emitted file
  is recognised, not silently re-processed.
- It NEVER touches a blob whose status is non-terminal (pending/ocr/extracted/
  review_*): that is live backlog, the worker still needs the bytes.
- Re-download safety: the Drive cursor (intake_drive_page_token) advances, so a
  blob already seen does not return in the changes feed unless the file truly
  changes on Drive. Deleting the bytes is therefore safe — the extracted value
  already lives in the DB; the file is a 1:1 re-downloadable copy of Drive.

Dry-run is the DEFAULT. Pass --apply to actually unlink. Always logs what it
would reclaim first.

Env:
- LOCAL_DATABASE_URL   (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
- INTAKE_BLOB_ROOT     (default ~/.nuzantara/intake-blobs) — only paths under
                        this root are ever unlinked (defence-in-depth).
- INTAKE_BLOB_TTL_DAYS (default 7) — min blob age before a terminal blob is
                        eligible. created_at-based.

State JSON for the sentinel family: ~/.agent/decisions/state/intake_blob_retention.last.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("intake_blob_retention")

STATE_FILE = Path.home() / ".agent" / "decisions" / "state" / "intake_blob_retention.last.json"

# Statuses where the blob FILE is no longer needed (extracted value is in DB).
# Mirrors the chk_iq_status terminal set; excludes anything still in flight.
_TERMINAL_STATUSES = (
    "done",
    "routed",
    "rejected",
    "duplicate",
    "dead",
)


def _blob_roots() -> list[Path]:
    """The set of directories whose blobs this job is allowed to unlink.

    Defence-in-depth: a blob is only ever unlinked if it resolves strictly
    under ONE of these roots — never an arbitrary path from the DB row.

    Two managed roots by default:
    - the Drive/Dropbox intake cache (``~/.nuzantara/intake-blobs``)
    - the WhatsApp mirror media dir (``~/wa-mirror-media``) — historically
      *outside* the single root, so WA blobs were skipped forever and grew
      unbounded (2.0 GB / 5.6k files, 2026-06-27). They are terminal-status
      copies whose extracted value already lives in the DB, so they obey the
      same TTL contract as every other intake blob.

    Override the whole set with ``INTAKE_BLOB_ROOTS`` (os.pathsep-separated).
    ``INTAKE_BLOB_ROOT`` (singular, legacy) still overrides the first root.
    """
    multi = os.environ.get("INTAKE_BLOB_ROOTS")
    if multi:
        raw = [p for p in multi.split(os.pathsep) if p.strip()]
    else:
        raw = [
            os.environ.get("INTAKE_BLOB_ROOT", os.path.expanduser("~/.nuzantara/intake-blobs")),
            os.path.expanduser("~/wa-mirror-media"),
        ]
    roots: list[Path] = []
    for r in raw:
        try:
            roots.append(Path(r).expanduser().resolve())
        except OSError:
            continue
    return roots


def _is_under_any_root(path: Path, roots: list[Path]) -> bool:
    """True iff `path` is strictly under ANY managed root (defence-in-depth)."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


async def reclaim(pool: asyncpg.Pool, *, ttl_days: int, apply: bool) -> dict[str, int]:
    counters = {
        "candidates": 0,
        "unlinked": 0,
        "bytes_reclaimed": 0,
        "already_gone": 0,
        "outside_root": 0,
        "errors": 0,
    }
    roots = _blob_roots()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT q.id, q.blob_path, q.status, di.byte_size
            FROM intake_queue q
            JOIN document_instances di ON di.id = q.instance_id
            WHERE q.status = ANY($1::text[])
              AND q.created_at < now() - ($2::int * interval '1 day')
            ORDER BY q.created_at
            """,
            list(_TERMINAL_STATUSES),
            ttl_days,
        )

    counters["candidates"] = len(rows)
    for row in rows:
        blob_path = row["blob_path"]
        if not blob_path:
            continue
        p = Path(blob_path)
        if not _is_under_any_root(p, roots):
            counters["outside_root"] += 1
            logger.warning("retention: blob_path outside managed blob roots, skipping: %s", blob_path)
            continue
        if not p.exists():
            counters["already_gone"] += 1
            continue
        size = row["byte_size"] or 0
        if apply:
            try:
                p.unlink()
                counters["unlinked"] += 1
                counters["bytes_reclaimed"] += size
            except OSError as exc:
                counters["errors"] += 1
                logger.warning("retention: unlink failed for %s (%s)", blob_path, exc)
        else:
            counters["unlinked"] += 1  # would-unlink, in dry-run
            counters["bytes_reclaimed"] += size

    return counters


async def main() -> int:
    parser = argparse.ArgumentParser(description="Reclaim disk from terminal intake blobs.")
    parser.add_argument("--apply", action="store_true", help="actually unlink (default: dry-run)")
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=int(os.getenv("INTAKE_BLOB_TTL_DAYS", "7")),
        help="min blob age (created_at) before a terminal blob is eligible",
    )
    args = parser.parse_args()

    db_url = os.getenv(
        "LOCAL_DATABASE_URL", "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
    )

    started = time.time()
    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=2)
    try:
        counters = await reclaim(pool, ttl_days=args.ttl_days, apply=args.apply)
    finally:
        await pool.close()

    elapsed = round(time.time() - started, 1)
    mode = "apply" if args.apply else "dry-run"
    gb = round(counters["bytes_reclaimed"] / (1024**3), 2)
    state = {
        "job": "intake_blob_retention",
        "ts": int(time.time()),
        "status": "ok" if counters["errors"] == 0 else "partial",
        "mode": mode,
        "ttl_days": args.ttl_days,
        "elapsed": elapsed,
        "gb_reclaimed": gb,
        **counters,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state) + "\n")
    logger.info(
        "retention %s done: %s candidates, %s blobs %s, %.2f GB %s",
        mode,
        counters["candidates"],
        counters["unlinked"],
        "unlinked" if args.apply else "would-unlink",
        gb,
        "reclaimed" if args.apply else "reclaimable",
    )
    return 0 if counters["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
