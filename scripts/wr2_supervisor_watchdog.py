#!/usr/bin/env python3
"""WR2 Supervisor Watchdog — Sprint B B3 (2026-05-08).

Reads the latest row from `wr2_supervisor_heartbeat` every 60s and
fires tiered Telegram alerts when the WR2 pipeline shows signs of
hanging. The watchdog itself runs as its own launchd daemon
(KeepAlive=true) so a crash respawns within ~10s.

Tiered alerts (decisions confirmed by the Sprint B design review):

  P0 SUPERVISOR_DOWN
      Latest heartbeat row is older than HEARTBEAT_STALE_SEC (default
      300s = 5× the 60s heartbeat). Means wr2_supervisor is either
      dead or wedged on `await conn.execute("SELECT 1")`.

  P0 PIPELINE_FROZEN
      Oldest non-terminal draft has been pending more than
      PENDING_OLDEST_HOURS hours AND no draft has reached `rendered`
      in the last RENDERED_24H_HOURS. Either input ran dry, or the
      pipeline is unable to render anything.

  P1 SUCCESS_RATE_LOW
      Success rate over the trailing SUCCESS_WINDOW_DAYS (7 days)
      is below SUCCESS_THRESHOLD_PCT (80%). 24h was rejected during
      review because at 1 draft/day a single failure flips to 0%
      and a single success flips to 100% — too noisy. 7-day rolling
      window is robust to per-day variance.

Cooldown:
  Each alert key has its own 24h cooldown so a persistent failure
  doesn't spam the operator. State file
  ~/.agent/decisions/state/wr2_supervisor_watchdog.state with one
  `last_alert_<key>=<epoch>` line per fired alert.

Dependencies:
  - `wr2_supervisor_heartbeat` table (migration 161)
  - `war_room_drafts` (status, updated_at, canva_applied_at)
  - DATABASE_URL (Fly Postgres tunnel via wr2-script-wrapper.sh)
  - TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID for alerts (optional;
    when missing, alerts are logged but no Telegram POST is made).

Telemetry source for the success rate is the JSONL the canva-apply
worker appends to ~/logs/wr2_canva_apply_telemetry.jsonl (PR #516,
B0 instrumentation). Reading the JSONL avoids a second DB round-trip
and counts at-attempt resolution (post-fix #521 ensures the
"success" rows truly persisted to DB).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

logger = logging.getLogger("wr2.supervisor_watchdog")

# ─────────────────────────────────────────────────────────────────────────
# Tunables — env-overridable for test isolation
# ─────────────────────────────────────────────────────────────────────────

POLL_INTERVAL_SEC = int(os.environ.get("WR2_WATCHDOG_POLL_SEC", "60"))
HEARTBEAT_STALE_SEC = int(os.environ.get("WR2_WATCHDOG_HEARTBEAT_STALE_SEC", "300"))  # 5 min
PENDING_OLDEST_HOURS = float(os.environ.get("WR2_WATCHDOG_PENDING_OLDEST_HOURS", "2"))
RENDERED_24H_HOURS = float(os.environ.get("WR2_WATCHDOG_RENDERED_HOURS", "24"))
SUCCESS_WINDOW_DAYS = int(os.environ.get("WR2_WATCHDOG_SUCCESS_WINDOW_DAYS", "7"))
SUCCESS_THRESHOLD_PCT = float(os.environ.get("WR2_WATCHDOG_SUCCESS_THRESHOLD_PCT", "80"))
ALERT_COOLDOWN_SEC = int(os.environ.get("WR2_WATCHDOG_ALERT_COOLDOWN_SEC", "86400"))  # 24h

STATE_PATH = Path.home() / ".agent" / "decisions" / "state" / "wr2_supervisor_watchdog.state"
TELEMETRY_PATH = Path.home() / "logs" / "wr2_canva_apply_telemetry.jsonl"

# ─────────────────────────────────────────────────────────────────────────
# State (cooldown tracking)
# ─────────────────────────────────────────────────────────────────────────

_shutdown_event: asyncio.Event | None = None


def _state_get(key: str) -> int | None:
    """Read an integer epoch from the state file. Missing → None."""
    if not STATE_PATH.is_file():
        return None
    for line in STATE_PATH.read_text().splitlines():
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k == key and v.strip().isdigit():
            return int(v.strip())
    return None


def _state_set(key: str, value: int) -> None:
    """Write key=value into the state file (overwrites existing key)."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    found = False
    if STATE_PATH.is_file():
        for line in STATE_PATH.read_text().splitlines():
            if "=" not in line:
                lines.append(line)
                continue
            k, _, _v = line.partition("=")
            if k == key:
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    STATE_PATH.write_text("\n".join(lines) + "\n")


def _alert_due(key: str, now_epoch: int, cooldown: int = ALERT_COOLDOWN_SEC) -> bool:
    """True if the cooldown for this alert key has elapsed (or never fired)."""
    last = _state_get(f"last_alert_{key}")
    if last is None:
        return True
    return (now_epoch - last) >= cooldown


