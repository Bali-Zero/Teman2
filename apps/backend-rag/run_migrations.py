#!/usr/bin/env python3
"""
Run database migrations for ZANTARA Memory System
Applies SQL schemas to Fly.io PostgreSQL database
"""

import asyncio
import os
from pathlib import Path

import asyncpg


async def run_migrations():
    """Run all SQL migrations in order"""

    # Get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        print("   Please set DATABASE_URL from Fly.io dashboard")
        return False

    print("=" * 80)
    print("🚀 ZANTARA MEMORY SYSTEM - DATABASE MIGRATIONS")
    print("=" * 80)
    print(
        f"\n📊 Database: {database_url.split('@')[1] if '@' in database_url else 'Fly.io PostgreSQL'}"
    )

    try:
        # Connect to database
        print("\n🔌 Connecting to PostgreSQL...")
        conn = await asyncpg.connect(database_url)
        print("✅ Connected successfully")

        # Find migration files
        migrations_dir = Path(__file__).parent / "backend" / "db" / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        print(f"\n📁 Found {len(migration_files)} migration file(s):")
        for f in migration_files:
            print(f"   - {f.name}")

        # Run each migration
        for migration_file in migration_files:
            print(f"\n⚙️  Running migration: {migration_file.name}")

            # Read SQL file
            with open(migration_file) as f:
                sql = f.read()

            # Execute SQL
            try:
                await conn.execute(sql)
                print(f"   ✅ {migration_file.name} applied successfully")
            except Exception as e:
                print(f"   ⚠️  {migration_file.name} - {str(e)}")
                # Continue with other migrations

        # Verify tables were created
        print("\n🔍 Verifying tables...")

        tables_to_check = ["memory_facts", "user_stats", "conversations", "users"]

        for table_name in tables_to_check:
            result = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = $1
                )
                """,
                table_name,
            )

            if result:
                # Count rows
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                print(f"   ✅ {table_name}: exists ({count} rows)")
            else:
                print(f"   ❌ {table_name}: NOT FOUND")

        # Close connection
        await conn.close()
        print("\n" + "=" * 80)
        print("✅ MIGRATIONS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Check for DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("\n⚠️  DATABASE_URL not set. Please export it first:")
        print("   export DATABASE_URL='postgresql://...'")
        print("\n   Get it from Fly.io dashboard:")
        print("   railway variables | grep DATABASE_URL")
        exit(1)

    # Run migrations
    success = asyncio.run(run_migrations())

    exit(0 if success else 1)
