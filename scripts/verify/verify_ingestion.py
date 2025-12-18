import asyncio

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def verify():
    print("🔍 Verifying Ingestion Results...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)

        # 1. Parent Documents
        row = await conn.fetchrow("SELECT COUNT(*) FROM parent_documents")
        print(f"📄 Parent Documents: {row['count']}")

        # 2. KG Entities
        row = await conn.fetchrow("SELECT COUNT(*) FROM kg_entities")
        print(f"🧠 KG Entities: {row['count']}")

        # 3. KG Relationships
        row = await conn.fetchrow("SELECT COUNT(*) FROM kg_relationships")
        print(f"🔗 KG Relationships: {row['count']}")

        # 4. Check a sample document
        row = await conn.fetchrow("SELECT title, summary FROM parent_documents LIMIT 1")
        if row:
            print(
                f"\n📝 Sample Document:\n   Title: {row['title']}\n   Summary: {row['summary'][:100]}..."
            )

        await conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(verify())
