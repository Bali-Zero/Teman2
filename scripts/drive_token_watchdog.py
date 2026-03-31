#!/usr/bin/env python3
"""
Drive Token Watchdog — Controlla scadenza OAuth token Google Drive e SA key.
Invia alert Telegram 7 giorni prima della scadenza (o se già scaduto).

Cron OpenClaw Air: 0 */6 * * *

Usage:
    python3 scripts/drive_token_watchdog.py              # Full run
    python3 scripts/drive_token_watchdog.py --dry-run    # Preview, no Telegram
    python3 scripts/drive_token_watchdog.py --verbose    # Debug output
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_ENV = PROJECT_ROOT / "apps" / "backend-rag" / ".env"

# Telegram — stessa config di expiry_alerter.py
TELEGRAM_OWNER_CHAT_ID = "1125336968"  # Zero (archangelsamyaza) — corretto 2026-03-31

# Soglie di alert
WARN_DAYS = 7    # ⚠️ alert se scade entro 7 giorni
SA_KEY_MAX_AGE_DAYS = 30  # ⚠️ alert se SA key > 30 giorni

# SA email (service account Drive bot)
SA_EMAIL = "nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com"

VERBOSE = False
DRY_RUN = False


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[drive-watchdog] {msg}", file=sys.stderr)


def _load_env() -> dict[str, str]:
    """Carica variabili da apps/backend-rag/.env"""
    env: dict[str, str] = {}
    if BACKEND_ENV.exists():
        for line in BACKEND_ENV.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _send_telegram(text: str, bot_token: str) -> bool:
    """Invia messaggio Telegram all'owner."""
    if DRY_RUN:
        print(f"[DRY RUN] Telegram: {text[:120]}...")
        return True
    if not bot_token:
        log("TELEGRAM_BOT_TOKEN non trovato")
        return False
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_OWNER_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data,
            timeout=10,
        )
        log("Telegram inviato")
        return True
    except Exception as e:
        log(f"Telegram fallito: {e}")
        return False


