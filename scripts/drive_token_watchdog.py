#!/usr/bin/env python3
"""
Drive Token Watchdog — Controlla scadenza OAuth token Google Drive e SA key.

Tiered alert system (P1-11, zero-crash audit 2026-04-29):
    - 30 days  → INFO    (heads-up, plan re-auth)
    - 14 days  → WARNING (schedule re-auth this week)
    -  7 days  → URGENT  (re-auth NOW)
    -  1 day   → CRITICAL (immediate action — Drive will break tomorrow)
    -  expired → CRITICAL (Drive polling already broken)

Idempotent: alerts only escalate when the tier *changes*. State persisted in
`~/.agent/decisions/state/drive_oauth_watchdog.state.json` so cron can fire
every 6h without spamming Telegram.

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
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

WITA = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_ENV = PROJECT_ROOT / "apps" / "backend-rag" / ".env"

# Telegram — stessa config di expiry_alerter.py
TELEGRAM_OWNER_CHAT_ID = "1125336968"  # Zero (archangelsamyaza) — corretto 2026-03-31

# State file for idempotency (avoid Telegram spam on every cron run)
STATE_DIR = Path(os.path.expanduser("~/.agent/decisions/state"))
STATE_FILE = STATE_DIR / "drive_oauth_watchdog.state.json"

# Tier names (most-urgent first). Use string constants so state files written
# by previous runs are forward-compatible.
TIER_EXPIRED = "critical_expired"
TIER_1_DAY = "critical_1d"
TIER_7_DAYS = "urgent_7d"
TIER_14_DAYS = "warning_14d"
TIER_30_DAYS = "info_30d"
TIER_OK = "ok"

# Numerical severity for "is this a more urgent tier than last time?".
# Higher number = more urgent. TIER_OK is the baseline (no alert).
TIER_SEVERITY: dict[str, int] = {
    TIER_OK: 0,
    TIER_30_DAYS: 1,
    TIER_14_DAYS: 2,
    TIER_7_DAYS: 3,
    TIER_1_DAY: 4,
    TIER_EXPIRED: 5,
}

# SA key threshold (separate from OAuth — SA keys never expire by default,
# but rotation policy = 30 days)
SA_KEY_MAX_AGE_DAYS = 30

# SA email (service account Drive bot)
SA_EMAIL = "nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com"

VERBOSE = False
DRY_RUN = False


# ---------------------------------------------------------------------------
# Tier classification — pure function, no I/O. Easy to unit-test.
# ---------------------------------------------------------------------------

@dataclass
class TierAlert:
    """Result of classify_tier()."""
    tier: str  # one of TIER_* constants
    emoji: str
    severity_label: str
    message_template: str
    days_left: int  # negative if already expired


def classify_tier(days_left: int) -> TierAlert:
    """
    Map days remaining to a tier. Pure function.

    days_left < 0     → TIER_EXPIRED (already expired)
    days_left <= 1    → TIER_1_DAY    (critical, last day)
    days_left <= 7    → TIER_7_DAYS   (urgent)
    days_left <= 14   → TIER_14_DAYS  (warning)
    days_left <= 30   → TIER_30_DAYS  (info heads-up)
    days_left > 30    → TIER_OK       (no alert)
    """
    if days_left < 0:
        return TierAlert(
            tier=TIER_EXPIRED,
            emoji="🔴",
            severity_label="CRITICAL — EXPIRED",
            message_template=(
                "🔴 <b>Drive OAuth SCADUTO</b> ({abs_days} giorni fa!)\n"
                "Drive polling NON funziona. Re-auth IMMEDIATA:\n"
                "<code>https://kita.balizero.com/settings/integrations</code>"
            ),
            days_left=days_left,
        )
    if days_left <= 1:
        return TierAlert(
            tier=TIER_1_DAY,
            emoji="🚨",
            severity_label="CRITICAL",
            message_template=(
                "🚨 <b>Drive OAuth scade DOMANI</b> ({days} giorni rimasti)\n"
                "Re-auth ORA per evitare interruzione Drive polling:\n"
                "<code>https://kita.balizero.com/settings/integrations</code>"
            ),
            days_left=days_left,
        )
    if days_left <= 7:
        return TierAlert(
            tier=TIER_7_DAYS,
            emoji="⚠️",
            severity_label="URGENT",
            message_template=(
                "⚠️ <b>Drive OAuth</b> scade in <b>{days} giorni</b> (URGENT)\n"
                "Pianifica re-auth questa settimana:\n"
                "<code>https://kita.balizero.com/settings/integrations</code>"
            ),
            days_left=days_left,
        )
    if days_left <= 14:
        return TierAlert(
            tier=TIER_14_DAYS,
            emoji="🟡",
            severity_label="WARNING",
            message_template=(
                "🟡 <b>Drive OAuth</b>: <b>{days} giorni</b> alla scadenza\n"
                "Pianifica re-auth nei prossimi giorni:\n"
                "<code>https://kita.balizero.com/settings/integrations</code>"
            ),
            days_left=days_left,
        )
    if days_left <= 30:
        return TierAlert(
            tier=TIER_30_DAYS,
            emoji="🔵",
            severity_label="INFO",
            message_template=(
                "🔵 <b>Drive OAuth</b>: heads-up — {days} giorni alla scadenza\n"
                "Re-auth diventa urgente sotto i 14 giorni."
            ),
            days_left=days_left,
        )
    return TierAlert(
        tier=TIER_OK,
        emoji="✅",
        severity_label="OK",
        message_template="",
        days_left=days_left,
    )


def render_alert_text(alert: TierAlert) -> str:
    """Format alert.message_template with days_left / abs_days."""
    return alert.message_template.format(
        days=alert.days_left,
        abs_days=abs(alert.days_left),
    )


# ---------------------------------------------------------------------------
# Idempotency — load/save last-alerted tier so we don't spam every 6h.
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load watchdog state. Returns empty dict if missing/corrupt."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    """Persist watchdog state. Best-effort (errors logged, not raised)."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        log(f"Failed to save state: {e}")


