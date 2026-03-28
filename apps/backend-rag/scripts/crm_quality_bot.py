#!/usr/bin/env python3
"""CRM Data Quality Bot — nightly audit + auto-fix.

Runs as cron job at 07:00 WITA (23:00 UTC).
Audits CRM data, applies safe auto-fixes, sends Telegram report.

Usage:
    python scripts/crm_quality_bot.py              # full run (audit + fix + report)
    python scripts/crm_quality_bot.py --audit-only  # audit only, no fixes
    python scripts/crm_quality_bot.py --dry-run     # show what would be fixed
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "413539912")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "crm_quality.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("crm_quality_bot")
logger.setLevel(logging.INFO)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_sh)

# ---------------------------------------------------------------------------
# Standard practice statuses
# ---------------------------------------------------------------------------
STANDARD_STATUSES = {
    "active", "completed", "pending", "cancelled", "inquiry",
    "in_progress", "on_hold", "expired", "pending_renewal",
    "expiring_soon", "renewed",
}

STATUS_MAP: dict[str, str] = {
    "on_process": "in_progress",
    "sending_invoice": "pending",
    "quotation_sent": "pending",
    "approved": "active",
    "submitted_to_gov": "in_progress",
    "waiting_documents": "pending",
}


# ---------------------------------------------------------------------------
# Audit queries
# ---------------------------------------------------------------------------
async def run_audit(pool: asyncpg.Pool) -> dict[str, Any]:
    """Run all audit checks and return counts."""
    checks: dict[str, Any] = {}
    async with pool.acquire() as conn:
        checks["clients_no_email"] = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND (email IS NULL OR TRIM(email) = '')"
        )
        checks["duplicate_emails"] = await conn.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT LOWER(TRIM(email)) AS e
                FROM clients WHERE deleted_at IS NULL AND email IS NOT NULL AND TRIM(email) != ''
                GROUP BY LOWER(TRIM(email)) HAVING COUNT(*) > 1
            ) d
        """)
        checks["emails_uppercase"] = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND email IS NOT NULL AND email != LOWER(email)"
        )
        checks["emails_whitespace"] = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND email IS NOT NULL AND email != TRIM(email)"
        )
        checks["no_drive_folder"] = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND (google_drive_folder_id IS NULL OR TRIM(google_drive_folder_id) = '')"
        )
        checks["empty_string_folder"] = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND google_drive_folder_id = ''"
        )
        checks["no_npwp_active_practices"] = await conn.fetchval("""
            SELECT COUNT(DISTINCT c.id)
            FROM clients c JOIN practices p ON p.client_id = c.id
            WHERE c.deleted_at IS NULL AND (c.npwp IS NULL OR TRIM(c.npwp) = '')
            AND p.status IN ('active', 'completed', 'pending')
        """)
        checks["orphan_practices"] = await conn.fetchval(
            "SELECT COUNT(*) FROM practices WHERE client_id IS NULL OR client_id NOT IN (SELECT id FROM clients)"
        )
        checks["nonstandard_statuses"] = await conn.fetchval(f"""
            SELECT COUNT(*) FROM practices
            WHERE status NOT IN ({','.join(f"'{s}'" for s in STANDARD_STATUSES)})
        """)
        checks["duplicate_companies"] = await conn.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT co.company_name, ccl.client_id
                FROM companies co JOIN client_company_links ccl ON ccl.company_id = co.id
                GROUP BY co.company_name, ccl.client_id HAVING COUNT(*) > 1
            ) d
        """)
        checks["docs_no_file_url"] = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE (file_url IS NULL OR TRIM(file_url) = '') AND google_drive_file_url IS NOT NULL AND TRIM(google_drive_file_url) != ''"
        )
        checks["docs_no_url_at_all"] = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE (file_url IS NULL OR TRIM(file_url) = '') AND (google_drive_file_url IS NULL OR TRIM(google_drive_file_url) = '')"
        )
        checks["total_clients"] = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL"
        )
        checks["total_practices"] = await conn.fetchval("SELECT COUNT(*) FROM practices")
    return checks


# ---------------------------------------------------------------------------
# Auto-fix
# ---------------------------------------------------------------------------
async def apply_fixes(pool: asyncpg.Pool, *, dry_run: bool = False) -> dict[str, int]:
    """Apply safe auto-fixes. Returns fix counts."""
    fixes: dict[str, int] = {}
    async with pool.acquire() as conn:
        # 1. Normalize emails: lowercase + trim
        if dry_run:
            fixes["email_normalized"] = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND email IS NOT NULL AND (email != LOWER(email) OR email != TRIM(email))"
            )
        else:
            tag = await conn.execute(
                "UPDATE clients SET email = LOWER(TRIM(email)), updated_by = 'crm_quality_bot', updated_at = NOW() "
                "WHERE deleted_at IS NULL AND email IS NOT NULL AND (email != LOWER(email) OR email != TRIM(email))"
            )
            fixes["email_normalized"] = int(tag.split()[-1])

        # 2. Normalize practice statuses
        total_status = 0
        for old, new in STATUS_MAP.items():
            if dry_run:
                cnt = await conn.fetchval("SELECT COUNT(*) FROM practices WHERE status = $1", old)
            else:
                tag = await conn.execute(
                    "UPDATE practices SET status = $1, updated_by = 'crm_quality_bot', updated_at = NOW() WHERE status = $2",
                    new, old,
                )
                cnt = int(tag.split()[-1])
            total_status += cnt
        fixes["status_normalized"] = total_status

        # 3. Set empty string folder_id to NULL
        if dry_run:
            fixes["folder_id_nullified"] = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND google_drive_folder_id = ''"
            )
        else:
            tag = await conn.execute(
                "UPDATE clients SET google_drive_folder_id = NULL, updated_by = 'crm_quality_bot', updated_at = NOW() "
                "WHERE deleted_at IS NULL AND google_drive_folder_id = ''"
            )
            fixes["folder_id_nullified"] = int(tag.split()[-1])

        # 4. Backfill file_url from google_drive_file_url
        if dry_run:
            fixes["docs_url_backfilled"] = await conn.fetchval(
                "SELECT COUNT(*) FROM documents WHERE (file_url IS NULL OR TRIM(file_url) = '') "
                "AND google_drive_file_url IS NOT NULL AND TRIM(google_drive_file_url) != ''"
            )
        else:
            tag = await conn.execute(
                "UPDATE documents SET file_url = google_drive_file_url, updated_at = NOW() "
                "WHERE (file_url IS NULL OR TRIM(file_url) = '') "
                "AND google_drive_file_url IS NOT NULL AND TRIM(google_drive_file_url) != ''"
            )
            fixes["docs_url_backfilled"] = int(tag.split()[-1])

    return fixes


# ---------------------------------------------------------------------------
# Telegram report
# ---------------------------------------------------------------------------
def build_report(
    before: dict[str, Any],
    after: dict[str, Any],
    fixes: dict[str, int],
    *,
    dry_run: bool = False,
) -> str:
    """Build a Telegram-friendly report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode = "DRY RUN" if dry_run else "AUTO-FIX"

    lines = [
        f"📊 <b>CRM Quality Bot — {mode}</b>",
        f"🕐 {now}",
        "",
        f"👥 Clients: {before['total_clients']} | Practices: {before['total_practices']}",
        "",
        "<b>Audit Before → After:</b>",
    ]

    audit_keys = [
        ("emails_uppercase", "Emails uppercase"),
        ("emails_whitespace", "Emails whitespace"),
        ("empty_string_folder", "Empty folder_id"),
        ("nonstandard_statuses", "Bad practice status"),
        ("docs_no_file_url", "Docs missing file_url"),
        ("duplicate_emails", "Duplicate emails"),
        ("orphan_practices", "Orphan practices"),
        ("duplicate_companies", "Duplicate companies"),
    ]

    total_before = 0
    total_after = 0
    for key, label in audit_keys:
        b = before.get(key, 0)
        a = after.get(key, 0)
        total_before += b
        total_after += a
        if b > 0 or a > 0:
            emoji = "✅" if a == 0 else "⚠️"
            lines.append(f"  {emoji} {label}: {b} → {a}")

    lines.append("")
    lines.append("<b>Fixes applied:</b>")
    total_fixes = 0
    for key, cnt in fixes.items():
        if cnt > 0:
            lines.append(f"  🔧 {key}: {cnt}")
            total_fixes += cnt

    if total_fixes == 0:
        lines.append("  ✨ Nothing to fix — all clean!")

    lines.append("")
    lines.append(f"<b>Total anomalies: {total_before} → {total_after}</b>")

    # Flags for human review (non-fixable)
    flag_lines = []
    if before.get("clients_no_email", 0) > 0:
        flag_lines.append(f"  📋 {before['clients_no_email']} clients without email")
    if before.get("no_npwp_active_practices", 0) > 0:
        flag_lines.append(f"  📋 {before['no_npwp_active_practices']} without NPWP (active practices)")
    if after.get("docs_no_url_at_all", 0) > 0:
        flag_lines.append(f"  📋 {after['docs_no_url_at_all']} docs with no URL at all")

    if flag_lines:
        lines.append("")
        lines.append("<b>Flags (need human review):</b>")
        lines.extend(flag_lines)

    return "\n".join(lines)


async def send_telegram(message: str) -> bool:
    """Send message to Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notification")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram report sent")
                return True
            logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(*, audit_only: bool = False, dry_run: bool = False) -> None:
    logger.info(f"CRM Quality Bot started (audit_only={audit_only}, dry_run={dry_run})")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    try:
        # Audit BEFORE
        before = await run_audit(pool)
        logger.info(f"Audit before: {before}")

        if audit_only:
            # Just print and send report
            after = before
            fixes: dict[str, int] = {}
        else:
            # Apply fixes
            fixes = await apply_fixes(pool, dry_run=dry_run)
            logger.info(f"Fixes: {fixes}")

            # Audit AFTER
            after = await run_audit(pool)
            logger.info(f"Audit after: {after}")

        # Build and send report
        report = build_report(before, after, fixes, dry_run=dry_run)
        logger.info(f"Report:\n{report}")
        await send_telegram(report)

    finally:
        await pool.close()

    logger.info("CRM Quality Bot finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRM Data Quality Bot")
    parser.add_argument("--audit-only", action="store_true", help="Audit only, no fixes")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed")
    args = parser.parse_args()

    asyncio.run(main(audit_only=args.audit_only, dry_run=args.dry_run))
