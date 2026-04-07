#!/usr/bin/env python3
"""
One-off fix: correct client_id mismatch in LKPM Q1 2026 reports.

The import script (import_lkpm_q1_2026.py) incorrectly stored companies.id
as lkpm_reports.client_id, but the system expects clients.id.  This script
resolves the correct client_id via client_company_links.

DRY-RUN by default. Pass --commit to actually write.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    DATABASE_URL=... PYTHONPATH=. python scripts/fix_lkpm_q1_2026_client_ids.py --dry-run
    DATABASE_URL=... PYTHONPATH=. python scripts/fix_lkpm_q1_2026_client_ids.py --commit
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Client 5912 is "Zainal Abidin" — OCR garbage linked to 40+ companies.
KNOWN_FAKE_FOUNDER_IDS: frozenset[int] = frozenset({5912})

_LKPM_SCAN_QUERY = """
SELECT r.id, r.client_id, r.quarter, r.year,
       COALESCE(co.company_name, 'UNKNOWN') AS company_name
FROM lkpm_reports r
LEFT JOIN companies co ON co.id = r.client_id
WHERE r.quarter = 'Q1' AND r.year = 2026
ORDER BY r.id
"""

_LINKS_FOR_COMPANY_QUERY = """
SELECT ccl.client_id, ccl.is_primary, ccl.role, ccl.status,
       c.full_name, c.deleted_at, c.deleted_by
