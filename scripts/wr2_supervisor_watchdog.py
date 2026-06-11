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

  P2 LEDGER_GAP (P-1 S10d, 2026-06-11)
      A draft reached `rendered` (drive_url set) more than 24h ago but has
      no `topic_type_log` row — the anti-sameness ledger write (best-effort
      in wr2_html_render_apply) silently failed. Closes spec metric M2.

Dependencies:
  - `wr2_supervisor_heartbeat` table (migration 161)
  - `war_room_drafts` (status, updated_at, drive_url)
  - `topic_type_log` (migration 216) for the ledger-gap probe
  - DATABASE_URL (Fly Postgres tunnel via wr2-script-wrapper.sh)
  - TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID for alerts (optional;
    when missing, alerts are logged but no Telegram POST is made).

P-1 re-key (2026-06-11, spec S10): the watchdog was Canva-keyed (flag
wr2_canva_renderer_enabled, freshness canva_applied_at, success rate from
~/logs/wr2_canva_apply_telemetry.jsonl with a degrade-open 100% on empty
file). After the 2026-06-09 HTML cutover all three sources went blind. Now:
flag = wr2_html_renderer_enabled, freshness = drive_url/updated_at, success
rate = DB-derived over war_room_drafts (0 attempts → NO-DATA, never 100%).
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
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
# Ledger-gap probe lower bound: only drafts rendered AFTER S1 shipped count as
# gaps (the 39 Canva-era rendered rows legitimately predate the HTML ledger hook).
LEDGER_GAP_SINCE = datetime.fromisoformat(
    os.environ.get("WR2_WATCHDOG_LEDGER_SINCE", "2026-06-11T00:00:00+00:00")
)

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


async def _probe_renderer_enabled(conn: asyncpg.Connection) -> bool:
    """Kill-switch awareness (W46 pattern, re-keyed to the HTML lane by P-1 S10).

    Reads `system_settings.wr2_html_renderer_enabled` — the live chokepoint
    flag since the 2026-06-09 cutover (PR #1236). Defaults to True when the
    row is missing (degrade-OPEN: assume feature is on, fire alerts as
    before — safer than silent suppression on fresh prod).

    Pipeline_frozen + success_rate_low alerts are gated on this flag at
    their respective sites — when the render worker is deliberately
    disabled, the pipeline being "frozen" is the EXPECTED state, not an
    incident (W46 root finding, 2026-05-23).
    """
    try:
        row = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key = $1",
            "wr2_html_renderer_enabled",
        )
    except asyncpg.UndefinedTableError:
        logger.debug("system_settings table missing — degrade-open (assume enabled)")
        return True
    if row is None:
        return True  # missing row = default enabled
    return str(row).strip().lower() in {"true", "1", "yes", "on", "enabled"}


async def _probe_pipeline_state(conn: asyncpg.Connection) -> dict[str, Any]:
    """Snapshot for PIPELINE_FROZEN: oldest pending + recent renders.

    Returns `{"renderer_disabled": True, ...}` early when the HTML render
    worker is killed via system_settings.wr2_html_renderer_enabled=false
    (W46 pattern). Caller sees `renderer_disabled=True` and skips the
    pipeline_frozen alert — pipeline naturally backs up while feature is
    off, which is by design.
    """
    if not await _probe_renderer_enabled(conn):
        return {
            "oldest_pending_hours": 0.0,
            "rendered_recent": 0,
            "renderer_disabled": True,
        }
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
    # asyncpg accepts datetime.timedelta and binds it directly as
    # `interval`. Passing a string and casting via $1::interval fails
    # with "'str' object has no attribute 'days'" because asyncpg's
    # codec dispatches by Python type, not target type. Empirical
    # repro 2026-05-08 08:10 WITA on production tunnel.
    rendered_recent = await conn.fetchval(
        """
        SELECT COUNT(*)
          FROM war_room_drafts
         WHERE status = 'rendered'
           AND drive_url IS NOT NULL
           AND updated_at > NOW() - $1::interval
        """,
        timedelta(hours=RENDERED_24H_HOURS),
    )
    return {
        "oldest_pending_hours": float(oldest_pending) if oldest_pending else 0.0,
        "rendered_recent": int(rendered_recent or 0),
        "renderer_disabled": False,
    }


