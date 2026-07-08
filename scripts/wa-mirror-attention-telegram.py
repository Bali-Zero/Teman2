#!/usr/bin/env python3
"""wa-mirror attention Telegram alerter (Phase 1)

Two modes:
- `--digest`: send a single end-of-day summary (08:00 / 18:00 cron). Always sends.
- `--realtime`: scan for new HIGH messages since last_seen_state, alert only on
  critical reason codes (refund/complaint/deadline/payment_dispute/lawyer/audit).
  Dedup per phone within 4h.

OSINT-safe: Telegram message contains only:
- contact display_name + phone (last 4 digits masked)
- reason codes (no free text)
- N unresolved
- link to local dashboard (http://localhost:8767)

Raw body NEVER sent to Telegram cloud.

State: ~/.cache/wa-mirror-attention-state.json
"""
from __future__ import annotations
import asyncio
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import asyncpg

ENV_FILE = Path.home() / ".wa-mirror.env"


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def first_nonempty(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return ""


ENV_VALUES = read_env_file(ENV_FILE)
DB_URL = ENV_VALUES.get("WA_MIRROR_DATABASE_URL")
if not DB_URL:
    print("ERR: WA_MIRROR_DATABASE_URL missing", file=sys.stderr)
    sys.exit(2)
# W57 (2026-05-26): removed legacy rewrite to pg-proxy Fly (cf. wa-mirror-attention-classifier.py).
# Post-cutover 2026-05-24 wa-mirror is LOCAL-ONLY → honor URL as written.
DB_URL = DB_URL.replace("postgres://","postgresql://")

TOKEN = first_nonempty(
    os.environ.get("TELEGRAM_BOT_TOKEN"),
    os.environ.get("BALIZEROBOT_TOKEN"),
    ENV_VALUES.get("TELEGRAM_BOT_TOKEN"),
    ENV_VALUES.get("BALIZEROBOT_TOKEN"),
)
CHAT_ID = first_nonempty(
    os.environ.get("TELEGRAM_OWNER_CHAT_ID"),
    os.environ.get("TELEGRAM_CHAT_ID"),
    ENV_VALUES.get("TELEGRAM_OWNER_CHAT_ID"),
    ENV_VALUES.get("TELEGRAM_CHAT_ID"),
)
DASHBOARD_URL = first_nonempty(os.environ.get("WA_DASHBOARD_URL"), ENV_VALUES.get("WA_DASHBOARD_URL")) or "http://localhost:8767"
STATE_PATH = Path.home() / ".cache" / "wa-mirror-attention-state.json"
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

CRITICAL_REASONS = {"refund", "complaint", "deadline", "payment_dispute", "lawyer", "audit"}
DEDUP_WINDOW = timedelta(hours=4)


def mask_phone(phone: str) -> str:
    """+62812****7456 — keep prefix(4) + suffix(4)."""
    if not phone or len(phone) < 6:
        return f"+{phone}"
    return f"+{phone[:4]}****{phone[-4:]}"


def send_telegram(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print(f"ERR: TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID missing", file=sys.stderr)
        return False
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=data, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"ERR: telegram send: {e}", file=sys.stderr)
        return False


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"last_alerted": {}, "last_digest_at": None}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"last_alerted": {}, "last_digest_at": None}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str))


