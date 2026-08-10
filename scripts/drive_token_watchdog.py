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
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered  # noqa: E402

WITA = timezone(timedelta(hours=8))

BACKEND_ENV = PROJECT_ROOT / "apps" / "backend-rag" / ".env"

# Telegram — stessa config di expiry_alerter.py
TELEGRAM_OWNER_CHAT_ID = "1125336968"  # Zero (archangelsamyaza) — corretto 2026-03-31

# State file for idempotency (avoid Telegram spam on every cron run)
STATE_DIR = Path(os.path.expanduser("~/.agent/decisions/state"))
STATE_FILE = STATE_DIR / "drive_oauth_watchdog.state.json"

# OAuth health verdicts. There are exactly two failure modes this table can
# express, and NO countdown — see `classify_oauth_health` for why the previous
# 30/14/7/1-day tier ladder was unreachable by construction.
HEALTH_OK = "ok"
HEALTH_NO_ROWS = "no-token"
HEALTH_NO_REFRESH = "no-refresh"
HEALTH_STALE_REFRESH = "stale-refresh"

# A row whose consumer runs daily refreshes daily — refresh is lazy-on-use, so
# `updated_at` advancing IS the consumer succeeding. Three days = three missed
# runs, past any single-night flake.
STALE_REFRESH_DAYS = 3

# Excluded from the staleness check, by ENTITY and not by shape: this exact row
# is left unrefreshed ON PURPOSE since 2026-05-10 —
# `GoogleDriveService._refresh_token` early-returns for it because Drive moved
# to ServiceAccountDriveService. Its `updated_at` has been frozen since
# 2026-06-15 and that is the intended state, not a fault.
UNREFRESHED_BY_DESIGN = frozenset({"SYSTEM"})

# SA key threshold (separate from OAuth — SA keys never expire by default,
# but rotation policy = 30 days)
SA_KEY_MAX_AGE_DAYS = 30

# SA email (service account Drive bot)
SA_EMAIL = "nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com"

VERBOSE = False
DRY_RUN = False


# ---------------------------------------------------------------------------
# OAuth health — pure function, no I/O. Easy to unit-test.
# ---------------------------------------------------------------------------

@dataclass
class OAuthHealth:
    """Result of classify_oauth_health()."""
    verdict: str  # one of HEALTH_* constants
    message: str  # "" when healthy
    detail: str   # one line of context for the log, always populated


