#!/usr/bin/env python3
"""WR2 Supervisor — event-driven pipeline orchestrator.

Replaces five chained launchd plists (draft-generator, image-generator,
fact-extractor, fact-checker, canva-apply) that previously fired at fixed
WITA minutes 05:11..05:16. Topic-selector keeps its 05:10 cron as the
daily entry point.

Architecture
------------
Postgres (Fly nuzantara-postgres) has a row trigger on `war_room_drafts`
that fires `NOTIFY wr2_status_change` whenever `status` changes (or on
INSERT). Payload is JSON: {draft_id, old_status, new_status, changed_at}.

This daemon LISTENs via the local pg-proxy (port 15432). On every payload:
  1. Acquire per-draft asyncio.Lock (preserve commit order for same draft)
  2. Re-read the LATEST status from DB (payload may be stale)
  3. Resolve next stage from TRANSITIONS dict (with wildcard support)
  4. Skip if (draft_id, target) was just dispatched (dedup)
  5. `launchctl kickstart` the next plist — NEVER with `-k` (would kill
     a running stage; workers always drain via bulk SELECT, so a no-op
     kickstart on an already-running stage is fine)
  6. Telegram-alert on rendered / fact_check_failed

Reconciliation
--------------
NOTIFY is fire-and-forget: any messages emitted while the supervisor is
down (Mac sleep, crash, network drop) are LOST. To recover:
  - On startup: scan for non-terminal drafts not updated in
    WR2_RECONCILE_STALE_MIN minutes; re-kick the appropriate stage.
  - Every WR2_RECONCILE_INTERVAL_SEC seconds: same scan repeated.

Lifecycle
---------
- launchd starts us with KeepAlive (on crash) and RunAtLoad=true
- asyncpg auto-reconnects with exp backoff (cap 60s) on conn drop
- SIGTERM drains in-flight handler tasks (15s timeout) before exit

Env (sourced via wr2-script-wrapper.sh)
---------------------------------------
- DATABASE_URL                   local pg-proxy DSN (port 15432)
- TELEGRAM_BOT_TOKEN             review notifications (optional)
- TELEGRAM_OWNER_CHAT_ID         Zero's chat (optional)
- WR2_SUPERVISOR_DRY_RUN         if 'true', log decisions, no kickstarts
- WR2_RECONCILE_INTERVAL_SEC     periodic sweep period (default 300)
- WR2_RECONCILE_STALE_MIN        minutes since last update to consider
                                 a draft stalled (default 30)

Reviewed by Codex GPT-5.5, Gemini 3.1 Pro, DeepSeek Reasoner (2026-04-26).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Any

import asyncpg

logger = logging.getLogger("wr2.supervisor")

# ─────────────────────────────────────────────────────────────────────────
# State machine
# ─────────────────────────────────────────────────────────────────────────

# (old_status, new_status) → next plist label, or None for alert-only.
# "*" matches any prior status (including None for INSERT).
TRANSITIONS: dict[tuple[str | None, str], str | None] = {
    ("*", "briefed"):                                  "com.balizero.wr2.draft-generator",
    ("briefed", "briefed_facted"):                     "com.balizero.wr2.draft-generator",
    ("briefed", "drafts"):                             "com.balizero.wr2.image-generator",
    ("briefed_facted", "drafts"):                      "com.balizero.wr2.image-generator",
    ("drafts", "drafts_imaged"):                       "com.balizero.wr2.fact-extractor",
    ("drafts_imaged", "drafts_imaged_facted"):         "com.balizero.wr2.fact-checker",
    ("drafts_imaged_facted", "drafts_imaged_checked"): "com.balizero.wr2.canva-apply",
    ("*", "rendered"):                                 None,  # Telegram only
    ("*", "fact_check_failed"):                        None,  # Telegram only
    ("*", "rejected"):                                 None,  # log only
}

ALERT_STATUSES = {"rendered", "fact_check_failed"}

# Reconciliation map: which non-terminal statuses need a re-kick if stalled.
NONTERMINAL_TO_NEXT_STAGE: dict[str, str] = {
    "briefed":               "com.balizero.wr2.draft-generator",
    "briefed_facted":        "com.balizero.wr2.draft-generator",
    "drafts":                "com.balizero.wr2.image-generator",
    "drafts_imaged":         "com.balizero.wr2.fact-extractor",
    "drafts_imaged_facted":  "com.balizero.wr2.fact-checker",
    "drafts_imaged_checked": "com.balizero.wr2.canva-apply",
}

RECONCILE_INTERVAL_SEC = int(os.environ.get("WR2_RECONCILE_INTERVAL_SEC", "300"))
RECONCILE_STALE_MIN = int(os.environ.get("WR2_RECONCILE_STALE_MIN", "30"))

# ─────────────────────────────────────────────────────────────────────────
# Globals (initialised in _amain)
# ─────────────────────────────────────────────────────────────────────────

_draft_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_recently_dispatched: set[tuple[str, str]] = set()
_RECENTLY_DISPATCHED_MAX = 1000
_handler_tasks: set[asyncio.Task] = set()
_shutdown_event: asyncio.Event | None = None

# Sentinel for "transition not in TRANSITIONS dict" (vs. None which means alert-only).
_SENTINEL_UNKNOWN = object()


# ─────────────────────────────────────────────────────────────────────────
# Transition resolution
# ─────────────────────────────────────────────────────────────────────────

def _resolve_transition(old: str | None, new: str) -> Any:
    """Resolve (old, new) to a target plist label or sentinel.

    Returns:
        - str (plist label) → kickstart it
        - None              → known transition, no kickstart (alert-only)
        - _SENTINEL_UNKNOWN → no entry, log DEBUG and skip
    """
    if (old, new) in TRANSITIONS:
        return TRANSITIONS[(old, new)]
    if ("*", new) in TRANSITIONS:
        return TRANSITIONS[("*", new)]
    return _SENTINEL_UNKNOWN


# ─────────────────────────────────────────────────────────────────────────
# launchctl kickstart (no -k flag — never kills a running stage)
# ─────────────────────────────────────────────────────────────────────────

def _kickstart(plist_label: str) -> None:
    """Trigger a launchd job. Does NOT use -k (would kill in-flight work).

    If the stage is already running, launchctl returns rc=113 ("service is
    busy") which we treat as a benign no-op: workers always drain ALL
    pending drafts in one bulk SELECT, so a kickstart while busy just
    means "this draft will be picked up on the next iteration".
    """
    if os.environ.get("WR2_SUPERVISOR_DRY_RUN", "").lower() == "true":
        logger.info("[DRY-RUN] would kickstart %s", plist_label)
        return
    try:
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", f"gui/{uid}/{plist_label}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        logger.info("kickstarted %s", plist_label)
    except subprocess.CalledProcessError as e:
        # rc 113 = service busy / already running — that's fine.
        if e.returncode == 113:
            logger.debug("kickstart %s no-op (already running, rc=113)", plist_label)
            return
        logger.error(
            "kickstart %s failed: rc=%d stderr=%s",
            plist_label, e.returncode, (e.stderr or "").strip(),
        )
        _telegram_sync(f"WR2 supervisor: kickstart {plist_label} failed (rc={e.returncode})")
    except subprocess.TimeoutExpired:
        logger.error("kickstart %s timed out (>10s)", plist_label)
        _telegram_sync(f"WR2 supervisor: kickstart {plist_label} timed out")


# ─────────────────────────────────────────────────────────────────────────
# Telegram (sync, called from executor only)
# ─────────────────────────────────────────────────────────────────────────

def _telegram_sync(msg: str) -> None:
    """Synchronous Telegram send. Must be called via run_in_executor."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    if not (token and chat):
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=8
        )
    except Exception as e:
        logger.warning("telegram failed: %s", e)


