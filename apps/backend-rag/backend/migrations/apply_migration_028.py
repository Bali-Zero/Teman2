"""
Apply Migration 028: Knowledge Graph Schema
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migrations.migration_028_knowledge_graph_schema import apply


async def main():
    # Fallback to local dev URL if env var is missing
    db_url = os.getenv("DATABASE_URL") or "postgresql://user:password@localhost:5433/nuzantara_dev"

    if not db_url:
        sys.exit(1)

    try:
        conn = await asyncpg.connect(db_url)

        await apply(conn)

        await conn.close()
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
