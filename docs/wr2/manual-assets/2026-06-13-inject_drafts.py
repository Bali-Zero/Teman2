#!/usr/bin/env python3
"""Inject the two 2026-06-13 manual carousels into war_room_drafts.

Manual-injection entry point for pre-authored WR2 content (bypasses the
designer agent on purpose: slides are already written and imaged).

Two-step write: INSERT at 'drafts_imaged_facted', then UPDATE to
'drafts_imaged_checked'. The UPDATE produces the exact
(drafts_imaged_facted -> drafts_imaged_checked) transition the supervisor's
TRANSITIONS dict maps to com.balizero.wr2.html-apply — a plain INSERT at
the final status would resolve to _SENTINEL_UNKNOWN and never kick.
Fallback: the supervisor's reconciliation loop re-kicks any stale
'drafts_imaged_checked' row after WR2_RECONCILE_STALE_MIN (30 min).

PREREQUISITE: the slide PNGs referenced by hero_image_path MUST already
exist on the Pro deploy worktree (they arrive via wr2-deploy-puller pulling
origin/main hourly). Injecting before that means the render hero-gate fails.

Usage (from M5 or Pro):
    # terminal 1 (M5 only — Pro already has pg-proxy on 15432):
    fly proxy 15432:5432 -a nuzantara-postgres
    # terminal 2:
    DATABASE_URL=postgresql://<user>:<pw>@127.0.0.1:15432/zantara \
        python3 docs/wr2/manual-assets/2026-06-13-inject_drafts.py [--dry-run]

The script is idempotent: fixed UUIDs + ON CONFLICT DO UPDATE (re-running
resets the drafts to drafts_imaged_checked and re-kicks the render).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("inject-manual-carousels")

HERE = Path(__file__).resolve().parent

# Fixed UUIDs → idempotent re-runs (UUIDv4, generated once for this batch)
DRAFTS = [
    {
        "id": "7c1f4e62-93ab-4f0e-8d11-20260613aa01",
        "dir": "2026-06-13-pp20-tax",
    },
    {
        "id": "7c1f4e62-93ab-4f0e-8d11-20260613aa02",
        "dir": "2026-06-13-june-deadlines",
    },
]


def _load(draft: dict) -> tuple[str, str, str]:
    spec = json.loads((HERE / draft["dir"] / "slides.json").read_text())
    return spec["topic"], spec.get("register", "pedagogico"), json.dumps(spec["slides"])


async def main() -> int:
    dry_run = "--dry-run" in sys.argv
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2

    payloads = [(d["id"], *_load(d)) for d in DRAFTS]
    for draft_id, topic, register, slides_json in payloads:
        n = len(json.loads(slides_json))
        logger.info("prepared draft %s — %r (%d slides)", draft_id, topic, n)
    if dry_run:
        logger.info("dry-run: no DB write")
        return 0

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        for draft_id, topic, register, slides_json in payloads:
            await conn.execute(
                """
                INSERT INTO war_room_drafts
                  (id, topic, register, slides_json, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, 'drafts_imaged_facted', NOW(), NOW())
                ON CONFLICT (id) DO UPDATE
                  SET topic = EXCLUDED.topic,
                      slides_json = EXCLUDED.slides_json,
                      status = 'drafts_imaged_facted',
                      canva_edit_url = NULL,
                      canva_design_id = NULL,
                      lease_owner = NULL,
                      lease_acquired_at = NULL,
                      updated_at = NOW()
                """,
                draft_id,
                topic,
                register,
                slides_json,
            )
            # Separate statement => status-change trigger fires the exact
            # (drafts_imaged_facted -> drafts_imaged_checked) transition.
            await conn.execute(
                """
                UPDATE war_room_drafts
                   SET status = 'drafts_imaged_checked', updated_at = NOW()
                 WHERE id = $1
                """,
                draft_id,
            )
            logger.info("injected draft %s -> drafts_imaged_checked", draft_id)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
