import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from migrations.migration_041_clients_missing_columns import apply_migration

load_dotenv("apps/backend-rag/.env")
DATABASE_URL = os.getenv("DATABASE_URL")


async def apply():
    """Apply migration 041 to add missing columns to clients table"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("📦 Applying migration 041: Adding missing columns to clients table...")
        await apply_migration(conn)
        print("✅ Migration 041 applied successfully!")
    except Exception as e:
        print(f"❌ Migration 041 failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(apply())