def should_alert(current_tier: str, last_tier: Optional[str]) -> bool:
    """
    Return True iff current_tier is *strictly more severe* than last_tier.

    Examples:
        should_alert(TIER_30_DAYS, None)           → True   (first time ever)
        should_alert(TIER_30_DAYS, TIER_OK)        → True   (just crossed 30d threshold)
        should_alert(TIER_14_DAYS, TIER_30_DAYS)   → True   (escalation)
        should_alert(TIER_14_DAYS, TIER_14_DAYS)   → False  (same tier — silent)
        should_alert(TIER_14_DAYS, TIER_7_DAYS)    → False  (de-escalation, e.g. after re-auth)
        should_alert(TIER_OK, TIER_7_DAYS)         → False  (recovered — no alert needed)
    """
    if current_tier == TIER_OK:
        return False  # never alert on recovery
    current_sev = TIER_SEVERITY.get(current_tier, 0)
    last_sev = TIER_SEVERITY.get(last_tier or TIER_OK, 0)
    return current_sev > last_sev


# ---------------------------------------------------------------------------
# I/O helpers (unchanged from previous version)
# ---------------------------------------------------------------------------

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


def parse_expires_at(expires_str: str) -> datetime:
    """Parse asyncpg/SSH-stringified timestamp → tz-aware datetime."""
    if "+" in expires_str or expires_str.endswith("Z"):
        return datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
    # Naive datetime — assume UTC
    return datetime.fromisoformat(expires_str).replace(tzinfo=timezone.utc)


