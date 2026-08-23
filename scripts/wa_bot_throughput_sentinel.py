#!/usr/bin/env python3
"""wa_bot_throughput_sentinel.py — read-only throughput guardian for the WhatsApp BOT product.

W0 read-only guardian (SELECT-only; never mutates `inbound_webhooks`, `wa_outbox`,
or any bot state). Measured on Fly prod 2026-08-23: the WhatsApp bot produced its
last successful answer on 2026-07-30 01:23:58Z and received its last message
webhook at the same instant — 24 days of total silence while `/health`, the
broker gauge, the breaker, and the seat probe all read green. No organ in this
repo watched whether the bot actually SERVED anyone: `wa_mirror_freshness_liveness.py`
watches `whatsapp_message_context WHERE source='wa_mirror'` — a different table,
belonging to the personal-WhatsApp mirror, not the bot product. This organ is the
clock-watch for the bot product's own tables: `inbound_webhooks`
(channel='whatsapp', migration 145) and `wa_outbox` (status='done', migration 206).

TWO SIGNALS, NOT ONE (do not collapse them): INBOUND freshness = are clients
reaching us at all? OUTBOUND-DONE freshness = are we actually answering them?
A single "last activity" timestamp cannot tell "quiet night" apart from "the bot
is silently dropping every incoming message" — that blindness is what let the
real 24-day outage hide behind a green breaker.

BUSINESS-TIME STALENESS (same fix as wa_mirror_freshness_liveness.py, applied to
both signals independently): staleness is measured against
`ref = max(newest, today_open)`, never the raw age, so an ordinary quiet night
never pages anyone. Outside business hours neither business-adjusted check runs.

THE ONE EXCEPTION: the dead-channel check (`WA_BOT_DEAD_CHANNEL_HOURS`, default
48h) reads the RAW age of both signals and runs 24/7 — 24 days of silence must
never be excused by "it is currently 21:00". It is deliberately NOT
business-hours-floored: flooring it would shrink the duration it measures.

Alarm priority per tick (at most one condition reported):
  1. dead_channel   — both signals raw-stale beyond WA_BOT_DEAD_CHANNEL_HOURS
                       (24/7, ignores business hours)                    -> P0
  2. bot_broken     — business hours, inbound NOT stale, outbound stale  -> P0
                       (messages arriving, nothing answering — the loudest case)
  3. inbound_stale  — business hours, inbound stale, (1) and (2) false   -> digest
An inbound that is stale but has a NEWER outbound (we answered the last thing
that arrived) never trips bot_broken — that needs inbound to be fresh.

Model: scripts/wa_mirror_freshness_liveness.py (business-hours reference,
module-level `_tg_notify`/`_heartbeat`, `run()`/`_tick()` split so tests
inject a fake clock + fake rows + fake tg without touching the DB or network).

Env:
  INTAKE_DATABASE_URL / LOCAL_DATABASE_URL / DATABASE_URL_LOCAL
                                             DSN, tried in that order (default
                                             local nuzantara_dev, which is EMPTY —
                                             DATABASE_URL_LOCAL is the name with a
                                             live path to production via the
                                             flyctl proxy on 127.0.0.1:15432)
  WA_BOT_THROUGHPUT_SENTINEL_ENABLED         kill switch (default true)
  WA_BOT_INBOUND_STALE_MIN                   default 180 (3h) — business-hours-adjusted, digest tier
  WA_BOT_OUTBOUND_STALE_MIN                  default 60  (1h) — business-hours-adjusted, only
                                              meaningful while inbound is NOT stale, P0
  WA_BOT_DEAD_CHANNEL_HOURS                  default 48h — raw age, evaluated 24/7, P0
  WA_BOT_BUSINESS_START                      default 8  (WITA hour, inclusive)
  WA_BOT_BUSINESS_END                        default 20 (WITA hour, exclusive)
  WA_BOT_BUSINESS_DAYS                       default "0,1,2,3,4,5" (Mon=0..Sun=6; Mon-Sat)
  WA_BOT_THROUGHPUT_DRY_RUN=1                same as --dry-run

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
    level=os.getenv("WA_BOT_THROUGHPUT_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("wa_bot_throughput_sentinel")

ORGAN_ID = "pro.wa_bot_throughput_sentinel"
STATE_PATH = Path.home() / ".agent" / "decisions" / "state" / "wa_bot_throughput.json"
LOCK_FILE = Path.home() / ".cell-bridge-state" / "wa_bot_throughput_sentinel.lock"
DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
WITA = ZoneInfo("Asia/Makassar")

BOT_BROKEN_KEY = "wa-bot:throughput:bot-broken"
DEAD_CHANNEL_KEY = "wa-bot:throughput:dead-channel"
INBOUND_STALE_KEY = "wa-bot:throughput:inbound-stale"
# Not a channel condition: the organ is reading a database that has no WA
# history at all. Its own dedup key so it can never be mistaken for an outage.
# pragma below: a Telegram dedup key, not a credential — same shape as the three
# constants above. detect-secrets flags only THIS one of the four; probed and not
# fully explained (renaming the variable OR changing the value each clears it, so
# both participate), so the suppression is scoped to the one real finding rather
# than widened on a mechanism I could not isolate.
WRONG_DB_KEY = "wa-bot:throughput:wrong-database"  # pragma: allowlist secret

_PY3_CANDIDATES: tuple[str, ...] = (
    "/usr/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
)

# inbound_webhooks (migration 145) durably records every acked webhook per
# channel; wa_outbox (migration 206, status enum incl. 'done') durably
# records every generated reply, 'done' meaning it actually went out. Both
# SELECT-only, both scoped to the BOT product's own writers — never the
# wa-mirror tables wa_mirror_freshness_liveness.py already watches.
INBOUND_SQL = "SELECT max(received_at) AS newest FROM inbound_webhooks WHERE channel = 'whatsapp'"
OUTBOUND_SQL = "SELECT max(created_at) AS newest FROM wa_outbox WHERE status = 'done'"
# Discriminator, measured 2026-08-23: the LOCAL dev database carries both tables
# with ZERO rows, so a run against the default DSN would read NULL on both signals
# and classify a healthy world as dead_channel — a p0 on every tick, forever. An
# alarm that always fires is an alarm nobody reads, which is worse than none. So
# "this table has never held a row" is separated from "its newest row is old":
# the first is a misconfiguration (wrong DSN / unprovisioned DB), never an outage.
HISTORY_SQL = "SELECT (SELECT count(*) FROM wa_outbox) AS outbox_rows, (SELECT count(*) FROM inbound_webhooks WHERE channel = 'whatsapp') AS inbound_rows"


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
            logger.warning("[wa_bot_throughput] tg_notify.py missing at %s", gateway)
            return False
        res = subprocess.run(
            [_resolve_py3(), str(gateway), "--tier", tier,
             "--source", "wa-bot-throughput-sentinel", "--dedup-key", dedup_key, "--", text],
            capture_output=True, text=True, timeout=30,
        )
        verdict = extract_gateway_verdict(res.stderr)
        logger.info("[wa_bot_throughput] tg_notify: %s", verdict or f"NESSUN verdetto rc={res.returncode}")
        return res.returncode == 0 and gateway_delivered(verdict)
    except Exception as exc:  # noqa: BLE001 — never raises
        logger.warning("[wa_bot_throughput] tg_notify failed: %s", exc)
        return False


def _heartbeat(status: str, note: str = "") -> None:
    try:
        from scripts.lib.heartbeat import organism_heartbeat

        organism_heartbeat(ORGAN_ID, status, note=note)
    except Exception as exc:  # noqa: BLE001 — never raises
        logger.warning("[wa_bot_throughput] heartbeat write failed: %s", exc)


def _write_state(state: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, STATE_PATH)
    except OSError as exc:
        logger.warning("[wa_bot_throughput] state write failed: %s", exc)


def _read_state() -> dict[str, Any] | None:
    """Best-effort read of the previous tick's state — used only to detect an
    alerted->clear transition for the recovered digest. Never raises; a
    missing/corrupt file just means "no prior state to compare against"."""
    try:
        if not STATE_PATH.is_file():
            return None
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("[wa_bot_throughput] state read failed: %s", exc)
        return None


def _acquire_lock_or_exit() -> int | None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o600)
    # O_CREAT's mode only applies when the file is CREATED — chmod repairs a
    # pre-existing lock (same rationale as wa_mirror_freshness_liveness.py).
    try:
        os.chmod(LOCK_FILE, 0o600)
    except OSError as exc:  # noqa: BLE001 — never let a chmod failure block the lock
        logger.warning("[wa_bot_throughput] lock chmod failed: %s", exc)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[wa_bot_throughput] another instance running, skipping tick")
        os.close(fd)
        return None


# ---------------------------------------------------------------- pure helpers (unit-tested, no DB/network)


def age_minutes(newest: datetime | None, now: datetime) -> float | None:
    """Minutes since the newest row, or None when the table has no rows at all."""
    if newest is None:
        return None
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone.utc) - newest.astimezone(timezone.utc)).total_seconds() / 60.0


def is_stale(age_min: float | None, max_age_min: float) -> bool:
    return age_min is None or age_min > max_age_min


def in_business_hours(
    now_wita: datetime, *, start_hour: int, end_hour: int, business_days: set[int]
) -> bool:
    """Mon–Sat (default) 08:00–20:00 Asia/Makassar, both bounds env-overridable."""
    return now_wita.weekday() in business_days and start_hour <= now_wita.hour < end_hour


def business_hours_open_wita(now_wita: datetime, *, start_hour: int) -> datetime:
    """Today's business-open instant in WITA — the staleness reference floor."""
    return now_wita.replace(hour=start_hour, minute=0, second=0, microsecond=0)


