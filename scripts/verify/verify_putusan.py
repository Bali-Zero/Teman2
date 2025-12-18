import asyncio
import json

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def verify_putusan():
    print("🔍 Verifying Putusan Ingestion...")
    conn = await asyncpg.connect(DATABASE_URL)

    # Check for documents in litigation_oracle collection (via metadata)
    rows = await conn.fetch(
        """
        SELECT title, summary, metadata
        FROM parent_documents
        WHERE metadata->>'collection' = 'litigation_oracle'
    """
    )

    print(f"Found {len(rows)} Putusan documents.")
    for row in rows:
        print(f"\n📄 Title: {row['title']}")
        print(f"   Summary: {row['summary']}")
        meta = json.loads(row["metadata"])
        print(f"   Verdict: {meta.get('verdict', 'N/A')}")
        print(f"   Case Number: {meta.get('number', 'N/A')}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify_putusan())
