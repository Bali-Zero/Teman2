import asyncio
import asyncpg
import json
from collections import Counter

DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def analyze():
    try:
        conn = await asyncpg.connect(DB_URL)

        # Get total count
        total = await conn.fetchval("SELECT COUNT(*) FROM parent_documents")
        print(f"Total Documents in DB: {total}")

        # Get breakdown by collection (from metadata)
        rows = await conn.fetch("SELECT metadata FROM parent_documents")
        collections = Counter()
        types = Counter()

        for r in rows:
            meta = json.loads(r["metadata"])
            collections[meta.get("collection", "unknown")] += 1
            types[meta.get("type", "unknown")] += 1

        print("\nBy Collection:")
        for c, count in collections.most_common():
            print(f"  - {c}: {count}")

        print("\nBy Type:")
        for t, count in types.most_common():
            print(f"  - {t}: {count}")

        # List last 10 titles
        print("\nLast 10 Ingested Documents:")
        recents = await conn.fetch(
            "SELECT title FROM parent_documents ORDER BY id DESC LIMIT 10"
        )
        for r in recents:
            print(f"  - {r['title']}")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(analyze())