# ─────────────────────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        logger.info("Telegram skipped (no TELEGRAM_BOT_TOKEN)")
        return
    try:
        data = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": "true",
            }
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — known URL
            f"https://api.telegram.org/bot{token}/sendMessage",
            data,
            timeout=10,
        )
    except Exception as e:  # noqa: BLE001 — alert delivery is best-effort
        logger.warning("Telegram POST failed: %s", e)


# ─────────────────────────────────────────────────────────────────────────
# Probes
# ─────────────────────────────────────────────────────────────────────────

async def _probe_heartbeat_age(conn: asyncpg.Connection) -> float | None:
    """Seconds since the latest wr2_supervisor_heartbeat row.

    Returns None if the table is empty or missing (degrade-open: missing
    table is treated as "no signal" rather than "supervisor down" so we
    don't false-alert during a fresh prod where migration 161 has not yet
    landed).
    """
    try:
        age = await conn.fetchval(
            """
            SELECT EXTRACT(EPOCH FROM (NOW() - written_at))
              FROM wr2_supervisor_heartbeat
             ORDER BY written_at DESC
             LIMIT 1
            """
        )
    except asyncpg.UndefinedTableError:
        logger.debug("heartbeat table missing — degrade-open")
        return None
    if age is None:
        return None
    return float(age)


async def _probe_pipeline_state(conn: asyncpg.Connection) -> dict[str, Any]:
    """Snapshot for PIPELINE_FROZEN: oldest pending + recent renders."""
    # Non-terminal statuses are everything that NeedsToProgress; the
    # supervisor reconcile uses the same list (cf. NONTERMINAL_TO_NEXT_STAGE).
    oldest_pending = await conn.fetchval(
        """
        SELECT EXTRACT(EPOCH FROM (NOW() - MIN(updated_at))) / 3600.0
          FROM war_room_drafts
         WHERE status IN ('briefed', 'briefed_facted', 'drafts',
                          'drafts_imaged', 'drafts_imaged_facted',
                          'drafts_imaged_checked')
        """
    )
    rendered_recent = await conn.fetchval(
        """
        SELECT COUNT(*)
          FROM war_room_drafts
         WHERE status = 'rendered'
           AND canva_applied_at > NOW() - $1::interval
        """,
        f"{int(RENDERED_24H_HOURS)} hours",
    )
    return {
        "oldest_pending_hours": float(oldest_pending) if oldest_pending else 0.0,
        "rendered_recent": int(rendered_recent or 0),
    }


def _probe_success_rate_telemetry() -> dict[str, Any]:
    """7-day success rate from canva-apply telemetry JSONL.

    Reads ~/logs/wr2_canva_apply_telemetry.jsonl (PR #516); returns:
      {"window_days": 7, "attempted": N, "succeeded": M, "rate_pct": float}

    Empty/missing file → attempted=0, rate=100.0 (degrade-open: silence
    is golden until enough datapoints accumulate).
    """
    if not TELEMETRY_PATH.is_file():
        return {"window_days": SUCCESS_WINDOW_DAYS, "attempted": 0, "succeeded": 0, "rate_pct": 100.0}

    cutoff_epoch = (
        datetime.now(timezone.utc).timestamp() - SUCCESS_WINDOW_DAYS * 86400
    )
    attempted = 0
    succeeded = 0
    try:
        with open(TELEMETRY_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = rec.get("ts")
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str).timestamp()
                except ValueError:
                    continue
                if ts < cutoff_epoch:
                    continue
                outcome = rec.get("outcome")
                # Count only attempt-1 rows; cold→retry-success is also
                # counted via attempt=2 success but it's the same draft.
                # Simpler: count every row as one attempt; success is
                # any row with outcome=='success'.
                attempted += 1
                if outcome == "success":
                    succeeded += 1
    except OSError as e:
        logger.warning("telemetry read failed: %s", e)
        return {"window_days": SUCCESS_WINDOW_DAYS, "attempted": 0, "succeeded": 0, "rate_pct": 100.0}

    if attempted == 0:
        rate = 100.0
    else:
        rate = (succeeded / attempted) * 100.0
    return {
        "window_days": SUCCESS_WINDOW_DAYS,
        "attempted": attempted,
        "succeeded": succeeded,
        "rate_pct": round(rate, 1),
    }


# ─────────────────────────────────────────────────────────────────────────
# Alert evaluation
# ─────────────────────────────────────────────────────────────────────────

