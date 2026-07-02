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

Outcome probes (C1, next-level plan 2026-06-30 — cicatrix #2 "launchd è
trasporto, non verità"; all READ-ONLY, run right after _evaluate_once):

  P1 STALE_LEASE
      'rendering' rows whose lease heartbeat went silent (>15min; a live
      worker renews every 60s) OR held longer than the max render window
      (>90min — the heartbeat task can keep ticking while the main path
      hangs on Drive, so heartbeat alone is not health). NULL-safe via
      COALESCE(lease_heartbeat_at, lease_acquired_at, updated_at):
      lease_heartbeat_at is nullable (migration 222).

  P2 STATE_AGE
      Oldest row per NON-terminal state older than threshold (default 6h)
      — catches ONE stuck stage while the rest of the pipeline flows
      (pipeline_frozen needs a global zero-render 24h). 'rendering' is
      excluded (covered by STALE_LEASE: its updated_at is heartbeat-touched).
      UNKNOWN states (not in the known machine) are always flagged — the
      state-machine-drift detector (cicatrix #9). When the renderer kill
      switch is OFF, 'drafts_imaged_checked' backlog is expected (W46) and
      is not flagged.

  P2 MANIFEST_GAP (hourly throttle, LIMIT 10, 48h window)
      Drafts at 'rendered' whose Drive folder lacks the C0 manifest.json
      (PR #1892 writes it under the lease — absence = anomaly). Uses the
      renderer's own SA-DWD service lazily; every Drive/import failure
      degrades OPEN (log, no false alert) BUT feeds a fail-streak counter:
      ≥24 consecutive failed sweeps (≈1 day) fire MANIFEST_PROBE_BROKEN so
      the probe cannot rot silently (red-team 2026-07-02 finding #5).
      An unparseable drive_url (no /folders/<id>) is reported as an anomaly.

  P2 WEEKLY_SILENT
      The WR2 reflexion Delta-Gate ledger (_reflexion-state.json, written
      by scripts/lib/reflexion.record_run) has no run newer than 8 days —
      OR the file is missing/malformed. Missing is an ALERT, not a skip:
      the never-armed cron is exactly the W81 disease this probe hunts.

  P1 RUNTIME_STALE (C2, deploy-fork content-gate — cicatrix #1/D5)
      Reads the ~/.organism/last_seen/<organ>.runtime.json provenance
      stamps written by wr2_html_render_apply (per run) and wr2_supervisor
      (at daemon startup). Two disease classes:
        - checkout diseases (dirty / stale_modules): the code on disk is
          not the code HEAD says — alert regardless of process state;
        - process disease (head-moved): the stamped pid is STILL ALIVE but
          the checkout's HEAD moved since its boot — a daemon executing
          pre-pull code forever; the cure is a restart, and only an alert
          makes that visible. Dead pid + moved head is the NORMAL one-shot
          worker case (next run re-stamps) — not flagged.
      Degrade-open when stamps are missing (C2 organs not armed yet).
      Reader is inline JSON (no import from scripts/lib) so this probe and
      the stamp writers can merge/arm in any order.

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
import json
import logging
import os
import re
import signal
import subprocess
import sys
import urllib.error
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

# ── C1 outcome-probe tunables ────────────────────────────────────────────
LEASE_STALE_MIN = float(os.environ.get("WR2_WATCHDOG_LEASE_STALE_MIN", "15"))
LEASE_MAX_HELD_MIN = float(os.environ.get("WR2_WATCHDOG_LEASE_MAX_HELD_MIN", "90"))
STATE_AGE_HOURS = float(os.environ.get("WR2_WATCHDOG_STATE_AGE_HOURS", "6"))
MANIFEST_PROBE_ENABLED = os.environ.get("WR2_WATCHDOG_MANIFEST_PROBE", "1") != "0"
MANIFEST_PROBE_INTERVAL_SEC = int(
    os.environ.get("WR2_WATCHDOG_MANIFEST_PROBE_INTERVAL_SEC", "3600")
)
MANIFEST_FAIL_STREAK = int(os.environ.get("WR2_WATCHDOG_MANIFEST_FAIL_STREAK", "24"))
REFLEXION_STALE_DAYS = float(os.environ.get("WR2_WATCHDOG_REFLEXION_STALE_DAYS", "8"))

# Live state machine (cf. wr2_supervisor.NONTERMINAL_TO_NEXT_STAGE — the dead
# 'briefed_facted' was removed by P-1 2026-06-11; keeping the lists aligned by
# ENTITY, not by copy-paste of the old probe's hardcoded set).
KNOWN_NONTERMINAL_STATUSES = (
    "briefed",
    "drafts",
    "drafts_imaged",
    "drafts_imaged_facted",
    "drafts_imaged_checked",
)
TERMINAL_STATUSES = (
    "rendered",
    "rendered_shadow",
    "render_failed",
    "fact_check_failed",
    "image_failed",
    "rejected",
)

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

def _post_telegram(token: str, payload: dict) -> None:
    data = urllib.parse.urlencode(payload).encode()
    urllib.request.urlopen(  # noqa: S310 — known URL
        f"https://api.telegram.org/bot{token}/sendMessage",
        data,
        timeout=10,
    )


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        logger.info("Telegram skipped (no TELEGRAM_BOT_TOKEN)")
        return
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }
    try:
        _post_telegram(token, payload)
    except urllib.error.HTTPError as e:
        # HTTP 400 = Markdown entity parse failure (unbalanced * / _ in job
        # names or paths). The alert was being silently DROPPED once per
        # cooldown window (observed daily 2026-06-10..12). Resend as plain
        # text: delivery beats formatting for a P0/P1 alert channel.
        if e.code == 400:
            plain = {k: v for k, v in payload.items() if k != "parse_mode"}
            try:
                _post_telegram(token, plain)
                logger.warning("Telegram Markdown rejected (400) — delivered as plain text")
            except Exception as e2:  # noqa: BLE001 — alert delivery is best-effort
                logger.warning("Telegram POST failed (plain-text retry): %s", e2)
        else:
            logger.warning("Telegram POST failed: %s", e)
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
# C1 outcome probes (read-only — the watchdog reads the WORK, not the exit code)
# ─────────────────────────────────────────────────────────────────────────

async def _probe_stale_leases(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """'rendering' rows whose lease looks dead OR held past the max render window.

    Two independent conditions (red-team 2026-07-02 finding #1 — "heartbeat is
    not health": the heartbeat task can keep renewing while the main path hangs):
      a) heartbeat silent  > LEASE_STALE_MIN  (live worker renews every ~60s)
      b) lease held        > LEASE_MAX_HELD_MIN (renders take ~13-22min)
    NULL-safe: lease_heartbeat_at is nullable (migration 222), so COALESCE down
    to lease_acquired_at then updated_at — a NULL chain must never hide a row.
    """
    rows = await conn.fetch(
        """
        SELECT id::text AS draft_id,
               lease_owner,
               EXTRACT(EPOCH FROM (NOW() - COALESCE(lease_heartbeat_at, lease_acquired_at, updated_at))) AS hb_age_sec,
               EXTRACT(EPOCH FROM (NOW() - COALESCE(lease_acquired_at, updated_at))) AS held_sec
          FROM war_room_drafts
         WHERE status = 'rendering'
           AND (
                COALESCE(lease_heartbeat_at, lease_acquired_at, updated_at) < NOW() - $1::interval
             OR COALESCE(lease_acquired_at, updated_at) < NOW() - $2::interval
           )
        """,
        timedelta(minutes=LEASE_STALE_MIN),
        timedelta(minutes=LEASE_MAX_HELD_MIN),
    )
    return [dict(r) for r in rows]


async def _probe_state_ages(
    conn: asyncpg.Connection, *, renderer_enabled: bool
) -> dict[str, list[dict[str, Any]]]:
    """Per-state oldest-row age for every non-terminal state (except 'rendering').

    Returns {"over": [...], "unknown": [...]}:
      over    — KNOWN non-terminal states whose oldest row exceeds STATE_AGE_HOURS.
                When the renderer kill switch is OFF, 'drafts_imaged_checked'
                backlog is by design (W46) and is not flagged.
      unknown — states outside the known machine (terminal ∪ non-terminal ∪
                'rendering'): always flagged, whatever their age — a state
                appearing here means the state machine drifted (cicatrix #9).
    'rendering' is excluded: its updated_at is touched by every heartbeat, so
    age-by-updated_at would lie (red-team finding #4); STALE_LEASE covers it.
    """
    rows = await conn.fetch(
        """
        SELECT status,
               COUNT(*) AS n,
               EXTRACT(EPOCH FROM (NOW() - MIN(updated_at))) / 3600.0 AS oldest_hours
          FROM war_room_drafts
         WHERE status <> ALL($1::text[])
         GROUP BY status
        """,
        list(TERMINAL_STATUSES) + ["rendering"],
    )
    over: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for r in rows:
        entry = {
            "status": r["status"],
            "n": int(r["n"]),
            "oldest_hours": float(r["oldest_hours"] or 0.0),
        }
        if r["status"] not in KNOWN_NONTERMINAL_STATUSES:
            unknown.append(entry)
            continue
        if not renderer_enabled and r["status"] == "drafts_imaged_checked":
            continue  # backlog while kill-switched OFF is the expected state (W46)
        if entry["oldest_hours"] > STATE_AGE_HOURS:
            over.append(entry)
    return {"over": over, "unknown": unknown}


_FOLDER_ID_RE = re.compile(r"/folders/([A-Za-z0-9_-]+)")


def _extract_folder_id(drive_url: str) -> str | None:
    """Folder id from a Drive folder webViewLink; None when the URL has no
    /folders/<id> segment (anomaly — reported, never silently skipped)."""
    m = _FOLDER_ID_RE.search(drive_url or "")
    return m.group(1) if m else None


def _drive_list_names_sync(folder_id: str) -> set[str]:
    """Names of every non-trashed child of a Drive folder.

    Mirrors the renderer's own listing shape (supportsAllDrives +
    includeItemsFromAllDrives — red-team finding #6: omitting either turns
    shared-drive folders into phantom-empty). Lazy imports so the watchdog
    stays asyncpg-only when the probe is disabled; runs in a thread.
    """
    repo = Path(__file__).resolve().parents[1]
    backend_root = str(repo / "apps" / "backend-rag")
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    from backend.services.integrations.service_account_drive_service import (  # noqa: PLC0415
        ServiceAccountDriveService,
    )

    svc = ServiceAccountDriveService()
    names: set[str] = set()
    page_token: str | None = None
    while True:
        res = (
            svc.service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )
        names.update(f.get("name", "") for f in res.get("files", []))
        page_token = res.get("nextPageToken")
        if not page_token:
            return names


async def _probe_manifest_gaps(conn: asyncpg.Connection) -> dict[str, Any] | None:
    """C0-manifest presence sweep over recently rendered drafts.

    Returns None when skipped (kill switch or hourly throttle not elapsed),
    else {"missing": [draft_ids], "unparseable": [draft_ids], "checked": n}.
    Per-draft Drive failures degrade OPEN (a Drive hiccup must not cry wolf)
    but feed the manifest_probe_fail_streak counter so a probe broken for
    ≥MANIFEST_FAIL_STREAK consecutive sweeps raises its own alert instead of
    rotting silently (red-team finding #5).
    """
    if not MANIFEST_PROBE_ENABLED:
        return None
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    last = _state_get("last_probe_manifest")
    if last is not None and (now_epoch - last) < MANIFEST_PROBE_INTERVAL_SEC:
        return None
    _state_set("last_probe_manifest", now_epoch)

    rows = await conn.fetch(
        """
        SELECT id::text AS draft_id, drive_url
          FROM war_room_drafts
         WHERE status = 'rendered'
           AND drive_url IS NOT NULL
           AND updated_at > NOW() - INTERVAL '48 hours'
         ORDER BY updated_at DESC
         LIMIT 10
        """
    )
    missing: list[str] = []
    unparseable: list[str] = []
    probe_failed = False
    for r in rows:
        folder_id = _extract_folder_id(r["drive_url"])
        if folder_id is None:
            unparseable.append(r["draft_id"])
            continue
        try:
            names = await asyncio.to_thread(_drive_list_names_sync, folder_id)
        except Exception as e:  # noqa: BLE001 — degrade-open, streak-counted
            logger.warning("manifest probe: Drive listing failed for %s: %s", r["draft_id"], e)
            probe_failed = True
            continue
        if "manifest.json" not in names:
            missing.append(r["draft_id"])

    if probe_failed:
        _state_set("manifest_probe_fail_streak", (_state_get("manifest_probe_fail_streak") or 0) + 1)
    else:
        _state_set("manifest_probe_fail_streak", 0)
    return {"missing": missing, "unparseable": unparseable, "checked": len(rows)}


RUNTIME_STALE_ORGANS = ("wr2.html_apply", "wr2.supervisor")


def _read_runtime_stamp(organ_id: str) -> dict[str, Any] | None:
    """~/.organism/last_seen/<organ>.runtime.json; None = missing/unreadable
    (degrade-open — the C2 stamp writers may not be armed yet)."""
    try:
        path = Path.home() / ".organism" / "last_seen" / f"{organ_id}.runtime.json"
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _git_head(checkout: str) -> str | None:
    """Current on-disk HEAD of a checkout; None on any failure (fail-open)."""
    try:
        out = subprocess.run(
            ["git", "-C", checkout, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def _pid_alive(pid: Any) -> bool:
    """True if pid is a live process on THIS host (stamps are local files)."""
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _probe_runtime_stale() -> list[dict[str, Any]]:
    """C2: organs whose runtime provenance diverges from the checkout on disk.

    checkout diseases (dirty / stale-modules) flag regardless of process
    state; head-moved flags ONLY when the stamped pid is still alive — a dead
    one-shot worker whose checkout advanced afterwards is the normal case.
    """
    findings: list[dict[str, Any]] = []
    for organ in RUNTIME_STALE_ORGANS:
        stamp = _read_runtime_stamp(organ)
        if not stamp:
            continue
        problems: list[str] = []
        if stamp.get("dirty"):
            problems.append("dirty-checkout")
        if stamp.get("stale_modules"):
            problems.append("stale-modules:" + ",".join(stamp["stale_modules"]))
        checkout = stamp.get("checkout")
        head = stamp.get("head_sha")
        if checkout and head and _pid_alive(stamp.get("pid")):
            disk = _git_head(checkout)
            if disk and disk != head:
                problems.append(
                    f"head-moved:{head[:12]}->{disk[:12]} (live pid {stamp.get('pid')} on old code)"
                )
        if problems:
            findings.append({"organ": organ, "problems": problems, "ts": stamp.get("ts")})
    return findings


def _probe_reflexion_age() -> tuple[str, float | None]:
    """State of the WR2 reflexion Delta-Gate ledger.

    Returns (state, age_days): state ∈ {"ok", "stale", "missing", "malformed"}.
    Missing/malformed are ALERT states, not skips — a ledger that was never
    written is the never-armed weekly cron (W81), exactly what this hunts.
    """
    skill_dir = Path(os.environ.get("WR2_SKILL_DIR", str(Path.home() / ".claude/skills/bali-zero-brand")))
    state_path = skill_dir / "_reflexion-state.json"
    if not state_path.is_file():
        return ("missing", None)
    try:
        history = json.loads(state_path.read_text())
        runs = [h["run_at"] for h in history if isinstance(h, dict) and h.get("run_at")]
        latest = max(datetime.fromisoformat(ts) for ts in runs)
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        logger.warning("reflexion ledger unreadable (%s): %s", state_path, e)
        return ("malformed", None)
    age_days = (datetime.now(timezone.utc) - latest).total_seconds() / 86400.0
    return ("stale" if age_days > REFLEXION_STALE_DAYS else "ok", age_days)


async def _evaluate_outcome_probes(conn: asyncpg.Connection) -> None:
    """C1: audit the pipeline's OUTCOME signals (launchd is transport, not truth).

    Kept separate from _evaluate_once so its probe sequence (and the existing
    tests pinned to it) stays untouched; the run loop calls both back to back.
    """
    now_epoch = int(datetime.now(timezone.utc).timestamp())

    # P1 — STALE_LEASE
    stale = await _probe_stale_leases(conn)
    if stale:
        if _alert_due("stale_lease", now_epoch):
            lines = "\n".join(
                f"- `{s['draft_id']}` owner=`{s['lease_owner']}` "
                f"hb {int(s['hb_age_sec'] or 0)}s ago, held {int((s['held_sec'] or 0) / 60)}min"
                for s in stale[:5]
            )
            _send_telegram(
                "⚠️ *WR2 stale render lease(s)*\n"
                f"{len(stale)} draft(s) stuck at `rendering` (heartbeat "
                f">{int(LEASE_STALE_MIN)}min silent or held >{int(LEASE_MAX_HELD_MIN)}min):\n"
                f"{lines}\n"
                "A live worker renews every 60s — this lease is dead or the "
                "worker is hung. Check `~/logs/wr2-html-apply.log`."
            )
            _state_set("last_alert_stale_lease", now_epoch)
            logger.warning("ALERT P1 stale_lease count=%d", len(stale))
        else:
            logger.info("stale_lease detected but cooldown active (count=%d)", len(stale))
    else:
        logger.debug("leases ok")

    # P1 — RUNTIME_STALE (C2): provenance stamps vs the checkout on disk
    runtime = _probe_runtime_stale()
    if runtime:
        if _alert_due("runtime_stale", now_epoch):
            lines = "\n".join(
                f"- `{r['organ']}`: {'; '.join(r['problems'])} (stamped {r.get('ts')})"
                for r in runtime
            )
            _send_telegram(
                "⚠️ *WR2 runtime provenance*\n"
                f"{lines}\n"
                "An organ is executing code that diverges from its checkout — "
                "restart the daemon (`launchctl kickstart -k gui/$(id -u)/"
                "com.balizero.wr2.supervisor`) or investigate the dirty checkout."
            )
            _state_set("last_alert_runtime_stale", now_epoch)
            logger.warning("ALERT P1 runtime_stale organs=%d", len(runtime))
        else:
            logger.info("runtime_stale found but cooldown active (organs=%d)", len(runtime))
    else:
        logger.debug("runtime provenance ok")

    # P2 — STATE_AGE (+ unknown-state drift)
    renderer_enabled = await _probe_renderer_enabled(conn)
    ages = await _probe_state_ages(conn, renderer_enabled=renderer_enabled)
    if ages["over"] or ages["unknown"]:
        if _alert_due("state_age", now_epoch):
            parts = []
            if ages["over"]:
                parts.append(
                    "Stuck stages (oldest row per state):\n" + "\n".join(
                        f"- `{a['status']}`: {a['n']} row(s), oldest {a['oldest_hours']:.1f}h"
                        for a in ages["over"]
                    )
                )
            if ages["unknown"]:
                parts.append(
                    "UNKNOWN states (machine drift — cicatrix #9):\n" + "\n".join(
                        f"- `{a['status']}`: {a['n']} row(s)" for a in ages["unknown"]
                    )
                )
            _send_telegram("⚠️ *WR2 state-age audit*\n" + "\n".join(parts))
            _state_set("last_alert_state_age", now_epoch)
            logger.warning(
                "ALERT P2 state_age over=%d unknown=%d", len(ages["over"]), len(ages["unknown"])
            )
        else:
            logger.info("state_age findings but cooldown active")
    else:
        logger.debug("state ages ok")

    # P2 — MANIFEST_GAP (hourly, degrade-open with fail-streak meta-alert)
    manifest = await _probe_manifest_gaps(conn)
    if manifest is not None:
        gaps = manifest["missing"] + manifest["unparseable"]
        if gaps and _alert_due("manifest_gap", now_epoch):
            _send_telegram(
                "⚠️ *WR2 rendered-without-manifest*\n"
                f"missing manifest.json: {manifest['missing'] or '—'}\n"
                f"unparseable drive_url: {manifest['unparseable'] or '—'}\n"
                f"(checked {manifest['checked']} rendered draft(s), 48h window). "
                "The C0 render writes the manifest under the lease — absence "
                "means a partial upload or manual deletion."
            )
            _state_set("last_alert_manifest_gap", now_epoch)
            logger.warning("ALERT P2 manifest_gap gaps=%d", len(gaps))
        streak = _state_get("manifest_probe_fail_streak") or 0
        if streak >= MANIFEST_FAIL_STREAK and _alert_due("manifest_probe_broken", now_epoch):
            _send_telegram(
                "⚠️ *WR2 manifest probe BROKEN*\n"
                f"{streak} consecutive sweeps failed to reach Drive — the probe "
                "is blind, not the pipeline healthy. Check SA credentials / "
                "googleapiclient availability in the watchdog venv."
            )
            _state_set("last_alert_manifest_probe_broken", now_epoch)
            logger.warning("ALERT P2 manifest_probe_broken streak=%d", streak)

    # P2 — WEEKLY_SILENT (reflexion Delta-Gate ledger)
    refl_state, refl_age = _probe_reflexion_age()
    if refl_state != "ok":
        if _alert_due("weekly_silent", now_epoch):
            detail = {
                "stale": f"last run {refl_age:.1f}d ago (threshold {REFLEXION_STALE_DAYS:.0f}d)"
                if refl_age is not None
                else "stale",
                "missing": "ledger file MISSING — the weekly cron may have never run (W81)",
                "malformed": "ledger file unreadable — the Delta-Gate write is broken",
            }[refl_state]
            _send_telegram(
                "⚠️ *WR2 weekly reflexion SILENT*\n"
                f"{detail}\n"
                "`_reflexion-state.json` is the Delta-Gate that kills green-cron "
                "theater — check `launchctl print gui/$(id -u)/com.balizero.wr2.reflexion`."
            )
            _state_set("last_alert_weekly_silent", now_epoch)
            logger.warning("ALERT P2 weekly_silent state=%s age=%s", refl_state, refl_age)
        else:
            logger.info("weekly_silent (%s) but cooldown active", refl_state)
    else:
        logger.debug("reflexion ledger ok (age=%.1fd)", refl_age or -1)


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
                    await _evaluate_outcome_probes(conn)
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