def business_reference(newest: datetime | None, now_wita: datetime, *, start_hour: int) -> datetime:
    """max(newest, today_open) in WITA. A NULL table also floors at today_open
    (never "since epoch", which would be a meaningless multi-year age)."""
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


def _business_days_from_env() -> set[int]:
    raw = os.getenv("WA_BOT_BUSINESS_DAYS", "0,1,2,3,4,5")
    return {int(x) for x in raw.split(",") if x.strip() != ""}


def build_bot_broken_text(inbound_age_min: float | None, outbound_age_min: float | None) -> str:
    inbound_txt = "never" if inbound_age_min is None else f"{inbound_age_min:.0f} min"
    outbound_txt = "never" if outbound_age_min is None else f"{outbound_age_min:.0f} min"
    return (
        f"🔴 WA BOT is dropping live traffic — newest inbound webhook is {inbound_txt} old "
        f"but newest DONE outbound answer is {outbound_txt} old (business-hours reference). "
        f"Messages are arriving and nothing is being answered."
    )


def build_dead_channel_text(inbound_age_h: float | None, outbound_age_h: float | None) -> str:
    inbound_txt = "never" if inbound_age_h is None else f"{inbound_age_h:.1f}h"
    outbound_txt = "never" if outbound_age_h is None else f"{outbound_age_h:.1f}h"
    return (
        f"🔴 WA BOT channel is SILENT end-to-end — newest inbound webhook is {inbound_txt} old, "
        f"newest DONE outbound answer is {outbound_txt} old (raw age, 24/7 check, business hours ignored)."
    )