async def fetch_high_unresolved(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch("""
      WITH highs AS (
        SELECT
          REGEXP_REPLACE(m.raw_baileys_event->'key'->>'senderPn', '@.*', '') AS phone,
          MIN(m.id) AS first_high_id,
          MAX(m.id) AS last_high_id,
          MIN(m.created_at) AS first_high_at,
          MAX(m.created_at) AS last_high_at,
          COUNT(*) AS n_high,
          ARRAY_AGG(DISTINCT reason) AS reasons
        FROM whatsapp_message_context m,
             LATERAL UNNEST(COALESCE(m.attention_reason, ARRAY[]::text[])) AS reason
        WHERE m.attention_priority = 'HIGH'
          AND m.attention_resolved_at IS NULL
          AND m.direction = 'inbound'
          AND m.raw_baileys_event->'key'->>'senderPn' ~ '^[0-9]+@'
        GROUP BY 1
      )
      SELECT h.*,
             c.id AS crm_id, c.full_name AS crm_name, c.status AS crm_status, c.lead_source
      FROM highs h
      LEFT JOIN clients c ON c.phone_normalized = h.phone AND c.deleted_at IS NULL
      ORDER BY h.last_high_at DESC
    """)
    return [dict(r) for r in rows]


async def fetch_digest_metrics(conn: asyncpg.Connection) -> dict:
    """Aggregate metrics for end-of-day digest (last 24h window)."""
    row = await conn.fetchrow("""
      WITH window_msgs AS (
        SELECT * FROM whatsapp_message_context
        WHERE direction='inbound'
          AND created_at >= NOW() - INTERVAL '24 hours'
          AND raw_baileys_event->'key'->>'senderPn' ~ '^[0-9]+@'
      )
      SELECT
        COUNT(*) FILTER (WHERE attention_priority='HIGH' AND attention_resolved_at IS NULL) AS high_open,
        COUNT(*) FILTER (WHERE attention_priority='HIGH' AND attention_resolved_at IS NOT NULL) AS high_resolved,
        COUNT(*) FILTER (WHERE attention_priority='MEDIUM') AS medium,
        COUNT(DISTINCT REGEXP_REPLACE(raw_baileys_event->'key'->>'senderPn','@.*','')) AS distinct_phones_24h,
        COUNT(*) AS inbound_24h
      FROM window_msgs
    """)
    new_leads = await conn.fetchval("""
      SELECT COUNT(*) FROM clients
      WHERE created_by='wa-mirror-auto-promote'
        AND created_at >= NOW() - INTERVAL '24 hours'
    """)
    return {**dict(row), "new_leads_24h": new_leads}


async def cmd_realtime(force: bool = False):
    state = load_state()
    last_alerted = state.get("last_alerted", {})
    now = datetime.now(timezone.utc)

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2, ssl=False)
    try:
        async with pool.acquire() as conn:
            items = await fetch_high_unresolved(conn)
    finally:
        await pool.close()

    alerted = 0
    for it in items:
        critical = [r for r in (it["reasons"] or []) if r in CRITICAL_REASONS]
        if not critical:
            continue
        phone = it["phone"]
        key = f"{phone}:{sorted(critical)[0]}"
        last_ts_str = last_alerted.get(key)
        if last_ts_str and not force:
            try:
                last_ts = datetime.fromisoformat(last_ts_str)
                if now - last_ts < DEDUP_WINDOW:
                    continue  # dedup
            except Exception:
                pass

        display = it.get("crm_name") or f"+{phone}"
        crm_tag = f"CRM #{it['crm_id']}" if it["crm_id"] else "new lead"
        reason_chips = " ".join(f"<code>{r}</code>" for r in critical)
        n_high = it["n_high"]
        msg = (
            "🚨 <b>HIGH attention</b>\n"
            f"<b>{display}</b> — {mask_phone(phone)}\n"
            f"<i>{crm_tag}</i> · {n_high} unresolved msg\n"
            f"Reasons: {reason_chips}\n"
            f"→ <a href='{DASHBOARD_URL}'>Open dashboard</a>"
        )
        if send_telegram(msg):
            last_alerted[key] = now.isoformat()
            alerted += 1

    state["last_alerted"] = last_alerted
    save_state(state)
    print(json.dumps({"alerted": alerted, "high_open": len(items), "ts": now.isoformat()}))


async def cmd_digest():
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2, ssl=False)
    try:
        async with pool.acquire() as conn:
            metrics = await fetch_digest_metrics(conn)
            items = await fetch_high_unresolved(conn)
    finally:
        await pool.close()

    now_iso = datetime.now(timezone.utc).isoformat()
    lines = [
        "📊 <b>WA mirror daily digest</b>",
        f"<i>{datetime.now().strftime('%a %d %b %Y, %H:%M WITA')}</i>",
        "",
        "<b>Last 24h:</b>",
        f"  • {metrics['inbound_24h']} inbound msgs from {metrics['distinct_phones_24h']} contacts",
        f"  • <b>{metrics['high_open']}</b> HIGH unresolved · {metrics['high_resolved']} resolved",
        f"  • {metrics['medium']} MEDIUM",
        f"  • {metrics['new_leads_24h']} new leads auto-promoted to CRM",
    ]
    if items:
        lines.append("")
        lines.append("<b>🚨 Needs your attention:</b>")
        for it in items[:8]:  # cap to 8 to keep msg readable
            name = it.get("crm_name") or f"+{it['phone']}"
            crm_marker = "" if it["crm_id"] else " <i>(new lead)</i>"
            crit = [r for r in (it["reasons"] or []) if r in CRITICAL_REASONS]
            unanswered = "unanswered_thread_3plus" in (it["reasons"] or [])
            tags = [f"<code>{r}</code>" for r in crit[:3]]
            if unanswered:
                tags.append("<code>⏰thread</code>")
            lines.append(f"  • <b>{name}</b>{crm_marker} — {it['n_high']} msg · {' '.join(tags)}")
        if len(items) > 8:
            lines.append(f"  …and {len(items)-8} more")
    else:
        lines.append("")
        lines.append("🟢 Everything is acknowledged.")

    lines.append("")
    lines.append(f"→ <a href='{DASHBOARD_URL}'>Open dashboard</a>")
    msg = "\n".join(lines)
    ok = send_telegram(msg)
    print(json.dumps({"sent": ok, "high_open": len(items), "ts": now_iso}))


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--digest", action="store_true")
    p.add_argument("--realtime", action="store_true")
    p.add_argument("--force", action="store_true", help="bypass dedup (test only)")
    args = p.parse_args()
    if args.digest:
        await cmd_digest()
    elif args.realtime:
        await cmd_realtime(force=args.force)
    else:
        # default: realtime
        await cmd_realtime(force=False)


if __name__ == "__main__":
    asyncio.run(main())
