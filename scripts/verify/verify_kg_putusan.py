import asyncio

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def verify_kg():
    print("🔍 Verifying KG Entities...")
    conn = await asyncpg.connect(DATABASE_URL)

    # Check for PERSON or ORG entities which likely come from Putusan
    rows = await conn.fetch(
        """
        SELECT name, type, description
        FROM kg_entities
        WHERE type IN ('PERSON', 'ORG', 'LAW')
        ORDER BY created_at DESC
        LIMIT 10
    """
    )

    for row in rows:
        print(f"[{row['type']}] {row['name']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify_kg())
