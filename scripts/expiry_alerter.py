#!/usr/bin/env python3
"""
Expiry Alerter — Scans CRM for upcoming visa/passport expirations,
emails the responsible team member, and sends Telegram summary to owner.

Run daily via cron (recommended: 08:00 WITA).

Usage:
    python3 scripts/expiry_alerter.py              # Full run
    python3 scripts/expiry_alerter.py --dry-run     # Preview only, no emails/telegram
    python3 scripts/expiry_alerter.py --verbose      # Debug output
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import subprocess
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

WITA = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_ENV = PROJECT_ROOT / "apps" / "backend-rag" / ".env"

# SMTP config (Zoho via damar@, send as zantara@)
SMTP_HOST = "smtppro.zoho.com"
SMTP_PORT = 465
SMTP_LOGIN = os.environ.get("SMTP_LOGIN", "damar@balizero.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = "zantara@balizero.com"
FROM_NAME = "Zantara AI"

# Telegram config
TELEGRAM_OWNER_CHAT_ID = "413539912"

# Thresholds (days)
CRITICAL_DAYS = 14   # 🔴
WARNING_DAYS = 30    # 🟡
OVERDUE_DAYS = 0     # Already expired

VERBOSE = False


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[alerter] {msg}", file=sys.stderr)


def _load_env() -> dict[str, str]:
    env = {}
    if BACKEND_ENV.exists():
        for line in BACKEND_ENV.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def _query_expiries() -> list[dict]:
    """Query CRM for upcoming expirations AND overdue practices via fly ssh to backend."""
    import base64
    code = '''import asyncio,os,asyncpg,json
async def m():
 c=await asyncpg.connect(os.environ["DATABASE_URL"])
 items = []

 # 1. Passport/visa expirations within 30 days
 r=await c.fetch("""
  SELECT DISTINCT ON (c.id, exp_type)
   c.id as client_id, c.full_name, c.email as client_email, c.phone,
   c.assigned_to, c.passport_expiry,
   p.title as practice_title, p.expiry_date as practice_expiry, p.status,
   CASE
    WHEN c.passport_expiry IS NOT NULL AND c.passport_expiry < now() + interval '30 days'
     THEN 'passport'
    ELSE 'practice'
   END as exp_type,
   COALESCE(
    CASE WHEN c.passport_expiry < now() + interval '30 days' THEN c.passport_expiry END,
    p.expiry_date
   ) as expiry_date
  FROM clients c
  LEFT JOIN practices p ON p.client_id = c.id AND p.status NOT IN ('completed','cancelled')
  WHERE c.status = 'active'
   AND c.assigned_to IS NOT NULL
   AND (
    (c.passport_expiry IS NOT NULL AND c.passport_expiry < now() + interval '30 days')
    OR (p.expiry_date IS NOT NULL AND p.expiry_date < now() + interval '30 days')
   )
  ORDER BY c.id, exp_type, expiry_date
 """)
 for x in r:
  items.append({
   "client_id": x["client_id"],
   "full_name": x["full_name"],
   "client_email": x["client_email"],
   "phone": x["phone"],
   "assigned_to": x["assigned_to"],
   "exp_type": x["exp_type"],
   "practice_title": x["practice_title"],
   "expiry_date": str(x["expiry_date"])[:10] if x["expiry_date"] else None,
   "passport_expiry": str(x["passport_expiry"])[:10] if x["passport_expiry"] else None,
  })

 # 2. Overdue practices (expected_completion_date passed, still active)
 r2=await c.fetch("""
  SELECT c.id as client_id, c.full_name, c.email as client_email, c.phone,
   c.assigned_to, p.title as practice_title, p.status,
   p.expected_completion_date
  FROM practices p
  JOIN clients c ON p.client_id = c.id
  WHERE p.expected_completion_date < now()
   AND p.status NOT IN ('completed','cancelled','inquiry','declined')
   AND (p.title IS NULL OR p.title NOT ILIKE '%tax%')
   AND c.assigned_to IS NOT NULL
  ORDER BY p.expected_completion_date
 """)
 for x in r2:
  items.append({
   "client_id": x["client_id"],
   "full_name": x["full_name"],
   "client_email": x["client_email"],
   "phone": x["phone"],
   "assigned_to": x["assigned_to"],
   "exp_type": "overdue_practice",
   "practice_title": x["practice_title"] or x["status"],
   "expiry_date": str(x["expected_completion_date"])[:10],
   "passport_expiry": None,
  })

 print(json.dumps(items))
 await c.close()
asyncio.run(m())
'''
    encoded = __import__("base64").b64encode(code.encode()).decode()

    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro",
         f'fly ssh console --app nuzantara-rag -C "python3 -c \\"import base64;exec(base64.b64decode(b\'{encoded}\'))\\"" 2>/dev/null'],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        log(f"Query failed: {result.stderr[:200]}")
        return []

    output = result.stdout.strip()
    # Find the JSON line (last line starting with [)
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("["):
            return json.loads(line)
    return []


def _classify_urgency(expiry_str: str) -> tuple[str, int, str]:
    """Return (emoji, days_left, label)."""
    if not expiry_str:
        return "⚪", 999, "unknown"
    exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    today = datetime.now(WITA).date()
    days = (exp - today).days

    if days < 0:
        return "🔴", days, f"SCADUTO {abs(days)} hari lalu"
    elif days <= CRITICAL_DAYS:
        return "🔴", days, f"Scade tra {days} hari"
    elif days <= WARNING_DAYS:
        return "🟡", days, f"Scade tra {days} hari"
    else:
        return "🟢", days, f"Scade tra {days} hari"


def _send_email(to: str, subject: str, body: str, dry_run: bool = False) -> bool:
    """Send email via Zoho SMTP."""
    if dry_run:
        print(f"[DRY RUN] Email to {to}: {subject}")
        return True

    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        server.login(SMTP_LOGIN, SMTP_PASS)

        msg = MIMEMultipart()
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Reply-To"] = FROM_EMAIL
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server.sendmail(FROM_EMAIL, [to], msg.as_string())
        server.quit()
        log(f"Email sent to {to}")
        return True
    except Exception as e:
        log(f"Email failed to {to}: {e}")
        return False


def _send_telegram(chat_id: str, text: str, bot_token: str, dry_run: bool = False) -> bool:
    """Send Telegram message."""
    if dry_run:
        print(f"[DRY RUN] Telegram to {chat_id}: {text[:100]}...")
        return True
    if not bot_token:
        log("No TELEGRAM_BOT_TOKEN")
        return False

    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data, timeout=10,
        )
        return True
    except Exception as e:
        log(f"Telegram failed: {e}")
        return False


def _build_team_email(assigned_to: str, items: list[dict]) -> tuple[str, str]:
    """Build email subject and body for a team member."""
    name = assigned_to.split("@")[0].capitalize()
    critical = [i for i in items if i["emoji"] == "🔴"]
    warning = [i for i in items if i["emoji"] == "🟡"]

    n_items = len(items)
    subject = f"📋 Daily Update: {n_items} klien perlu di-update — {datetime.now(WITA).strftime('%d/%m')}"

    overdue = [i for i in items if i["exp_type"] == "overdue_practice"]
    expiries = [i for i in items if i["exp_type"] != "overdue_practice"]

    lines = [
        f"Halo {name},",
        "",
        f"Ini pengingat harian dari Zantara AI. Ada {n_items} klien yang perlu perhatian kamu hari ini:",
        "",
    ]

    if overdue:
        lines.append("📌 PRAKTIK OVERDUE — update status atau tutup:")
        lines.append("")
        for item in sorted(overdue, key=lambda x: x["days"]):
            title = item.get("practice_title", "?")
            days_late = abs(item["days"])
            lines.append(f"  • {item['full_name']} — {title} (telat {days_late} hari)")
            lines.append(f"    → Jika klien tidak lanjut, ubah status ke 'declined'")
            lines.append(f"    → Jika masih jalan, update step terbaru di CRM")
            if item.get("phone"):
                lines.append(f"    📞 {item['phone']}")
            lines.append("")

    if expiries:
        lines.append("🛂 DOKUMEN MENDEKATI/MELEWATI TENGGAT:")
        lines.append("")
        for item in sorted(expiries, key=lambda x: x["days"]):
            exp_type = "Paspor" if item["exp_type"] == "passport" else item.get("practice_title", "Visa")
            lines.append(f"  • {item['full_name']} — {exp_type}: {item['label']}")
            if item["days"] < 0:
                lines.append(f"    → Jika klien sudah pergi/tidak aktif, update profil di CRM")
            else:
                lines.append(f"    → Hubungi klien untuk mulai proses perpanjangan")
            if item.get("phone"):
                lines.append(f"    📞 {item['phone']}")
            lines.append("")

    lines.extend([
        "─" * 40,
        "🔄 REMINDER HARIAN:",
        "  1. Upload dokumen baru ke Drive klien",
        "  2. Update status praktik di CRM (jangan biarkan 'on_process' berminggu-minggu)",
        "  3. Buat profil klien baru untuk setiap inquiry yang masuk",
        "  4. Jika klien tidak jadi → set status 'declined' (jangan dibiarkan menggantung)",
        "",
        "Balas email ini dengan update singkat.",
        "",
        "Terima kasih,",
        "Zantara AI — Bali Zero Operations",
    ])

    return subject, "\n".join(lines)


def _build_telegram_summary(all_items: list[dict], emails_sent: int) -> str:
    """Build Telegram summary for owner."""
    now = datetime.now(WITA).strftime("%d/%m %H:%M")
    lines = [f"📋 <b>Expiry Alert</b> — {now} WITA", ""]

    # Group by urgency
    critical = [i for i in all_items if i["emoji"] == "🔴"]
    warning = [i for i in all_items if i["emoji"] == "🟡"]

    if critical:
        lines.append(f"🔴 <b>{len(critical)} CRITICI:</b>")
        for i in critical:
            if i["exp_type"] == "passport":
                exp_type = "PP"
            elif i["exp_type"] == "overdue_practice":
                exp_type = f"⏰{(i.get('practice_title') or '?')[:15]}"
            else:
                exp_type = (i.get("practice_title") or "Visa")[:15]
            lines.append(f"  • {i['full_name']} ({exp_type}) → {i['assigned_to'].split('@')[0]} | {i['label']}")
        lines.append("")

    if warning:
        lines.append(f"🟡 <b>{len(warning)} warning:</b>")
        for i in warning[:10]:
            if i["exp_type"] == "passport":
                exp_type = "PP"
            elif i["exp_type"] == "overdue_practice":
                exp_type = f"⏰{(i.get('practice_title') or '?')[:15]}"
            else:
                exp_type = (i.get("practice_title") or "Visa")[:15]
            lines.append(f"  • {i['full_name']} ({exp_type}) → {i['assigned_to'].split('@')[0]} | {i['label']}")
        if len(warning) > 10:
            lines.append(f"  ...+{len(warning) - 10} altri")
        lines.append("")

    lines.append(f"📧 {emails_sent} email inviate ai team member")

    return "\n".join(lines)


def _writeback_renewal_required(items: list[dict], dry_run: bool = False) -> None:
    """Update practice status to renewal_required in CRM for items ≤30 days to expiry."""
    # Only practice-type expirations (not overdue_practice, not passport)
    practice_items = [
        i for i in items
        if i.get("exp_type") not in ("overdue_practice", "passport")
        and i.get("days", 999) <= 30
        and i.get("client_id")
    ]

    if not practice_items:
        log("No practices to mark renewal_required")
        return

    import base64
    client_ids = list({str(i["client_id"]) for i in practice_items})
    ids_csv = ",".join(client_ids)

    code = f"""import asyncio,os,asyncpg
