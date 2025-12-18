"""
Verify Data Population
"""

import asyncio
import sys
from pathlib import Path

import asyncpg

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import settings


async def verify():
    db_url = settings.database_url
    if not db_url:
        print("❌ DATABASE_URL not set in settings")
        return
    try:
        conn = await asyncpg.connect(db_url)

        # Check KG Entities
        entities_count = await conn.fetchval("SELECT COUNT(*) FROM kg_entities")
        print(f"✅ KG Entities: {entities_count}")

        # Check KG Relationships
        rel_count = await conn.fetchval("SELECT COUNT(*) FROM kg_relationships")
        print(f"✅ KG Relationships: {rel_count}")

        # Check Golden Routes
        routes_count = await conn.fetchval("SELECT COUNT(*) FROM golden_routes")
        print(f"✅ Golden Routes: {routes_count}")

        await conn.close()

    except Exception as e:
        print(f"❌ Verification failed: {e}")


if __name__ == "__main__":
    asyncio.run(verify())
