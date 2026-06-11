#!/usr/bin/env python3
"""WR2 worktree garbage collector — daily 08:00 WITA cron.

Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §10

Cleans up `.worktrees/wr2-run-*` directories created by wr2_carousel_dispatcher
via scripts/agent_start.py. A successful carousel run leaves artifacts in
~/.claude/carousels/<carousel_id>/ (canonical); the worktree itself is just
scratch space that should be pruned post-publish.

Policy (Spec §10):
    - Delete worktrees with name pattern `wr2-run-*` AND age > 24h
    - Skip worktrees that match an open `wr2_carousel_runs.state IN ('drafted',
      'brief_done', 'storyboard_done', 'layout_done', 'critic_pass', 'rendered',
      'awaiting_approval')` — those are in-flight
    - Run `git worktree remove <path>` AND `git branch -D <branch>` (cleanup)
    - Telegram alert if N>5 deleted in single run (catches loop bug)

Env:
    DATABASE_URL            — to check in-flight carousels
    WR2_WORKTREE_GC_ENABLED — false to disable without removing plist
    WR2_WORKTREE_GC_MAX_AGE_HOURS — default 24

Usage:
    python scripts/wr2_worktree_gc.py             # dry-run by default
    python scripts/wr2_worktree_gc.py --apply     # actually delete
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import asyncpg

logger = logging.getLogger("wr2.worktree_gc")

_REPO_ROOT = Path(__file__).resolve().parent.parent
WORKTREES_DIR = _REPO_ROOT / ".worktrees"
WORKTREE_PREFIX = "wr2-run-"
DEFAULT_MAX_AGE_HOURS = 24
TELEGRAM_DELETE_THRESHOLD = 5  # alert if more deleted in single run


def is_enabled() -> bool:
    return os.environ.get("WR2_WORKTREE_GC_ENABLED", "true").lower() not in ("false", "0", "no")


def get_max_age_hours() -> int:
    try:
        return int(os.environ.get("WR2_WORKTREE_GC_MAX_AGE_HOURS", DEFAULT_MAX_AGE_HOURS))
    except ValueError:
        return DEFAULT_MAX_AGE_HOURS


def list_wr2_run_worktrees() -> list[dict]:
    """Enumerate candidate worktrees with mtime."""
    out: list[dict] = []
    if not WORKTREES_DIR.is_dir():
        return out
    for entry in WORKTREES_DIR.iterdir():
        if not entry.is_dir():
            continue
        if not entry.name.startswith(WORKTREE_PREFIX):
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        out.append({
            "path": entry,
            "name": entry.name,
            "age_hours": (time.time() - mtime) / 3600,
            # task_id pattern: wr2-run-<task_id>, where task_id may equal carousel_id
            "task_id": entry.name[len(WORKTREE_PREFIX):],
        })
    return out


async def fetch_inflight_carousels(conn: asyncpg.Connection) -> set[str]:
    """Return set of carousel_ids currently in-flight (not in terminal state).

    P-1 R1.1: `wr2_carousel_runs` belongs to the retired Pipeline A and is
    slated for a drop migration. Tolerate its absence (no in-flight runs can
    exist without the table) instead of crashing the daily GC — spec metric M10.
    """
    try:
        rows = await conn.fetch(
            """
            SELECT carousel_id::text FROM wr2_carousel_runs
             WHERE state IN ('drafted','brief_done','storyboard_done',
                             'layout_done','critic_pass','rendered','awaiting_approval')
            """
        )
    except asyncpg.UndefinedTableError:
        logger.info("wr2_carousel_runs absent (Pipeline A retired) — no in-flight runs")
        return set()
    return {r["carousel_id"] for r in rows}


def remove_worktree(path: Path, *, apply: bool) -> bool:
    """Run git worktree remove + cleanup branch."""
    if not apply:
        logger.info(f"[dry-run] would remove worktree {path.name}")
        return True

    cmd = ["git", "worktree", "remove", "--force", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO_ROOT, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error(f"git worktree remove {path.name} failed: {exc}")
        return False

    if r.returncode != 0:
        logger.warning(f"git worktree remove {path.name} rc={r.returncode} stderr={r.stderr[:200]}")
        # fallback: direct removal if path still exists (git worktree may already be unaware)
        if path.is_dir():
            try:
                shutil.rmtree(path)
            except OSError as exc:
                logger.error(f"shutil.rmtree {path.name} failed: {exc}")
                return False
        return False

    logger.info(f"removed worktree {path.name}")
    return True


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WR2 worktree garbage collector")
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not is_enabled():
        logger.info("WR2_WORKTREE_GC_ENABLED=false — exit clean")
        return 0

    max_age = get_max_age_hours()
    candidates = list_wr2_run_worktrees()
    aged = [c for c in candidates if c["age_hours"] > max_age]

    logger.info(f"scanned {len(candidates)} worktrees, {len(aged)} aged > {max_age}h")
    if not aged:
        return 0

    # Check in-flight via PG
    dsn = os.environ.get("DATABASE_URL")
    inflight: set[str] = set()
    if dsn:
        try:
            conn = await asyncpg.connect(dsn, timeout=10)
            try:
                inflight = await fetch_inflight_carousels(conn)
            finally:
                await conn.close()
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as exc:
            logger.warning(f"in-flight check failed ({exc}), CONSERVATIVE skip all")
            # If we can't check, refuse to delete (avoid clobbering active run)
            return 0
    else:
        logger.warning("DATABASE_URL unset, CONSERVATIVE skip all")
        return 0

    # Filter out in-flight carousels
    to_delete = [c for c in aged if c["task_id"] not in inflight]
    skipped = len(aged) - len(to_delete)
    if skipped:
        logger.info(f"skipped {skipped} aged worktrees (in-flight)")

    deleted = 0
    for c in to_delete:
        if remove_worktree(c["path"], apply=args.apply):
            deleted += 1

    if args.apply and deleted > TELEGRAM_DELETE_THRESHOLD:
        logger.warning(
            f"[TELEGRAM-ALERT] WR2 worktree GC deleted {deleted} worktrees in single run — "
            f"investigate possible loop bug"
        )

    logger.info(f"done: {deleted} deleted, {skipped} skipped (in-flight), apply={args.apply}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
