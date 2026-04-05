#!/usr/bin/env python3
"""CRM Data Cleanup — normalizza e sanifica i dati del CRM.

Operazioni:
  1. Normalizza email (lowercase, strip whitespace)
  2. Normalizza phone (strip spazi/trattini, formato +62)
  3. Normalizza status clienti (mappa valori non-standard)
  4. Normalizza status practices
  5. Backfill last_interaction_date mancante da practices
  6. Deduplica tags (rimuove duplicati JSON)
  7. Report finale con conteggi

Usage:
    python scripts/crm_data_cleanup.py --dry-run    # preview only, no writes
    python scripts/crm_data_cleanup.py              # full run
    python scripts/crm_data_cleanup.py --module email  # solo email normalization
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "crm_data_cleanup.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("crm_cleanup")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
for _h in [logging.FileHandler(LOG_FILE), logging.StreamHandler()]:
    _h.setFormatter(_fmt)
    logger.addHandler(_h)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VALID_CLIENT_STATUSES = {
    "active", "inactive", "prospect", "completed", "cancelled",
    "pending", "inquiry", "in_progress", "on_hold", "expired",
    "pending_renewal", "expiring_soon", "renewed",
}

CLIENT_STATUS_MAP: dict[str, str] = {
    "on_process": "in_progress",
    "sending_invoice": "pending",
    "quotation_sent": "pending",
    "approved": "active",
    "submitted_to_gov": "in_progress",
    "waiting_documents": "pending",
    "new": "prospect",
    "lead": "prospect",
    "churned": "inactive",
    "closed": "inactive",
}

VALID_PRACTICE_STATUSES = {
    "inquiry", "waiting_documents", "sending_invoice", "on_process",
    "completed", "expiring_soon", "expired", "pending_renewal",
    "pending", "in_progress", "cancelled",
}

PRACTICE_STATUS_MAP: dict[str, str] = {
    "new": "inquiry",
    "open": "inquiry",
    "active": "on_process",
    "processing": "on_process",
    "done": "completed",
    "closed": "completed",
    "renewed": "pending_renewal",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_phone(phone: str | None) -> str | None:
    """Normalizza numero di telefono: strip spazi/trattini, gestisce +62."""
    if not phone:
        return phone
    cleaned = re.sub(r"[\s\-\(\)\.]", "", phone.strip())
    # Converti 08xx → +628xx (Indonesia)
    if cleaned.startswith("08") and len(cleaned) >= 9:
        cleaned = "+62" + cleaned[1:]
    # Converti 628xx → +628xx
    elif cleaned.startswith("628") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned if cleaned else phone


def deduplicate_tags(tags_json: Any) -> list[str]:
    """Rimuove tag duplicati da campo JSON."""
    if not tags_json:
        return []
    try:
        if isinstance(tags_json, str):
            tags = json.loads(tags_json)
        else:
            tags = tags_json
        if not isinstance(tags, list):
            return []
        seen: set[str] = set()
        result: list[str] = []
        for tag in tags:
            if isinstance(tag, str):
                normalized = tag.strip().lower()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    result.append(tag.strip())
        return result
    except (json.JSONDecodeError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Cleanup modules
# ---------------------------------------------------------------------------
async def cleanup_emails(conn: asyncpg.Connection, dry_run: bool) -> dict[str, int]:
    """Normalizza email: lowercase + strip."""
    rows = await conn.fetch(
        "SELECT id, email FROM clients WHERE email IS NOT NULL AND email != '' AND deleted_at IS NULL"
    )
    fixed = 0
    for row in rows:
        normalized = row["email"].strip().lower()
        if normalized != row["email"]:
            if not dry_run:
                await conn.execute(
                    "UPDATE clients SET email = $1, updated_at = NOW() WHERE id = $2",
                    normalized, row["id"],
                )
            fixed += 1
            logger.debug(f"  email fix: id={row['id']} '{row['email']}' → '{normalized}'")

    logger.info(f"[email] {fixed}/{len(rows)} records fixed (dry_run={dry_run})")
    return {"checked": len(rows), "fixed": fixed}


async def cleanup_phones(conn: asyncpg.Connection, dry_run: bool) -> dict[str, int]:
    """Normalizza telefoni (phone + whatsapp)."""
    rows = await conn.fetch(
        "SELECT id, phone, whatsapp FROM clients WHERE deleted_at IS NULL"
    )
    fixed = 0
    for row in rows:
        updates: dict[str, str] = {}
        for field in ("phone", "whatsapp"):
            original = row[field]
            if original:
                normalized = normalize_phone(original)
                if normalized != original:
                    updates[field] = normalized  # type: ignore[assignment]

        if updates:
            if not dry_run:
                set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
                values = [row["id"]] + list(updates.values())
                await conn.execute(
                    f"UPDATE clients SET {set_clause}, updated_at = NOW() WHERE id = $1",
                    *values,
                )
            fixed += 1
            logger.debug(f"  phone fix: id={row['id']} {updates}")

    logger.info(f"[phone] {fixed}/{len(rows)} records fixed (dry_run={dry_run})")
    return {"checked": len(rows), "fixed": fixed}


async def cleanup_client_statuses(conn: asyncpg.Connection, dry_run: bool) -> dict[str, int]:
    """Mappa status non-standard a valori canonici."""
    rows = await conn.fetch(
        "SELECT id, status FROM clients WHERE deleted_at IS NULL AND status IS NOT NULL"
    )
    fixed = 0
    unknown: list[str] = []
    for row in rows:
        status = row["status"]
        if status in VALID_CLIENT_STATUSES:
            continue
        mapped = CLIENT_STATUS_MAP.get(status)
        if mapped:
            if not dry_run:
                await conn.execute(
                    "UPDATE clients SET status = $1, updated_at = NOW() WHERE id = $2",
                    mapped, row["id"],
                )
            fixed += 1
            logger.debug(f"  client status: id={row['id']} '{status}' → '{mapped}'")
        else:
            if status not in unknown:
                unknown.append(status)

    if unknown:
        logger.warning(f"[client_status] Unknown statuses (not mapped): {unknown}")
    logger.info(f"[client_status] {fixed}/{len(rows)} records fixed (dry_run={dry_run})")
    return {"checked": len(rows), "fixed": fixed, "unknown": len(unknown)}


async def cleanup_practice_statuses(conn: asyncpg.Connection, dry_run: bool) -> dict[str, int]:
    """Mappa status practices non-standard."""
    rows = await conn.fetch(
        "SELECT id, status FROM practices WHERE status IS NOT NULL"
    )
    fixed = 0
    unknown: list[str] = []
    for row in rows:
        status = row["status"]
        if status in VALID_PRACTICE_STATUSES:
            continue
        mapped = PRACTICE_STATUS_MAP.get(status)
        if mapped:
            if not dry_run:
                await conn.execute(
                    "UPDATE practices SET status = $1, updated_at = NOW() WHERE id = $2",
                    mapped, row["id"],
                )
            fixed += 1
            logger.debug(f"  practice status: id={row['id']} '{status}' → '{mapped}'")
        else:
            if status not in unknown:
                unknown.append(status)

    if unknown:
        logger.warning(f"[practice_status] Unknown statuses (not mapped): {unknown}")
    logger.info(f"[practice_status] {fixed}/{len(rows)} records fixed (dry_run={dry_run})")
    return {"checked": len(rows), "fixed": fixed, "unknown": len(unknown)}


async def backfill_last_interaction(conn: asyncpg.Connection, dry_run: bool) -> dict[str, int]:
    """Backfill last_interaction_date da practices recenti."""
    rows = await conn.fetch(
        """
        SELECT c.id, MAX(p.updated_at) AS last_practice_update
        FROM clients c
        JOIN practices p ON p.client_id = c.id
        WHERE c.last_interaction_date IS NULL
          AND c.deleted_at IS NULL
        GROUP BY c.id
        HAVING MAX(p.updated_at) IS NOT NULL
        """
    )
    fixed = 0
    for row in rows:
        if not dry_run:
            await conn.execute(
                "UPDATE clients SET last_interaction_date = $1, updated_at = NOW() WHERE id = $2",
                row["last_practice_update"], row["id"],
            )
        fixed += 1
        logger.debug(f"  backfill: id={row['id']} last_interaction → {row['last_practice_update']}")

    logger.info(f"[last_interaction] {fixed} records backfilled (dry_run={dry_run})")
    return {"backfilled": fixed}


async def dedup_tags(conn: asyncpg.Connection, dry_run: bool) -> dict[str, int]:
    """Rimuove tag duplicati dal campo JSON tags."""
    rows = await conn.fetch(
        "SELECT id, tags FROM clients WHERE tags IS NOT NULL AND deleted_at IS NULL"
    )
    fixed = 0
    for row in rows:
        original_tags = row["tags"]
        deduped = deduplicate_tags(original_tags)
        original_list = original_tags if isinstance(original_tags, list) else []
        if len(deduped) != len(original_list) or deduped != original_list:
            if not dry_run:
                await conn.execute(
                    "UPDATE clients SET tags = $1::jsonb, updated_at = NOW() WHERE id = $2",
                    json.dumps(deduped), row["id"],
                )
            fixed += 1
            logger.debug(f"  tags dedup: id={row['id']} {len(original_list)} → {len(deduped)} tags")

    logger.info(f"[tags] {fixed}/{len(rows)} records deduped (dry_run={dry_run})")
    return {"checked": len(rows), "fixed": fixed}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
async def get_crm_stats(conn: asyncpg.Connection) -> dict[str, Any]:
    """Conta record per categoria per il report iniziale."""
    total_clients = await conn.fetchval("SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL")
    total_practices = await conn.fetchval("SELECT COUNT(*) FROM practices")
    clients_no_email = await conn.fetchval(
        "SELECT COUNT(*) FROM clients WHERE (email IS NULL OR email = '') AND deleted_at IS NULL"
    )
    clients_no_phone = await conn.fetchval(
        "SELECT COUNT(*) FROM clients WHERE (phone IS NULL OR phone = '') AND deleted_at IS NULL"
    )
    clients_no_assignment = await conn.fetchval(
        "SELECT COUNT(*) FROM clients WHERE (assigned_to IS NULL OR assigned_to = '') AND deleted_at IS NULL"
    )
    clients_no_interaction = await conn.fetchval(
        "SELECT COUNT(*) FROM clients WHERE last_interaction_date IS NULL AND deleted_at IS NULL"
    )
    invalid_client_statuses = await conn.fetchval(
        f"SELECT COUNT(*) FROM clients WHERE status NOT IN ({','.join(['$' + str(i + 1) for i in range(len(VALID_CLIENT_STATUSES))])}) AND deleted_at IS NULL",
        *VALID_CLIENT_STATUSES,
    )
    return {
        "total_clients": total_clients,
        "total_practices": total_practices,
        "clients_no_email": clients_no_email,
        "clients_no_phone": clients_no_phone,
        "clients_no_assignment": clients_no_assignment,
        "clients_no_interaction": clients_no_interaction,
        "invalid_client_statuses": invalid_client_statuses,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
MODULES = {
    "email": cleanup_emails,
    "phone": cleanup_phones,
    "client_status": cleanup_client_statuses,
    "practice_status": cleanup_practice_statuses,
    "last_interaction": backfill_last_interaction,
    "tags": dedup_tags,
}


async def main(dry_run: bool, module: str | None) -> None:
    logger.info("=" * 60)
    logger.info(f"CRM Data Cleanup — {'DRY RUN' if dry_run else 'LIVE RUN'} — {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stats = await get_crm_stats(conn)
        logger.info("📊 CRM Status before cleanup:")
        for k, v in stats.items():
            logger.info(f"   {k}: {v}")

        results: dict[str, Any] = {}

        if module:
            if module not in MODULES:
                logger.error(f"Unknown module '{module}'. Valid: {list(MODULES.keys())}")
                sys.exit(1)
            results[module] = await MODULES[module](conn, dry_run)
        else:
            for name, fn in MODULES.items():
                logger.info(f"\n▶ Running module: {name}")
                results[name] = await fn(conn, dry_run)

        logger.info("\n" + "=" * 60)
        logger.info("✅ Cleanup complete. Summary:")
        for mod, res in results.items():
            logger.info(f"   {mod}: {res}")
        if dry_run:
            logger.info("\n⚠️  DRY RUN — No changes written to DB. Re-run without --dry-run to apply.")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRM Data Cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    parser.add_argument("--module", choices=list(MODULES.keys()), help="Run single module only")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, module=args.module))
