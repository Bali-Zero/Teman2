#!/usr/bin/env python3
"""
Profile-Monitor Wrapper (Pro local, listens on Tailscale)

Riceve POST da Mac dipendenti su evento checkout profilo balizero.
Cross-referenzia con login CRM giornaliero per decidere se inviare alert Telegram.

Endpoint: POST http://100.107.22.111:9099/checkout
Body: {"employee": "surya", "event": "CHECKOUT", "timestamp": "2026-05-19T14:23:08+08:00",
       "console_owner": "root", "hostname": "Surya-MacBook"}

Logic:
  1. Lookup last CRM login today for this employee (auth_audit_log)
  2. Compute work-end = crm_login + 9h
  3. If now < work-end → ALERT (entro finestra lavoro)
  4. If now >= work-end → silence (fine giornata)
  5. Dedup: max 1 alert per employee per 30 min
"""

import json
import logging
import os
import re
import signal
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import asyncpg
import asyncio

LOG_PATH = os.path.expanduser("~/logs/profile-monitor-wrapper.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger("profile-monitor")

WITA = timezone(timedelta(hours=8))
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 9099
WORK_DURATION_HOURS = 9  # 8h lavoro + 1h pranzo
DEDUP_WINDOW_MINUTES = 30

# Dedup state in-memory: {employee: last_alert_dt}
_last_alert: dict[str, datetime] = {}

# Mapping E-mail dipendente → identificatore breve
EMPLOYEE_EMAILS = {
    "surya": "surya@balizero.com",
    "vino": "vino@balizero.com",
    "damar": "damar@balizero.com",
    "krisna": "krisna@balizero.com",
    "adit": "adit@balizero.com",
    "ari": "ari.firda@balizero.com",
    "asya": "asya@balizero.com",
    "sahira": "sahira@balizero.com",
    "antonello": "zero@balizero.com",  # owner — solo per test profile-monitor
}


def _load_secrets() -> dict[str, str]:
    """Read keys from ~/.nuzantara-secrets.env."""
    secrets = {}
    path = os.path.expanduser("~/.nuzantara-secrets.env")
    if not os.path.exists(path):
        return secrets
    content = open(path).read()
    for key in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_OWNER_CHAT_ID",
        "DATABASE_URL_LOCAL",
    ):
        m = re.search(rf'{key}\s*=\s*["\']?([^"\'\n]+)["\']?', content)
        if m:
            secrets[key] = m.group(1).strip()
    return secrets


SECRETS = _load_secrets()


def _send_telegram(text: str) -> None:
    token = SECRETS.get("TELEGRAM_BOT_TOKEN")
    chat_id = SECRETS.get("TELEGRAM_OWNER_CHAT_ID")
    if not token or not chat_id:
        logger.error("Telegram credentials missing — alert lost: %s", text)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        logger.info("Telegram sent: %s", text[:80])
    except Exception as e:
        logger.error("Telegram send failed: %s", e)


async def _last_crm_login_today(email: str) -> datetime | None:
    """Query auth_audit_log for last successful login today (WITA timezone)."""
    db_url = SECRETS.get("DATABASE_URL_LOCAL")
    if not db_url:
        logger.error("DATABASE_URL_LOCAL missing")
        return None
    db_url_proxy = re.sub(r"@[^/]+/", "@localhost:15432/", db_url)
    db_url_proxy = db_url_proxy.replace("postgres://", "postgresql://")
    try:
        conn = await asyncpg.connect(db_url_proxy, timeout=5)
        today_wita = datetime.now(WITA).date()
        row = await conn.fetchrow(
            """
            SELECT timestamp
            FROM auth_audit_log
            WHERE email = $1
              AND action IN ('login_success', 'login')
              AND success IS TRUE
              AND timestamp AT TIME ZONE 'Asia/Makassar' >= $2::timestamp
            ORDER BY timestamp ASC
            LIMIT 1
            """,
            email,
            today_wita,
        )
        await conn.close()
        if row:
            return row["timestamp"].astimezone(WITA)
        return None
    except Exception as e:
        logger.error("DB query failed for %s: %s", email, e)
        return None