def compute_days_left(expires_at: datetime, now_utc: datetime | None = None) -> int:
    """Days remaining until expiry. Negative if already expired."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    return (expires_at - now_utc).days


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main() -> int:
    env = _load_env()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")

    alerts: list[str] = []
    now_utc = datetime.now(timezone.utc)
    now_wita = now_utc.astimezone(WITA)
    timestamp = now_wita.strftime("%Y-%m-%d %H:%M WITA")

    state = load_state()
    last_oauth_tier: Optional[str] = state.get("last_oauth_tier")
    last_sa_alert_age: Optional[int] = state.get("last_sa_alert_age")

    # --- Check 1: Drive OAuth token with tier system ---
    log("Controllo Drive OAuth token...")
    token_data = _check_drive_token_via_fly()

    new_oauth_tier: Optional[str] = None  # set if classification succeeds
    new_oauth_days_left: Optional[int] = None  # last computed days_left (sensor input)

    if token_data is None:
        # Connection failure — separate from tier system; always alert.
        alerts.append(
            "⚠️ <b>Drive Watchdog</b>: impossibile connettersi al backend Fly.io\n"
            "Verifica che <code>fly ssh</code> funzioni."
        )
    elif token_data.get("expires_at") is None:
        # Same effect as expired — fold into TIER_EXPIRED with synthetic message.
        new_oauth_tier = TIER_EXPIRED
        if should_alert(new_oauth_tier, last_oauth_tier):
            alerts.append(
                "🔴 <b>Drive OAuth</b>: NESSUN TOKEN in DB\n"
                "Drive polling disabilitato. Esegui re-auth:\n"
                "<code>https://kita.balizero.com/settings/integrations</code>"
            )
    else:
        expires_str = token_data["expires_at"]
        log(f"expires_at raw: {expires_str}")
        try:
            expires_dt = parse_expires_at(expires_str)
            days_left = compute_days_left(expires_dt, now_utc)
            log(f"Token scade in {days_left} giorni")

            tier_alert = classify_tier(days_left)
            new_oauth_tier = tier_alert.tier
            new_oauth_days_left = days_left

            if should_alert(new_oauth_tier, last_oauth_tier):
                alerts.append(render_alert_text(tier_alert))
                log(
                    f"Tier transition: {last_oauth_tier or 'OK'} → {new_oauth_tier} "
                    f"({tier_alert.severity_label})"
                )
            else:
                log(
                    f"Tier {new_oauth_tier} (last: {last_oauth_tier or 'OK'}) — "
                    f"no alert (idempotent)"
                )
        except Exception as e:
            log(f"Parse expires_at fallito: {e}")
            alerts.append(f"⚠️ <b>Drive Watchdog</b>: errore parsing expires_at: {e}")

    # --- Check 2: SA key age (kept simple — no tier system, single threshold) ---
    log("Controllo SA key age...")
    sa_age = _check_sa_key_age()
    new_sa_alert_age: Optional[int] = None
    if sa_age is not None and sa_age > SA_KEY_MAX_AGE_DAYS:
        # Idempotent: only alert if age went UP since last alert (or no prev alert).
        if last_sa_alert_age is None or sa_age > last_sa_alert_age:
            alerts.append(
                f"⚠️ <b>SA Key</b> age: {sa_age} giorni (soglia: {SA_KEY_MAX_AGE_DAYS})\n"
                "Rotazione consigliata: Google Cloud Console → IAM → Service Accounts\n"
                f"<code>{SA_EMAIL}</code>"
            )
            new_sa_alert_age = sa_age
        else:
            new_sa_alert_age = last_sa_alert_age

    # --- Persist state (best-effort) ---
    if not DRY_RUN:
        new_state = dict(state)
        if new_oauth_tier is not None:
            new_state["last_oauth_tier"] = new_oauth_tier
            new_state["last_oauth_check_iso"] = now_utc.isoformat()
            if new_oauth_days_left is not None:
                new_state["last_oauth_days_left"] = new_oauth_days_left
        if new_sa_alert_age is not None:
            new_state["last_sa_alert_age"] = new_sa_alert_age
        save_state(new_state)

    # --- Invia alerts ---
    if alerts:
        header = f"🔔 <b>Drive Watchdog</b> — {timestamp}\n\n"
        message = header + "\n\n".join(alerts)
        sent = _send_telegram(message, bot_token)
        print(f"[drive-watchdog] {len(alerts)} alert{'s' if len(alerts) > 1 else ''} inviato: {sent}")
        # Always exit 0 after successful alert delivery — the watchdog's job is done.
        # Exit 1 would cause cron-wrapper to retry, sending duplicate alerts.
        return 0
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
