import asyncio

import asyncpg

DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def check_kbli():
    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch(
            """
            SELECT title, metadata->>'collection' as collection
            FROM parent_documents
            WHERE title ILIKE '%KBLI%' OR summary ILIKE '%KBLI%'
        """
        )

        print(f"Found {len(rows)} potential KBLI documents:")
        for row in rows:
            print(f"- {row['title']} (Collection: {row['collection']})")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(check_kbli())
