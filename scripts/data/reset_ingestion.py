import asyncio
import asyncpg
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load env
load_dotenv(Path(__file__).parent.parent / "apps/backend-rag/.env")

DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv(
    "QDRANT_API_KEY", "QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
)

COLLECTIONS = [
    "legal_unified",
    "visa_oracle",
    "tax_genius",
    "litigation_oracle",
    "kbli_unified",
    "property_unified",
    "legal_unified_v2",  # Cleanup old experiment
]


async def reset_all():
    print("🚨 STARTING FULL RESET OF INGESTION DATA 🚨")
    print("===========================================")

    # 1. Postgres Cleanup
    print("\n🗑️  Cleaning Postgres Tables...")
    try:
        conn = await asyncpg.connect(DB_URL)
        await conn.execute("TRUNCATE TABLE parent_documents CASCADE;")
        await conn.execute("TRUNCATE TABLE kg_entities CASCADE;")
        await conn.execute("TRUNCATE TABLE kg_relationships CASCADE;")
        print(
            "   ✅ Postgres tables truncated (parent_documents, kg_entities, kg_relationships)"
        )
        await conn.close()
    except Exception as e:
        print(f"   ❌ Postgres Error: {e}")

    # 2. Qdrant Cleanup
    print("\n🗑️  Cleaning Qdrant Collections...")
    headers = {"api-key": QDRANT_API_KEY}

    for col in COLLECTIONS:
        try:
            resp = requests.delete(f"{QDRANT_URL}/collections/{col}", headers=headers)
            if resp.status_code == 200:
                print(f"   ✅ Deleted collection: {col}")
            elif resp.status_code == 404:
                print(f"   ⚠️ Collection not found (already deleted): {col}")
            else:
                print(f"   ❌ Failed to delete {col}: {resp.text}")
        except Exception as e:
            print(f"   ❌ Qdrant Error for {col}: {e}")

    print("\n✨ RESET COMPLETE. Ready for fresh ingestion.")


if __name__ == "__main__":
    asyncio.run(reset_all())
