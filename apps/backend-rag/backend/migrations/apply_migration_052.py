import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from migrations.migration_052_openclaw_message_logs import apply

load_dotenv("apps/backend-rag/.env")
DATABASE_URL = os.getenv("DATABASE_URL")


async def run_migration():
    """Apply migration 052 to create openclaw_message_logs table"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await apply(conn)
    except Exception:
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
