#!/usr/bin/env python3
"""B1 CRM Data Quality Cleanup — idempotent, safe to re-run.

Executed 2026-04-05. This script documents and can replay the B1 cleanup:
  1. NULLIF empty strings → NULL (phone, whatsapp, address, nationality, passport_number, notes)
  2. Normalize tags (NULL → empty array)
  3. Dedup known duplicates (soft-delete inferior record, merge practices)
  4. Backfill last_interaction_date from practices
  5. Round-robin assignment of unassigned clients

Usage:
    python scripts/crm_b1_data_quality.py --dry-run   # preview
    python scripts/crm_b1_data_quality.py              # execute
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timezone
from itertools import cycle
from pathlib import Path

import asyncpg

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("crm_b1")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
for _h in [logging.FileHandler(LOG_DIR / "crm_b1_data_quality.log"), logging.StreamHandler()]:
    _h.setFormatter(_fmt)
    logger.addHandler(_h)

SETUP_TEAM = [
    "ari.firda@balizero.com",
    "surya@balizero.com",
    "krisna@balizero.com",
    "dea@balizero.com",
    "sahira@balizero.com",
    "adit@balizero.com",
    "vino@balizero.com",
    "damar@balizero.com",
]

NULLIF_FIELDS = ["phone", "whatsapp", "address", "nationality", "passport_number", "notes"]

# Known duplicates: (id_to_delete, id_to_keep, reason, merge_practices)
DEDUP_LIST = [
    (11397, 11394, "Alexandra Natalia Maria Bob — inactive dup", False),
    (11393, 11396, "Catalin Iulius Rojisteanu �� inactive dup", False),
    (1824, 11390, "Christian Fixl — old inactive, new has 3 prax", False),
    (7441, 10550, "Anna Fishchenko/Fischenko — typo dup", False),
    (11386, 10825, "Olha Pavlova — merge practices to active", True),
    (10573, 9507, "Marine Gralepois — merge practices to active", True),
]


async def step1_nullif(conn: asyncpg.Connection, dry_run: bool) -> int:
    """Convert empty strings to NULL for specified fields."""
    total = 0
    for field in NULLIF_FIELDS:
        count = await conn.fetchval(
            f"SELECT COUNT(*) FROM clients WHERE {field} = '' AND deleted_at IS NULL"
        )
        if count > 0:
            if not dry_run:
                await conn.execute(
                    f"UPDATE clients SET {field} = NULLIF({field}, ''), updated_at = NOW() "
                    f"WHERE {field} = '' AND deleted_at IS NULL"
                )
            logger.info(f"  [nullif] {field}: {count} rows {'fixed' if not dry_run else 'to fix'}")
            total += count
        else:
            logger.info(f"  [nullif] {field}: 0 empty strings")
    return total


async def step2_tags(conn: asyncpg.Connection, dry_run: bool) -> int:
    """Normalize NULL tags to empty array."""
    count = await conn.fetchval("SELECT COUNT(*) FROM clients WHERE tags IS NULL AND deleted_at IS NULL")
    if count > 0 and not dry_run:
        await conn.execute(
            "UPDATE clients SET tags = '{}', updated_at = NOW() WHERE tags IS NULL AND deleted_at IS NULL"
        )
    logger.info(f"  [tags] NULL → empty array: {count} rows")
    return count


async def step3_dedup(conn: asyncpg.Connection, dry_run: bool) -> int:
    """Soft-delete known duplicates, merge practices where needed."""
    deleted = 0
    for del_id, keep_id, reason, merge in DEDUP_LIST:
        row = await conn.fetchrow("SELECT id, deleted_at FROM clients WHERE id = $1", del_id)
        if not row or row["deleted_at"] is not None:
            logger.info(f"  [dedup] SKIP id={del_id}: already deleted — {reason}")
            continue

        if merge:
            prax_count = await conn.fetchval(
                "SELECT COUNT(*) FROM practices WHERE client_id = $1", del_id
            )
            if prax_count > 0 and not dry_run:
                await conn.execute(
                    "UPDATE practices SET client_id = $1, updated_at = NOW() WHERE client_id = $2",
                    keep_id, del_id,
                )
            logger.info(f"  [dedup] MERGE {prax_count} practices {del_id} → {keep_id}")

        if not dry_run:
            await conn.execute(
                "UPDATE clients SET deleted_at = NOW(), deleted_by = 'dedup_b1_cleanup', "
                "updated_at = NOW() WHERE id = $1",
                del_id,
            )
        logger.info(f"  [dedup] DELETE id={del_id}: {reason}")
        deleted += 1
    return deleted


async def step4_backfill_interaction(conn: asyncpg.Connection, dry_run: bool) -> int:
    """Backfill last_interaction_date from practices."""
    rows = await conn.fetch(
        """
        SELECT c.id, MAX(p.updated_at) AS last_update
        FROM clients c JOIN practices p ON p.client_id = c.id
        WHERE c.last_interaction_date IS NULL AND c.deleted_at IS NULL
        GROUP BY c.id HAVING MAX(p.updated_at) IS NOT NULL
        """
    )
    if rows and not dry_run:
        for row in rows:
            await conn.execute(
                "UPDATE clients SET last_interaction_date = $1, updated_at = NOW() WHERE id = $2",
                row["last_update"], row["id"],
            )
    logger.info(f"  [backfill] {len(rows)} last_interaction_date records")
    return len(rows)


async def step5_assign(conn: asyncpg.Connection, dry_run: bool) -> int:
    """Round-robin assign unassigned clients."""
    unassigned = await conn.fetch(
        """
        SELECT id, full_name FROM clients
        WHERE (assigned_to IS NULL OR assigned_to = '') AND deleted_at IS NULL
        ORDER BY created_at DESC
        """
    )
    if not unassigned:
        logger.info("  [assign] 0 unassigned clients")
        return 0

    workload = {}
    rows = await conn.fetch(
        "SELECT assigned_to, COUNT(*) as cnt FROM clients "
        "WHERE assigned_to IS NOT NULL AND assigned_to != '' AND deleted_at IS NULL "
        "GROUP BY assigned_to"
    )
    for r in rows:
        workload[r["assigned_to"]] = r["cnt"]

    team_sorted = sorted(SETUP_TEAM, key=lambda e: workload.get(e, 0))
    team_cycle = cycle(team_sorted)

    assigned = 0
    for client in unassigned:
        assignee = next(team_cycle)
        if not dry_run:
            await conn.execute(
                "UPDATE clients SET assigned_to = $1, updated_at = NOW() WHERE id = $2",
                assignee, client["id"],
            )
        assigned += 1

    logger.info(f"  [assign] {assigned} clients assigned round-robin to {len(SETUP_TEAM)} members")
    return assigned


async def main(dry_run: bool) -> None:
    label = "DRY RUN" if dry_run else "LIVE"
    logger.info(f"{'=' * 60}")
    logger.info(f"B1 CRM Data Quality — {label} — {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"{'=' * 60}")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        total_before = await conn.fetchval("SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL")
        logger.info(f"Active clients before: {total_before}")

        async with conn.transaction():
            s1 = await step1_nullif(conn, dry_run)
            s2 = await step2_tags(conn, dry_run)
            s3 = await step3_dedup(conn, dry_run)
            s4 = await step4_backfill_interaction(conn, dry_run)
            s5 = await step5_assign(conn, dry_run)

        total_after = await conn.fetchval("SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL")
        unassigned = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE assigned_to IS NULL AND deleted_at IS NULL"
        )

        logger.info(f"\n{'=' * 60}")
        logger.info(f"SUMMARY ({label}):")
        logger.info(f"  NULLIF empty strings: {s1}")
        logger.info(f"  Tags normalized:      {s2}")
        logger.info(f"  Duplicates removed:   {s3}")
        logger.info(f"  Interaction backfill: {s4}")
        logger.info(f"  Clients assigned:     {s5}")
        logger.info(f"  Active clients:       {total_before} → {total_after}")
        logger.info(f"  Unassigned remaining: {unassigned}")

        if dry_run:
            logger.info("\nDRY RUN — no changes written. Re-run without --dry-run to apply.")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B1 CRM Data Quality Cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
