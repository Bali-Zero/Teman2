#!/usr/bin/env python3
"""wr2_image_requeue.py — official WR2 image-lane requeue verb (CLI, DB leg).

Puts an `image_failed` draft back into the PRE-image lane so the image
generator's per-draft cron picks it up on its next tick. Sibling of
`wr2_rerender_requeue.py` (which requeues the HTML render lane) — this one
covers the image-generation lane instead.

Why this exists (2026-07-14): `image_failed` was previously a DEAD-END.
`_fetch_pending` in wr2_image_generator.py only ever selects status IN
('drafts_checked', 'drafts'); nothing rewound a failed draft back into that
set. `wr2_rerender_requeue.py` cannot help either — its whitelist is
('rendered', 'render_failed', 'drafts_imaged_checked'), all POST-image
statuses; the anti-jump doctrine in `_pg.requeue_draft_for_rerender`
("a pre-image draft must never be jumped forward") means it correctly
refuses an `image_failed` row. `image_failed` drafts had no way back in.

Target status (verified against the actual state machine, not guessed):
  `image_failed` -> `drafts`
War_room_drafts.status is CHECK-constrained (migration 222,
`war_room_drafts_status_check`) to an explicit enum that includes both
`drafts` and `drafts_checked` — but only `drafts` is ever WRITTEN by any
producer in this codebase (`wr2_draft_generator.py` sets it on insert;
`drafts_checked` appears only as a legacy/vestigial accept-value in
`_fetch_pending`'s WHERE clause, produced by no current code path). Landing
on `drafts` reuses the exact literal value the image generator's own fetch
already accepts — no new status is invented, no stage is skipped.

What this does (per draft id):
  status -> 'drafts', rejection_reason -> trace note, updated_at -> NOW()
  (ONLY when current status = 'image_failed' — see requeue_image_failed_draft).

What happens next (NOT triggered here — the cron picks it up naturally):
  the image generator re-attempts hero generation (Codex -> FlowKit fallback
  per the 2026-07-14 cascade fix), then the normal drafts_imaged -> ... chain
  resumes untouched.

Usage (runs where DATABASE_URL reaches prod — Pro, or via scripts/pg.sh env):
  DATABASE_URL=... python3 scripts/wr2_image_requeue.py <draft-uuid> [<draft-uuid> ...]
  DATABASE_URL=... python3 scripts/wr2_image_requeue.py --dry-run <draft-uuid>

Exit codes: 0 = all requeued · 1 = at least one draft refused (not found /
wrong status) · 2 = usage/connection error.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from uuid import UUID

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("wr2-image-requeue")

# Only source status this verb ever touches — a pre-image draft, or any
# other status, is refused untouched (no forward/backward jump across a
# stage this tool doesn't own).
_SOURCE_STATUS = "image_failed"
_TARGET_STATUS = "drafts"
_REQUEUE_NOTE = "requeued after fallback-engagement fix 2026-07-14"


async def requeue_image_failed_draft(conn: asyncpg.Connection, draft_id: UUID | str) -> bool:
    """Reset one `image_failed` draft back to the pre-image `drafts` status.

    Guard: only rows currently in status='image_failed' are touched — a
    no-op (False) on anything else, so a wrong/stale id can never be
    silently jumped across the state machine.

    Returns True when the draft re-entered the image-generation lane.
    """
    row = await conn.fetchrow(
        """
        UPDATE war_room_drafts
           SET status           = $2,
               rejection_reason = $3,
               updated_at       = NOW()
         WHERE id = $1
           AND status = $4
        RETURNING id
        """,
        draft_id,
        _TARGET_STATUS,
        _REQUEUE_NOTE,
        _SOURCE_STATUS,
    )
    if row is None:
        logger.warning(
            "requeue_image_failed_draft: draft %s NOT requeued (not found or status != %s)",
            draft_id, _SOURCE_STATUS,
        )
        return False
    logger.info(
        "requeue_image_failed_draft: draft %s -> status=%s (back in image lane)",
        draft_id, _TARGET_STATUS,
    )
    return True


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
                "SELECT status FROM war_room_drafts WHERE id = $1",
                draft_id,
            )
            if row is None:
                logger.error("%s: NOT FOUND", draft_id)
                failures += 1
                continue
            logger.info("%s: status=%s", draft_id, row["status"])
            if row["status"] != _SOURCE_STATUS:
                logger.error(
                    "%s: REFUSED — status=%s (this verb only requeues status=%s)",
                    draft_id, row["status"], _SOURCE_STATUS,
                )
                failures += 1
                continue
            if dry_run:
                logger.info("%s: [DRY-RUN] would requeue to status=%s", draft_id, _TARGET_STATUS)
                continue
            ok = await requeue_image_failed_draft(conn, draft_id)
            if not ok:
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
    except (
        asyncpg.PostgresError,
        asyncpg.InterfaceError,  # sibling of PostgresError, NOT a subclass (W34)
        OSError,
    ) as exc:
        logger.error("connection/query failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
