#!/usr/bin/env python3
"""Assign Unassigned Clients — Inverse-Load Weighted Round-Robin.

Finds clients with no assigned team member and distributes them
using inverse-load weighting: the member with the fewest current
clients gets the next assignment.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate

    # Preview assignments (default: dry-run)
    PYTHONPATH=. python scripts/assign_unassigned_clients.py

    # Actually update the database
    PYTHONPATH=. python scripts/assign_unassigned_clients.py --execute

    # Limit how many clients to assign
    PYTHONPATH=. python scripts/assign_unassigned_clients.py --execute --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_db_raw: str | None = os.environ.get("DATABASE_URL")
if not _db_raw:
    print("ERROR: DATABASE_URL environment variable is required.", file=sys.stderr)
    sys.exit(1)
DATABASE_URL: str = _db_raw.replace("postgres://", "postgresql://") if _db_raw.startswith("postgres://") else _db_raw

# Team members ordered by current load (ascending) — updated at runtime
TEAM_MEMBERS: list[str] = [
    "ruslana@balizero.com",
    "damar@balizero.com",
    "sahira@balizero.com",
    "adit@balizero.com",
    "surya@balizero.com",
    "krisna@balizero.com",
    "vino@balizero.com",
    "ari.firda@balizero.com",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("assign_unassigned")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
QUERY_UNASSIGNED: str = """
    SELECT id, full_name, email, status
    FROM clients
    WHERE (assigned_to IS NULL OR assigned_to = '' OR assigned_to = 'unassigned')
      AND status IN ('active', 'prospect', 'lead')
    ORDER BY created_at DESC
"""

QUERY_TEAM_LOAD: str = """
    SELECT assigned_to, COUNT(*) AS client_count
    FROM clients
    WHERE assigned_to IS NOT NULL
      AND assigned_to != ''
      AND assigned_to != 'unassigned'
      AND status IN ('active', 'prospect', 'lead')
    GROUP BY assigned_to
    ORDER BY client_count ASC
"""

UPDATE_ASSIGNED: str = """
    UPDATE clients
    SET assigned_to = $1, updated_at = NOW()
    WHERE id = $2