async def m():
 c=await asyncpg.connect(os.environ["DATABASE_URL"])
 r=await c.execute(\"\"\"
  UPDATE practices
  SET status='renewal_required', updated_at=NOW()
  WHERE client_id=ANY($1::int[])
    AND status NOT IN ('completed','cancelled','renewal_required','declined')
    AND expiry_date IS NOT NULL
    AND expiry_date < now() + interval '30 days'
    AND expiry_date > now() - interval '90 days'
 \"\"\", [{ids_csv}])
 print(f"Updated: {{r}}")
 await c.close()
asyncio.run(m())
"""
    encoded = base64.b64encode(code.encode()).decode()

    if dry_run:
        print(f"[DRY RUN] Would mark renewal_required for {len(client_ids)} clients: {ids_csv}")
        return

    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro",
         f'fly ssh console --app nuzantara-rag -C "python3 -c \\"import base64;exec(base64.b64decode(b\'{encoded}\'))\\"" 2>/dev/null'],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        log(f"CRM write-back: marked {len(client_ids)} clients renewal_required")
    else:
        log(f"CRM write-back failed: {result.stderr[:100]}")


def main() -> None:
    global VERBOSE

    parser = argparse.ArgumentParser(description="Expiry Alerter")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    VERBOSE = args.verbose

    env = _load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")

    log("Querying CRM for expiries...")
    raw_items = _query_expiries()

    if not raw_items:
        log("No expiries found in next 30 days")
        print("No expiries found.")
        return

    # Classify urgency
    items = []
    for item in raw_items:
        exp_date = item.get("expiry_date") or item.get("passport_expiry")
        if not exp_date:
            continue
        emoji, days, label = _classify_urgency(exp_date)
        if emoji in ("🔴", "🟡") and days > -90:  # Skip items expired >90 days (stale data)
            item["emoji"] = emoji
            item["days"] = days
            item["label"] = label
            items.append(item)

    if not items:
        log("No critical/warning expiries")
        print("No urgent expiries.")
        return

    log(f"Found {len(items)} expiries needing attention")

    # Write-back to CRM: mark practices with ≤30 days to expiry as renewal_required
    # (practice-type items only, not overdue_practice — those already have their own flow)
    _writeback_renewal_required(items, args.dry_run)

    # Group by assigned_to
    by_member: dict[str, list[dict]] = {}
    for item in items:
        member = item.get("assigned_to", "unassigned")
        by_member.setdefault(member, []).append(item)

    # Send emails to each team member
    emails_sent = 0
    for member, member_items in by_member.items():
        if not member or member == "unassigned" or "@" not in member:
            continue
        subject, body = _build_team_email(member, member_items)
        if _send_email(member, subject, body, dry_run=args.dry_run):
            emails_sent += 1

    # Send Telegram summary to owner
    tg_text = _build_telegram_summary(items, emails_sent)
    _send_telegram(TELEGRAM_OWNER_CHAT_ID, tg_text, bot_token, dry_run=args.dry_run)

    print(f"Done: {len(items)} expiries, {emails_sent} emails sent")
    if args.dry_run:
        print("\n--- TELEGRAM PREVIEW ---")
        print(tg_text)


if __name__ == "__main__":
    main()