async def _telegram(msg: str) -> None:
    """Async Telegram wrapper — runs blocking urllib in default executor.

    Avoids blocking the event loop for up to 8 seconds per alert (which
    would stall NOTIFY processing for all other drafts).
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _telegram_sync, msg)


# ─────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────

async def _current_status(conn: asyncpg.Connection, draft_id: str) -> str | None:
    """Read the LATEST status for a draft. Used to skip stale payloads."""
    return await conn.fetchval(
        "SELECT status FROM war_room_drafts WHERE id = $1::uuid", draft_id
    )


# ─────────────────────────────────────────────────────────────────────────
# Notification handler
# ─────────────────────────────────────────────────────────────────────────

async def _handle_payload(payload: dict[str, Any], conn: asyncpg.Connection) -> None:
    """Dispatch one notification payload, with per-draft serialisation.

    Per-draft asyncio.Lock guarantees that two transitions for the SAME
    draft are processed in commit order (without it, asyncio.create_task
    can interleave them and kickstart B before A).
    """
    draft_id = payload.get("draft_id")
    old = payload.get("old_status")
    new = payload.get("new_status")
    if not (draft_id and new):
        logger.debug("malformed payload, skip: %r", payload)
        return

    async with _draft_locks[draft_id]:
        logger.info("draft %s: %s → %s", draft_id, old, new)

        # Re-read current status: payload may be stale if multiple updates
        # landed between our LISTEN and the handler dispatch.
        try:
            current = await _current_status(conn, draft_id)
        except (asyncpg.PostgresError, OSError) as e:
            logger.warning("draft %s: cannot re-read status (%s) — using payload", draft_id, e)
            current = new

        if current is None:
            logger.warning("draft %s no longer exists (deleted?), skip", draft_id)
            return
        if current != new:
            logger.info(
                "draft %s payload says new=%s but current=%s — using current",
                draft_id, new, current,
            )
            new = current

        # Telegram alerts
        if new in ALERT_STATUSES:
            await _telegram(f"WR2 {new}\nDraft: {draft_id}\nFrom: {old}")

        # Resolve next stage
        target = _resolve_transition(old, new)
        if target is _SENTINEL_UNKNOWN:
            logger.debug("no transition mapped for (%s, %s), skip", old, new)
            return
        if target is None:
            return  # alert-only status, no kickstart

        # Per-(draft, target) dedup. Replaces v1's per-plist cooldown which
        # incorrectly suppressed legitimate work for DIFFERENT drafts that
        # happened to target the same plist within 5s.
        dedup_key = (draft_id, target)
        if dedup_key in _recently_dispatched:
            logger.info(
                "dedup skip: draft=%s already dispatched to %s recently",
                draft_id, target,
            )
            return
        _recently_dispatched.add(dedup_key)
        _trim_dedup()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _kickstart, target)


def _trim_dedup() -> None:
    """Bound the dedup set size to avoid unbounded growth."""
    if len(_recently_dispatched) > _RECENTLY_DISPATCHED_MAX:
        # Trim ~10% — set.pop() is O(1) and removes arbitrary elements.
        for _ in range(_RECENTLY_DISPATCHED_MAX // 10):
            _recently_dispatched.pop()


# ─────────────────────────────────────────────────────────────────────────
# Notification listener (asyncpg sync callback)
# ─────────────────────────────────────────────────────────────────────────

def _on_notification(connection, pid, channel, payload_str):  # noqa: ARG001 — asyncpg signature
    """asyncpg notify callback. Schedules async handler and tracks the task.

    Tracked tasks are drained on SIGTERM (see _amain) so we don't leave
    orphan kickstarts in flight after `launchctl bootout`.
    """
    if _shutdown_event is not None and _shutdown_event.is_set():
        logger.debug("shutting down, dropping notification")
        return
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        logger.warning("non-JSON notification on %s: %r (%s)", channel, payload_str, e)
        return
    task = asyncio.create_task(_handle_payload(payload, connection))
    _handler_tasks.add(task)
    task.add_done_callback(_handler_tasks.discard)
    task.add_done_callback(_log_task_exception)


def _log_task_exception(task: asyncio.Task) -> None:
    """Surface exceptions from fire-and-forget handler tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("handler task raised", exc_info=exc)