def classify_oauth_health(
    rows: list[dict], now_utc: datetime | None = None
) -> OAuthHealth:
    """
    Judge the OAuth credential from what `google_drive_tokens` can actually say.

    WHY THERE IS NO COUNTDOWN HERE (2026-08-06). This function replaces a
    30/14/7/1-**day** tier ladder over `expires_at`, and that ladder could
    never fire truthfully, because `expires_at` is not a 90-day credential
    clock — it is the **one-hour access token**:

        google_drive_service.py:163  expires_at = now + expires_in (3600)
        google_drive_service.py:230  refresh when expires_at <= now + 5min

    Measured on the live production table the same day, both rows:

        SYSTEM      updated_at 2026-06-15 17:24:19  expires_at 18:24:18
        7dfe56b2…   updated_at 2026-08-06 11:11:20  expires_at 12:11:19

    `expires_at - updated_at == 1h` exactly, always. So `days_left` is 0 for a
    token refreshed one minute ago and negative for every idle row — TIER_30,
    TIER_14 and TIER_7 were unreachable **by construction**, and the only two
    states the ladder could produce were "🚨 scade DOMANI" for a perfectly
    healthy credential and "🔴 SCADUTO" for one nobody happened to use today.

    It never showed because the read itself always failed (#3690 PATH, then the
    fly credential). Curing the read is what would have armed the false alarm.

    What the table CAN support:
      - no rows                → the credential does not exist. Real P0.
      - a row without a        → `get_valid_token` returns None forever; no
        refresh_token            re-auth can happen by itself. Real P0.
      - a refreshable row      → its consumer has not succeeded in that long.
        frozen for 3+ days       Not a P0; a digest note. See below.
      - otherwise              → healthy.

    THE STALENESS RULE, and why it is here rather than in the "declared limit"
    where an earlier draft of this function put it. Refresh is lazy-on-use, so
    `updated_at` advancing IS a consumer succeeding — and when a refresh token
    is REVOKED the column simply stops moving, because every attempt now fails.
    That is exactly what happened, and it is the only trace the table kept:

        row 7dfe56b2…  last successful refresh  2026-07-25 19:02
        GARUDA indexer (daily 20:36, GARUDA_DRIVE_USER_ID = that row):
            `invalid_grant: Token has been expired or revoked`, every night
        re-authorised by hand                   2026-08-06 11:11

    Twelve days frozen, twelve nights of a real outage, and nothing said so.
    A revoked token still has `refresh_token IS NOT NULL`, so the P0 above
    cannot see this; the freeze can.

    DECLARED LIMITS on that rule, both deliberate:
      - It cannot distinguish "the credential is dead" from "nobody used
        Drive". That is why it is a DIGEST note, not a P0 — the ground truth
        is a consumer's own failure, and this is the cheap early hint, not a
        replacement for it.
      - CHANGED 2026-08-07 by the GARUDA decommission: the daily consumer of
        the one non-SYSTEM row WAS the GARUDA indexer, and it is gone (its
        Drive corpus was never filled — 0 files, 0 trashed). Nothing refreshes
        that row now, so within STALE_REFRESH_DAYS it will read `stale-refresh`
        — correctly. Read that verdict as "this grant has no consumer left,
        consider revoking it", not as "the credential is dying". The row is
        left in place deliberately: revoking a Google grant is Zero's call.
      - It assumes a consumer that runs at least every STALE_REFRESH_DAYS. One
        that ran weekly would read stale while perfectly healthy. A weekly
        consumer would need its own
        threshold rather than a blanket raise.
      - `SYSTEM` is excluded: unrefreshed on purpose since 2026-05-10.
    """
    if not rows:
        return OAuthHealth(
            verdict=HEALTH_NO_ROWS,
            message=(
                "🔴 <b>Drive OAuth</b>: NESSUN TOKEN in DB\n"
                "Nessuna credenziale OAuth esiste. Re-auth:\n"
                "<code>https://kita.balizero.com/settings/integrations</code>"
            ),
            detail="0 righe in google_drive_tokens",
        )

    broken = [r for r in rows if not r.get("has_refresh")]
    if broken:
        who = ", ".join(str(r.get("user_id", "?")) for r in broken)
        return OAuthHealth(
            verdict=HEALTH_NO_REFRESH,
            message=(
                f"🔴 <b>Drive OAuth</b>: riga senza refresh_token ({who})\n"
                "Il token NON può più rinnovarsi da solo — ogni richiesta "
                "riceve None finché non viene ri-autorizzato:\n"
                "<code>https://kita.balizero.com/settings/integrations</code>"
            ),
            detail=f"{len(broken)}/{len(rows)} righe senza refresh_token: {who}",
        )

    ages = ", ".join(
        f"{r.get('user_id', '?')} rinnovato {_age_text(r.get('updated_at'), now_utc)}"
        for r in rows
    )

    frozen = []
    for r in rows:
        if str(r.get("user_id")) in UNREFRESHED_BY_DESIGN:
            continue
        age = _age_days(r.get("updated_at"), now_utc)
        # An unparseable timestamp is NOT staleness: it is a read we could not
        # make, and calling it a fault would put a false digest note on a
        # healthy row every six hours. The parse failure surfaces as "?" in
        # `detail`, where a human sees it.
        if age is not None and age >= STALE_REFRESH_DAYS:
            frozen.append((str(r.get("user_id", "?")), age))

    if frozen:
        who = ", ".join(f"{u} ({a:.0f}g)" for u, a in frozen)
        return OAuthHealth(
            verdict=HEALTH_STALE_REFRESH,
            message=(
                f"🟡 <b>Drive OAuth</b>: nessun rinnovo da {STALE_REFRESH_DAYS}+ "
                f"giorni ({who})\n"
                "Il rinnovo avviene all'uso: o il consumatore è fermo, o il "
                "refresh_token è stato REVOCATO (in DB sembra identico).\n"
                "Conferma nel log del consumatore — un <code>invalid_grant</code> "
                "lì è la prova."
            ),
            detail=f"stale: {who} — {len(rows)} righe, {ages}",
        )

    return OAuthHealth(
        verdict=HEALTH_OK,
        message="",
        detail=f"{len(rows)} righe, tutte con refresh_token — {ages}",
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


def should_alert(current: str, last: Optional[str]) -> bool:
    """
    Return True iff the OAuth verdict is broken AND it is not a repeat.

    The severity ladder this replaced existed to rank six tiers. With three
    verdicts and no countdown there is nothing to rank: speak when the verdict
    is bad and it is not the same bad verdict we already sent.

    A CHANGED failure (no-token → no-refresh) speaks again: it is different
    news, and the remedy line differs. Recovery is silent, as before.
    """
    if current == HEALTH_OK:
        return False
    return current != last


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


def _send_telegram(
    text: str, bot_token: str, condition: str = "alert", tier: str = "p0"
) -> bool:
    """Route via the tg_notify gateway (2026-07-11 migration, cohort-5).

    `tier` is a parameter and not a constant since 2026-08-06: the staleness
    note is a "look at this", not a "act now", and sending it p0 would spend
    the daily budget of the two verdicts that ARE actionable.

    p0 tier: alerts only fire on an escalating tier (URGENT/CRITICAL) or an
    expired SA key — actionable now, Drive polling either already broke or
    breaks tomorrow. bot_token guard kept for callers still passing an empty
    token (dry-run/test harnesses).

    A digest is accepted when the gateway durably queues it (or recognizes an
    already queued duplicate). A p0 is accepted only when Telegram received it.
    """
    if DRY_RUN:
        print(f"[DRY RUN] Telegram: {text[:120]}...")
        return True
    if not bot_token:
        log("TELEGRAM_BOT_TOKEN non trovato")
        return False
    gateway = PROJECT_ROOT / "scripts" / "tg_notify.py"
    if not gateway.is_file():
        gateway = Path(os.path.expanduser("~/nuzantara/scripts/tg_notify.py"))
    # Stable key (cohort-3 disk_watchdog.sh pattern) — the message body embeds
    # a live timestamp + variable days-left, so tg_notify's default
    # source+text[:160] hash never matches twice and dedup can't suppress
    # flap-refiring (PENDING-ARMS 2026-07-12).
    # The key names the CONDITION, not just the source (fixed 2026-08-06).
    #
    # It used to be `drive-token-watchdog:<host>` for everything this organ
    # says, and that is how the first real expiry alert died. Measured in the
    # gateway state on Pro, minutes after the read was finally working:
    #
    #   drive-token-watchdog:Nuzantara  count=4  ts=18:00
    #   last_text = "🔴 Drive OAuth SCADUTO (12 giorni fa)"
    #
    # The `ts` is the 18:00 send — the LAST "impossibile connettersi" noise —
    # so the 18:42 expiry message was recorded and suppressed as a repeat of
    # the very noise it replaces. Two different facts, one key, and the
    # 6/24/72/168h ladder of the loud one swallows the quiet one.
    #
    # Stability still matters (that is why the key carries the tier and never
    # `days_left`: a tier is a condition, a day count is a measurement, and a
    # measurement in the key mints a fresh key per run — #3677). But stable
    # PER CONDITION, not per source.
    dedup_key = f"drive-token-watchdog:{condition}:{socket.gethostname().split('.')[0]}"
    try:
        proc = subprocess.run(
            [sys.executable, str(gateway), "--tier", tier,
             "--source", "drive-token-watchdog",
             "--dedup-key", dedup_key, "--", text],
            capture_output=True, text=True, timeout=30,
        )
        verdict = extract_gateway_verdict(proc.stderr)
        log(f"tg_notify: {verdict or f'NESSUN verdetto rc={proc.returncode}'}")
        return proc.returncode == 0 and (
            verdict in {"spooled", "deduped"}
            if tier == "digest"
            else gateway_delivered(verdict)
        )
    except Exception as e:
        log(f"Telegram fallito: {e}")
        return False


# Cron's PATH is /usr/bin:/bin:/usr/sbin:/sbin — Homebrew is NOT on it, and
# flyctl lives in /opt/homebrew/bin. Calling bare "fly" therefore worked in
# every interactive test and failed on every scheduled run, which is how this
# watchdog sent 65 identical "impossibile connettersi" alerts over 24 days
# while the thing it guards silently expired underneath (2026-08-06).
# Reproduced both ways before fixing, on Pro:
#   PATH=/usr/bin:/bin:/usr/sbin:/sbin      -> None
#   PATH=/opt/homebrew/bin:/usr/bin:/bin    -> {'expires_at': '2026-07-25 ...'}
# `which` first so an operator's own install still wins; the absolute list is
# the fallback for exactly the impoverished environment cron provides.
_FLY_CANDIDATES = (
    "/opt/homebrew/bin/flyctl",
    "/opt/homebrew/bin/fly",
    "/usr/local/bin/flyctl",
    "/usr/local/bin/fly",
    str(Path.home() / ".fly" / "bin" / "flyctl"),
    str(Path.home() / ".fly" / "bin" / "fly"),
)


def _resolve_fly() -> str | None:
    """Absolute path to flyctl, or None if it genuinely is not installed."""
    import shutil

    found = shutil.which("fly") or shutil.which("flyctl")
    if found:
        return found
    for cand in _FLY_CANDIDATES:
        if os.access(cand, os.X_OK):
            return cand
    return None


def _check_drive_token_via_fly() -> tuple[dict | None, str | None]:
    """
    Interroga google_drive_tokens via fly ssh console sul backend Fly.io.

    Restituisce `(data, failure_reason)`: esattamente uno dei due è non-None.
    La ragione esiste perché il messaggio d'allarme deve NOMINARE la causa —
    quello vecchio diceva "verifica che fly ssh funzioni", indirizzando chi
    legge verso l'autenticazione mentre il problema era che `fly` non era
    nemmeno risolvibile. Una diagnosi che punta lontano dalla causa costa più
    del silenzio (W106: cura e messaggio scadono insieme).
    """
    # EVERY row, not `ORDER BY created_at DESC LIMIT 1`. That old query guarded
    # whichever row happened to be newest — today the per-user one, silently a
    # different one the moment anybody authorises again — while the row the
    # code names by hand (`SYSTEM`, read by crm_guardian and zantara-media's
    # indexer) went unwatched. There are two rows; judge both.
    code = (
        "import asyncio, asyncpg, os, json\n"
        "async def m():\n"
        "    c = await asyncpg.connect(os.environ['DATABASE_URL'])\n"
        "    rs = await c.fetch(\n"
        "        'SELECT user_id, (refresh_token IS NOT NULL) AS has_refresh, "
        "expires_at, updated_at FROM google_drive_tokens ORDER BY user_id'\n"
        "    )\n"
        "    await c.close()\n"
        "    print(json.dumps({'rows': [\n"
        "        {'user_id': r['user_id'], 'has_refresh': r['has_refresh'],\n"
        "         'expires_at': str(r['expires_at']),\n"
        "         'updated_at': str(r['updated_at'])} for r in rs\n"
        "    ]}))\n"
        "asyncio.run(m())\n"
    )
    import base64
    code_b64 = base64.b64encode(code.encode()).decode()

    fly = _resolve_fly()
    if fly is None:
        return None, (
            "il binario <code>fly</code> non è sul PATH di questo processo "
            f"(PATH={os.environ.get('PATH', '')[:120]})"
        )

    cmd = [
        fly, "ssh", "console",
        "--app", "nuzantara-rag",
        "--command",
        f"python3 -c \"import base64,os; exec(base64.b64decode('{code_b64}').decode())\"",
    ]
    # TWO credentials, and only one of them works — probe, never assume (W106).
    #
    # Measured on Pro 2026-08-06, running the REAL command rather than
    # `auth whoami` (which passes for a token scoped to a different app and
    # only dies later, on the work):
    #
    #   with FLY_API_TOKEN from ~/.nuzantara-secrets.env
    #       -> Could not find App "nuzantara-rag"
    #   with FLY_API_TOKEN unset, falling back to ~/.fly/config.yml
    #       -> PROBE_OK
    #
    # This is a SECOND, independent cause of the same blindness #3690 cured,
    # and it is the one that bites in production: cron reaches this script
    # through `cron-wrapper.sh`, which sources the secrets file, so the live
    # path always carried the credential that cannot see this app. The earlier
    # verification runs succeeded only because they ran under `env -i`, which
    # stripped it — the mirror of W108's dev machine that was structurally
    # unable to reproduce the red.
    #
    # Deliberately NOT hardcoded as "the env token is stale, so always unset
    # it". That is exactly the frozen measurement W106 is about: the fly-backup
    # script hardcoded `unset FLY_API_TOKEN` when it was true, the world
    # inverted, and the cure threw away the only working credential for 27h.
    # Try each credential the environment actually offers, in order, and LOG
    # which one was accepted.
    attempts: list[tuple[str, dict]] = [("env/inherited", dict(os.environ))]
    if os.environ.get("FLY_API_TOKEN"):
        fallback = dict(os.environ)
        fallback.pop("FLY_API_TOKEN", None)
        attempts.append(("~/.fly/config.yml", fallback))

    failures: list[str] = []
    for source, env in attempts:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=60, env=env)
            output = result.stdout.strip()
            log(f"fly ssh via {source}: exit={result.returncode} {output[:160]}")
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    log(f"credential accepted: {source}")
                    return json.loads(line), None
            detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:150]
            failures.append(f"{source}: exit {result.returncode} — {detail or '(nessun output)'}")
        except subprocess.TimeoutExpired:
            failures.append(f"{source}: nessuna risposta entro 60s")
        except Exception as e:  # noqa: BLE001 — the reason is reported, never guessed
            log(f"fly ssh via {source} fallito: {e}")
            failures.append(f"{source}: {type(e).__name__}: {e}")

    # Every credential refused. Name each one and what IT said — a diagnosis
    # that points away from the cause costs more than silence (W106).
    return None, "<code>fly ssh</code> rifiutato da ogni credenziale — " + " | ".join(failures)



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


