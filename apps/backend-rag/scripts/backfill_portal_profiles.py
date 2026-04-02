#!/usr/bin/env python3
"""
One-shot backfill: create team_members records (role='client') for all
existing CRM clients that don't have one yet.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/backfill_portal_profiles.py [--dry-run]
"""

import argparse
import asyncio
import os
import sys

import asyncpg

# Placeholder bcrypt hash — login impossible until client sets real PIN via invite
PLACEHOLDER_PIN = "$2b$12$000000000000000000000uNOLOGIN.placeholder.hash.nevermatches"


async def main(dry_run: bool = False) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(database_url)

    try:
        # Count current state
        total_clients = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL",
        )
        existing_portal = await conn.fetchval(
            "SELECT COUNT(*) FROM team_members WHERE role = 'client' AND linked_client_id IS NOT NULL",
        )

        print(f"Total active clients: {total_clients}")
        print(f"Existing portal profiles: {existing_portal}")
        print(f"Missing: {total_clients - existing_portal}")
        print()

        # Find clients without portal profile
        missing = await conn.fetch(
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
            """,
        )

        print(f"Clients to backfill (with valid email): {len(missing)}")

        if dry_run:
            print("\n[DRY RUN] Would create portal profiles for:")
            for row in missing[:10]:
                print(f"  - {row['full_name']} ({row['email']}) [id={row['id']}]")
            if len(missing) > 10:
                print(f"  ... and {len(missing) - 10} more")
            return

        # Batch insert
        created = 0
        skipped = 0
        errors = 0

        for row in missing:
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
                    RETURNING id
                    """,
                    row["full_name"] or "Unknown",
                    row["email"].strip().lower(),
                    PLACEHOLDER_PIN,
                    row["id"],
                )
                if result:
                    created += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                print(f"  ERROR for client {row['id']} ({row['email']}): {e}")

        print("\nResults:")
        print(f"  Created: {created}")
        print(f"  Skipped (conflict with non-client): {skipped}")
        print(f"  Errors: {errors}")

        # Verify
        final_count = await conn.fetchval(
            "SELECT COUNT(*) FROM team_members WHERE role = 'client' AND linked_client_id IS NOT NULL",
        )
        print(f"\nFinal portal profiles: {final_count}")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill portal profiles for existing clients")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))
