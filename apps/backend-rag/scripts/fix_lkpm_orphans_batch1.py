#!/usr/bin/env python3
"""
One-off fix: create missing clients and client_company_links for 13 LKPM orphan rows.

These companies were imported into lkpm_reports with client_id pointing at
companies.id, but they have NO client_company_links rows at all.  This script:
  1. Finds or creates the director as a clients row
  2. Creates client_company_links for director (and commissioner if provided)
  3. Updates lkpm_reports.client_id to point at the director
  4. Updates lkpm_client_config.client_id to match

Before updating lkpm_reports, checks the UNIQUE constraint
(client_id, quarter, year) to avoid collisions.

lkpm_id=86 (PT Megah Sentosa Properti) is excluded from this batch because
its sole director (Roman Pukhov, client_id=283) already owns lkpm_id=85
(PT Triple Peak), causing a genuine UNIQUE collision that needs schema discussion.

DRY-RUN by default.  Pass --commit to actually write.

Usage:
    cd apps/backend-rag
    source /path/to/.venv/bin/activate
    set -a && source /path/to/.env && set +a
    PYTHONPATH=. python scripts/fix_lkpm_orphans_batch1.py --dry-run
    PYTHONPATH=. python scripts/fix_lkpm_orphans_batch1.py --commit
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
# Data: 6 orphan PTs with confirmed director data
# ---------------------------------------------------------------------------

ORPHAN_FIXES: list[dict[str, Any]] = [
    {
        "lkpm_id": 71,  # PT Atlas Property Management
        "company_id": 4073,
        "director_name": "Bugra Sitemkar",
        "director_nationality": "Turkish",
        "director_email": "bugrasitemkar@gmail.com",
        "director_phone": "+6282144790955",
        "commissioner_name": "Aynca Sitemkar",
        "commissioner_nationality": "Turkish",
    },
    {
        "lkpm_id": 77,  # PT Ventura Impact Positif
        "company_id": 2375,
        "director_name": "Adrian Christopher Alan Keet",
        "director_nationality": None,
        "director_email": "adrian.keet@lightatwork.org",
        "director_phone": "08214646916",
        "commissioner_name": "Linzi Louise Harrison",
        "commissioner_nationality": None,
    },
    {
        "lkpm_id": 84,  # PT Karta Entertainment Found
        "company_id": 2000,
        "director_name": "Nikita Zimarkov",
        "director_nationality": None,
        "director_email": None,
        "director_phone": None,
        "commissioner_name": "Aleksandar Angelov Radoslavov",
        "commissioner_nationality": None,
    },
    {
        "lkpm_id": 103,  # PT Cirera and Nello Investments
        "company_id": 2349,
        "director_name": "Christian Nicolai",
        "director_nationality": None,
        "director_email": None,
        "director_phone": None,
        "commissioner_name": "I Ketut Arya Widenaw",
        "commissioner_nationality": "Indonesian",
    },
    {
        "lkpm_id": 116,  # PT Villa Stella Belle
        "company_id": 2498,
        "director_name": "Belinda Jane Pillios",
        "director_nationality": "Australian",
        "director_email": None,
        "director_phone": None,
        "director_passport": "RA2340374",
        "commissioner_name": "Matthew James Pillios",
        "commissioner_nationality": "Australian",
        "commissioner_passport": "PB4816268",
    },
    {
        "lkpm_id": 121,  # PT Yume Innovation Studio
        "company_id": 2366,
        "director_name": "Ludwig Marius Guenther Frank",
        "director_nationality": "German",
        "director_email": None,
        "director_phone": None,
        "director_passport": "CG9FNY3C5",
        "commissioner_name": "Gabriele Frank",
        "commissioner_nationality": "German",
        "commissioner_passport": "CG9F3W19F",
    },
    # ── Batch 2: added 2026-04-08 from profil perseroan PDFs ──
    {
        "lkpm_id": 75,  # PT Royal Aura Brands
        "company_id": 2380,
        "director_name": "Tugce Oztol",
        "director_nationality": "Turkish",
        "director_email": None,
        "director_phone": None,
        "director_passport": "U13979970",
        "commissioner_name": "Halit Yagiz Oztol",
        "commissioner_nationality": "Turkish",
        "commissioner_passport": "U30677413",
    },
    {
        "lkpm_id": 76,  # PT Karta Developers Paradise
        "company_id": 1999,
        "director_name": "Nikita Zimarkov",
        "director_nationality": "Russian",
        "director_email": None,
        "director_phone": None,
        "commissioner_name": "Kira Naumenko",
        "commissioner_nationality": "Russian",
    },
    {
        "lkpm_id": 82,  # PT Sduare Property Bali
        "company_id": 2399,
        "director_name": "Ivan Sizov",
        "director_nationality": "Russian",
        "director_email": None,
        "director_phone": None,
        "commissioner_name": "Liudmila Sizova",
        "commissioner_nationality": "Russian",
    },
    {
        "lkpm_id": 93,  # PT Alis Volat Propriis
        "company_id": 4074,
        "director_name": "Sophia Julia Bonafini",
        "director_nationality": "Italian",
        "director_email": None,
        "director_phone": None,
        "director_passport": "YC2156357",
        "commissioner_name": "Nicolo Scarabello",
        "commissioner_nationality": "Italian",
        "commissioner_passport": "YC0369193",
    },
    {
        "lkpm_id": 94,  # PT Ichnos West Sumbawa
        "company_id": 1897,
        "director_name": "Armando Puddu",
        "director_nationality": "Italian",
        "director_email": None,
        "director_phone": None,
        "director_passport": "YB7750628",
        "commissioner_name": "Valentina Milani",
        "commissioner_nationality": "Italian",
        "commissioner_passport": "YB2375645",
    },
    {
        "lkpm_id": 102,  # PT Nepu Global Invest
        "company_id": 2345,
        "director_name": "Enrique Nello Jover",
        "director_nationality": "Spanish",
        "director_email": None,
        "director_phone": None,
        "director_passport": "PAJ215067",
        "commissioner_name": "Maria Carmen Pueyo Toldra",
        "commissioner_nationality": "Spanish",
        "commissioner_passport": "PAB273722",
    },
    {
        "lkpm_id": 115,  # PT Whatsyum Tech Group
        "company_id": 2467,
        "director_name": "James Andrew Barton",
        "director_nationality": None,
        "director_email": None,
        "director_phone": None,
        "commissioner_name": "James Aidan Charles Earley",
        "commissioner_nationality": None,
    },
]

CREATED_BY = "fix_lkpm_orphans_batch1"


# ---------------------------------------------------------------------------
# Internal exception for transaction rollback on collision
# ---------------------------------------------------------------------------


class _SkipTransaction(Exception):
    """Raised inside a transaction to trigger rollback on UNIQUE collision."""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def find_client_by_name(
    conn: asyncpg.Connection, full_name: str
) -> dict[str, Any] | None:
    """Search clients by case-insensitive full_name match."""
    row = await conn.fetchrow(
        "SELECT id, full_name, email, phone, nationality, passport_number "
        "FROM clients WHERE full_name ILIKE $1 LIMIT 1",
        full_name,
    )
    return dict(row) if row else None


async def create_client(
    conn: asyncpg.Connection,
    *,
    full_name: str,
    email: str | None = None,
    phone: str | None = None,
    nationality: str | None = None,
    passport_number: str | None = None,
) -> int:
    """Insert a new client and return the id."""
    client_id: int = await conn.fetchval(
        """
        INSERT INTO clients (
            full_name, email, phone, nationality, passport_number,
            status, client_type, created_by, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, 'active', 'individual', $6, NOW(), NOW())
        RETURNING id
        """,
        full_name,
        email,
        phone,
        nationality,
        passport_number,
        CREATED_BY,
    )
    return client_id


async def create_company_link(
    conn: asyncpg.Connection,
    *,
    client_id: int,
    company_id: int,
    role: str,
    is_primary: bool = False,
) -> None:
    """Insert a client_company_links row (ON CONFLICT DO NOTHING)."""
    await conn.execute(
        """
        INSERT INTO client_company_links (
            client_id, company_id, role, is_primary, status, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, 'active', NOW(), NOW())
        ON CONFLICT DO NOTHING
        """,
        client_id,
        company_id,
        role,
        is_primary,
    )


async def check_lkpm_unique_collision(
    conn: asyncpg.Connection,
    client_id: int,
    quarter: str,
    year: int,
) -> int | None:
    """Return the lkpm_reports.id that already uses (client_id, quarter, year), or None."""
    return await conn.fetchval(
        "SELECT id FROM lkpm_reports "
        "WHERE client_id = $1 AND quarter = $2 AND year = $3",
        client_id,
        quarter,
        year,
    )


# ---------------------------------------------------------------------------
# Per-person flow: find or create client + link
# ---------------------------------------------------------------------------


async def find_or_create_person(
    conn: asyncpg.Connection,
    *,
    name: str,
    email: str | None,
    phone: str | None,
    nationality: str | None,
    passport_number: str | None,
    company_id: int,
    role: str,
    is_primary: bool,
    dry_run: bool,
) -> tuple[int | None, bool]:
    """Find or create a client, then link to company.

    Returns (client_id, was_created).
    In dry-run mode returns (None, True) for would-be-created clients.
    """
    existing = await find_client_by_name(conn, name)
    if existing:
        client_id = existing["id"]
        logger.info("    FOUND existing client id=%d for '%s'", client_id, name)
        if not dry_run:
            await create_company_link(
                conn,
                client_id=client_id,
                company_id=company_id,
                role=role,
                is_primary=is_primary,
            )
        return client_id, False

    # Need to create
    logger.info("    WILL CREATE client '%s' (%s)", name, role)
    if dry_run:
        return None, True

    client_id = await create_client(
        conn,
        full_name=name,
        email=email,
        phone=phone,
        nationality=nationality,
        passport_number=passport_number,
    )
    logger.info("    CREATED client id=%d for '%s'", client_id, name)

    await create_company_link(
        conn,
        client_id=client_id,
        company_id=company_id,
        role=role,
        is_primary=is_primary,
    )
    return client_id, True


# ---------------------------------------------------------------------------
# Main fix loop
# ---------------------------------------------------------------------------


async def fix_orphans(
    pool: asyncpg.Pool,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Process all orphan fixes.  Each entry runs in its own transaction."""
    results: list[dict[str, Any]] = []

    for entry in ORPHAN_FIXES:
        lkpm_id: int = entry["lkpm_id"]
        company_id: int = entry["company_id"]
        result: dict[str, Any] = {
            "lkpm_id": lkpm_id,
            "company_id": company_id,
            "director_name": entry["director_name"],
            "action": "pending",
        }

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    logger.info(
                        "--- lkpm_id=%d  company_id=%d  director='%s' ---",
                        lkpm_id,
                        company_id,
                        entry["director_name"],
                    )

                    # Step 1: Find or create director
                    director_id, director_created = await find_or_create_person(
                        conn,
                        name=entry["director_name"],
                        email=entry.get("director_email"),
                        phone=entry.get("director_phone"),
                        nationality=entry.get("director_nationality"),
                        passport_number=entry.get("director_passport"),
                        company_id=company_id,
                        role="Director",
                        is_primary=True,
                        dry_run=dry_run,
                    )

                    # Step 2: Find or create commissioner (if provided)
                    commissioner_id: int | None = None
                    commissioner_name = entry.get("commissioner_name")
                    if commissioner_name:
                        commissioner_id, _ = await find_or_create_person(
                            conn,
                            name=commissioner_name,
                            email=None,
                            phone=None,
                            nationality=entry.get("commissioner_nationality"),
                            passport_number=entry.get("commissioner_passport"),
                            company_id=company_id,
                            role="Commissioner",
                            is_primary=False,
                            dry_run=dry_run,
                        )

                    # Step 3: Check UNIQUE constraint before updating lkpm_reports
                    if director_id is not None:
                        collision_id = await check_lkpm_unique_collision(
                            conn, director_id, "Q1", 2026,
                        )
                        if collision_id is not None and collision_id != lkpm_id:
                            result["action"] = "UNIQUE_COLLISION"
                            result["director_client_id"] = director_id
                            result["collision_lkpm_id"] = collision_id
                            result["info"] = (
                                f"client_id={director_id} already used by "
                                f"lkpm_id={collision_id} for Q1/2026"
                            )
                            logger.warning(
                                "    UNIQUE COLLISION: client_id=%d already in "
                                "lkpm_reports id=%d for Q1/2026 -- SKIPPING",
                                director_id,
                                collision_id,
                            )
                            # Raise to rollback the entire transaction (including
                            # any client/link rows we just created for this entry)
                            raise _SkipTransaction()

                    # Step 4: Update lkpm_reports.client_id
                    if not dry_run and director_id is not None:
                        old_client_id = await conn.fetchval(
                            "SELECT client_id FROM lkpm_reports WHERE id = $1",
                            lkpm_id,
                        )
                        await conn.execute(
                            "UPDATE lkpm_reports SET client_id = $1 WHERE id = $2",
                            director_id,
                            lkpm_id,
                        )
                        logger.info(
                            "    UPDATE lkpm_reports SET client_id=%d "
                            "WHERE id=%d (was %s)",
                            director_id,
                            lkpm_id,
                            old_client_id,
                        )

                        # Step 5: Update lkpm_client_config.client_id
                        config_updated = await conn.execute(
                            "UPDATE lkpm_client_config SET client_id = $1 "
                            "WHERE client_id = $2",
                            director_id,
                            old_client_id,
                        )
                        logger.info(
                            "    UPDATE lkpm_client_config SET client_id=%d "
                            "WHERE client_id=%d (%s)",
                            director_id,
                            old_client_id,
                            config_updated,
                        )

                    result["action"] = "DRY_RUN" if dry_run else "FIXED"
                    result["director_client_id"] = director_id
                    result["director_created"] = director_created
                    result["commissioner_client_id"] = commissioner_id

        except _SkipTransaction:
            # Transaction was rolled back; result already populated above
            pass
        except Exception as exc:
            result["action"] = "ERROR"
            result["info"] = str(exc)
            logger.exception(
                "    ERROR processing lkpm_id=%d: %s", lkpm_id, exc,
            )

        results.append(result)

    _print_summary(results, dry_run)
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_summary(results: list[dict[str, Any]], dry_run: bool) -> None:
    """Print a formatted summary table."""
    mode = "DRY-RUN" if dry_run else "COMMIT"
    print(f"\n{'=' * 78}")
    print(f"  LKPM Orphan Fix Batch 1  [{mode}]")
    print(f"{'=' * 78}")
    print(
        f"  {'LKPM':>5}  {'CO':>5}  {'DIR_ID':>6}  {'COM_ID':>6}  "
        f"{'Action':<18}  Director"
    )
    print(
        f"  {'-' * 5}  {'-' * 5}  {'-' * 6}  {'-' * 6}  "
        f"{'-' * 18}  {'-' * 30}"
    )

    for r in results:
        dir_id = str(r.get("director_client_id") or "---")
        com_id = str(r.get("commissioner_client_id") or "---")
        action = r.get("action", "?")
        info = r.get("info", "")
        extra = f"  ({info})" if info else ""
        print(
            f"  {r['lkpm_id']:>5}  {r['company_id']:>5}  {dir_id:>6}  "
            f"{com_id:>6}  {action:<18}  {r['director_name']}{extra}"
        )

    counts: dict[str, int] = {}
    for r in results:
        a = r.get("action", "?")
        counts[a] = counts.get(a, 0) + 1

    print(f"\n  Total: {len(results)} entries")
    for action, count in sorted(counts.items()):
        print(f"    {action}: {count}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix 6 LKPM orphan rows (batch 1): create missing clients + links",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run", action="store_true", default=True, help="Preview only (default)",
    )
    group.add_argument("--commit", action="store_true", help="Apply fixes")
    args = parser.parse_args()

    dry_run = not args.commit
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    try:
        await fix_orphans(pool, dry_run=dry_run)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
