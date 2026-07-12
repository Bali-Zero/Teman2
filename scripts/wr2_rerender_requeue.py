#!/usr/bin/env python3
"""wr2_rerender_requeue.py — official WR2 re-render verb (CLI, DB leg).

Puts finished drafts back into the HTML render lane. Cures the W82
exist-not-content blind spot: the HTML-lane fetch gates on `drive_url IS NULL`,
so a draft whose brief/layout was fixed AFTER a render can never re-enter the
pipeline on its own — the row exists, the refreshed content is unreachable.

What this does (per draft id):
  status -> 'drafts_imaged_checked', drive_url -> NULL
  (only from 'rendered' / 'render_failed' / a starved 'drafts_imaged_checked',
   and only when no live lease — see _pg.requeue_draft_for_rerender).

What happens next (NOT triggered here — the cron picks it up naturally):
  the renderer re-renders, `_append_review_queue` REPOINTS the existing queue
  entry in place (same id, fresh slides_dir/drive_url), and a one-shot
  `WR2_PULL_CHECKSUM=1 wr2-queue-pull.sh --once` on M5 reconciles the mirror
  (steady-state `--ignore-existing` skips replaced-in-place PNGs).

Usage (runs where DATABASE_URL reaches prod — Pro, or via scripts/pg.sh env):
  DATABASE_URL=... python3 scripts/wr2_rerender_requeue.py <draft-uuid> [<draft-uuid> ...]
  DATABASE_URL=... python3 scripts/wr2_rerender_requeue.py --dry-run <draft-uuid>

Exit codes: 0 = all requeued · 1 = at least one draft refused (leased/wrong
status/not found) · 2 = usage/connection error.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

# --- sys.path so backend.* imports regardless of cwd (same pattern as wr2_html_render_apply)
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.services.canva_renderer_v2 import _pg  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("wr2-rerender-requeue")


async def _run(draft_ids: list[uuid.UUID], *, dry_run: bool) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set — run where prod PG is reachable (see scripts/pg.sh)")
        return 2
    conn = await asyncpg.connect(dsn, timeout=10)
    failures = 0
    try:
        for draft_id in draft_ids:
            row = await conn.fetchrow(
                "SELECT status, drive_url IS NOT NULL AS has_drive, lease_owner"
                "  FROM war_room_drafts WHERE id = $1",
                draft_id,
            )
            if row is None:
                logger.error("%s: NOT FOUND", draft_id)
                failures += 1
                continue
            logger.info(
                "%s: status=%s has_drive=%s lease=%s",
                draft_id, row["status"], row["has_drive"], row["lease_owner"],
            )
            if dry_run:
                continue
            ok = await _pg.requeue_draft_for_rerender(conn, draft_id)
            if ok:
                logger.info("%s: REQUEUED — next renderer tick will pick it up", draft_id)
            else:
                logger.error("%s: REFUSED (live lease or pre-image status)", draft_id)
                failures += 1
    finally:
        await conn.close()
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("draft_ids", nargs="+", help="war_room_drafts UUIDs to requeue")
    parser.add_argument("--dry-run", action="store_true", help="show current state, change nothing")
    args = parser.parse_args(argv)
    try:
        ids = [uuid.UUID(d) for d in args.draft_ids]
    except ValueError as exc:
        logger.error("invalid draft id: %s", exc)
        return 2
    try:
        return asyncio.run(_run(ids, dry_run=args.dry_run))
    except (asyncpg.PostgresError, OSError) as exc:
        logger.error("connection/query failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