def build_inbound_stale_text(inbound_age_min: float | None) -> str:
    inbound_txt = "never" if inbound_age_min is None else f"{inbound_age_min:.0f} min"
    return (
        f"🟡 WA BOT inbound traffic is quiet — newest inbound webhook is {inbound_txt} old "
        f"(business-hours reference). No new client messages are arriving."
    )


def build_recovered_text(inbound_age_min: float | None, outbound_age_min: float | None) -> str:
    inbound_txt = "n/a" if inbound_age_min is None else f"{inbound_age_min:.0f} min"
    outbound_txt = "n/a" if outbound_age_min is None else f"{outbound_age_min:.0f} min"
    return (
        f"✅ WA BOT throughput recovered — inbound {inbound_txt} old, outbound-done {outbound_txt} old "
        f"(business-hours reference), back under threshold after a prior alert."
    )


def recovered_dedup_key(now_wita: datetime) -> str:
    return f"wa-bot:throughput:recovered:{now_wita.strftime('%Y-%m-%d')}"


def build_wrong_db_text() -> str:
    """Deliberately does NOT say the channel is down — it says the organ cannot
    see it. Naming the env var means the reader fixes config, not WhatsApp."""
    return (
        "🔴 WA throughput sentinel is BLIND — it is connected to a database where "
        "wa_outbox and inbound_webhooks are both completely empty, so it cannot "
        "tell a healthy bot from a dead one. This is a CONFIGURATION fault, not a "
        "channel outage: check INTAKE_DATABASE_URL points at production."
    )


def _alert_payload(
    condition: str,
    inbound_business_age: float | None,
    outbound_business_age: float | None,
    raw_inbound_age_h: float | None,
    raw_outbound_age_h: float | None,
) -> tuple[str, str, str]:
    if condition == "dead_channel":
        return "p0", DEAD_CHANNEL_KEY, build_dead_channel_text(raw_inbound_age_h, raw_outbound_age_h)
    if condition == "bot_broken":
        return "p0", BOT_BROKEN_KEY, build_bot_broken_text(inbound_business_age, outbound_business_age)
    if condition == "inbound_stale":
        # NOT "p1": tg_notify.py:150 is TIERS = ("p0", "digest", "log") and :868
        # binds it as argparse `choices=`, so --tier p1 is REJECTED and the alert
        # becomes a silent no-op — the exact blindness this organ exists to cure.
        # "digest" is the gateway's own name (tg_notify.py:10) for informative
        # watcher findings, which is what a soft inbound-quiet notice is.
        return "digest", INBOUND_STALE_KEY, build_inbound_stale_text(inbound_business_age)
    raise ValueError(f"unknown condition: {condition!r}")


