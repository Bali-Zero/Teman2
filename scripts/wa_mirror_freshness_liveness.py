#!/usr/bin/env python3
"""wa_mirror_freshness_liveness.py — read-only freshness guardian for the WhatsApp mirror.

W0 read-only guardian (SELECT-only; never mutates whatsapp_message_context or
any wa-mirror state). The intake mouth's blind spot (Mythos M4, 2026-06-14):
"no new media arriving" is silently indistinguishable from "the bridge is
paralyzed" unless something watches the clock. This organ is the clock-watch:
it reads the newest whatsapp_message_context row and, ONLY during business
hours (so an overnight quiet line — Law 6, disconnection is natural — never
pages anyone), alerts once when that row is older than the freshness window.

BUSINESS-TIME STALENESS (post-refuter fix, verbale #1, 2026-08-17): staleness
is measured against a business-hours-adjusted REFERENCE, not the raw age of
the newest row. The 12h overnight gap (20:00 close -> 08:00 reopen, Asia/
Makassar) is longer than any sane intraday freshness window, so comparing raw
age against a flat threshold guaranteed a false P0 on the FIRST in-business-
hours tick after every ordinary quiet night (proven live: the PR's own
"guilt" test used a 7h overnight gap and asserted a P0 — indistinguishable
from a real outage). The fix: `ref = max(newest, today_open)` where
`today_open` is today's business-start instant in WITA. A message from last
night floors at today's open, so the clock effectively starts fresh at
08:00 — staleness now measures "how long INTO the business day has this been
quiet", never "how long since the office closed". WA_FRESHNESS_MAX_AGE_MIN's
default therefore drops from 360 (6h — sized to survive the false-positive
overnight gap) to 180 (3h — sized to the actual intraday risk, now that the
overnight gap no longer inflates the age). Outside business hours the organ
never evaluates staleness at all (business=False short-circuits before the
threshold comparison) — a quiet night is Law 6, not a fault.

Secondary signal (best-effort, tolerates absence): counts "DEAD" lines out of
`bash ~/scripts/wa-mirror-launcher/status.sh` — the per-employee bridge
process table — and folds the count into the alert text. Absence of that
script (a different machine, a moved path) never blocks the primary
freshness check; it degrades to "n/a", logged, not silent.

Model: scripts/wa_mirror_bridge_liveness_alarm.py (business-hours + cooldown
+ tg_notify gateway shape) and scripts/wr2_daily_reconciler.py (module-level
`_tg_notify`/`_heartbeat`, `run()`/`_tick()` split so tests inject a fake
clock + fake rows + fake tg without touching the DB or network).

Env:
  INTAKE_DATABASE_URL / LOCAL_DATABASE_URL   DSN (default local nuzantara_dev)
  WA_MIRROR_FRESHNESS_LIVENESS_ENABLED       kill switch (default true) — G5
  WA_FRESHNESS_MAX_AGE_MIN                   default 180 (3h) — business-hours-adjusted staleness threshold (see above)
  WA_FRESHNESS_BUSINESS_START                default 8  (WITA hour, inclusive)
  WA_FRESHNESS_BUSINESS_END                  default 20 (WITA hour, exclusive)
  WA_FRESHNESS_BUSINESS_DAYS                 default "0,1,2,3,4,5" (Mon=0..Sun=6; Mon-Sat)
  WA_MIRROR_STATUS_SCRIPT                    default ~/scripts/wa-mirror-launcher/status.sh
  WA_FRESHNESS_DRY_RUN=1                     same as --dry-run

Exit: 0 always, except a DSN/connect failure or an uncaught tick error
(logged, heartbeat status=error) -> 2.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered  # noqa: E402

logging.basicConfig(
    level=os.getenv("WA_FRESHNESS_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("wa_mirror_freshness_liveness")

ORGAN_ID = "pro.wa_mirror_freshness_liveness"
STATE_PATH = Path.home() / ".agent" / "decisions" / "state" / "wa_mirror_freshness.json"
LOCK_FILE = Path.home() / ".cell-bridge-state" / "wa_mirror_freshness_liveness.lock"
DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_STATUS_SCRIPT = Path.home() / "scripts" / "wa-mirror-launcher" / "status.sh"
WITA = ZoneInfo("Asia/Makassar")
DEDUP_KEY = "wa-mirror:freshness:stale"

_PY3_CANDIDATES: tuple[str, ...] = (
    "/usr/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
)

FRESHNESS_SQL = "SELECT max(created_at) AS newest FROM whatsapp_message_context"


# ---------------------------------------------------------------- side effects (module-level, monkeypatchable)


def _resolve_py3() -> str:
    for candidate in _PY3_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return sys.executable


def _tg_notify(tier: str, dedup_key: str, text: str) -> bool:
    """Route through the tg_notify gateway; never raises."""
    try:
        gateway = _REPO / "scripts" / "tg_notify.py"
        if not gateway.is_file():
            logger.warning("[wa_freshness] tg_notify.py missing at %s", gateway)
            return False
        res = subprocess.run(
            [_resolve_py3(), str(gateway), "--tier", tier,
             "--source", "wa-mirror-freshness-liveness", "--dedup-key", dedup_key, "--", text],
            capture_output=True, text=True, timeout=30,
        )
        verdict = extract_gateway_verdict(res.stderr)
        logger.info("[wa_freshness] tg_notify: %s", verdict or f"NESSUN verdetto rc={res.returncode}")
        return res.returncode == 0 and gateway_delivered(verdict)
    except Exception as exc:  # noqa: BLE001 — never raises
        logger.warning("[wa_freshness] tg_notify failed: %s", exc)
        return False


def _heartbeat(status: str, note: str = "") -> None:
    try:
        from scripts.lib.heartbeat import organism_heartbeat

        organism_heartbeat(ORGAN_ID, status, note=note)
    except Exception as exc:  # noqa: BLE001 — never raises
        logger.warning("[wa_freshness] heartbeat write failed: %s", exc)


def _write_state(state: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, STATE_PATH)
    except OSError as exc:
        logger.warning("[wa_freshness] state write failed: %s", exc)


def _read_state() -> dict[str, Any] | None:
    """Best-effort read of the previous tick's state file — used only to
    detect a stale->fresh transition for the recovered digest. Never raises;
    a missing/corrupt file just means "no prior state to compare against"."""
    try:
        if not STATE_PATH.is_file():
            return None
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("[wa_freshness] state read failed: %s", exc)
        return None


def _acquire_lock_or_exit() -> int | None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[wa_freshness] another instance running, skipping tick")
        os.close(fd)
        return None


def _run_status_script() -> str | None:
    """Best-effort: run the wa-mirror status table. None (not '') when the
    script is absent/unreadable/times out — the caller must tell "n/a" apart
    from "zero DEAD lines"."""
    script = Path(os.getenv("WA_MIRROR_STATUS_SCRIPT", "") or DEFAULT_STATUS_SCRIPT)
    if not script.is_file():
        logger.info("[wa_freshness] status script absent at %s — DEAD count n/a", script)
        return None
    try:
        res = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, timeout=30,
        )
        return res.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("[wa_freshness] status script run failed: %s", exc)
        return None


# ---------------------------------------------------------------- pure helpers (unit-tested, no DB/network)


def count_dead_lines(status_output: str | None) -> int | None:
    """Count table rows whose STATUS column reads DEAD (e.g. '🔴 DEAD').
    None when the script output itself is unavailable — never conflated with
    a genuine zero."""
    if status_output is None:
        return None
    return sum(1 for line in status_output.splitlines() if "DEAD" in line)


def age_minutes(newest: datetime | None, now: datetime) -> float | None:
    """Minutes since the newest row, or None when the table has no rows at
    all (treated as maximally stale by is_stale — an empty mirror table
    during business hours is itself a genuine paralysis signal)."""
    if newest is None:
        return None
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone.utc) - newest.astimezone(timezone.utc)).total_seconds() / 60.0


def is_stale(age_min: float | None, max_age_min: float) -> bool:
    return age_min is None or age_min > max_age_min


def in_business_hours(
    now_wita: datetime,
    *,
    start_hour: int,
    end_hour: int,
    business_days: set[int],
) -> bool:
    """Mon–Sat (default) 08:00–20:00 Asia/Makassar, both bounds env-overridable."""
    return now_wita.weekday() in business_days and start_hour <= now_wita.hour < end_hour


def business_hours_open_wita(now_wita: datetime, *, start_hour: int) -> datetime:
    """Today's business-open instant in WITA — the staleness reference floor
    (verbale #1): a message received before this instant never counts as
    "old" beyond how long the business day has been open."""
    return now_wita.replace(hour=start_hour, minute=0, second=0, microsecond=0)


def business_reference(
    newest: datetime | None, now_wita: datetime, *, start_hour: int
) -> datetime:
    """max(newest, today_open) in WITA. A NULL table (never a row) also
    floors at today_open — never "since epoch", which would report a
    meaningless multi-year age instead of the intended maximally-stale-for-
    today signal."""
    today_open = business_hours_open_wita(now_wita, start_hour=start_hour)
    if newest is None:
        return today_open
    newest_wita = (
        newest.astimezone(WITA)
        if newest.tzinfo is not None
        else newest.replace(tzinfo=timezone.utc).astimezone(WITA)
    )
    return max(newest_wita, today_open)


def business_age_minutes(ref: datetime, now_wita: datetime) -> float:
    return (now_wita - ref).total_seconds() / 60.0


def build_alert_text(age_min: float | None, dead_count: int | None) -> str:
    age_txt = "never (table empty)" if age_min is None else f"{age_min:.0f} min"
    dead_txt = "n/a" if dead_count is None else str(dead_count)
    return (
        f"🔴 WA mirror FRESHNESS stale — newest message context row is {age_txt} old "
        f"(business-hours reference; bridge DEAD lines: {dead_txt}). During business "
        f"hours this reads as intake CIECO on WhatsApp, not quiet. "
        f"Check: bash ~/scripts/wa-mirror-launcher/status.sh"
    )


def build_recovered_text(business_age_min: float) -> str:
    return (
        f"✅ WA mirror FRESHNESS recovered — newest message context row is now "
        f"{business_age_min:.0f} min old (business-hours reference), back under the "
        f"threshold after a prior P0."
    )


def recovered_dedup_key(now_wita: datetime) -> str:
    return f"wa-mirror:freshness:recovered:{now_wita.strftime('%Y-%m-%d')}"


def _business_days_from_env() -> set[int]:
    raw = os.getenv("WA_FRESHNESS_BUSINESS_DAYS", "0,1,2,3,4,5")
    return {int(x) for x in raw.split(",") if x.strip() != ""}


# ---------------------------------------------------------------- core tick (async, DB-only I/O via `conn`)


async def _tick(conn: Any, now_wita: datetime, *, dry_run: bool) -> int:
    max_age_min = float(os.getenv("WA_FRESHNESS_MAX_AGE_MIN", "180"))
    start_hour = int(os.getenv("WA_FRESHNESS_BUSINESS_START", "8"))
    end_hour = int(os.getenv("WA_FRESHNESS_BUSINESS_END", "20"))
    business_days = _business_days_from_env()

    row = await conn.fetchrow(FRESHNESS_SQL)
    newest = row["newest"]
    business = in_business_hours(
        now_wita, start_hour=start_hour, end_hour=end_hour, business_days=business_days
    )
    ref = business_reference(newest, now_wita, start_hour=start_hour)
    business_age_min = business_age_minutes(ref, now_wita)
    # Outside business hours the organ never evaluates staleness at all —
    # an overnight/Sunday quiet line is Law 6, not a fault (verbale #1).
    stale = business and is_stale(business_age_min, max_age_min)
    raw_age_min = age_minutes(newest, now_wita)
    dead_count = count_dead_lines(_run_status_script())

    previous_state = _read_state()
    previously_alerted = bool(previous_state.get("alerted")) if previous_state else False

    logger.info(
        "[wa_freshness] business_age_min=%s stale=%s business_hours=%s dead=%s",
        round(business_age_min, 1), stale, business, dead_count,
    )

    # `alerted` is computed BEFORE _write_state (verbale #5) so the persisted
    # state file — which the NEXT tick reads back for recovered-detection —
    # actually carries whether this tick paged.
    alerted = False
    recovered_sent = False
    if stale and business and not dry_run:
        alerted = _tg_notify("p0", DEDUP_KEY, build_alert_text(raw_age_min, dead_count))
    elif previously_alerted and not stale and not dry_run:
        recovered_sent = _tg_notify(
            "digest", recovered_dedup_key(now_wita), build_recovered_text(business_age_min)
        )

    state = {
        "generated_at": now_wita.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "newest_created_at": newest.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if newest else None,
        "age_minutes": round(raw_age_min, 1) if raw_age_min is not None else None,
        "business_age_minutes": round(business_age_min, 1),
        "stale": stale,
        "business_hours": business,
        "dead_bridge_count": dead_count,
        "max_age_minutes": max_age_min,
        "alerted": alerted,
        "recovered_sent": recovered_sent,
    }

    if not dry_run:
        _write_state(state)

    _heartbeat(
        "degraded" if stale else "ok",
        note=f"business_age_min={round(business_age_min, 1)} business_hours={business}",
    )

    return 0


async def run(*, dry_run: bool) -> int:
    if os.getenv("WA_MIRROR_FRESHNESS_LIVENESS_ENABLED", "true").strip().lower() in ("0", "false", "no"):
        logger.info("[wa_freshness] disabled via WA_MIRROR_FRESHNESS_LIVENESS_ENABLED — no-op")
        _heartbeat("disabled", "WA_MIRROR_FRESHNESS_LIVENESS_ENABLED=false")
        return 0

    dry_run = dry_run or os.getenv("WA_FRESHNESS_DRY_RUN", "") == "1"

    lock_fd = _acquire_lock_or_exit()
    if lock_fd is None:
        return 0
    try:
        dsn = os.getenv("INTAKE_DATABASE_URL") or os.getenv("LOCAL_DATABASE_URL") or DEFAULT_DSN
        try:
            conn = await asyncpg.connect(
                dsn, server_settings={"default_transaction_read_only": "on"}
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[wa_freshness] DB connect failed: %s", exc)
            _heartbeat("error", f"db connect failed: {exc}")
            return 2

        try:
            now_wita = datetime.now(WITA)
            return await _tick(conn, now_wita, dry_run=dry_run)
        finally:
            await conn.close()
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--dry-run", action="store_true", help="no Telegram, no state-file write")
    args = parser.parse_args()
    return asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
