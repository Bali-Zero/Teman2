#!/usr/bin/env python3
"""wa-mirror bridge-liveness ALARM — the antibody for the silent-paralysis gap.

The intake mouth has a blind spot (Mythos M4, 2026-06-14): when no new client
media is enqueued, the pipeline cannot tell "no food is arriving" (benign quiet)
from "the WhatsApp bridge is paralyzed" (a dead intake channel). The
``wa_mirror_session_janitor`` *cleans* the ghost DB row but says nothing to the
operator — so a dead bridge during business hours is silently indistinguishable
from a quiet line.

This probe closes that gap WITHOUT violating Law 6 (local sovereignty:
disconnection is a natural state, not a fault). It is a **periodic runtime
probe**, never a boot-assert: it does not block startup, it does not halt the
node on a missing peer. It only *escalates an observable alarm* when a bridge
that the DB believes is ``connected`` has a dead process AND has been stale past
a grace window AND we are inside business hours WITA — i.e. exactly the window
where "no media" should mean "the team is working", so silence is suspicious.

Design (mirrors ``wa_mirror_session_janitor`` deliberately — reuse, not reinvent):
  * Liveness signal = same PID-file + ``pgrep --employee=<name>`` check.
  * A bridge is ALARMING only if ALL hold:
      1. its DB row status is ``connected`` (the system *believes* it is up), AND
      2. no live bridge process for that account, AND
      3. ``last_seen_at`` older than ``WA_LIVENESS_GRACE_MINUTES`` (default 20)
         — generous, so a routine restart / brief network blip never fires, AND
      4. now is within business hours WITA (``WA_LIVENESS_BUSINESS_START``..``END``,
         default 08..20) — outside hours, a dead bridge is expected (overnight).
  * Cooldown: one alarm per (account) per ``WA_LIVENESS_COOLDOWN_MINUTES``
    (default 120) via a state file, so a persistently-dead bridge does not spam.

Read-only on the DB (no UPDATE — the janitor owns state mutation; this only
observes). Cron-tick shim (flock single-instance), local DB only, no PII leaves
the Pro (only an account name + e164 + timestamp go to the owner's Telegram —
the same metadata the existing watchdogs already send).

Env:
  WA_MIRROR_DATABASE_URL        (default postgresql://nuzantara@localhost:5432/nuzantara_dev)
  WA_LIVENESS_GRACE_MINUTES     (default 20)
  WA_LIVENESS_COOLDOWN_MINUTES  (default 120)
  WA_LIVENESS_BUSINESS_START    (default 8,  WITA hour)
  WA_LIVENESS_BUSINESS_END      (default 20, WITA hour)
  TELEGRAM_BOT_TOKEN            (from env or ~/.cell-bridge-state/*.env)
  WA_LIVENESS_DRY_RUN=1         (print instead of send)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import fcntl
import json
import logging
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("wa_liveness_alarm")

STATE_DIR = Path.home() / ".cell-bridge-state"
LOCK_FILE = STATE_DIR / "wa_liveness_alarm.lock"
COOLDOWN_STATE = STATE_DIR / "wa_liveness_alarm.cooldown.json"
PID_DIR = Path("/tmp/wa-mirror-pids")
ACCOUNTS_JSON = Path.home() / ".wa-mirror.accounts.json"

WITA = ZoneInfo("Asia/Makassar")
TELEGRAM_OWNER_CHAT_ID = "1125336968"  # Zero — per CLAUDE.md §13 / drive_token_watchdog parity

_GRACE_MIN = int(os.getenv("WA_LIVENESS_GRACE_MINUTES", "20"))
_COOLDOWN_MIN = int(os.getenv("WA_LIVENESS_COOLDOWN_MINUTES", "120"))
_BIZ_START = int(os.getenv("WA_LIVENESS_BUSINESS_START", "8"))
_BIZ_END = int(os.getenv("WA_LIVENESS_BUSINESS_END", "20"))
_DRY_RUN = os.getenv("WA_LIVENESS_DRY_RUN", "") == "1"

_LOCK_FD: int | None = None


def _acquire_lock_or_exit() -> None:
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.info("[wa_liveness] another instance running, skipping tick")
        os.close(fd)
        sys.exit(0)
    global _LOCK_FD
    _LOCK_FD = fd


def _db_url() -> str:
    return os.getenv("WA_MIRROR_DATABASE_URL", "") or "postgresql://nuzantara@localhost:5432/nuzantara_dev"


def _bot_token() -> str:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if tok:
        return tok
    # Parity with the durable-secret env-file convention (PR #1208).
    for envf in (STATE_DIR / "wa-media.env", STATE_DIR / "intake.env"):
        try:
            for line in envf.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def _phone_to_name() -> dict[str, str]:
    try:
        data = json.loads(ACCOUNTS_JSON.read_text())
    except (OSError, ValueError) as exc:
        logger.warning("[wa_liveness] accounts file unreadable (%s)", exc)
        return {}
    accounts = data.get("accounts", data if isinstance(data, list) else [])
    out: dict[str, str] = {}
    for a in accounts:
        phone = a.get("phone") or a.get("e164")
        name = a.get("name")
        if phone and name:
            out[phone] = name.lower()
    return out


def _bridge_alive(name: str) -> bool:
    """Same liveness check as the janitor: PID file then pgrep --employee."""
    pidfile = PID_DIR / name
    try:
        pid = int(pidfile.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        pass
    try:
        res = subprocess.run(
            ["pgrep", "-f", f"--employee={name}"],
            capture_output=True, text=True, timeout=5,
        )
        return res.returncode == 0 and bool(res.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def _in_business_hours(now: dt.datetime) -> bool:
    return _BIZ_START <= now.hour < _BIZ_END


def _load_cooldown() -> dict[str, float]:
    try:
        return json.loads(COOLDOWN_STATE.read_text())
    except (OSError, ValueError):
        return {}


def _save_cooldown(state: dict[str, float]) -> None:
    try:
        COOLDOWN_STATE.write_text(json.dumps(state))
    except OSError as exc:
        logger.warning("[wa_liveness] cooldown state write failed: %s", exc)


def _send_telegram(text: str) -> bool:
    if _DRY_RUN:
        print(f"[DRY RUN] Telegram: {text}")
        return True
    token = _bot_token()
    if not token:
        logger.warning("[wa_liveness] TELEGRAM_BOT_TOKEN not found; cannot alert")
        return False
    try:
        data = urllib.parse.urlencode(
            {"chat_id": TELEGRAM_OWNER_CHAT_ID, "text": text, "parse_mode": "HTML"}
        ).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=10
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[wa_liveness] telegram send failed: %s", exc)
        return False


async def _run(now: dt.datetime) -> int:
    if not _in_business_hours(now):
        logger.info("[wa_liveness] outside business hours WITA (%02d:00); a dead bridge is expected, no alarm", now.hour)
        return 0

    name_map = _phone_to_name()
    conn = await asyncpg.connect(_db_url())
    try:
        rows = await conn.fetch(
            """
            SELECT id, team_member_name, team_member_phone, last_seen_at,
                   (last_seen_at IS NULL
                    OR last_seen_at < now() - ($1::int * interval '1 minute')) AS past_grace
            FROM whatsapp_team_sessions
            WHERE status = 'connected'
            """,
            _GRACE_MIN,
        )
    finally:
        await conn.close()

    cooldown = _load_cooldown()
    now_ts = now.timestamp()
    alarmed = 0

    for r in rows:
        name = (r["team_member_name"] or name_map.get(r["team_member_phone"] or "", "")).lower()
        if not name:
            continue
        if _bridge_alive(name):
            continue  # healthy — the common case
        if not r["past_grace"]:
            continue  # dead but within grace (routine restart / blip) — stay quiet

        # DB says connected, process is dead, past grace, business hours → PARALYSIS.
        last_alarm = cooldown.get(name, 0.0)
        if now_ts - last_alarm < _COOLDOWN_MIN * 60:
            logger.info("[wa_liveness] %s still dead but within cooldown; not re-alerting", name)
            continue

        phone = r["team_member_phone"] or "?"
        last_seen = r["last_seen_at"].astimezone(WITA).strftime("%Y-%m-%d %H:%M WITA") if r["last_seen_at"] else "never"
        msg = (
            f"🔴 <b>WA bridge PARALIZZATO</b>\n"
            f"Account: <b>{name}</b> ({phone})\n"
            f"Il DB lo crede <code>connected</code> ma il processo è MORTO da &gt;{_GRACE_MIN}min "
            f"(ultimo segnale: {last_seen}).\n"
            f"Durante orario di lavoro = intake CIECO su questa linea, non quiete.\n"
            f"Re-link: <code>bash ~/scripts/wa-mirror-launcher/start-one.sh {name} --qr</code>"
        )
        if _send_telegram(msg):
            cooldown[name] = now_ts
            alarmed += 1
            logger.info("[wa_liveness] ALARM sent for %s (dead, past grace, business hours)", name)

    if alarmed == 0:
        logger.info("[wa_liveness] all 'connected' bridges alive (or within grace/cooldown); active=%d", len(rows))
    _save_cooldown(cooldown)
    return alarmed


def main() -> None:
    _acquire_lock_or_exit()
    try:
        now = dt.datetime.now(WITA)
        asyncio.run(_run(now))
    finally:
        if _LOCK_FD is not None:
            os.close(_LOCK_FD)


if __name__ == "__main__":
    main()