async def _evaluate_once(conn: asyncpg.Connection) -> None:
    now_epoch = int(datetime.now(timezone.utc).timestamp())

    # P0 — SUPERVISOR_DOWN
    age = await _probe_heartbeat_age(conn)
    if age is not None and age > HEARTBEAT_STALE_SEC:
        if _alert_due("supervisor_down", now_epoch):
            msg = (
                "🚨 *WR2 Supervisor DOWN*\n"
                f"Latest heartbeat row is *{int(age)}s* old "
                f"(threshold {HEARTBEAT_STALE_SEC}s).\n"
                "The wr2_supervisor daemon is wedged or crashed. "
                "Check `launchctl print gui/$(id -u)/com.balizero.wr2.supervisor` "
                "and `tail ~/logs/wr2_supervisor.launchd.err.log`."
            )
            _send_telegram(msg)
            _state_set(f"last_alert_supervisor_down", now_epoch)
            logger.warning("ALERT P0 supervisor_down age=%.0fs", age)
        else:
            logger.info("supervisor_down stale but cooldown active (age=%.0fs)", age)
    else:
        logger.debug("heartbeat ok (age=%s)", age)

    # P0 — PIPELINE_FROZEN
    pipeline = await _probe_pipeline_state(conn)
    if (
        pipeline["oldest_pending_hours"] > PENDING_OLDEST_HOURS
        and pipeline["rendered_recent"] == 0
    ):
        if _alert_due("pipeline_frozen", now_epoch):
            msg = (
                "🚨 *WR2 Pipeline FROZEN*\n"
                f"Oldest pending draft: *{pipeline['oldest_pending_hours']:.1f}h*\n"
                f"Drafts rendered in last {int(RENDERED_24H_HOURS)}h: *{pipeline['rendered_recent']}*\n"
                "Either the canva-apply worker is failing every run, or "
                "input has stopped. Check `~/logs/wr2_canva_apply.log` and "
                "`~/logs/wr2_canva_apply_telemetry.jsonl`."
            )
            _send_telegram(msg)
            _state_set("last_alert_pipeline_frozen", now_epoch)
            logger.warning(
                "ALERT P0 pipeline_frozen oldest=%.1fh rendered=%d",
                pipeline["oldest_pending_hours"],
                pipeline["rendered_recent"],
            )
        else:
            logger.info("pipeline_frozen detected but cooldown active")
    else:
        logger.debug(
            "pipeline ok (oldest=%.1fh rendered=%d)",
            pipeline["oldest_pending_hours"],
            pipeline["rendered_recent"],
        )

    # P1 — SUCCESS_RATE_LOW (7-day rolling)
    sr = _probe_success_rate_telemetry()
    # Need a minimum sample size to avoid first-day flutter.
    MIN_ATTEMPTS = 5
    if (
        sr["attempted"] >= MIN_ATTEMPTS
        and sr["rate_pct"] < SUCCESS_THRESHOLD_PCT
    ):
        if _alert_due("success_rate_low", now_epoch):
            msg = (
                "⚠️ *WR2 Canva success rate LOW*\n"
                f"Last {sr['window_days']}d: *{sr['succeeded']}/{sr['attempted']}* successful "
                f"({sr['rate_pct']}%, threshold {SUCCESS_THRESHOLD_PCT}%).\n"
                "Review canva-apply telemetry for the dominant failure outcome.\n"
                "If the failure mode is `cold_sentinel`/`other` related to MCP, "
                "check the OAuth watchdog state file: "
                "`cat ~/.agent/decisions/state/wr2_canva_oauth.state`."
            )
            _send_telegram(msg)
            _state_set("last_alert_success_rate_low", now_epoch)
            logger.warning(
                "ALERT P1 success_rate_low rate=%.1f%% attempts=%d",
                sr["rate_pct"],
                sr["attempted"],
            )
        else:
            logger.info(
                "success_rate_low detected but cooldown active (rate=%.1f%%)",
                sr["rate_pct"],
            )
    else:
        logger.debug(
            "success rate ok (rate=%.1f%% attempts=%d)", sr["rate_pct"], sr["attempted"]
        )


# ─────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────

async def _run_loop() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set")

    assert _shutdown_event is not None
    backoff = 1.0
    while not _shutdown_event.is_set():
        conn: asyncpg.Connection | None = None
        try:
            logger.info(
                "watchdog connecting to Postgres (poll=%ds, stale=%ds)…",
                POLL_INTERVAL_SEC,
                HEARTBEAT_STALE_SEC,
            )
            conn = await asyncpg.connect(dsn=dsn, command_timeout=30)
            logger.info("watchdog connected; poll loop active")
            backoff = 1.0
            while not _shutdown_event.is_set():
                try:
                    await _evaluate_once(conn)
                except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
                    raise  # let outer reconnect handle it
                except Exception as e:  # noqa: BLE001 — never crash on per-tick error
                    logger.exception("evaluate failed: %s", e)
                try:
                    await asyncio.sleep(POLL_INTERVAL_SEC)
                except asyncio.CancelledError:
                    return
        except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as e:
            logger.warning("watchdog connection lost: %s — reconnecting in %.1fs", e, backoff)
        finally:
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


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    fh = logging.FileHandler(str(log_dir / "wr2_supervisor_watchdog.log"))
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
    loop = asyncio.get_running_loop()

    def _shutdown(signame: str) -> None:
        logger.info("watchdog received %s, draining…", signame)
        assert _shutdown_event is not None
        _shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown, sig.name)

    await _run_loop()
    logger.info("watchdog stopped cleanly")


def main() -> int:
    _configure_logging()
    try:
        asyncio.run(_amain())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