FROM client_company_links ccl
LEFT JOIN clients c ON c.id = ccl.client_id
WHERE ccl.company_id = $1
"""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def pick_director_from_links(
    links: list[dict[str, Any]],
    *,
    fake_founder_ids: frozenset[int] = KNOWN_FAKE_FOUNDER_IDS,
) -> dict[str, Any] | None:
    """Pick the best director from a list of client_company_links rows.

    Priority (highest first):
    1. Alive over deleted
    2. Primary over non-primary
    3. Director role over commissioner
    4. Lowest client_id as tiebreaker

    Filters out known fake founders before ranking.
    """
    if not links:
        return None

    # Filter out fake founders
    filtered = [l for l in links if l["client_id"] not in fake_founder_ids]
    if not filtered:
        return None

    def _sort_key(link: dict[str, Any]) -> tuple[int, int, int, int]:
        alive = 0 if link.get("deleted_at") is None else 1
        primary = 0 if link.get("is_primary") else 1
        role_str = (link.get("role") or "").lower()
        role = 0 if "director" in role_str else 1
        cid = link.get("client_id") or 999999
        return (alive, primary, role, cid)

    filtered.sort(key=_sort_key)
    return filtered[0]


def make_decision(
    lkpm_report: dict[str, Any],
    picked_director: dict[str, Any] | None,
) -> dict[str, Any]:
    """Decide what action to take for a single LKPM report row.

    Returns a dict with keys: action, lkpm_id, old_client_id, new_client_id, info.
    Actions: 'orphan', 'noop', 'fix_client_id', 'undelete_and_fix'.
    """
    lkpm_id = lkpm_report["id"]
    old_client_id = lkpm_report["client_id"]

    if picked_director is None:
        return {
            "action": "orphan",
            "lkpm_id": lkpm_id,
            "old_client_id": old_client_id,
            "new_client_id": None,
            "info": "no links found for company",
        }

    new_client_id = picked_director["client_id"]

    if new_client_id == old_client_id:
        return {
            "action": "noop",
            "lkpm_id": lkpm_id,
            "old_client_id": old_client_id,
            "new_client_id": new_client_id,
            "info": "already correct",
        }

    if picked_director.get("deleted_at") is not None:
        return {
            "action": "undelete_and_fix",
            "lkpm_id": lkpm_id,
            "old_client_id": old_client_id,
            "new_client_id": new_client_id,
            "info": f"undelete client {new_client_id} then fix",
        }

    return {
        "action": "fix_client_id",
        "lkpm_id": lkpm_id,
        "old_client_id": old_client_id,
        "new_client_id": new_client_id,
        "info": f"fix {old_client_id} -> {new_client_id}",
    }


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


async def _apply_fix(
    conn: asyncpg.Connection,
    lkpm_id: int,
    old_client_id: int,
    new_client_id: int,
    undelete: bool,
) -> None:
    """Apply the fix in a single transaction."""
    async with conn.transaction():
        if undelete:
            await conn.execute(
                "UPDATE clients SET deleted_at = NULL, deleted_by = NULL WHERE id = $1",
                new_client_id,
            )
        await conn.execute(
            "UPDATE lkpm_reports SET client_id = $1 WHERE id = $2",
            new_client_id,
            lkpm_id,
        )
        await conn.execute(
            "UPDATE lkpm_client_config SET client_id = $1 WHERE client_id = $2",
            new_client_id,
            old_client_id,
        )


async def resolve_and_fix(
    pool: asyncpg.Pool,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Main loop: scan LKPM Q1 2026, resolve correct client_ids, fix if not dry_run."""
    report: list[dict[str, Any]] = []

    async with pool.acquire() as conn:
        lkpm_rows = await conn.fetch(_LKPM_SCAN_QUERY)

        for row in lkpm_rows:
            row_dict = dict(row)
            company_id = row_dict["client_id"]

            links_raw = await conn.fetch(_LINKS_FOR_COMPANY_QUERY, company_id)
            links = [dict(l) for l in links_raw]

            picked = pick_director_from_links(links)
            decision = make_decision(row_dict, picked)
            report.append(decision)

            if dry_run:
                continue

            action = decision["action"]
            if action == "orphan" or action == "noop":
                continue

            undelete = action == "undelete_and_fix"
            try:
                await _apply_fix(
                    conn,
                    decision["lkpm_id"],
                    decision["old_client_id"],
                    decision["new_client_id"],
                    undelete,
                )
            except Exception as exc:
                if "uq_lkpm_report" in str(exc):
                    decision["action"] = "unique_collision"
                    decision["info"] = (
                        f"UNIQUE(client_id={decision['new_client_id']}, Q1, 2026) "
                        f"already taken — same director for 2+ PTs"
                    )
                    decision["marker"] = "⚡"
                else:
                    decision["action"] = "error"
                    decision["info"] = str(exc)
                    decision["marker"] = "!"

    _print_summary(report, dry_run)
    return report


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_summary(report: list[dict[str, Any]], dry_run: bool) -> None:
    """Print a formatted decision table."""
    markers = {
        "fix_client_id": "\u2192",
        "undelete_and_fix": "\u219f",
        "orphan": "\u2717",
        "noop": " ",
    }

    mode = "DRY-RUN" if dry_run else "COMMIT"
    print(f"\n{'=' * 70}")
    print(f"  LKPM Q1 2026 client_id fix  [{mode}]")
    print(f"{'=' * 70}")
    print(f"  {'ID':>5}  {'OLD':>6}  {'NEW':>6}  M  Action")
    print(f"  {'-' * 5}  {'-' * 6}  {'-' * 6}  -  {'-' * 30}")

    for row in report:
        marker = markers.get(row["action"], "?")
        new_str = str(row["new_client_id"] or "---")
        print(
            f"  {row['lkpm_id']:>5}  {row['old_client_id']:>6}  {new_str:>6}"
            f"  {marker}  {row['info']}"
        )

    counts = {}
    for row in report:
        counts[row["action"]] = counts.get(row["action"], 0) + 1

    print(f"\n  Total: {len(report)} rows")
    for action, count in sorted(counts.items()):
        m = markers.get(action, "?")
        print(f"    {m} {action}: {count}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix LKPM Q1 2026 client_id mismatch"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    group.add_argument("--commit", action="store_true", help="Apply fixes")
    args = parser.parse_args()

    dry_run = not args.commit
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    try:
        await resolve_and_fix(pool, dry_run=dry_run)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