"""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
async def fetch_team_load(pool: asyncpg.Pool) -> dict[str, int]:
    """Return a mapping of team member email -> current client count."""
    rows: list[asyncpg.Record] = await pool.fetch(QUERY_TEAM_LOAD)
    load: dict[str, int] = {member: 0 for member in TEAM_MEMBERS}
    for row in rows:
        email: str = row["assigned_to"]
        if email in load:
            load[email] = row["client_count"]
    return load


async def fetch_unassigned_clients(
    pool: asyncpg.Pool, *, limit: int = 200
) -> list[dict[str, Any]]:
    """Return unassigned clients up to `limit`."""
    rows: list[asyncpg.Record] = await pool.fetch(QUERY_UNASSIGNED)
    clients: list[dict[str, Any]] = [dict(r) for r in rows[:limit]]
    return clients


def build_assignment_plan(
    clients: list[dict[str, Any]],
    load: dict[str, int],
) -> list[tuple[dict[str, Any], str]]:
    """Assign clients round-robin by inverse load (lowest-load-first).

    Each cycle, all team members are sorted ascending by current load,
    and each member receives one client. Then loads are updated and
    the next cycle begins.
    """
    assignments: list[tuple[dict[str, Any], str]] = []
    working_load: dict[str, int] = dict(load)
    remaining: list[dict[str, Any]] = list(clients)

    while remaining:
        # Sort team by current load ascending for this cycle
        sorted_team: list[str] = sorted(
            TEAM_MEMBERS, key=lambda m: working_load.get(m, 0)
        )
        for member in sorted_team:
            if not remaining:
                break
            client = remaining.pop(0)
            assignments.append((client, member))
            working_load[member] = working_load.get(member, 0) + 1

    return assignments


async def execute_assignments(
    pool: asyncpg.Pool,
    assignments: list[tuple[dict[str, Any], str]],
) -> int:
    """Write assignment updates to the database. Return count of updates."""
    updated: int = 0
    async with pool.acquire() as conn:
        for client, member in assignments:
            await conn.execute(UPDATE_ASSIGNED, member, client["id"])
            updated += 1
    return updated


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_table(
    assignments: list[tuple[dict[str, Any], str]],
    load_before: dict[str, int],
) -> None:
    """Print a summary table of who gets how many clients."""
    # Count assignments per member
    counts: dict[str, int] = {m: 0 for m in TEAM_MEMBERS}
    for _, member in assignments:
        counts[member] += 1

    # Header
    logger.info("")
    logger.info("=" * 72)
    logger.info("  ASSIGNMENT PLAN")
    logger.info("=" * 72)
    logger.info(
        f"  {'Team Member':<30} {'Before':>8} {'Assigned':>10} {'After':>8}"
    )
    logger.info("-" * 72)

    total_before: int = 0
    total_assigned: int = 0
    for member in TEAM_MEMBERS:
        before: int = load_before.get(member, 0)
        assigned: int = counts.get(member, 0)
        after: int = before + assigned
        total_before += before
        total_assigned += assigned
        logger.info(
            f"  {member:<30} {before:>8} {assigned:>10} {after:>8}"
        )

    logger.info("-" * 72)
    logger.info(
        f"  {'TOTAL':<30} {total_before:>8} {total_assigned:>10} "
        f"{total_before + total_assigned:>8}"
    )
    logger.info("=" * 72)
    logger.info("")


def print_detail(assignments: list[tuple[dict[str, Any], str]]) -> None:
    """Print first 20 individual assignments for verification."""
    preview: int = min(20, len(assignments))
    if preview == 0:
        return
    logger.info(f"  First {preview} assignments:")
    logger.info(
        f"    {'Client ID':>10}  {'Name':<30} {'Assigned To':<30}"
    )
    logger.info("    " + "-" * 72)
    for client, member in assignments[:preview]:
        name: str = (client.get("full_name") or "N/A")[:28]
        logger.info(
            f"    {client['id']:>10}  {name:<30} {member:<30}"
        )
    if len(assignments) > preview:
        logger.info(f"    ... and {len(assignments) - preview} more")
    logger.info("")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(*, dry_run: bool = True, limit: int = 200) -> None:
    """Run the assignment pipeline."""
    logger.info("Connecting to database...")
    pool: asyncpg.Pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)

    try:
        # 1. Fetch current team load
        load_before: dict[str, int] = await fetch_team_load(pool)
        logger.info("Current team load:")
        for member in TEAM_MEMBERS:
            logger.info(f"  {member}: {load_before.get(member, 0)} clients")

        # 2. Fetch unassigned clients
        clients: list[dict[str, Any]] = await fetch_unassigned_clients(pool, limit=limit)
        logger.info(f"Found {len(clients)} unassigned clients (limit={limit})")

        if not clients:
            logger.info("No unassigned clients found. Nothing to do.")
            return

        # 3. Build assignment plan
        assignments: list[tuple[dict[str, Any], str]] = build_assignment_plan(
            clients, load_before
        )

        # 4. Print summary
        print_table(assignments, load_before)
        print_detail(assignments)

        # 5. Execute or dry-run
        if dry_run:
            logger.info("DRY RUN — no changes written. Use --execute to apply.")
        else:
            logger.info("Executing assignments...")
            count: int = await execute_assignments(pool, assignments)
            logger.info(f"Updated {count} clients in the database.")

            # Verify new load
            load_after: dict[str, int] = await fetch_team_load(pool)
            logger.info("Verified team load after assignment:")
            for member in TEAM_MEMBERS:
                logger.info(f"  {member}: {load_after.get(member, 0)} clients")

    finally:
        await pool.close()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Assign unassigned CRM clients to team members (inverse-load round-robin)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually update the database (default: dry-run).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of clients to assign (default: 200).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args: argparse.Namespace = parse_args()
    dry_run: bool = not args.execute
    if dry_run:
        logger.info("Running in DRY-RUN mode (pass --execute to apply changes)")
    else:
        logger.info("Running in EXECUTE mode — will update the database")
    asyncio.run(main(dry_run=dry_run, limit=args.limit))
