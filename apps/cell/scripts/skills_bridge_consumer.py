#!/usr/bin/env python3
"""Skills bridge cron shim — Pro side of TICKET G HTTP bridge.

Pulls `cell:skills` Redis stream entries from Fly Upstash via
`GET /api/bridge/skills` and XADDs them to Pro localhost Redis. Designed
to be invoked by a LaunchAgent cron tick (every 5 min between 06-22 WITA).

Spec: research/symbiosis/2026-05-13-ticket-G-narrow-spec.md

Per spec v2:
- CORR-G2: incremental state save every 50 events (resilience under crash).
- CORR-G6: file-based flock single-instance guard + 4 explicit log lines +
  Telegram alert after 3 consecutive 503.
- CORR-G7: cron-invoked shim (NOT daemon — KeepAlive=false in plist).

Environment variables:
- FLY_BRIDGE_URL          (default https://nuzantara-rag.fly.dev)
- BRIDGE_SKILLS_API_KEY   (required; dedicated key, NOT BRIDGE_API_KEY)
- PRO_REDIS_URL           (default redis://127.0.0.1:6379)
- TELEGRAM_BOT_TOKEN      (optional; alerts disabled if unset)
- TELEGRAM_OWNER_CHAT_ID  (optional; default 1125336968)
"""
from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as aioredis

logger = logging.getLogger("skills_bridge")

STATE_DIR = Path.home() / ".cell-bridge-state"
LAST_ID_FILE = STATE_DIR / "skills_last_id.txt"
LOCK_FILE = STATE_DIR / "skills_bridge.lock"
FAIL_COUNT_FILE = STATE_DIR / "skills_bridge_503_count.txt"

INCREMENTAL_SAVE_EVERY = 50  # CORR-G2
STREAM_MAXLEN = 5000


def _acquire_lock_or_exit() -> int:
    """CORR-G6: file-based flock single-instance guard. Returns fd or sys.exit(0)."""
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[skills_bridge] another instance running, skipping this tick")
        os.close(fd)
        sys.exit(0)


def _load_last_id() -> str:
    if not LAST_ID_FILE.exists():
        return "0-0"
    try:
        content = LAST_ID_FILE.read_text().strip()
        return content or "0-0"
    except Exception as e:
        logger.warning("[skills_bridge] state file unreadable, reset to 0-0: %s", e)
        return "0-0"


def _save_last_id(last_id: str) -> None:
    """Atomic write via tempfile + rename."""
    STATE_DIR.mkdir(exist_ok=True)
    tmp = LAST_ID_FILE.with_suffix(".tmp")
    tmp.write_text(last_id)
    tmp.replace(LAST_ID_FILE)


def _increment_503_counter() -> int:
    n = 0
    if FAIL_COUNT_FILE.exists():
        try:
            n = int(FAIL_COUNT_FILE.read_text().strip() or "0")
        except Exception:
            n = 0
    n += 1
    STATE_DIR.mkdir(exist_ok=True)
    FAIL_COUNT_FILE.write_text(str(n))
    return n


def _reset_503_counter() -> None:
    if FAIL_COUNT_FILE.exists():
        try:
            FAIL_COUNT_FILE.unlink()
        except Exception:
            pass


def _send_telegram_alert(msg: str) -> None:
    """CORR-G6: best-effort Telegram alert on 3 consecutive 503."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not bot_token:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=data,
            timeout=5,
        )
    except Exception as e:
        logger.warning("[skills_bridge] Telegram alert failed: %s", e)


async def _xadd_events(
    redis_url: str,
    events: list[dict[str, Any]],
    final_last_id: str,
) -> int:
    """XADD events to Pro Redis with incremental state save every 50 events."""
    client = aioredis.from_url(redis_url, decode_responses=False)
    added = 0
    try:
        for ev in events:
            fields = ev.get("fields", {})
            if not fields:
                continue
            await client.xadd(
                "cell:skills",
                fields,
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
            added += 1
            # CORR-G2: incremental save every N events to survive crash mid-batch
            if added % INCREMENTAL_SAVE_EVERY == 0:
                _save_last_id(ev["id"])
                logger.debug(
                    "[skills_bridge] incremental save at event %d (id=%s)",
                    added, ev["id"],
                )
        _save_last_id(final_last_id)
    finally:
        await client.aclose()
    return added


async def run_one_poll(
    fly_bridge_url: str,
    api_key: str,
    pro_redis_url: str,
) -> int:
    """Single poll cycle. Returns exit code: 0 ok, 1 fail."""
    last_id = _load_last_id()

    if not api_key:
        logger.error("[skills_bridge] BRIDGE_SKILLS_API_KEY not set, aborting")
        return 1

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(
                f"{fly_bridge_url}/api/bridge/skills",
                params={"after_id": last_id, "count": 500},
                headers={"X-Bridge-Skills-Auth": api_key},
            )
    except httpx.RequestError as e:
        logger.warning("[skills_bridge] HTTP request failed: %s", e)
        return 1

    if resp.status_code == 401:
        logger.error("[skills_bridge] auth failed (401) — check BRIDGE_SKILLS_API_KEY")
        return 1
    if resp.status_code == 503:
        n = _increment_503_counter()
        logger.warning("[skills_bridge] Fly returned 503 (consecutive=%d)", n)
        if n >= 3:
            _send_telegram_alert(
                f"⚠️ skills_bridge_consumer: Fly returned 503 {n} times "
                "consecutively. Check Fly app health + Upstash connectivity."
            )
        return 1
    if resp.status_code != 200:
        logger.error(
            "[skills_bridge] unexpected status %d: %s",
            resp.status_code, resp.text[:200],
        )
        return 1

    _reset_503_counter()
    payload = resp.json()
    events = payload.get("events", [])
    new_last_id = payload.get("last_stream_id", last_id)
    events_orphaned = payload.get("events_orphaned", False)
    stream_lowest_id = payload.get("stream_lowest_id")

    # CORR-G4: gap detected — reset to "$" (current head)
    if events_orphaned:
        logger.critical(
            "[skills_bridge] STREAM GAP DETECTED: after_id=%s precedes "
            "stream_lowest=%s. Resetting last_id to '$' — events ORPHANED.",
            last_id, stream_lowest_id,
        )
        _save_last_id("$")
        _send_telegram_alert(
            f"🚨 skills_bridge: stream gap. {last_id} < {stream_lowest_id}. "
            "Reset last_id to $ — events orphaned. Investigate Fly Upstash MAXLEN."
        )
        return 1

    if not events:
        logger.info("[skills_bridge] no new events (last_id=%s)", last_id)
        return 0

    added = await _xadd_events(pro_redis_url, events, new_last_id)
    logger.info(
        "[skills_bridge] success: XADD'd %d events, last_id=%s (was %s)",
        added, new_last_id, last_id,
    )
    return 0


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    fly_bridge_url = os.getenv("FLY_BRIDGE_URL", "https://nuzantara-rag.fly.dev")
    api_key = os.getenv("BRIDGE_SKILLS_API_KEY", "")
    pro_redis_url = os.getenv("PRO_REDIS_URL", "redis://127.0.0.1:6379")

    lock_fd = _acquire_lock_or_exit()
    try:
        return await run_one_poll(fly_bridge_url, api_key, pro_redis_url)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