# ─────────────────────────────────────────────────────────────────────────
# Reconciliation: catches NOTIFYs missed during sleep / crash / disconnect
# ─────────────────────────────────────────────────────────────────────────

async def _reconcile_once(conn: asyncpg.Connection) -> int:
    """Find non-terminal drafts not updated for >RECONCILE_STALE_MIN and re-kick.

    Returns the number of kickstarts issued. Idempotent: dedup set prevents
    re-kicking the same (draft_id, target) twice in a row.
    """
    rows = await conn.fetch(
        """
        SELECT id::text AS draft_id, status, updated_at
          FROM war_room_drafts
         WHERE status = ANY($1::text[])
           AND updated_at < NOW() - ($2 || ' minutes')::interval
         ORDER BY updated_at ASC
        """,
        list(NONTERMINAL_TO_NEXT_STAGE.keys()),
        str(RECONCILE_STALE_MIN),
    )
    n = 0
    for r in rows:
        draft_id = r["draft_id"]
        status = r["status"]
        target = NONTERMINAL_TO_NEXT_STAGE.get(status)
        if not target:
            continue
        dedup_key = (draft_id, target)
        if dedup_key in _recently_dispatched:
            continue
        _recently_dispatched.add(dedup_key)
        _trim_dedup()
        logger.info(
            "reconcile: draft %s stuck at %s for >%dmin → kick %s",
            draft_id, status, RECONCILE_STALE_MIN, target,
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _kickstart, target)
        n += 1
    return n