# ---------------------------------------------------------------- core tick (async, DB-only I/O via `conn`)


async def _tick(conn: Any, now_wita: datetime, *, dry_run: bool) -> int:
    inbound_stale_min = float(os.getenv("WA_BOT_INBOUND_STALE_MIN", "180"))
    outbound_stale_min = float(os.getenv("WA_BOT_OUTBOUND_STALE_MIN", "60"))
    dead_channel_hours = float(os.getenv("WA_BOT_DEAD_CHANNEL_HOURS", "48"))
    start_hour = int(os.getenv("WA_BOT_BUSINESS_START", "8"))
    end_hour = int(os.getenv("WA_BOT_BUSINESS_END", "20"))
    business_days = _business_days_from_env()

    inbound_row = await conn.fetchrow(INBOUND_SQL, timeout=30)
    outbound_row = await conn.fetchrow(OUTBOUND_SQL, timeout=30)
    inbound_newest = inbound_row["newest"]
    outbound_newest = outbound_row["newest"]

    # Wrong-database short-circuit, evaluated BEFORE any staleness reasoning.
    # Both signals NULL is ambiguous on its own: it is what a truncated prod
    # table looks like AND what a dev database looks like. The row counts
    # disambiguate — a product that has ever run leaves rows behind, even
    # failed ones (prod carried 325 wa_outbox rows while dead). Zero of both
    # means this organ is not looking at the product's database.
    if inbound_newest is None and outbound_newest is None:
        history = await conn.fetchrow(HISTORY_SQL, timeout=30)
        if history["outbox_rows"] == 0 and history["inbound_rows"] == 0:
            logger.error(
                "[wa_bot_throughput] wrong database: wa_outbox and inbound_webhooks "
                "are both entirely empty — check INTAKE_DATABASE_URL"
            )
            _heartbeat("error", "wrong database (both tables empty)")
            if not dry_run:
                _tg_notify("p0", WRONG_DB_KEY, build_wrong_db_text())
            return 2

    business = in_business_hours(
        now_wita, start_hour=start_hour, end_hour=end_hour, business_days=business_days
    )

    inbound_ref = business_reference(inbound_newest, now_wita, start_hour=start_hour)
    outbound_ref = business_reference(outbound_newest, now_wita, start_hour=start_hour)
    inbound_business_age = business_age_minutes(inbound_ref, now_wita)
    outbound_business_age = business_age_minutes(outbound_ref, now_wita)

    # Outside business hours neither check runs — an overnight/Sunday quiet
    # line is Law 6, not a fault. `bot_broken` is the loudest condition.
    inbound_stale = business and is_stale(inbound_business_age, inbound_stale_min)
    outbound_stale = business and is_stale(outbound_business_age, outbound_stale_min)
    bot_broken = business and (not inbound_stale) and outbound_stale
    inbound_only_stale = business and inbound_stale and not bot_broken

    # Dead-channel is the ONE exception to "business hours only": RAW age of
    # both signals, never business-floored, evaluated regardless of the
    # clock — 24 days of silence can never be excused by "outside hours".
    raw_inbound_age_min = age_minutes(inbound_newest, now_wita)
    raw_outbound_age_min = age_minutes(outbound_newest, now_wita)
    raw_inbound_age_h = raw_inbound_age_min / 60.0 if raw_inbound_age_min is not None else None
    raw_outbound_age_h = raw_outbound_age_min / 60.0 if raw_outbound_age_min is not None else None
    inbound_dead = raw_inbound_age_h is None or raw_inbound_age_h > dead_channel_hours
    outbound_dead = raw_outbound_age_h is None or raw_outbound_age_h > dead_channel_hours
    dead_channel = inbound_dead and outbound_dead

    if dead_channel:
        condition = "dead_channel"
    elif bot_broken:
        condition = "bot_broken"
    elif inbound_only_stale:
        condition = "inbound_stale"
    else:
        condition = None

    previous_state = _read_state()
    previously_alerted = bool(previous_state.get("alerted")) if previous_state else False

    logger.info(
        "[wa_bot_throughput] condition=%s business=%s inbound_age_min=%s outbound_age_min=%s "
        "raw_inbound_h=%s raw_outbound_h=%s",
        condition, business, round(inbound_business_age, 1), round(outbound_business_age, 1),
        None if raw_inbound_age_h is None else round(raw_inbound_age_h, 1),
        None if raw_outbound_age_h is None else round(raw_outbound_age_h, 1),
    )

    # `alerted` is computed BEFORE _write_state so the persisted state file —
    # which the NEXT tick reads back for recovered-detection — actually
    # carries whether THIS tick paged (same ordering as the model file).
    alerted = False
    recovered_sent = False
    if condition and not dry_run:
        tier, dedup_key, text = _alert_payload(
            condition, inbound_business_age, outbound_business_age, raw_inbound_age_h, raw_outbound_age_h,
        )
        alerted = _tg_notify(tier, dedup_key, text)
    elif previously_alerted and not condition and not dry_run:
        recovered_sent = _tg_notify(
            "digest", recovered_dedup_key(now_wita),
            build_recovered_text(inbound_business_age, outbound_business_age),
        )

    state = {
        "generated_at": now_wita.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "condition": condition,
        "business_hours": business,
        "inbound_business_age_minutes": round(inbound_business_age, 1),
        "outbound_business_age_minutes": round(outbound_business_age, 1),
        "raw_inbound_age_hours": None if raw_inbound_age_h is None else round(raw_inbound_age_h, 1),
        "raw_outbound_age_hours": None if raw_outbound_age_h is None else round(raw_outbound_age_h, 1),
        "alerted": alerted,
        "recovered_sent": recovered_sent,
    }
    if not dry_run:
        _write_state(state)

    # Heartbeat reflects the ORGAN (did the tick complete?), never the
    # FINDING (is throughput broken?) — same contract as
    # wa_mirror_freshness_liveness.py (verbale #2), else an unconditional
    # "degraded" heartbeat gets this healthy organ auto-remediated.
    _heartbeat("ok", note=f"condition={condition} business={business} alerted={alerted}")

    return 0


