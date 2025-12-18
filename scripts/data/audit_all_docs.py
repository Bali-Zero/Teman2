import asyncio

import asyncpg

DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def list_all_docs():
    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch(
            """
            SELECT title, metadata->>'collection' as collection, metadata->>'source_file' as filename
            FROM parent_documents
            ORDER BY collection, title
        """
        )

        print(f"Total Documents: {len(rows)}")
        print("-" * 80)
        print(f"{'Collection':<20} | {'Filename':<40} | {'Title'}")
        print("-" * 80)
        for row in rows:
            coll = row["collection"] or "N/A"
            fname = row["filename"] or "N/A"
            title = row["title"] or "N/A"
            print(f"{coll:<20} | {fname[:40]:<40} | {title[:50]}")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(list_all_docs())
