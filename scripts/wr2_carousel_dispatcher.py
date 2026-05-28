#!/usr/bin/env python3
"""WR2 Carousel Dispatcher — PG NOTIFY listener → spawn orchestrator.

Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §1
Phase 2.3 of WR2 autonomous carousel pipeline (Antonello 2026-05-27).

This is a SEPARATE daemon from wr2_supervisor.py (763 LOC, mature) —
keeping concerns isolated:

    - wr2_supervisor.py        → war_room_drafts state transitions
    - wr2_carousel_dispatcher  → THIS file, listens for new carousel topics
                                  and spawns wr2_carousel_orchestrator.py

Rationale (cicatrix family — minimal-invasive patch):
    The supervisor LISTEN connection has very specific keepalive +
    contention semantics (per its inline docstring). Adding a new
    channel listen path there would risk regression on a stable
    daemon. Separate dispatcher daemon = clean blast radius.

Flow:
    1. LISTEN topic_ready on dedicated asyncpg conn (W47 keepalive pattern)
    2. On NOTIFY payload {"topic": "...", "carousel_id": "<uuid?>"}:
       a. Pre-flight: quota_throttle_check (MAX usage_5h < 70%)
       b. Spawn worktree via scripts/agent_start.py --lane wr2-run
       c. Exec scripts/wr2_carousel_orchestrator.py in that worktree
       d. Detach (orchestrator runs ~5-15min, supervisor of supervisors
          should not block on it)
    3. Cleanup: post-run worktree GC handled by separate daily cron

Env:
    DATABASE_URL            — PG via localhost:15432
    WR2_DISPATCHER_ENABLED  — false to disable without removing plist
    AGENT_BROKER_ENABLED    — false to disable worktree broker globally
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import asyncpg

logger = logging.getLogger("wr2.dispatcher")

_REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_START_SCRIPT = _REPO_ROOT / "scripts" / "agent_start.py"
ORCHESTRATOR_SCRIPT = _REPO_ROOT / "scripts" / "wr2_carousel_orchestrator.py"
PG_NOTIFY_CHANNEL = "topic_ready"
KEEPALIVE_INTERVAL_SEC = 5
RECONNECT_BACKOFF_SEC = (1, 3, 7, 15, 30)


def is_enabled() -> bool:
    val = os.environ.get("WR2_DISPATCHER_ENABLED", "true").lower().strip()
    return val not in ("false", "0", "no", "off")


def quota_throttle_ok() -> bool:
    """Spec §2.1 — check MAX usage 5h window before spawning.

    Stub: reads claude-max-usage-watcher.py status file. If missing,
    default to allow (degrade gracefully — usage watcher is observability).
    """
    status_path = Path.home() / ".agent" / "decisions" / "claude-max-usage.json"
    if not status_path.is_file():
        return True
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
        usage_pct = float(data.get("usage_5h_pct", 0))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"quota_throttle: read failed ({exc}), allowing")
        return True
    if usage_pct > 70:
        logger.warning(f"quota_throttle: usage_5h={usage_pct}% > 70%, defer")
        return False
    return True


def spawn_orchestrator(carousel_id: str | None, topic: str) -> bool:
    """Spawn agent_start.py worktree + exec orchestrator. Detached."""
    if not AGENT_START_SCRIPT.is_file():
        logger.error(f"agent_start.py not found at {AGENT_START_SCRIPT}")
        return False
    if not ORCHESTRATOR_SCRIPT.is_file():
        logger.error(f"orchestrator not found at {ORCHESTRATOR_SCRIPT}")
        return False

    task_id = carousel_id or f"topic-{int(time.time())}"

    if os.environ.get("AGENT_BROKER_ENABLED", "true").lower() in ("false", "0"):
        logger.info("AGENT_BROKER_ENABLED=false — running orchestrator in main tree")
        cmd = ["python", str(ORCHESTRATOR_SCRIPT), "--topic", topic]
        if carousel_id:
            cmd.extend(["--carousel-id", carousel_id])
    else:
        # Use agent_start.py to create worktree, then orchestrator inside it
        cmd = [
            "python", str(AGENT_START_SCRIPT),
            "--lane", "wr2-run", "--task-id", task_id,
            "--exec", str(ORCHESTRATOR_SCRIPT),
            "--exec-arg", "--topic", "--exec-arg", topic,
        ]
        if carousel_id:
            cmd.extend(["--exec-arg", "--carousel-id", "--exec-arg", carousel_id])

    log_dir = Path.home() / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"wr2-carousel-{task_id}.log"

    try:
        with open(log_file, "ab", buffering=0) as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f, stderr=subprocess.STDOUT,
                start_new_session=True,  # detach from dispatcher process group
                close_fds=True,
            )
    except (OSError, FileNotFoundError) as exc:
        logger.error(f"spawn failed: {exc}")
        return False

    logger.info(f"spawned orchestrator pid={proc.pid} task_id={task_id} log={log_file.name}")
    return True


async def handle_notify(conn: asyncpg.Connection, pid: int, channel: str, payload: str) -> None:
    """asyncpg notify listener callback."""
    logger.info(f"NOTIFY {channel} pid={pid} payload={payload[:200]}")
    try:
        data = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        logger.warning(f"invalid JSON payload, treating as raw topic: {payload[:100]}")
        data = {"topic": payload}

    topic = (data.get("topic") or "").strip()
    if not topic:
        logger.warning("NOTIFY without topic, skipping")
        return

    carousel_id = data.get("carousel_id")

    if not quota_throttle_ok():
        # spawn fallback: scheduled retry via supervisor — for now log + skip
        logger.warning(f"quota throttle defer for topic={topic[:60]!r}")
        return

    spawn_orchestrator(carousel_id, topic)


async def listen_loop(dsn: str) -> int:
    """W47 cicatrix family — reconnect-on-error keepalive listener."""
    backoff_idx = 0
    while True:
        try:
            conn = await asyncpg.connect(dsn, timeout=10)
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as exc:
            wait = RECONNECT_BACKOFF_SEC[min(backoff_idx, len(RECONNECT_BACKOFF_SEC) - 1)]
            logger.warning(f"PG connect failed ({exc}), retry in {wait}s")
            await asyncio.sleep(wait)
            backoff_idx += 1
            continue

        backoff_idx = 0
        try:
            await conn.add_listener(PG_NOTIFY_CHANNEL, handle_notify)
            logger.info(f"LISTEN {PG_NOTIFY_CHANNEL} active")
            while True:
                # W47 keepalive — SELECT 1 every 5s to defeat pg-proxy idle drop
                await conn.execute("SELECT 1")
                await asyncio.sleep(KEEPALIVE_INTERVAL_SEC)
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as exc:
            logger.warning(f"listener error ({exc}), reconnect")
            try:
                await conn.close()
            except Exception:
                pass
            await asyncio.sleep(2)
            continue


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WR2 Carousel Dispatcher")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not is_enabled():
        logger.info("WR2_DISPATCHER_ENABLED=false — exit clean")
        return 0

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL env required")
        return 74

    return await listen_loop(dsn)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
