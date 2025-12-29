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

from app.core.config import settings
from migrations.migration_028_knowledge_graph_schema import apply

async def main():
    print("🔄 Connecting to database...")
    db_url = settings.database_url or os.getenv("DATABASE_URL")
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