async def _reconcile_loop(conn: asyncpg.Connection) -> None:
    """Periodic reconciliation. Runs in addition to the live LISTEN handler."""
    # Startup scan immediately — recovers from any NOTIFYs missed during
    # supervisor downtime (sleep, crash, network drop).
    try:
        n = await _reconcile_once(conn)
        if n:
            logger.info("startup reconcile: kicked %d stalled draft(s)", n)
        await _telegram(
            f"WR2 supervisor up. Startup reconcile: {n} stalled drafts re-kicked."
        )
    except Exception:
        logger.exception("startup reconcile failed")

    assert _shutdown_event is not None
    while not _shutdown_event.is_set():
        try:
            await asyncio.wait_for(
                _shutdown_event.wait(), timeout=RECONCILE_INTERVAL_SEC
            )
            break  # shutdown signalled
        except asyncio.TimeoutError:
            pass  # interval elapsed → run reconcile
        try:
            n = await _reconcile_once(conn)
            if n:
                logger.info("periodic reconcile: kicked %d stalled draft(s)", n)
        except Exception:
            logger.exception("periodic reconcile failed")


# ─────────────────────────────────────────────────────────────────────────
# Connection loop with auto-reconnect
# ─────────────────────────────────────────────────────────────────────────

async def _run_loop() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set")

    assert _shutdown_event is not None
    backoff = 1.0
    while not _shutdown_event.is_set():
        # Initialise to None so the finally block can safely check before close.
        # (Without this, `conn` could be unbound if asyncpg.connect raises.)
        conn: asyncpg.Connection | None = None
        reconcile_task: asyncio.Task | None = None
        try:
            logger.info("connecting to Postgres…")
            conn = await asyncpg.connect(dsn=dsn, command_timeout=30)
            await conn.add_listener("wr2_status_change", _on_notification)
            logger.info("LISTEN wr2_status_change active")
            backoff = 1.0  # reset on success

            reconcile_task = asyncio.create_task(_reconcile_loop(conn))

            # Heartbeat: SELECT 1 every 60s. Surfaces dead connections
            # quickly via TimeoutError → we drop and reconnect.
            while not _shutdown_event.is_set():
                await asyncio.sleep(60)
                await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as e:
            logger.warning("connection lost: %s — reconnecting in %.1fs", e, backoff)
        finally:
            # Cancel reconcile task before closing connection
            if reconcile_task is not None:
                reconcile_task.cancel()
                try:
                    await reconcile_task
                except (asyncio.CancelledError, Exception):
                    pass
            # Close connection if it was opened
            if conn is not None:
                try:
                    await asyncio.wait_for(conn.close(), timeout=5)
                except (asyncio.TimeoutError, Exception):
                    try:
                        conn.terminate()
                    except Exception:
                        pass

        if _shutdown_event.is_set():
            break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


# ─────────────────────────────────────────────────────────────────────────
# Setup + main
# ─────────────────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    log_dir = os.path.expanduser("~/logs")
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    fh = logging.FileHandler(f"{log_dir}/wr2_supervisor.log")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)


async def _amain() -> None:
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    # SIGTERM (launchd stop) and SIGINT (manual ctrl-c) both trigger drain.
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown_event.set)

    runner = asyncio.create_task(_run_loop())
    await _shutdown_event.wait()
    logger.info("shutdown signal received, draining handler tasks…")

    # Drain in-flight handler tasks with a 15s timeout. After that, cancel.
    if _handler_tasks:
        pending = list(_handler_tasks)
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=15,
            )
            logger.info("drained %d handler task(s)", len(pending))
        except asyncio.TimeoutError:
            logger.warning(
                "drain timeout, %d task(s) still running — cancelling",
                len(pending),
            )
            for t in pending:
                t.cancel()

    runner.cancel()
    try:
        await runner
    except asyncio.CancelledError:
        pass
    logger.info("wr2_supervisor stopped cleanly")


def main() -> int:
    _configure_logging()
    logger.info("wr2_supervisor starting (pid=%d)", os.getpid())
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
