#!/usr/bin/env python3
"""WR2 Canva apply outbox reconciler.

Closes the disallignment gap when `wr2_canva_desktop_apply.py` times out
or crashes BEFORE writing the DB UPDATE, even though the canva-apply
skill completed in Claude Desktop and wrote `carousel_canva.json`.

Symptom (observed 2026-05-10 03:48 WITA on draft de69f035):
- Skill in Claude Desktop completes successfully — `carousel_canva.json`
  has `status="applied"` and a real `design_id`.
- Python script process is dead (poll timeout, OS kill, etc.) — DB
  `war_room_drafts.status` is still `drafts_imaged`, `canva_design_id`
  still NULL.
- Operator has to UPDATE manually (which is what happened tonight).

This script reconciles. Default mode: scan all drafts in
`drafts_imaged` / `drafts` status, check the latest
`carousel_canva.json` for a matching topic, UPDATE if confirmed.

Usage:
    # Dry-run audit (default):
    python scripts/wr2_canva_reconcile.py

    # Apply UPDATE for a specific draft (skill JSON must exist):
    python scripts/wr2_canva_reconcile.py --draft-id <UUID> --apply

    # Apply for whatever the latest carousel_canva.json describes:
    python scripts/wr2_canva_reconcile.py --apply-latest

Idempotent: a draft already in `rendered` status is skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from uuid import UUID

import asyncpg

logger = logging.getLogger("wr2.canva_reconcile")

_LEGACY_OUTPUT_ROOT = Path(
    "/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva"
)
_OUTPUT_ROOT = Path(
    os.environ.get("WR2_OUTPUT_ROOT") or str(_LEGACY_OUTPUT_ROOT)
).resolve()
CANVA_OUTPUT_PATH = _OUTPUT_ROOT / "carousel_canva.json"


def _read_carousel_json() -> dict | None:
    if not CANVA_OUTPUT_PATH.is_file():
        return None
    try:
        return json.loads(CANVA_OUTPUT_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("could not read %s: %s", CANVA_OUTPUT_PATH, e)
        return None


async def _fetch_draft(conn: asyncpg.Connection, draft_id: str) -> asyncpg.Record | None:
    rows = await conn.fetch(
        """
        SELECT id, topic, status, canva_design_id
          FROM war_room_drafts
         WHERE id = $1::uuid
        """,
        draft_id,
    )
    return rows[0] if rows else None


async def _fetch_unfinished(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT id, topic, status, canva_design_id
          FROM war_room_drafts
         WHERE status IN ('drafts_imaged', 'drafts')
           AND canva_edit_url IS NULL
         ORDER BY created_at DESC
         LIMIT 20
        """,
    )


async def _apply_update(
    conn: asyncpg.Connection,
    draft_id: UUID,
    design_id: str,
    edit_url: str,
    view_url: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET canva_design_id  = $2,
               canva_edit_url   = $3,
               canva_view_url   = $4,
               canva_applied_at = NOW(),
               status           = 'rendered',
               updated_at       = NOW()
         WHERE id = $1
           AND status IN ('drafts_imaged', 'drafts')
        """,
        draft_id,
        design_id,
        edit_url,
        view_url,
    )


async def run(
    draft_id: str | None,
    apply_latest: bool,
    apply_changes: bool,
) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2

    payload = _read_carousel_json()
    if not payload:
        logger.error(
            "No %s found — nothing to reconcile against. The skill must "
            "have written its output before this script can match anything.",
            CANVA_OUTPUT_PATH,
        )
        return 2
    if payload.get("status") != "applied" or not payload.get("design_id"):
        logger.error(
            "%s is not in 'applied' state (status=%s, design_id=%s) — "
            "skill probably didn't finish. Re-kickstart the apply, don't "
            "reconcile a half-baked output.",
            CANVA_OUTPUT_PATH,
            payload.get("status"),
            payload.get("design_id"),
        )
        return 2

    skill_topic = payload.get("topic", "")
    skill_design = payload["design_id"]
    skill_edit = payload.get("design_url") or (
        f"https://www.canva.com/design/{skill_design}/edit"
    )
    skill_view = payload.get("view_url")

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        if draft_id:
            row = await _fetch_draft(conn, draft_id)
            if not row:
                logger.error("Draft %s not found in DB", draft_id)
                return 2
            if row["status"] == "rendered" and row["canva_design_id"] == skill_design:
                logger.info(
                    "Draft %s already at rendered with the same design_id — "
                    "no-op.",
                    draft_id,
                )
                return 0
            logger.info(
                "Draft %s: topic=%r DB-status=%s skill-design=%s",
                draft_id,
                row["topic"][:80],
                row["status"],
                skill_design,
            )
            if not apply_changes:
                logger.info("[DRY-RUN] would apply UPDATE; pass --apply to commit")
                return 0
            await _apply_update(
                conn, row["id"], skill_design, skill_edit, skill_view
            )
            logger.info("UPDATED draft %s → %s", draft_id, skill_design)
            return 0

        if apply_latest:
            # Find the unfinished draft whose topic matches the skill JSON.
            candidates = await _fetch_unfinished(conn)
            match = next(
                (r for r in candidates if r["topic"] == skill_topic),
                None,
            )
            if not match:
                logger.error(
                    "No unfinished draft with topic=%r among %d candidates. "
                    "Pick a specific UUID with --draft-id.",
                    skill_topic[:80],
                    len(candidates),
                )
                return 2
            logger.info(
                "Match: draft %s topic=%r → design %s",
                match["id"],
                skill_topic[:80],
                skill_design,
            )
            if not apply_changes:
                logger.info("[DRY-RUN] would apply UPDATE; pass --apply to commit")
                return 0
            await _apply_update(
                conn, match["id"], skill_design, skill_edit, skill_view
            )
            logger.info("UPDATED draft %s → %s", match["id"], skill_design)
            return 0

        # Default: audit only.
        candidates = await _fetch_unfinished(conn)
        logger.info("Skill JSON: topic=%r design=%s", skill_topic[:80], skill_design)
        logger.info("Unfinished drafts (last 20):")
        for r in candidates:
            mark = " ← matches skill" if r["topic"] == skill_topic else ""
            logger.info(
                "  %s | %s | %s%s",
                str(r["id"])[:8],
                r["status"],
                r["topic"][:70],
                mark,
            )
        return 0
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--draft-id",
        metavar="UUID",
        default=None,
        help="Reconcile this specific draft against the latest carousel_canva.json.",
    )
    parser.add_argument(
        "--apply-latest",
        action="store_true",
        help=(
            "Match the latest carousel_canva.json topic to an unfinished "
            "draft and update. Use this when you're sure the skill's most "
            "recent output corresponds to a stuck draft."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually commit the DB UPDATE (default is dry-run).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return asyncio.run(
        run(args.draft_id, args.apply_latest, apply_changes=args.apply)
    )


if __name__ == "__main__":
    sys.exit(main())
