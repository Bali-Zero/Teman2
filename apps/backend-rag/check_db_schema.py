#!/usr/bin/env python3
"""
Check PostgreSQL schema to see what tables exist and their columns
"""
import asyncio
import os

import asyncpg


async def check_schema():
    """Check existing PostgreSQL schema"""

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL not found")
        return

    print("=" * 80)
    print("🔍 CHECKING POSTGRESQL SCHEMA")
    print("=" * 80)

    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to PostgreSQL\n")

        # Check what tables exist
        tables_to_check = ["memory_facts", "user_stats", "conversations", "users"]

        for table_name in tables_to_check:
            # Check if table exists
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = $1
                )
                """,
                table_name,
            )

            if exists:
                # Get column information
                columns = await conn.fetch(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table_name,
                )

                # Get row count
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")

                print(f"✅ {table_name}: EXISTS ({count} rows)")
                print("   Columns:")
                for col in columns:
                    print(
                        f"     - {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}"
                    )
                print()
            else:
                print(f"❌ {table_name}: NOT FOUND\n")

        await conn.close()

        print("=" * 80)
        print("✅ SCHEMA CHECK COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_schema())