async def _probe_success_rate_db(conn: asyncpg.Connection) -> dict[str, Any]:
    """7-day render success rate, DB-derived (P-1 S10b).

    Replaces the Canva telemetry JSONL: the old probe returned a degrade-open
    100% on an empty/missing file, which goes permanently blind once the file
    stops being written (red-team finding 2026-06-11). DB outcomes cannot
    drift from reality: attempted = rendered|render_failed in the window,
    succeeded = rendered with drive_url.

    0 attempts → {"no_data": True, "rate_pct": None} — the caller logs
    NO-DATA and skips the alert; it must NEVER read as a healthy 100%.
    """
    row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS attempted,
               COUNT(*) FILTER (WHERE status = 'rendered' AND drive_url IS NOT NULL) AS succeeded
          FROM war_room_drafts
         WHERE status IN ('rendered', 'render_failed')
           AND updated_at > NOW() - $1::interval
        """,
        timedelta(days=SUCCESS_WINDOW_DAYS),
    )
    attempted = int(row["attempted"] or 0) if row else 0
    succeeded = int(row["succeeded"] or 0) if row else 0
    if attempted == 0:
        return {
            "window_days": SUCCESS_WINDOW_DAYS,
            "attempted": 0,
            "succeeded": 0,
            "rate_pct": None,
            "no_data": True,
        }
    return {
        "window_days": SUCCESS_WINDOW_DAYS,
        "attempted": attempted,
        "succeeded": succeeded,
        "rate_pct": round((succeeded / attempted) * 100.0, 1),
        "no_data": False,
    }


async def _probe_ledger_gap(conn: asyncpg.Connection) -> int:
    """Count rendered drafts (>24h old, post-S1) missing their topic_type_log
    row (P-1 S10d — closes spec metric M2 against the best-effort write).

    Bounded below by LEDGER_GAP_SINCE so Canva-era renders never count.
    """
    try:
        gap = await conn.fetchval(
            """
            SELECT COUNT(*)
              FROM war_room_drafts d
              LEFT JOIN topic_type_log t ON t.draft_id = d.id
             WHERE d.status = 'rendered'
               AND d.drive_url IS NOT NULL
               AND d.updated_at >= $1
               AND d.updated_at < NOW() - INTERVAL '24 hours'
               AND t.draft_id IS NULL
            """,
            LEDGER_GAP_SINCE,
        )
    except asyncpg.UndefinedTableError:
        logger.debug("topic_type_log table missing — degrade-open")
        return 0
    return int(gap or 0)


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
            _state_set("last_alert_supervisor_down", now_epoch)
            logger.warning("ALERT P0 supervisor_down age=%.0fs", age)
        else:
            logger.info("supervisor_down stale but cooldown active (age=%.0fs)", age)
    else:
        logger.debug("heartbeat ok (age=%s)", age)

    # P0 — PIPELINE_FROZEN (W46: skip when the render worker is kill-switched OFF)
    pipeline = await _probe_pipeline_state(conn)
    if pipeline.get("renderer_disabled"):
        # Operator deliberately disabled the render worker via
        # system_settings.wr2_html_renderer_enabled=false. Pipeline being
        # "frozen" while feature is off is the expected state, not an
        # incident. Skip the alert + reset cooldown so the next genuine
        # incident fires immediately when feature is re-enabled.
        logger.info("pipeline_frozen check skipped (html-renderer kill switch OFF)")
        # Clear stale cooldown so re-enabling the feature gets a fresh alert
        # window if the pipeline is still actually frozen.
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if STATE_PATH.is_file():
            kept = [
                line for line in STATE_PATH.read_text().splitlines()
                if not line.startswith("last_alert_pipeline_frozen=")
            ]
            STATE_PATH.write_text("\n".join(kept) + ("\n" if kept else ""))
    elif (
        pipeline["oldest_pending_hours"] > PENDING_OLDEST_HOURS
        and pipeline["rendered_recent"] == 0
    ):
        if _alert_due("pipeline_frozen", now_epoch):
            msg = (
                "🚨 *WR2 Pipeline FROZEN*\n"
                f"Oldest pending draft: *{pipeline['oldest_pending_hours']:.1f}h*\n"
                f"Drafts rendered in last {int(RENDERED_24H_HOURS)}h: *{pipeline['rendered_recent']}*\n"
                "Either the html-apply worker is failing every run, or "
                "input has stopped. Check `~/logs/wr2-html-apply.log` and "
                "`launchctl print gui/$(id -u)/com.balizero.wr2.html-apply`."
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

    # P1 — SUCCESS_RATE_LOW (7-day rolling, W46: skip when the renderer is OFF —
    # no work attempted = trivially "low rate", false-alert)
    if pipeline.get("renderer_disabled"):
        logger.info("success_rate_low check skipped (html-renderer kill switch OFF)")
        return
    sr = await _probe_success_rate_db(conn)
    # Need a minimum sample size to avoid first-day flutter.
    MIN_ATTEMPTS = 5
    if sr["no_data"]:
        logger.info("success rate NO-DATA (0 render attempts in %dd window)", sr["window_days"])
    elif (
        sr["attempted"] >= MIN_ATTEMPTS
        and sr["rate_pct"] < SUCCESS_THRESHOLD_PCT
    ):
        if _alert_due("success_rate_low", now_epoch):
            msg = (
                "⚠️ *WR2 render success rate LOW*\n"
                f"Last {sr['window_days']}d: *{sr['succeeded']}/{sr['attempted']}* successful "
                f"({sr['rate_pct']}%, threshold {SUCCESS_THRESHOLD_PCT}%).\n"
                "Review `~/logs/wr2-html-apply.log` for the dominant failure "
                "(designer-loop convergence, Drive upload, lease loss)."
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
            "success rate ok (rate=%s%% attempts=%d)", sr["rate_pct"], sr["attempted"]
        )

    # P2 — LEDGER_GAP (P-1 S10d): rendered >24h without a topic_type_log row
    # means the best-effort S1 write failed silently; the variety machine
    # starves without it (spec metric M2).
    gap = await _probe_ledger_gap(conn)
    if gap > 0:
        if _alert_due("ledger_gap", now_epoch):
            msg = (
                "⚠️ *WR2 topic_type_log GAP*\n"
                f"*{gap}* rendered draft(s) older than 24h have no anti-sameness "
                "ledger row. The S1 best-effort write in wr2_html_render_apply is "
                "failing — check `~/logs/wr2-html-apply.log` for "
                "`topic_type_log write failed`."
            )
            _send_telegram(msg)
            _state_set("last_alert_ledger_gap", now_epoch)
            logger.warning("ALERT P2 ledger_gap count=%d", gap)
        else:
            logger.info("ledger_gap detected but cooldown active (count=%d)", gap)
    else:
        logger.debug("ledger ok (no gaps)")


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
                except (
                    asyncpg.PostgresError,
                    asyncpg.InterfaceError,  # W29: stale connection after pg-proxy hiccup
                    OSError,
                    asyncio.TimeoutError,
                ):
                    raise  # let outer reconnect handle it
                except Exception as e:  # noqa: BLE001 — never crash on per-tick error
                    logger.exception("evaluate failed: %s", e)
                # W47 (2026-05-23): keepalive SELECT 1 every 5s while waiting for
                # next probe cycle. The watchdog poll interval is 60s by default
                # but Fly proxy WG tunnel drops idle conns at ~10s (cf. observed
                # 2026-04-28 in wr2_supervisor.py:649). Without keepalive, the
                # NEXT poll hits a dead conn → InterfaceError('connection is
                # closed') → outer catch + reconnect (=lost cycle). Empirical
                # pre-W47: 370 Tracebacks/24h, one lost cycle every ~4min.
                # 5s tick keeps socket below the tunnel timeout.
                try:
                    chunk_count = max(1, POLL_INTERVAL_SEC // 5)
                    for _ in range(chunk_count):
                        if _shutdown_event.is_set():
                            return
                        await asyncio.sleep(5)
                        # Keep socket alive. If this raises, outer reconnect
                        # handles it cleanly (same exception path as evaluate).
                        await conn.execute("SELECT 1")
                    # Handle remainder seconds (POLL_INTERVAL_SEC not divisible by 5).
                    remainder = POLL_INTERVAL_SEC - chunk_count * 5
                    if remainder > 0:
                        await asyncio.sleep(remainder)
                except asyncio.CancelledError:
                    return
        except (
            asyncpg.PostgresError,
            asyncpg.InterfaceError,  # W29: "connection is closed" after pg-proxy hiccup
            OSError,
            asyncio.TimeoutError,
        ) as e:
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
