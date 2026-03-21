
import asyncio
import os
import asyncpg

async def find_suspicious_nodes():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return
    
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch("SELECT entity_id, name, entity_type FROM kg_nodes WHERE entity_id LIKE 'node_%' LIMIT 50")
        if not rows:
            print("No suspicious nodes found.")
        else:
            print(f"Found {len(rows)} suspicious nodes:")
            for row in rows:
                print(f"  {row['entity_id']}: {row['name']} ({row['entity_type']})")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(find_suspicious_nodes())
