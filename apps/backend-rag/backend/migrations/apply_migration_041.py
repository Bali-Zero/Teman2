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
        await apply_migration(conn)
    except Exception:
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(apply())
