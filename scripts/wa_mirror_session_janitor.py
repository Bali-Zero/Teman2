#!/usr/bin/env python3
"""wa-mirror ghost-session janitor.

Marks ``whatsapp_team_sessions`` rows that are nominally active
(``status IN ('pending','connected')``) but whose bridge process is dead as
``disconnected``. This prevents the partial-unique index
``uq_whatsapp_team_sessions_active_phone`` from blocking a restart of the bridge
(the ghost-row crash-loop class, 2026-06-09: 4 bridges crash-looped ~1100x for 3
days because dead-process rows stayed ``connected``).

Why a janitor and not just an UPSERT-on-start: on abnormal bridge exit
(kill -9 / crash / reboot) the in-process ``markDisconnected()`` never runs, so
the row stays ``connected`` forever. Nothing else cleans it. This is the safety
net; an UPSERT-on-start (separate change) is the complementary belt.

Liveness signal: the launcher writes a PID file per account at
``/tmp/wa-mirror-pids/<name>`` and the live process is ``node ... --employee=<name>``.
A row is GHOST only if BOTH hold:
  1. no live process for that account (PID file PID dead AND no matching pgrep), AND
  2. ``last_seen_at`` is older than WA_JANITOR_STALE_MINUTES (default 5) or NULL.
The double condition avoids touching a bridge that just started (PID file not yet
written) or one mid-handshake.

Cron-tick shim (NOT a daemon): flock single-instance, read-mostly, one UPDATE.
Local DB only (WA_MIRROR_DATABASE_URL / nuzantara_dev). No secrets, no cloud.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("wa_mirror_janitor")

STATE_DIR = Path.home() / ".cell-bridge-state"
LOCK_FILE = STATE_DIR / "wa_mirror_janitor.lock"
PID_DIR = Path("/tmp/wa-mirror-pids")
ACCOUNTS_JSON = Path.home() / ".wa-mirror.accounts.json"

_STALE_MINUTES = int(os.getenv("WA_JANITOR_STALE_MINUTES", "5"))


def _acquire_lock_or_exit() -> int:
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[wa_janitor] another instance running, skipping this tick")
        os.close(fd)
        sys.exit(0)


def _db_url() -> str:
    url = os.getenv("WA_MIRROR_DATABASE_URL", "")
    if url:
        return url
    # Fallback parity with the launcher default.
    return "postgresql://nuzantara@localhost:5432/nuzantara_dev"


def _phone_to_name() -> dict[str, str]:
    """Map E.164 -> account name from the launcher's accounts file."""
    try:
        data = json.loads(ACCOUNTS_JSON.read_text())
    except (OSError, ValueError) as exc:
        logger.warning("[wa_janitor] accounts file unreadable (%s); name map empty", exc)
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
    """True if a live bridge process exists for this account.

    Checks the PID file first (cheap, authoritative when present), then falls
    back to pgrep on the --employee=<name> arg (covers a missing/stale PID file).
    """
    pidfile = PID_DIR / name
    try:
        pid = int(pidfile.read_text().strip())
        os.kill(pid, 0)  # raises if dead
        return True
    except (OSError, ValueError):
        pass
    try:
        res = subprocess.run(
            ["pgrep", "-f", f"--employee={name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return res.returncode == 0 and bool(res.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


async def _run() -> None:
    name_map = _phone_to_name()
    conn = await asyncpg.connect(_db_url())
    try:
        rows = await conn.fetch(
            """
            SELECT id, team_member_name, team_member_phone, status, last_seen_at,
                   (last_seen_at IS NULL
                    OR last_seen_at < now() - ($1::int * interval '1 minute')) AS is_stale
            FROM whatsapp_team_sessions
            WHERE status IN ('pending', 'connected')
            """,
            _STALE_MINUTES,
        )
        ghosts: list[int] = []
        for r in rows:
            name = (r["team_member_name"] or name_map.get(r["team_member_phone"] or "", "")).lower()
            if not name:
                # Cannot resolve a process to check — be conservative, skip.
                logger.warning(
                    "[wa_janitor] row id=%s phone=%s has no resolvable name; skipping",
                    r["id"], r["team_member_phone"],
                )
                continue
            alive = _bridge_alive(name)
            if not alive and r["is_stale"]:
                ghosts.append(r["id"])
                logger.info(
                    "[wa_janitor] ghost: id=%s name=%s status=%s last_seen=%s (no live bridge)",
                    r["id"], name, r["status"], r["last_seen_at"],
                )

        if not ghosts:
            logger.info("[wa_janitor] no ghost rows (active=%d)", len(rows))
            return

        await conn.execute(
            """
            UPDATE whatsapp_team_sessions
            SET status = 'disconnected',
                disconnected_at = now(),
                disconnect_reason = 'janitor-ghost-cleanup',
                updated_at = now()
            WHERE id = ANY($1::int[])
              AND status IN ('pending', 'connected')
            """,
            ghosts,
        )
        logger.info("[wa_janitor] marked %d ghost row(s) disconnected: %s", len(ghosts), ghosts)
    finally:
        await conn.close()


def main() -> None:
    _acquire_lock_or_exit()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
