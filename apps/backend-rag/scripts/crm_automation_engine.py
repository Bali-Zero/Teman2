#!/usr/bin/env python3
"""CRM Automation Engine — nightly full-cycle CRM automation.

Runs daily at 07:00 WITA (23:00 UTC). Executes ALL CRM automations in sequence:
  1. Data quality fixes (email normalization, status cleanup, doc URL backfill)
  2. Lead auto-assignment (round-robin to setup team)
  3. Practice required documents auto-populate
  4. Renewal/expiry alerts (90/60/30/7 days)
  5. Stale practice detection + escalation
  6. Single Telegram daily digest

Usage:
    python scripts/crm_automation_engine.py              # full run
    python scripts/crm_automation_engine.py --dry-run     # preview only
    python scripts/crm_automation_engine.py --module assignment  # single module
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone
from itertools import cycle
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
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "crm_automation.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("crm_engine")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
for h in [logging.FileHandler(LOG_FILE), logging.StreamHandler()]:
    h.setFormatter(_fmt)
    logger.addHandler(h)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Setup team for lead assignment (ordered by seniority — round-robin)
SETUP_TEAM = [
    "ari.firda@balizero.com",   # Team Leader
    "surya@balizero.com",       # Team Leader
    "krisna@balizero.com",      # Executive Consultant
    "dea@balizero.com",         # Executive Consultant
    "adit@balizero.com",        # Supervisor
    "vino@balizero.com",        # Junior Consultant
    "damar@balizero.com",       # Junior Consultant
]

STANDARD_STATUSES = {
    "inquiry", "waiting_documents", "sending_invoice",
    "on_process", "completed", "cancelled",
}

STATUS_MAP: dict[str, str] = {
    "quotation_sent": "sending_invoice",
    "payment_pending": "sending_invoice",
    "waiting_payment": "sending_invoice",
    "in_progress": "on_process",
    "submitted_to_gov": "on_process",
    "approved": "on_process",
}

# Required documents per practice type
PRACTICE_REQUIRED_DOCS: dict[str, list[dict[str, str]]] = {
    "kitas": [
        {"type": "passport_copy", "label": "Passport Copy (valid >18 months)"},
        {"type": "passport_photo", "label": "Passport-size Photo (4x6, white background)"},
        {"type": "sponsor_letter", "label": "Sponsor/Company Letter"},
        {"type": "cv", "label": "Curriculum Vitae"},
        {"type": "diploma", "label": "Degree/Diploma Certificate"},
    ],
    "kitas_application": [
        {"type": "passport_copy", "label": "Passport Copy (valid >18 months)"},
        {"type": "passport_photo", "label": "Passport-size Photo (4x6, white background)"},
        {"type": "sponsor_letter", "label": "Sponsor/Company Letter"},
        {"type": "cv", "label": "Curriculum Vitae"},
        {"type": "diploma", "label": "Degree/Diploma Certificate"},
    ],
    "extension_kitas": [
        {"type": "passport_copy", "label": "Passport Copy"},
        {"type": "current_kitas", "label": "Current KITAS Copy"},
        {"type": "passport_photo", "label": "Passport-size Photo (4x6)"},
        {"type": "sponsor_letter", "label": "Updated Sponsor Letter"},
    ],
    "kitap_application": [
        {"type": "passport_copy", "label": "Passport Copy"},
        {"type": "current_kitas", "label": "Current KITAS (5+ years proof)"},
        {"type": "passport_photo", "label": "Passport-size Photo (4x6)"},
        {"type": "sponsor_letter", "label": "Sponsor Letter"},
        {"type": "police_clearance", "label": "SKCK (Police Clearance)"},
        {"type": "domicile_letter", "label": "Domicile Letter (Surat Domisili)"},
    ],
    "visa": [
        {"type": "passport_copy", "label": "Passport Copy (valid >6 months)"},
        {"type": "passport_photo", "label": "Passport-size Photo"},
        {"type": "flight_itinerary", "label": "Flight Itinerary"},
    ],
    "extension_visa": [
        {"type": "passport_copy", "label": "Passport Copy"},
        {"type": "current_visa", "label": "Current Visa/Entry Stamp Copy"},
        {"type": "passport_photo", "label": "Passport-size Photo"},
    ],
    "pt_pma_setup": [
        {"type": "passport_copy", "label": "Director Passport Copy"},
        {"type": "shareholder_id", "label": "All Shareholders ID/Passport"},
        {"type": "domicile_letter", "label": "Domicile Letter (Surat Domisili)"},
        {"type": "company_deed", "label": "Company Deed Draft (Akta Pendirian)"},
        {"type": "npwp_director", "label": "Director NPWP"},
        {"type": "kbli_selection", "label": "KBLI Code Selection"},
        {"type": "investment_plan", "label": "Investment Plan (Rencana Investasi)"},
    ],
    "new_pt": [
        {"type": "passport_copy", "label": "Director Passport/KTP Copy"},
        {"type": "shareholder_id", "label": "All Shareholders ID"},
        {"type": "domicile_letter", "label": "Domicile Letter"},
        {"type": "company_deed", "label": "Company Deed Draft"},
        {"type": "npwp_director", "label": "Director NPWP"},
        {"type": "kbli_selection", "label": "KBLI Code Selection"},
    ],
    "revision_pt": [
        {"type": "current_deed", "label": "Current Company Deed (Akta Terakhir)"},
        {"type": "sk_menhumkam", "label": "SK Menhumkam"},
        {"type": "nib_certificate", "label": "NIB Certificate"},
        {"type": "npwp_company", "label": "Company NPWP"},
        {"type": "revision_details", "label": "Details of Changes Required"},
    ],
    "tax": [
        {"type": "npwp", "label": "NPWP Certificate"},
        {"type": "financial_records", "label": "Financial Records/Bookkeeping"},
        {"type": "bank_statements", "label": "Bank Statements (last 12 months)"},
    ],
    "tax_consulting": [
        {"type": "npwp", "label": "NPWP Certificate"},
        {"type": "financial_records", "label": "Financial Records"},
    ],
    "property_purchase": [
        {"type": "passport_copy", "label": "Buyer Passport Copy"},
        {"type": "kitas_copy", "label": "KITAS/KITAP Copy"},
        {"type": "property_certificate", "label": "Property Certificate (SHM/SHGB)"},
        {"type": "property_tax", "label": "Property Tax Receipt (PBB)"},
        {"type": "nominee_agreement", "label": "Nominee Agreement (if applicable)"},
    ],
}


# ---------------------------------------------------------------------------
# Telegram helper
# ---------------------------------------------------------------------------
async def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Telegram limit is 4096 chars — truncate if needed
    if len(message) > 4000:
        message = message[:3990] + "\n\n... (truncated)"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            if resp.status_code == 200:
                return True
            logger.error(f"Telegram error: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Telegram failed: {e}")
    return False


# ===================================================================
# MODULE 1: DATA QUALITY
# ===================================================================
async def run_data_quality(pool: asyncpg.Pool, *, dry_run: bool = False) -> dict[str, int]:
    """Normalize emails, statuses, backfill URLs."""
    fixes: dict[str, int] = {}
    async with pool.acquire() as conn:
        if dry_run:
            fixes["email_normalized"] = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND email IS NOT NULL AND (email != LOWER(email) OR email != TRIM(email))"
            )
        else:
            tag = await conn.execute(
                "UPDATE clients SET email = LOWER(TRIM(email)), updated_by = 'crm_engine', updated_at = NOW() "
                "WHERE deleted_at IS NULL AND email IS NOT NULL AND (email != LOWER(email) OR email != TRIM(email))"
            )
            fixes["email_normalized"] = int(tag.split()[-1])

        total_status = 0
        for old, new in STATUS_MAP.items():
            if dry_run:
                cnt = await conn.fetchval("SELECT COUNT(*) FROM practices WHERE status = $1", old)
            else:
                tag = await conn.execute(
                    "UPDATE practices SET status = $1, updated_by = 'crm_engine', updated_at = NOW() WHERE status = $2",
                    new, old,
                )
                cnt = int(tag.split()[-1])
            total_status += cnt
        fixes["status_normalized"] = total_status

        if dry_run:
            fixes["folder_id_nullified"] = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND google_drive_folder_id = ''"
            )
        else:
            tag = await conn.execute(
                "UPDATE clients SET google_drive_folder_id = NULL, updated_by = 'crm_engine', updated_at = NOW() "
                "WHERE deleted_at IS NULL AND google_drive_folder_id = ''"
            )
            fixes["folder_id_nullified"] = int(tag.split()[-1])

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


# ===================================================================
# MODULE 2: LEAD AUTO-ASSIGNMENT
# ===================================================================
async def run_lead_assignment(pool: asyncpg.Pool, *, dry_run: bool = False) -> dict[str, Any]:
    """Assign unassigned clients to setup team via load-balanced round-robin."""
    result: dict[str, Any] = {"assigned": 0, "distribution": {}}

    async with pool.acquire() as conn:
        # Get current workload per team member
        workloads = {}
        for email in SETUP_TEAM:
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL AND assigned_to = $1", email
            )
            workloads[email] = cnt

        # Get unassigned clients (prioritize those with practices first)
        unassigned = await conn.fetch("""
            SELECT c.id, c.full_name,
                   (SELECT COUNT(*) FROM practices p WHERE p.client_id = c.id) AS practice_count
            FROM clients c
            WHERE c.deleted_at IS NULL
            AND (c.assigned_to IS NULL OR c.assigned_to = '')
            ORDER BY
                (SELECT COUNT(*) FROM practices p WHERE p.client_id = c.id) DESC,
                c.created_at ASC
        """)

        if not unassigned:
            return result

        # Sort team by current workload (least loaded first) then cycle
        sorted_team = sorted(SETUP_TEAM, key=lambda e: workloads.get(e, 0))
        team_cycle = cycle(sorted_team)

        assignments: dict[str, int] = dict.fromkeys(SETUP_TEAM, 0)

        for row in unassigned:
            assignee = next(team_cycle)
            assignments[assignee] += 1

            if not dry_run:
                await conn.execute(
                    "UPDATE clients SET assigned_to = $1, updated_by = 'crm_engine', updated_at = NOW() WHERE id = $2",
                    assignee, row["id"],
                )

        result["assigned"] = len(unassigned)
        result["distribution"] = {k: v for k, v in assignments.items() if v > 0}

    return result


# ===================================================================
# MODULE 3: PRACTICE REQUIRED DOCUMENTS AUTO-POPULATE
# ===================================================================
async def run_doc_checklist_populate(pool: asyncpg.Pool, *, dry_run: bool = False) -> dict[str, Any]:
    """Auto-populate practice_required_documents for practices missing checklists."""
    result: dict[str, Any] = {"practices_populated": 0, "docs_created": 0}

    async with pool.acquire() as conn:
        # Find practices without required docs
        practices = await conn.fetch("""
            SELECT p.id, p.practice_type_code, p.title
            FROM practices p
            WHERE p.practice_type_code IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM practice_required_documents prd WHERE prd.practice_id = p.id
            )
        """)

        for p in practices:
            type_code = p["practice_type_code"]
            docs = PRACTICE_REQUIRED_DOCS.get(type_code, [])
            if not docs:
                continue

            result["practices_populated"] += 1

            for doc in docs:
                result["docs_created"] += 1
                if not dry_run:
                    await conn.execute("""
                        INSERT INTO practice_required_documents
                            (practice_id, document_type, document_label, is_required, status, created_by, created_at, updated_at)
                        VALUES ($1, $2, $3, true, 'pending', 'crm_engine', NOW(), NOW())
                        ON CONFLICT DO NOTHING
                    """, p["id"], doc["type"], doc["label"])

    return result


# ===================================================================
# MODULE 4: RENEWAL/EXPIRY ALERTS
# ===================================================================
async def run_renewal_alerts(pool: asyncpg.Pool, *, dry_run: bool = False) -> dict[str, Any]:
    """Scan practices for upcoming expiry, create renewal_alerts."""
    result: dict[str, Any] = {"alerts_created": 0, "by_urgency": {"critical_7d": 0, "urgent_30d": 0, "warning_60d": 0, "planning_90d": 0}}

    thresholds = [
        (7, "critical_7d", "CRITICAL: Expiring in 7 days"),
        (30, "urgent_30d", "URGENT: Expiring in 30 days"),
        (60, "warning_60d", "WARNING: Expiring in 60 days"),
        (90, "planning_90d", "PLANNING: Expiring in 90 days"),
    ]

    async with pool.acquire() as conn:
        for days, key, desc_prefix in thresholds:
            target = date.today() + timedelta(days=days)
            # Find practices expiring within this window that don't have an alert yet
            expiring = await conn.fetch("""
                SELECT p.id AS practice_id, p.client_id, p.title, p.practice_type_code,
                       p.expiry_date, c.full_name, c.email,
                       COALESCE(p.assigned_to, c.assigned_to) AS notify_to
                FROM practices p
                JOIN clients c ON c.id = p.client_id
                WHERE p.expiry_date IS NOT NULL
                AND p.expiry_date <= $1
                AND p.expiry_date >= CURRENT_DATE
                AND p.status NOT IN ('cancelled', 'completed')
                AND NOT EXISTS (
                    SELECT 1 FROM renewal_alerts ra
                    WHERE ra.practice_id = p.id
                    AND ra.alert_type = $2
                )
            """, target, key)

            for row in expiring:
                result["alerts_created"] += 1
                result["by_urgency"][key] += 1

                if not dry_run:
                    await conn.execute("""
                        INSERT INTO renewal_alerts
                            (practice_id, client_id, alert_type, description, target_date,
                             alert_date, status, notify_team_member, notify_client, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, CURRENT_DATE, 'pending', $6, true, NOW(), NOW())
                    """,
                        row["practice_id"],
                        row["client_id"],
                        key,
                        f"{desc_prefix} — {row['title'] or row['practice_type_code']} for {row['full_name']}",
                        row["expiry_date"],
                        row["notify_to"],
                    )

        # Note: passport expiry alerts skipped — renewal_alerts.practice_id is NOT NULL.
        # Passport expiry tracking handled separately via visa_expiry_team_notifier service.

    return result


# ===================================================================
# MODULE 5: STALE PRACTICE DETECTOR
# ===================================================================
async def run_stale_detector(pool: asyncpg.Pool, *, dry_run: bool = False) -> dict[str, Any]:
    """Detect practices stuck in same status too long."""
    result: dict[str, Any] = {"stale_total": 0, "details": []}

    # Thresholds per status (days)
    stale_rules = {
        "inquiry": 14,
        "pending": 14,
        "in_progress": 10,
        "active": 30,
        "on_hold": 21,
    }

    async with pool.acquire() as conn:
        for status, max_days in stale_rules.items():
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
            stale = await conn.fetch("""
                SELECT p.id, p.title, p.practice_type_code, p.status, p.updated_at,
                       c.full_name, COALESCE(p.assigned_to, c.assigned_to) AS owner
                FROM practices p
                JOIN clients c ON c.id = p.client_id
                WHERE p.status = $1
                AND p.updated_at < $2
                AND p.status NOT IN ('completed', 'cancelled', 'expired', 'renewed')
            """, status, cutoff)

            for row in stale:
                days_stuck = (datetime.now(timezone.utc) - row["updated_at"].replace(tzinfo=timezone.utc)).days
                result["stale_total"] += 1
                result["details"].append({
                    "id": row["id"],
                    "title": row["title"] or row["practice_type_code"] or "N/A",
                    "client": row["full_name"],
                    "status": row["status"],
                    "days_stuck": days_stuck,
                    "owner": row["owner"] or "UNASSIGNED",
                })

    # Sort by days_stuck descending
    result["details"].sort(key=lambda x: x["days_stuck"], reverse=True)
    return result


# ===================================================================
# DIGEST BUILDER
# ===================================================================
def build_digest(
    quality: dict[str, int],
    assignment: dict[str, Any],
    docs: dict[str, Any],
    renewals: dict[str, Any],
    stale: dict[str, Any],
    *,
    dry_run: bool = False,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode = "DRY RUN" if dry_run else "LIVE"
    lines = [
        f"<b>CRM Automation Engine — {mode}</b>",
        f"🕐 {now}",
        "",
    ]

    # 1. Quality
    total_quality = sum(quality.values())
    if total_quality > 0:
        lines.append(f"<b>1. Data Quality:</b> {total_quality} fixes")
        for k, v in quality.items():
            if v > 0:
                lines.append(f"   {k}: {v}")
    else:
        lines.append("<b>1. Data Quality:</b> clean ✅")

    # 2. Assignment
    lines.append("")
    if assignment["assigned"] > 0:
        lines.append(f"<b>2. Lead Assignment:</b> {assignment['assigned']} leads assigned")
        for email, cnt in sorted(assignment["distribution"].items(), key=lambda x: -x[1]):
            name = email.split("@")[0]
            lines.append(f"   {name}: +{cnt}")
    else:
        lines.append("<b>2. Lead Assignment:</b> all assigned ✅")

    # 3. Docs
    lines.append("")
    if docs["docs_created"] > 0:
        lines.append(f"<b>3. Doc Checklists:</b> {docs['practices_populated']} practices, {docs['docs_created']} docs")
    else:
        lines.append("<b>3. Doc Checklists:</b> all populated ✅")

    # 4. Renewals
    lines.append("")
    if renewals["alerts_created"] > 0:
        lines.append(f"<b>4. Renewal Alerts:</b> {renewals['alerts_created']} new")
        for k, v in renewals["by_urgency"].items():
            if v > 0:
                emoji = {"critical_7d": "🔴", "urgent_30d": "🟠", "warning_60d": "🟡", "planning_90d": "🔵"}.get(k, "⚪")
                lines.append(f"   {emoji} {k}: {v}")
    else:
        lines.append("<b>4. Renewal Alerts:</b> none due ✅")

    # 5. Stale
    lines.append("")
    if stale["stale_total"] > 0:
        lines.append(f"<b>5. Stale Practices:</b> {stale['stale_total']} stuck")
        for d in stale["details"][:8]:  # top 8
            lines.append(f"   ⚠️ #{d['id']} {d['title'][:25]} — {d['status']} {d['days_stuck']}d ({d['owner'].split('@')[0]})")
    else:
        lines.append("<b>5. Stale Practices:</b> none ✅")

    return "\n".join(lines)


# ===================================================================
# MAIN
# ===================================================================
async def main(*, dry_run: bool = False, module: str | None = None) -> None:
    logger.info(f"CRM Automation Engine started (dry_run={dry_run}, module={module})")

    # Retry pool creation — Fly.io PG cold start can cause ConnectionResetError
    pool = None
    for attempt in range(1, 4):
        try:
            pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            break
        except (ConnectionResetError, OSError, asyncpg.PostgresError) as exc:
            logger.warning(f"DB connect attempt {attempt}/3 failed: {exc}")
            if attempt < 3:
                await asyncio.sleep(10 * attempt)
            else:
                raise
    try:
        modules_to_run = [module] if module else ["quality", "docs", "renewals", "stale"]

        quality: dict[str, int] = {}
        assignment: dict[str, Any] = {"assigned": 0, "distribution": {}}
        docs: dict[str, Any] = {"practices_populated": 0, "docs_created": 0}
        renewals: dict[str, Any] = {"alerts_created": 0, "by_urgency": {}}
        stale_result: dict[str, Any] = {"stale_total": 0, "details": []}

        if "quality" in modules_to_run:
            logger.info("Running: data quality...")
            quality = await run_data_quality(pool, dry_run=dry_run)
            logger.info(f"Quality: {quality}")

        if "assignment" in modules_to_run:
            logger.info("Running: lead assignment...")
            assignment = await run_lead_assignment(pool, dry_run=dry_run)
            logger.info(f"Assignment: {assignment['assigned']} leads")

        if "docs" in modules_to_run:
            logger.info("Running: doc checklist populate...")
            docs = await run_doc_checklist_populate(pool, dry_run=dry_run)
            logger.info(f"Docs: {docs['practices_populated']} practices, {docs['docs_created']} docs")

        if "renewals" in modules_to_run:
            logger.info("Running: renewal alerts...")
            renewals = await run_renewal_alerts(pool, dry_run=dry_run)
            logger.info(f"Renewals: {renewals['alerts_created']} alerts")

        if "stale" in modules_to_run:
            logger.info("Running: stale detector...")
            stale_result = await run_stale_detector(pool, dry_run=dry_run)
            logger.info(f"Stale: {stale_result['stale_total']} practices")

        # Build and send digest
        digest = build_digest(quality, assignment, docs, renewals, stale_result, dry_run=dry_run)
        logger.info(f"Digest:\n{digest}")
        await send_telegram(digest)

    finally:
        await pool.close()

    logger.info("CRM Automation Engine finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRM Automation Engine")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes")
    parser.add_argument("--module", choices=["quality", "assignment", "docs", "renewals", "stale"], help="Run single module")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, module=args.module))
