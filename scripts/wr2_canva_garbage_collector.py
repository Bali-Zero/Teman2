#!/usr/bin/env python3
"""WR2 Canva Carousel folder garbage collector.

The canva-apply skill's Phase B duplicates the master into the Carousel
folder for every run. Designs that aren't published end up accumulating:

- 4 buggy orphans (DAHJDtWApaw, DAHJCzTzn1I, DAHHv6JaHiQ, and an old
  DAHJEkWpkzY pre-master variant) from the 2026-05-08/09 broken-master
  recovery cycle.
- 3 designs from 2026-05-10 (DAHJMncSsfo, DAHJM-wVcbg, DAHJNOjr5MM)
  which may or may not get published.
- DAHJNBAUUOk — an intermediate run-2 redo of a3fd4007 that is not in
  the DB at all.

Without GC, the Carousel folder grows monotonically.

This script:
1. Lists all designs in the Carousel folder via Canva MCP.
2. Cross-references with `war_room_drafts` to find which ones are linked
   to a draft AND which drafts have `published_at IS NOT NULL`.
3. Identifies designs that are:
   - linked to a draft, draft is published → KEEP
   - linked to a draft, draft NOT published, created > 30 days ago → CANDIDATE
   - NOT linked to any draft, created > 7 days ago → CANDIDATE (orphan)
4. Default mode: audit only. With --apply, trash the candidates.
5. Always preserves the current `TEMPLATE_DESIGN_ID` master (never trash).

Designed to run weekly via a LaunchAgent. Telegram-alerts on candidates
found so the operator can spot-check before --apply.

Usage:
    python scripts/wr2_canva_garbage_collector.py            # audit
    python scripts/wr2_canva_garbage_collector.py --apply    # trash
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg

logger = logging.getLogger("wr2.canva_gc")

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

try:
    from backend.services.canva_renderer.pending_builder import (
        CAROUSEL_FOLDER_ID,
        TEMPLATE_DESIGN_ID,
    )
except ImportError as exc:
    print(f"ERROR: cannot import pending_builder: {exc}", file=sys.stderr)
    sys.exit(2)

ORPHAN_AGE_DAYS = int(os.environ.get("WR2_GC_ORPHAN_AGE_DAYS", "7"))
UNPUBLISHED_AGE_DAYS = int(os.environ.get("WR2_GC_UNPUBLISHED_AGE_DAYS", "30"))


def _telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage",
            payload,
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


def _canva_list_folder(folder_id: str) -> list[dict] | None:
    """Shell out to claude CLI for the MCP call. Same pattern as the
    validator script — re-uses the operator's authenticated session."""
    prompt = (
        f"Use the Canva MCP list-folder-items tool with folder_id={folder_id} "
        "and item_types=['design'], sort_by='modified_descending'. "
        "Return ONLY the JSON response."
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("claude CLI unavailable: %s", exc)
        return None
    if result.returncode != 0:
        logger.warning("claude exit %d: %s", result.returncode, result.stderr)
        return None
    stdout = result.stdout
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(stdout[start : end + 1])
        return data.get("items") or []
    except json.JSONDecodeError:
        return None


async def _fetch_published_designs(conn: asyncpg.Connection) -> dict[str, dict]:
    """Map of canva_design_id → draft metadata for ALL drafts that have
    a non-null canva_design_id."""
    rows = await conn.fetch(
        """
        SELECT id, topic, status, canva_design_id, created_at, updated_at
          FROM war_room_drafts
         WHERE canva_design_id IS NOT NULL
        """,
    )
    return {r["canva_design_id"]: dict(r) for r in rows}


async def run(apply_changes: bool) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2

    items = _canva_list_folder(CAROUSEL_FOLDER_ID)
    if items is None:
        logger.error(
            "Could not list folder %s. Make sure claude CLI is authenticated "
            "with the Canva MCP. Skipping GC run.",
            CAROUSEL_FOLDER_ID,
        )
        return 2
    logger.info(
        "Folder %s has %d designs", CAROUSEL_FOLDER_ID, len(items)
    )

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        linked = await _fetch_published_designs(conn)
    finally:
        await conn.close()

    now = datetime.now(timezone.utc)
    keep: list[dict] = []
    orphan_candidates: list[dict] = []
    unpublished_candidates: list[dict] = []

    for item in items:
        design = item.get("design") or {}
        design_id = design.get("id")
        if not design_id:
            continue
        if design_id == TEMPLATE_DESIGN_ID:
            keep.append({"design_id": design_id, "reason": "current master"})
            continue
        # Canva returns Unix-seconds for created_at/updated_at.
        created_ts = design.get("created_at")
        try:
            created_dt = (
                datetime.fromtimestamp(int(created_ts), tz=timezone.utc)
                if created_ts
                else now
            )
        except (TypeError, ValueError):
            created_dt = now
        age_days = (now - created_dt).days

        draft = linked.get(design_id)
        if draft is not None:
            if draft.get("status") == "published":
                keep.append({"design_id": design_id, "reason": "draft published"})
            elif age_days >= UNPUBLISHED_AGE_DAYS:
                unpublished_candidates.append(
                    {
                        "design_id": design_id,
                        "draft_id": str(draft.get("id")),
                        "topic": draft.get("topic"),
                        "age_days": age_days,
                    }
                )
            else:
                keep.append(
                    {
                        "design_id": design_id,
                        "reason": f"linked draft, only {age_days}d old",
                    }
                )
        else:
            if age_days >= ORPHAN_AGE_DAYS:
                orphan_candidates.append(
                    {
                        "design_id": design_id,
                        "title": design.get("title"),
                        "age_days": age_days,
                    }
                )
            else:
                keep.append(
                    {
                        "design_id": design_id,
                        "reason": f"unlinked but only {age_days}d old",
                    }
                )

    logger.info("KEEP: %d designs", len(keep))
    logger.info("ORPHAN candidates (no draft, > %dd): %d", ORPHAN_AGE_DAYS, len(orphan_candidates))
    for c in orphan_candidates:
        logger.info(
            "  %s | %dd | %s", c["design_id"], c["age_days"], (c["title"] or "")[:70]
        )
    logger.info(
        "UNPUBLISHED candidates (linked, not published, > %dd): %d",
        UNPUBLISHED_AGE_DAYS,
        len(unpublished_candidates),
    )
    for c in unpublished_candidates:
        logger.info(
            "  %s | draft=%s | %dd | %s",
            c["design_id"],
            c["draft_id"][:8],
            c["age_days"],
            (c["topic"] or "")[:70],
        )

    total_candidates = len(orphan_candidates) + len(unpublished_candidates)
    if total_candidates == 0:
        logger.info("Nothing to clean.")
        return 0

    if not apply_changes:
        _telegram(
            f"WR2 Canva GC: {total_candidates} candidates "
            f"({len(orphan_candidates)} orphans, "
            f"{len(unpublished_candidates)} unpublished). "
            "Run with --apply to trash."
        )
        logger.info("[DRY-RUN] pass --apply to actually trash the candidates.")
        return 0

    # Apply mode: trash via Canva MCP. We don't have a direct trash tool
    # in the current MCP surface — the safest action is to MOVE them out
    # of the Carousel folder into a "trash" folder (operator must create
    # one and set CAROUSEL_TRASH_FOLDER_ID). For now, emit Telegram and
    # let the operator handle manual trash from Canva UI.
    _telegram(
        f"WR2 Canva GC --apply requested but auto-trash is not yet wired. "
        f"Manual trash needed:\n"
        f"Orphans: {', '.join(c['design_id'] for c in orphan_candidates)}\n"
        f"Unpublished: {', '.join(c['design_id'] for c in unpublished_candidates)}"
    )
    logger.warning(
        "auto-trash not yet implemented — Telegram alert sent for manual trash"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually trash the candidates (default is dry-run audit).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return asyncio.run(run(apply_changes=args.apply))


if __name__ == "__main__":
    sys.exit(main())
