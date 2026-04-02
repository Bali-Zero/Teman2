"""
Backfill Portal Profiles — one-shot script

Creates team_members records (role='client') for all existing CRM clients
that don't already have one.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    DATABASE_URL="postgresql://..." PYTHONPATH=. python ../../scripts/backfill_portal_profiles.py

Dry-run (no writes):
    DRY_RUN=1 PYTHONPATH=. python ../../scripts/backfill_portal_profiles.py
"""

import asyncio
import os
import sys

import asyncpg

# Placeholder bcrypt hash — same as portal_profile_service.py
_PLACEHOLDER_PIN_HASH = "$2b$12$000000000000000000000uNOLOGIN.placeholder.hash.nevermatches"


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    dry_run = os.environ.get("DRY_RUN", "0") == "1"
    if dry_run:
        print("DRY RUN — no writes will be made")

    conn = await asyncpg.connect(database_url)

    try:
        # Count before
        before_count = await conn.fetchval(
            "SELECT COUNT(*) FROM team_members WHERE role = 'client'"
        )
        eligible = await conn.fetch(
            """
            SELECT c.id, c.email, c.full_name
            FROM clients c
            WHERE c.deleted_at IS NULL
              AND c.email IS NOT NULL
              AND TRIM(c.email) != ''
              AND NOT EXISTS (
                  SELECT 1 FROM team_members tm
                  WHERE tm.linked_client_id = c.id AND tm.role = 'client'
              )
            ORDER BY c.id
            """
        )

        print(f"Portal profiles before: {before_count}")
        print(f"Clients eligible for backfill: {len(eligible)}")

        if not eligible:
            print("Nothing to backfill.")
            return

        if dry_run:
            for row in eligible[:10]:
                print(f"  Would create: client_id={row['id']} email={row['email']}")
            if len(eligible) > 10:
                print(f"  ... and {len(eligible) - 10} more")
            return

        inserted = 0
        updated = 0
        errors = 0

        for row in eligible:
            try:
                result = await conn.fetchval(
                    """
                    INSERT INTO team_members (
                        name, email, pin_hash, role,
                        linked_client_id, portal_access, active
                    )
                    VALUES ($1, $2, $3, 'client', $4, true, true)
                    ON CONFLICT (email) DO UPDATE
                        SET linked_client_id = EXCLUDED.linked_client_id,
                            portal_access = true,
                            name = EXCLUDED.name
                        WHERE team_members.role = 'client'
                    RETURNING (xmax = 0) AS is_insert
                    """,
                    row["full_name"] or "",
                    row["email"].strip().lower(),
                    _PLACEHOLDER_PIN_HASH,
                    row["id"],
                )
                if result:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                errors += 1
                print(f"  ERROR client_id={row['id']} email={row['email']}: {e}")

        after_count = await conn.fetchval(
            "SELECT COUNT(*) FROM team_members WHERE role = 'client'"
        )

        print(f"\nBackfill complete:")
        print(f"  Inserted: {inserted}")
        print(f"  Updated:  {updated}")
        print(f"  Errors:   {errors}")
        print(f"  Portal profiles after: {after_count}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
