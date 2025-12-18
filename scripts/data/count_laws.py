import asyncio

import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Force correct URL for local verification (using current user as role)
DATABASE_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def count_laws():
    try:
        conn = await asyncpg.connect(DATABASE_URL)

        # Count total parent documents
        count = await conn.fetchval("SELECT COUNT(*) FROM parent_documents")

        # Get a few examples of titles if possible
        examples = await conn.fetch("SELECT title FROM parent_documents LIMIT 5")

        print(f"Total Laws/Parent Documents in PostgreSQL: {count}")
        if count > 0:
            print("\nExamples:")
            for row in examples:
                print(f"- {row['title']}")

        await conn.close()
    except Exception as e:
        print(f"Error connecting to database: {e}")


if __name__ == "__main__":
    asyncio.run(count_laws())
