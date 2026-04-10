"""
Migration 085: Add CHECK constraints to prevent empty strings on FK-like columns.

Problem:
  PostgreSQL accepts '' (empty string) for TEXT/VARCHAR columns even with NOT NULL.
  This causes silent bugs: partial indexes (WHERE assigned_to IS NOT NULL) miss them,
  RBAC filters fail, and COALESCE(NULLIF(x,''), ...) workarounds proliferate.

Strategy:
  1. Clean existing empty strings → NULL
  2. Add CHECK (col IS NULL OR col <> '') for nullable columns
  3. Add CHECK (col <> '') for required columns

Usage:
    cd apps/backend-rag
    source venv/bin/activate  # or .venv on Pro
    DATABASE_URL=<url> PYTHONPATH=. python backend/migrations/migration_085_check_no_empty_strings.py
"""

import asyncio
import os
import sys

import asyncpg


# (table, column, required: bool)
# required=True → NOT NULL + CHECK col <> ''
# required=False → CHECK col IS NULL OR col <> ''
COLUMNS = [
    # clients
    ("clients", "assigned_to", False),
    ("clients", "created_by", False),
    ("clients", "email", False),
    ("clients", "phone", False),
    ("clients", "nationality", False),
    # practices
    ("practices", "assigned_to", False),
    ("practices", "created_by", False),
    # companies
    ("companies", "created_by", False),
]


def _constraint_name(table: str, column: str) -> str:
    return f"chk_{table}_{column}_no_empty"


async def upgrade(conn: asyncpg.Connection) -> None:
    """Clean empty strings and add CHECK constraints."""
    for table, column, required in COLUMNS:
        cname = _constraint_name(table, column)

        # 1. Clean: '' → NULL
        fixed = await conn.execute(
            f"UPDATE {table} SET {column} = NULL WHERE {column} = ''",
        )
        if fixed != "UPDATE 0":
            print(f"  Fixed {fixed} empty strings in {table}.{column}")

        # 2. Check if constraint already exists
        exists = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = $1 AND constraint_name = $2
            """,
            table, cname,
        )
        if exists:
            print(f"  {cname} already exists — skip")
            continue

        # 3. Add CHECK constraint
        if required:
            check_expr = f"{column} <> ''"
        else:
            check_expr = f"{column} IS NULL OR {column} <> ''"

        await conn.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {cname} CHECK ({check_expr})",
        )
        print(f"  Added {cname}")

    print("Migration 085 complete.")


async def downgrade(conn: asyncpg.Connection) -> None:
    """Remove CHECK constraints."""
    for table, column, _required in COLUMNS:
        cname = _constraint_name(table, column)
        await conn.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {cname}",
        )
        print(f"  Dropped {cname}")

    print("Migration 085 rollback complete.")


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(db_url)
    try:
        direction = sys.argv[1] if len(sys.argv) > 1 else "up"
        if direction == "down":
            await downgrade(conn)
        else:
            await upgrade(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