def _is_within_work_window(crm_login: datetime, now: datetime) -> tuple[bool, datetime]:
    """Return (within_window, work_end_time)."""
    work_end = crm_login + timedelta(hours=WORK_DURATION_HOURS)
    return now < work_end, work_end


def _should_dedup(employee: str, now: datetime) -> bool:
    last = _last_alert.get(employee)
    if last is None:
        return False
    return (now - last) < timedelta(minutes=DEDUP_WINDOW_MINUTES)


async def _handle_checkout(payload: dict) -> dict:
    """Process a checkout event and decide whether to alert."""
    employee = payload.get("employee", "").lower().strip()
    event = payload.get("event", "")
    hostname = payload.get("hostname", "unknown")
    console_owner = payload.get("console_owner", "unknown")
    force = bool(payload.get("force", False))  # bypass weekend+crm checks (for manual tests)

    if event != "CHECKOUT":
        return {"status": "ignored", "reason": f"event={event}"}

    if employee not in EMPLOYEE_EMAILS:
        logger.warning("Unknown employee: %s", employee)
        return {"status": "error", "reason": "unknown_employee"}

    email = EMPLOYEE_EMAILS[employee]
    now = datetime.now(WITA)

    if not force:
        if now.weekday() >= 5:
            return {"status": "silent", "reason": "weekend"}

        crm_login = await _last_crm_login_today(email)
        if crm_login is None:
            logger.info("No CRM login today for %s — silent", email)
            return {"status": "silent", "reason": "no_crm_login_today"}

        within_window, work_end = _is_within_work_window(crm_login, now)
        if not within_window:
            logger.info("Checkout after work end for %s", email)
            return {"status": "silent", "reason": "after_work_end"}
    else:
        # Force mode: fake login at "today 09:00" for the message
        crm_login = now.replace(hour=9, minute=0, second=0, microsecond=0)
        work_end = crm_login + timedelta(hours=WORK_DURATION_HOURS)

    if _should_dedup(employee, now) and not force:
        return {"status": "silent", "reason": "dedup_window"}

    _last_alert[employee] = now
    minutes_remaining = int((work_end - now).total_seconds() / 60)
    test_tag = " [TEST]" if force else ""
    msg = (
        f"⚠️ <b>Check-out profilo Bali Zero</b>{test_tag}\n"
        f"\n"
        f"<b>{employee.upper()}</b> ha lasciato il profilo balizero alle "
        f"<b>{now.strftime('%H:%M')}</b> WITA\n"
        f"\n"
        f"• Login CRM mattutino: {crm_login.strftime('%H:%M')}\n"
        f"• Fine prevista lavoro: {work_end.strftime('%H:%M')}\n"
        f"• Mancano <b>{minutes_remaining} min</b> al fine giornata\n"
        f"• Console attuale: <code>{console_owner}</code>\n"
        f"• Host: <code>{hostname}</code>"
    )
    _send_telegram(msg)
    return {"status": "alerted", "minutes_remaining": minutes_remaining, "force": force}


class CheckoutHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/checkout":
            self._send_json(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        if length == 0 or length > 10000:
            self._send_json(400, {"error": "bad_length"})
            return
        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw)
        except Exception as e:
            self._send_json(400, {"error": "bad_json", "detail": str(e)})
            return

        logger.info("POST /checkout: %s", payload)
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_handle_checkout(payload))
            loop.close()
            self._send_json(200, result)
        except Exception as e:
            logger.exception("Handler error: %s", e)
            self._send_json(500, {"error": "internal", "detail": str(e)})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "profile-monitor"})
        else:
            self._send_json(404, {"error": "not_found"})

    def log_message(self, fmt: str, *args) -> None:
        logger.info("HTTP %s - %s", self.address_string(), fmt % args)


def _shutdown(signum, frame) -> None:
    logger.info("Shutdown signal received")
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), CheckoutHandler)
    logger.info("profile-monitor wrapper listening on %s:%d", LISTEN_HOST, LISTEN_PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
