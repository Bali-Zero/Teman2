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
    print("🔄 Connecting to database...")
    # Fallback to local dev URL if env var is missing
    db_url = os.getenv("DATABASE_URL") or "postgresql://user:password@localhost:5433/nuzantara_dev"

    if not db_url:
        print("❌ DATABASE_URL not found")
        sys.exit(1)

    try:
        conn = await asyncpg.connect(db_url)
        print("✅ Connected. Applying Migration 028...")

        await apply(conn)

        await conn.close()
        print("🎉 Migration applied successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
