"""
CRM Data Cleanup Script
========================
Cleans dirty CRM data polluting dashboards:
  1. Archives stale clients (inactive + all docs expired before 2024 + no active practices)
  2. Flags test data (Mickey Mouse id=10890, other suspicious names)
  3. Fixes assigned_to anomalies (company_extract_import → NULL, unknown emails reported)
  4. Summary report

Run:
    cd apps/backend-rag
    source .venv/bin/activate

    # Dry run (default — no changes):
    PYTHONPATH=. python3 scripts/crm_data_cleanup.py

    # Execute changes:
    PYTHONPATH=. python3 scripts/crm_data_cleanup.py --execute

Requires: fly proxy 15432 -a nuzantara-postgres (in separate terminal)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_db_env: str | None = os.getenv("DATABASE_URL")
if not _db_env:
    print("ERROR: DATABASE_URL environment variable is required.", file=sys.stderr)
    sys.exit(1)
DB: str = _db_env.replace("postgres://", "postgresql://") if _db_env.startswith("postgres://") else _db_env

VALID_TEAM_EMAILS: set[str] = {
    "ari.firda@balizero.com",
    "vino@balizero.com",
    "krisna@balizero.com",
    "surya@balizero.com",
    "adit@balizero.com",
    "sahira@balizero.com",
    "damar@balizero.com",
    "ruslana@balizero.com",
    "zero@balizero.com",
}

TAG_ARCHIVED_STALE = "archived_stale_2026-04"
TAG_TEST_DATA = "test_data"


async def _safe_append_tag(
    conn: asyncpg.Connection,
    client_id: int,
    tag: str,
    *,
    dry_run: bool,
) -> list[str]:
    """Read current tags, append new tag if missing, write back. Returns updated tags list."""
    row = await conn.fetchrow("SELECT tags FROM clients WHERE id = $1", client_id)
    current_tags: list[str] = []
    if row and row["tags"]:
        raw = row["tags"]
        if isinstance(raw, str):
            try:
                current_tags = json.loads(raw)
            except json.JSONDecodeError:
                current_tags = []
        elif isinstance(raw, list):
            current_tags = list(raw)

    if tag in current_tags:
        return current_tags

    current_tags.append(tag)

    if not dry_run:
        await conn.execute(
            "UPDATE clients SET tags = $1::jsonb, updated_at = NOW() WHERE id = $2",
            json.dumps(current_tags),
            client_id,
        )
    return current_tags


async def task_archive_stale(
    conn: asyncpg.Connection,
    *,
    dry_run: bool,
) -> int:
    """Task 1: Archive stale clients — inactive, all docs expired before 2024, no active practices."""
    logger.info("=" * 60)
    logger.info("TASK 1: Archive stale records")
    logger.info("=" * 60)

    # Find inactive clients whose MOST RECENT document expiry is before 2024-01-01
    # AND who have NO practices in non-terminal status
    rows = await conn.fetch(
        """
        SELECT
            c.id,
            c.full_name,
            MAX(d.expiry_date) AS latest_expiry
        FROM clients c
        JOIN documents d ON d.client_id = c.id AND d.expiry_date IS NOT NULL
        WHERE c.status = 'inactive'
          AND NOT EXISTS (
              SELECT 1 FROM practices p
              WHERE p.client_id = c.id
                AND p.status NOT IN ('completed', 'cancelled')
          )
        GROUP BY c.id, c.full_name
        HAVING MAX(d.expiry_date) < '2024-01-01'::date
        ORDER BY MAX(d.expiry_date) ASC
        """
    )

    count = 0
    for row in rows:
        client_id: int = row["id"]
        name: str = row["full_name"]
        latest_expiry: datetime = row["latest_expiry"]

        prefix = "[DRY-RUN] " if dry_run else ""
        logger.info(
            "%s[ARCHIVE] Client %d %s: last doc expired %s",
            prefix,
            client_id,
            name,
            latest_expiry.strftime("%Y-%m-%d") if latest_expiry else "unknown",
        )

        await _safe_append_tag(conn, client_id, TAG_ARCHIVED_STALE, dry_run=dry_run)
        count += 1

    logger.info("Task 1 result: %d clients %s", count, "would be archived" if dry_run else "archived")
    return count


async def task_flag_test_data(
    conn: asyncpg.Connection,
    *,
    dry_run: bool,
) -> int:
    """Task 2: Flag test data. Auto-fix Mickey Mouse (id=10890), report other suspicious names."""
    logger.info("=" * 60)
    logger.info("TASK 2: Flag test data")
    logger.info("=" * 60)

    count = 0

    # --- Mickey Mouse (known test record) ---
    mickey = await conn.fetchrow("SELECT id, full_name, status, tags FROM clients WHERE id = 10890")
    if mickey:
        prefix = "[DRY-RUN] " if dry_run else ""
        logger.info(
            "%s[TEST-FLAG] Client %d '%s': setting status=inactive, adding tag '%s'",
            prefix,
            mickey["id"],
            mickey["full_name"],
            TAG_TEST_DATA,
        )
        if not dry_run:
            await conn.execute(
                "UPDATE clients SET status = 'inactive', updated_at = NOW() WHERE id = 10890",
            )
        await _safe_append_tag(conn, 10890, TAG_TEST_DATA, dry_run=dry_run)
        count += 1
    else:
        logger.info("Client id=10890 (Mickey Mouse) not found — skipping")

    # --- Search for other suspicious names ---
    suspects = await conn.fetch(
        """
        SELECT id, full_name, status, email
        FROM clients
        WHERE (full_name ILIKE '%%test%%client%%' OR full_name = 'Test')
          AND id != 10890
        ORDER BY id
        """
    )
    if suspects:
        logger.info("Found %d additional suspicious test-like clients (report only, no auto-fix):", len(suspects))
        for s in suspects:
            logger.info(
                "  [SUSPECT] Client %d '%s' (status=%s, email=%s)",
                s["id"],
                s["full_name"],
                s["status"],
                s["email"] or "NULL",
            )
    else:
        logger.info("No additional suspicious test-like clients found")

    logger.info("Task 2 result: %d test records %s", count, "would be flagged" if dry_run else "flagged")
    return count


async def task_fix_assigned_to(
    conn: asyncpg.Connection,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    """Task 3: Fix assigned_to anomalies. Returns (fixed_count, anomaly_count)."""
    logger.info("=" * 60)
    logger.info("TASK 3: Fix assigned_to anomalies")
    logger.info("=" * 60)

    fixed = 0
    anomalies = 0

    # --- company_extract_import → NULL ---
    cei_rows = await conn.fetch(
        "SELECT id, full_name FROM clients WHERE assigned_to = 'company_extract_import'"
    )
    if cei_rows:
        prefix = "[DRY-RUN] " if dry_run else ""
        for r in cei_rows:
            logger.info(
                "%s[FIX-ASSIGN] Client %d '%s': assigned_to='company_extract_import' → NULL",
                prefix,
                r["id"],
                r["full_name"],
            )
        if not dry_run:
            await conn.execute(
                "UPDATE clients SET assigned_to = NULL, updated_at = NOW() WHERE assigned_to = 'company_extract_import'"
            )
        fixed = len(cei_rows)
        logger.info(
            "%d clients %s (company_extract_import → NULL)",
            fixed,
            "would be fixed" if dry_run else "fixed",
        )
    else:
        logger.info("No clients with assigned_to='company_extract_import' found")

    # --- Report unknown assigned_to values ---
    # Build a parameterized query with the valid emails
    valid_list = list(VALID_TEAM_EMAILS)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(valid_list)))
    anomaly_rows = await conn.fetch(
        f"""
        SELECT assigned_to, COUNT(*) AS cnt
        FROM clients
        WHERE assigned_to IS NOT NULL
          AND assigned_to != ''
          AND assigned_to != 'company_extract_import'
          AND assigned_to NOT IN ({placeholders})
        GROUP BY assigned_to
        ORDER BY cnt DESC
        """,
        *valid_list,
    )
    if anomaly_rows:
        logger.info("Found %d unknown assigned_to values (report only, no auto-fix):", len(anomaly_rows))
        for a in anomaly_rows:
            logger.info("  [ANOMALY] assigned_to='%s' (%d clients)", a["assigned_to"], a["cnt"])
            anomalies += a["cnt"]
    else:
        logger.info("No unknown assigned_to values found — all assignments are valid team emails")

    logger.info(
        "Task 3 result: %d fixed, %d anomalies reported",
        fixed,
        anomalies,
    )
    return fixed, anomalies


async def main(dry_run: bool) -> None:
    """Main entry point — connects to DB, runs all tasks in a transaction, prints summary."""
    mode = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("=" * 60)
    logger.info("CRM Data Cleanup — %s mode", mode)
    logger.info("=" * 60)

    conn: asyncpg.Connection = await asyncpg.connect(DB)
    logger.info("Connected to database")

    try:
        tr = conn.transaction()
        await tr.start()

        archived = await task_archive_stale(conn, dry_run=dry_run)
        flagged = await task_flag_test_data(conn, dry_run=dry_run)
        assigned_fixed, anomalies_found = await task_fix_assigned_to(conn, dry_run=dry_run)

        if dry_run:
            await tr.rollback()
            logger.info("Transaction rolled back (dry-run mode)")
        else:
            await tr.commit()
            logger.info("Transaction committed")

        # --- Summary ---
        logger.info("=" * 60)
        logger.info("SUMMARY (%s)", mode)
        logger.info("=" * 60)
        logger.info("  Archived (stale):       %d", archived)
        logger.info("  Flagged (test data):    %d", flagged)
        logger.info("  Assigned_to fixed:      %d", assigned_fixed)
        logger.info("  Assigned_to anomalies:  %d", anomalies_found)
        logger.info("=" * 60)

        if dry_run:
            logger.info("No changes were made. Re-run with --execute to apply.")

    finally:
        await conn.close()
        logger.info("Database connection closed")


def cli() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="CRM Data Cleanup — archive stale records, flag test data, fix assigned_to",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually apply changes (default is dry-run)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = cli()
    if args.execute:
        confirm = input(
            "\n⚠️  EXECUTE MODE — this will modify the production database.\n"
            "   Type YES to proceed: "
        )
        if confirm.strip() != "YES":
            logger.info("Aborted by user.")
            sys.exit(0)
    asyncio.run(main(dry_run=not args.execute))
