import asyncio
import os

import asyncpg
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DATABASE_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


async def purge_postgres():
    print("🗑️  Cleaning PostgreSQL...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)

        # Truncate tables with CASCADE to handle foreign keys
        tables = [
            "parent_documents",
            "kg_entities",
            "kg_relationships",
            "golden_routes",
            "query_route_clusters",
        ]

        for table in tables:
            # Check if table exists first
            exists = await conn.fetchval(f"SELECT to_regclass('public.{table}')")
            if exists:
                await conn.execute(f"TRUNCATE TABLE {table} CASCADE")
                print(f"   - Truncated {table}")
            else:
                print(f"   - Table {table} not found (skipping)")

        await conn.close()
        print("✅ PostgreSQL cleaned.")
    except Exception as e:
        print(f"❌ Error cleaning PostgreSQL: {e}")


def purge_qdrant():
    print("\n🗑️  Cleaning Qdrant...")
    headers = {"api-key": QDRANT_API_KEY}

    try:
        # List collections
        resp = requests.get(f"{QDRANT_URL}/collections", headers=headers)
        if resp.status_code != 200:
            print(f"❌ Error listing collections: {resp.text}")
            return

        collections = resp.json().get("result", {}).get("collections", [])

        if not collections:
            print("   - No collections found.")
            return

        for col in collections:
            name = col["name"]
            # Delete collection
            del_resp = requests.delete(
                f"{QDRANT_URL}/collections/{name}", headers=headers
            )
            if del_resp.status_code == 200:
                print(f"   - Deleted collection: {name}")
            else:
                print(f"   - Failed to delete {name}: {del_resp.text}")

        print("✅ Qdrant cleaned.")

    except Exception as e:
        print(f"❌ Error cleaning Qdrant: {e}")


async def main():
    print("⚠️  STARTING FULL SYSTEM PURGE ⚠️")
    print("This will delete all ingested data in DB and Vector Store.")
    print("5 seconds to abort (Ctrl+C)...")
    await asyncio.sleep(5)

    await purge_postgres()
    purge_qdrant()

    print("\n✨ System is clean and ready for new ingestion.")


if __name__ == "__main__":
    asyncio.run(main())