def _age_days(ts: object, now_utc: datetime | None = None) -> float | None:
    """Age of a timestamp in days, or None if it cannot be read.

    None is not zero and not "fresh": callers must treat it as "unknown" and
    never as a fault, or an unparseable row becomes a recurring false alarm.
    """
    if not isinstance(ts, str) or not ts:
        return None
    try:
        when = parse_expires_at(ts)
    except Exception:
        return None
    return ((now_utc or datetime.now(timezone.utc)) - when).total_seconds() / 86400


def _age_text(ts: object, now_utc: datetime | None = None) -> str:
    """Human age of a timestamp, for CONTEXT lines only.

    Returns "?" rather than raising: this feeds the log/detail string, and a
    watchdog must not die describing itself.
    """
    days = _age_days(ts, now_utc)
    if days is None:
        return "?"
    hours = days * 24
    if hours < 48:
        return f"{hours:.0f}h fa"
    return f"{days:.0f}g fa"


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main() -> int:
    env = _load_env()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")

    alerts: list[str] = []
    alert_kinds: list[str] = []
    now_utc = datetime.now(timezone.utc)
    now_wita = now_utc.astimezone(WITA)
    timestamp = now_wita.strftime("%Y-%m-%d %H:%M WITA")

    state = load_state()
    last_oauth_health: Optional[str] = state.get("last_oauth_health")
    last_sa_alert_age: Optional[int] = state.get("last_sa_alert_age")

    # --- Check 1: Drive OAuth credential health ---
    log("Controllo Drive OAuth token...")
    token_data, token_read_error = _check_drive_token_via_fly()

    new_oauth_health: Optional[str] = None  # set if classification succeeds

    if token_data is None:
        # Read failure — separate from the health verdict; always alert.
        #
        # The message NAMES the measured cause instead of prescribing a guess,
        # and says out loud what the reader cannot otherwise know: while this
        # branch fires, the credential is NOT being judged, so silence means
        # "blind", not "fine".
        alert_kinds.append("read-failure")
        alerts.append(
            "⚠️ <b>Drive Watchdog</b>: non ho potuto LEGGERE lo stato del token\n"
            f"Causa: {token_read_error or 'sconosciuta'}\n"
            "<b>Mentre vedi questo, la credenziale NON è sorvegliata.</b>"
        )
    else:
        try:
            rows = token_data["rows"]
            if not isinstance(rows, list):
                raise TypeError(f"'rows' non è una lista: {type(rows).__name__}")

            health = classify_oauth_health(rows, now_utc)
            new_oauth_health = health.verdict
            log(f"OAuth: {health.verdict} — {health.detail}")

            if should_alert(new_oauth_health, last_oauth_health):
                alert_kinds.append(new_oauth_health)
                alerts.append(health.message)
                log(f"Verdetto: {last_oauth_health or 'ok'} → {new_oauth_health}")
        except Exception as e:
            # Payload the fly side did not produce — schema drift between the
            # two halves of this script (#9). Name it; never read it as health.
            log(f"Payload OAuth illeggibile: {e}")
            alert_kinds.append("parse-failure")
            alerts.append(
                f"⚠️ <b>Drive Watchdog</b>: payload OAuth illeggibile: {e}\n"
                "<b>Mentre vedi questo, la credenziale NON è sorvegliata.</b>"
            )

    # --- Check 2: SA key age (kept simple — no tier system, single threshold) ---
    log("Controllo SA key age...")
    sa_age = _check_sa_key_age()
    new_sa_alert_age: Optional[int] = None
    if sa_age is not None and sa_age > SA_KEY_MAX_AGE_DAYS:
        # Idempotent: only alert if age went UP since last alert (or no prev alert).
        if last_sa_alert_age is None or sa_age > last_sa_alert_age:
            alert_kinds.append("sa-key-age")
            alerts.append(
                f"⚠️ <b>SA Key</b> age: {sa_age} giorni (soglia: {SA_KEY_MAX_AGE_DAYS})\n"
                "Rotazione consigliata: Google Cloud Console → IAM → Service Accounts\n"
                f"<code>{SA_EMAIL}</code>"
            )
            new_sa_alert_age = sa_age
        else:
            new_sa_alert_age = last_sa_alert_age

    # --- Invia alerts, THEN persist ---
    #
    # This order is the fix (2026-08-06). It used to be the other way round:
    # `save_state` ran first and `_send_telegram`'s return value was printed
    # and discarded. The ratchet therefore advanced on CLASSIFICATION, not on
    # DELIVERY — and it only speaks on a CHANGE of verdict, so for a
    # once-per-lifetime event there is exactly ONE chance to speak.
    #
    # Measured, and it is how this was found: #3690 cured the PATH defect that
    # had kept this watchdog from ever reading the table; the run that VERIFIED
    # that cure classified a failure, wrote it to the state file, and delivered
    # nothing anyone read. The next cron found the same value already recorded
    # and stayed silent. Curing a mute watchdog and then muting it with the act
    # of verifying the cure.
    #
    # Three ways the old order lost the message, all now closed: a
    # verification run, a send that fails, and a cron environment with no
    # TELEGRAM_BOT_TOKEN (`_send_telegram` returns False on exactly that).
    #
    # The obvious worry about retrying forever is already handled, by the
    # component whose job it is: the alert goes through tg_notify with a
    # STABLE dedup key, so the 6/24/72/168h repeat ladder collapses a
    # persistent failure to about four messages a week. That split is the
    # point — the ratchet answers "has this been DELIVERED", the gateway
    # answers "how often may it repeat". One mechanism each, instead of the
    # ratchet doing both and doing the second one wrong.
    delivered = True
    if alerts:
        header = f"🔔 <b>Drive Watchdog</b> — {timestamp}\n\n"
        message = header + "\n\n".join(alerts)
        # The condition is the SET of facts in this message — sorted so the
        # same combination always yields the same key, and joined so a message
        # that carries two facts cannot be mistaken for either one alone.
        condition = "+".join(sorted(set(alert_kinds))) or "alert"
        # One message carries every fact of this run, so the tier is decided by
        # the LOUDEST of them: digest only when staleness is all there is.
        # Anything actionable in the bundle pulls the whole thing to p0 —
        # burying a "no refresh_token" inside a digest flush would be the same
        # class of mistake as shouting the staleness note.
        tier = (
            "digest"
            if set(alert_kinds) == {HEALTH_STALE_REFRESH}
            else "p0"
        )
        delivered = _send_telegram(message, bot_token, condition, tier)
        print(f"[drive-watchdog] {len(alerts)} alert{'s' if len(alerts) > 1 else ''} inviato: {delivered}")
    else:
        print(f"[drive-watchdog] {timestamp} — tutto OK (token valido, SA key OK)")

    # --- Persist state (best-effort), only for what actually got through ---
    if not DRY_RUN:
        new_state = dict(state)
        # The day-ladder keys are actively removed, not merely stopped: a state
        # file written before today carries `last_oauth_tier: critical_expired`
        # and `last_oauth_days_left: -12`, and the Cell's oauth_health_sensor
        # reads exactly those. Left behind, they would paint Drive red forever
        # off a measurement whose scale was wrong.
        new_state.pop("last_oauth_tier", None)
        new_state.pop("last_oauth_days_left", None)
        # Recovery is recorded UNCONDITIONALLY; only a BROKEN verdict waits for
        # delivery. `delivered` is one boolean for the whole message, so gating
        # the healthy verdict on it too would let an undelivered SA-key alert
        # leave `last_oauth_health` stuck on the old failure — and then the
        # next real occurrence of that same failure reads as a repeat and stays
        # silent. Nothing has to be delivered for "it is fine now".
        if new_oauth_health is not None and (
            new_oauth_health == HEALTH_OK or delivered
        ):
            new_state["last_oauth_health"] = new_oauth_health
            new_state["last_oauth_check_iso"] = now_utc.isoformat()
        if new_sa_alert_age is not None and delivered:
            new_state["last_sa_alert_age"] = new_sa_alert_age
        save_state(new_state)

    # Always exit 0 — the cron wrapper would retry on non-zero, and a retry
    # duplicates the alert. Undelivered state is carried by the ratchet not
    # advancing, not by the exit code.
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drive Token Watchdog")
    parser.add_argument("--dry-run", action="store_true", help="Nessun Telegram, solo preview")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug output")
    args = parser.parse_args()
    VERBOSE = args.verbose
    DRY_RUN = args.dry_run
    sys.exit(main())