async def run(*, dry_run: bool) -> int:
    if os.getenv("WA_BOT_THROUGHPUT_SENTINEL_ENABLED", "true").strip().lower() in ("0", "false", "no"):
        logger.info("[wa_bot_throughput] disabled via WA_BOT_THROUGHPUT_SENTINEL_ENABLED — no-op")
        _heartbeat("disabled", "WA_BOT_THROUGHPUT_SENTINEL_ENABLED=false")
        return 0

    dry_run = dry_run or os.getenv("WA_BOT_THROUGHPUT_DRY_RUN", "") == "1"

    lock_fd = _acquire_lock_or_exit()
    if lock_fd is None:
        return 0
    try:
        # DSN resolution order, and why the third name is here (audited 2026-08-23):
        # every organ in this repo that sets INTAKE_DATABASE_URL sets it to the
        # LOCAL dev database — three plists hardcode nuzantara_dev — so those two
        # names alone would have armed this sentinel against an empty world. The
        # one name with a proven, live path to PRODUCTION is DATABASE_URL_LOCAL,
        # sourced from ~/.nuzantara-secrets.env and reaching Fly Postgres through
        # the `flyctl proxy 15432:5432` tunnel the wr2 organs already depend on.
        # Verified through it this session: 244 whatsapp inbound rows, 108 done.
        # CAUTION: DATABASE_URL_LOCAL and LOCAL_DATABASE_URL are different names
        # with opposite meanings — the first is production via tunnel, the second
        # is a dev override. They are one word-swap apart; do not "tidy" them.
        dsn = (
            os.getenv("INTAKE_DATABASE_URL")
            or os.getenv("LOCAL_DATABASE_URL")
            or os.getenv("DATABASE_URL_LOCAL")
            or DEFAULT_DSN
        )
        try:
            conn = await asyncpg.connect(
                dsn, server_settings={"default_transaction_read_only": "on"}, timeout=20
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[wa_bot_throughput] DB connect failed: %s", exc)
            _heartbeat("error", f"db connect failed: {exc}")
            return 2

        try:
            now_wita = datetime.now(WITA)
            return await _tick(conn, now_wita, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001 — the whole tick (env parsing
            # included) must never exit uncaught (same contract as the model
            # file, verbale #6): always heartbeat("error") and return 2.
            logger.error("[wa_bot_throughput] tick failed: %s", exc)
            _heartbeat("error", f"tick failed: {exc}")
            # A heartbeat file is not an alarm: nothing pages off it, so a bad
            # column, a revoked GRANT or an unreachable DB would leave this organ
            # mute exactly like the outage it exists to catch. Page instead.
            if not dry_run:
                _tg_notify(
                    "p0", WRONG_DB_KEY,
                    f"🔴 WA throughput sentinel FAILED to run — it is not watching "
                    f"anything right now. Cause: {type(exc).__name__}: {exc}",
                )
            return 2
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
