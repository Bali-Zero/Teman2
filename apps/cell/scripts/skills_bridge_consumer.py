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
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as aioredis

logger = logging.getLogger("skills_bridge")

SECRETS_ENV_FILE = Path.home() / ".nuzantara-secrets.env"

STATE_DIR = Path.home() / ".cell-bridge-state"
LAST_ID_FILE = STATE_DIR / "skills_last_id.txt"
LOCK_FILE = STATE_DIR / "skills_bridge.lock"
FAIL_COUNT_FILE = STATE_DIR / "skills_bridge_503_count.txt"

INCREMENTAL_SAVE_EVERY = 50  # CORR-G2
STREAM_MAXLEN = 5000


def _load_secrets_env() -> None:
    """Best-effort load of ~/.nuzantara-secrets.env (setdefault, never override).

    The LaunchAgent invokes this script directly (no `bash -lc` wrapper that
    sources the secrets file), so env like REDIS_PASSWORD must be picked up
    here. Same pattern as scripts/pg-to-organism-bridge.py.
    """
    if not SECRETS_ENV_FILE.is_file():
        return
    try:
        for line in SECRETS_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except Exception as e:
        logger.warning("[skills_bridge] could not source secrets env: %s", e)


def _resolve_redis_url(url: str) -> str:
    """Inject REDIS_PASSWORD into a password-less redis URL.

    Local Pro Redis has requirepass since 2026-06-29; the fleet convention
    for the credential is the REDIS_PASSWORD env var (cf. scripts/
    agent_lease.py). A URL that already carries auth is returned untouched.
    """
    password = os.environ.get("REDIS_PASSWORD", "")
    if not password:
        return url
    parsed = urllib.parse.urlparse(url)
    if parsed.password:
        return url
    host_port = parsed.netloc.rsplit("@", 1)[-1]
    netloc = f":{urllib.parse.quote(password, safe='')}@{host_port}"
    return urllib.parse.urlunparse(parsed._replace(netloc=netloc))


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


_GATEWAY_VERDICT_RE = re.compile(r"^tg_notify:\s*(\S+)", re.MULTILINE)


def _find_gateway() -> Path | None:
    """Locate scripts/tg_notify.py — from the checkout this file sits in first.

    `parents[3]` walks scripts → cell → apps → repo root, which is where this
    shim actually runs from (`~/nuzantara/apps/cell/scripts/`). The `~/nuzantara`
    fallback covers a copy executed from anywhere else, so the alarm does not
    die with the location (superscar #1).
    """
    for candidate in (
        Path(__file__).resolve().parents[3] / "scripts" / "tg_notify.py",
        Path.home() / "nuzantara" / "scripts" / "tg_notify.py",
    ):
        if candidate.is_file():
            return candidate
    return None


def _send_telegram_alert(msg: str, *, dedup_key: str) -> None:
    """CORR-G6: route an alert through the tg_notify gateway.

    Why the gateway and not a raw POST. This shim runs every 450s, and the
    503 branch fires whenever the consecutive-failure counter is at or above
    three — the counter keeps CLIMBING, so a Fly outage used to mean one
    Telegram per run, 192 a day, all restating the same fact, with no cooldown
    anywhere in this file. The gateway collapses a repeated `dedup_key` on its
    6/24/72/168h ladder, counts the message against the P0 budget, and records
    it in the ledger — none of which a direct sendMessage can do.

    `dedup_key` is required rather than defaulted: the two callers report two
    different conditions (a 503 streak, an orphaned stream gap) and folding
    them onto one key would let the noisy one silence the rare one.
    """
    gateway = _find_gateway()
    if gateway is None:
        # Loud in the log rather than silent: an alert that could not be sent
        # must still leave a trace of not having been sent (W108).
        logger.warning("[skills_bridge] no tg_notify gateway — alert NOT sent: %s", msg)
        return
    cmd = [
        # Absolute interpreter: the alarm must not share a failure mode with
        # the thing it reports (W108).
        sys.executable,
        str(gateway),
        "--tier",
        "p0",
        "--source",
        "skills-bridge-consumer",
        "--dedup-key",
        dedup_key,
        "--",
        msg,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("[skills_bridge] tg_notify unreachable: %s", e)
        return
    # Verdict on stderr, never the exit code — the gateway exits 0 by design,
    # so a refusal read through returncode looks like a success (W104).
    match = _GATEWAY_VERDICT_RE.search(proc.stderr or "")
    if match:
        logger.info("[skills_bridge] tg_notify: %s (%s)", match.group(1), dedup_key)
    else:
        tail = " ".join((proc.stderr or "").split())[-160:]
        logger.warning(
            "[skills_bridge] tg_notify printed no verdict (rc=%s): %s",
            proc.returncode, tail or "<empty>",
        )


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
                "consecutively. Check Fly app health + Upstash connectivity.",
                # The key names the CONDITION, never the measurement: `n` is in
                # the TEXT because a human wants to know how bad it is, and out
                # of the KEY because a counter that climbs every 450s would mint
                # a fresh key per firing and defeat the dedup window entirely.
                dedup_key="skills-bridge:503-streak",
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
            "Reset last_id to $ — events orphaned. Investigate Fly Upstash MAXLEN.",
            # Its own key: an orphaned-events gap is rare and must not be
            # swallowed by a 503 storm holding the shared window open.
            dedup_key="skills-bridge:stream-gap",
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

    _load_secrets_env()
    fly_bridge_url = os.getenv("FLY_BRIDGE_URL", "https://nuzantara-rag.fly.dev")
    api_key = os.getenv("BRIDGE_SKILLS_API_KEY", "")
    pro_redis_url = _resolve_redis_url(os.getenv("PRO_REDIS_URL", "redis://127.0.0.1:6379"))

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