def _check_drive_token_via_fly() -> dict | None:
    """
    Interroga google_drive_tokens via fly ssh console sul backend Fly.io.
    Restituisce dict con expires_at (ISO string) oppure None.
    """
    code = (
        "import asyncio, asyncpg, os, json\n"
        "async def m():\n"
        "    c = await asyncpg.connect(os.environ['DATABASE_URL'])\n"
        "    r = await c.fetchrow(\n"
        "        'SELECT expires_at, created_at FROM google_drive_tokens "
        "ORDER BY created_at DESC LIMIT 1'\n"
        "    )\n"
        "    await c.close()\n"
        "    if r:\n"
        "        print(json.dumps({'expires_at': str(r[\"expires_at\"]), "
        "'created_at': str(r[\"created_at\"])}))\n"
        "    else:\n"
        "        print(json.dumps({'expires_at': None}))\n"
        "asyncio.run(m())\n"
    )
    import base64
    code_b64 = base64.b64encode(code.encode()).decode()
    cmd = [
        "fly", "ssh", "console",
        "--app", "nuzantara-rag",
        "--command",
        f"python3 -c \"import base64,os; exec(base64.b64decode('{code_b64}').decode())\"",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout.strip()
        log(f"fly ssh output: {output[:200]}")
        # Cerca JSON nella output (potrebbe avere banner ssh)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
    except Exception as e:
        log(f"fly ssh fallito: {e}")
    return None


def _check_sa_key_age() -> int | None:
    """
    Controlla età della SA key via gcloud CLI.
    Ritorna età in giorni, oppure None se gcloud non disponibile.
    """
    try:
        result = subprocess.run(
            [
                "gcloud", "iam", "service-accounts", "keys", "list",
                f"--iam-account={SA_EMAIL}",
                "--format=json",
                "--filter=keyType=USER_MANAGED",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log(f"gcloud error: {result.stderr[:100]}")
            return None
        keys = json.loads(result.stdout)
        if not keys:
            log("Nessuna SA key trovata")
            return None
        # Prende la key più vecchia tra le user-managed
        now = datetime.now(timezone.utc)
        oldest_age = 0
        for key in keys:
            valid_after = key.get("validAfterTime", "")
            if valid_after:
                try:
                    key_dt = datetime.fromisoformat(valid_after.replace("Z", "+00:00"))
                    age = (now - key_dt).days
                    oldest_age = max(oldest_age, age)
                except Exception:
                    pass
        log(f"SA key oldest age: {oldest_age} giorni")
        return oldest_age
    except FileNotFoundError:
        log("gcloud CLI non trovato — skip SA key check")
        return None
    except Exception as e:
        log(f"SA key check fallito: {e}")
        return None


def main() -> int:
    env = _load_env()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")

    alerts: list[str] = []
    now_utc = datetime.now(timezone.utc)
    now_wita = now_utc.astimezone(WITA)
    timestamp = now_wita.strftime("%Y-%m-%d %H:%M WITA")

    # --- Check 1: Drive OAuth token ---
    log("Controllo Drive OAuth token...")
    token_data = _check_drive_token_via_fly()

    if token_data is None:
        alerts.append(
            "⚠️ <b>Drive Watchdog</b>: impossibile connettersi al backend Fly.io\n"
            "Verifica che <code>fly ssh</code> funzioni."
        )
    elif token_data.get("expires_at") is None:
        alerts.append(
            "🔴 <b>Drive OAuth</b>: NESSUN TOKEN in DB\n"
            "Drive polling disabilitato. Esegui re-auth:\n"
            "<code>https://kita.balizero.com/settings/integrations</code>"
        )
    else:
        expires_str = token_data["expires_at"]
        log(f"expires_at raw: {expires_str}")
        try:
            # asyncpg restituisce datetime — ma via ssh diventa stringa
            if "+" in expires_str or expires_str.endswith("Z"):
                expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            else:
                # Naive datetime — assume UTC
                expires_dt = datetime.fromisoformat(expires_str).replace(tzinfo=timezone.utc)
            days_left = (expires_dt - now_utc).days
            log(f"Token scade in {days_left} giorni")
            if days_left < 0:
                alerts.append(
                    f"🔴 <b>Drive OAuth SCADUTO</b> ({abs(days_left)} giorni fa!)\n"
                    "Drive polling non funziona. Re-auth immediata:\n"
                    "<code>https://kita.balizero.com/settings/integrations</code>"
                )
            elif days_left < WARN_DAYS:
                alerts.append(
                    f"⚠️ <b>Drive OAuth</b> scade in <b>{days_left} giorni</b>\n"
                    "Pianifica re-auth prima che scada:\n"
                    "<code>https://kita.balizero.com/settings/integrations</code>"
                )
            else:
                log(f"Token OK — scade in {days_left} giorni")
        except Exception as e:
            log(f"Parse expires_at fallito: {e}")
            alerts.append(f"⚠️ <b>Drive Watchdog</b>: errore parsing expires_at: {e}")

    # --- Check 2: SA key age ---
    log("Controllo SA key age...")
    sa_age = _check_sa_key_age()
    if sa_age is not None and sa_age > SA_KEY_MAX_AGE_DAYS:
        alerts.append(
            f"⚠️ <b>SA Key</b> age: {sa_age} giorni (soglia: {SA_KEY_MAX_AGE_DAYS})\n"
            "Rotazione consigliata: Google Cloud Console → IAM → Service Accounts\n"
            f"<code>{SA_EMAIL}</code>"
        )

    # --- Invia alerts ---
    if alerts:
        header = f"🔔 <b>Drive Watchdog</b> — {timestamp}\n\n"
        message = header + "\n\n".join(alerts)
        sent = _send_telegram(message, bot_token)
        print(f"[drive-watchdog] {len(alerts)} alert{'s' if len(alerts) > 1 else ''} inviato: {sent}")
        return 1 if any("🔴" in a for a in alerts) else 0
    else:
        print(f"[drive-watchdog] {timestamp} — tutto OK (token valido, SA key OK)")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drive Token Watchdog")
    parser.add_argument("--dry-run", action="store_true", help="Nessun Telegram, solo preview")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug output")
    args = parser.parse_args()
    VERBOSE = args.verbose
    DRY_RUN = args.dry_run
    sys.exit(main())
