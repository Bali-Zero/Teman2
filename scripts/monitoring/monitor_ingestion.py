import asyncio
import os
import time
from datetime import datetime

import asyncpg
import requests

# Configuration
DB_URL = os.getenv(
    "DATABASE_URL", "postgres://antonellosiano@localhost:5432/nuzantara_dev"
)
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_API_KEY:
    raise OSError("QDRANT_API_KEY environment variable is required")
COLLECTIONS = [
    "legal_unified",
    "visa_oracle",
    "tax_genius",
    "litigation_oracle",
    "kbli_unified",
]


async def get_db_counts(pool):
    async with pool.acquire() as conn:
        docs = await conn.fetchval("SELECT COUNT(*) FROM parent_documents")
        entities = await conn.fetchval("SELECT COUNT(*) FROM kg_entities")
        relations = await conn.fetchval("SELECT COUNT(*) FROM kg_relationships")
    return docs, entities, relations


def get_qdrant_counts():
    total_points = 0
    details = {}
    headers = {"api-key": QDRANT_API_KEY}
    for col in COLLECTIONS:
        try:
            # Use count endpoint
            res = requests.post(
                f"{QDRANT_URL}/collections/{col}/points/count",
                json={"exact": True},
                headers=headers,
            )
            if res.status_code == 200:
                count = res.json()["result"]["count"]
                total_points += count
                details[col] = count
            else:
                details[col] = f"Err {res.status_code}"
        except Exception:
            details[col] = "Error"
    return total_points, details


async def monitor():
    print("🚀 Nuzantara Ingestion Monitor")
    print("Press Ctrl+C to stop")
    print("-" * 60)

    try:
        pool = await asyncpg.create_pool(DB_URL)
    except Exception as e:
        print(f"❌ DB Connection Failed: {e}")
        return

    start_docs = 0
    start_time = time.time()

    try:
        while True:
            # Get stats
            docs, entities, relations = await get_db_counts(pool)
            q_total, q_details = get_qdrant_counts()

            # Calculate speed
            elapsed = time.time() - start_time
            if start_docs == 0:
                start_docs = docs
            new_docs = docs - start_docs
            speed = (new_docs / elapsed) * 60 if elapsed > 0 else 0

            # Clear screen (ANSI)
            print("\033[2J\033[H", end="")

            print(
                f"🚀 Nuzantara Ingestion Monitor | {datetime.now().strftime('%H:%M:%S')}"
            )
            print("=" * 60)
            print(f"📚 Documents Processed:  {docs} \t(+{new_docs})")
            print(f"⚡ Speed:                {speed:.1f} docs/min")
            print("-" * 60)
            print("🧠 Knowledge Graph:")
            print(f"   • Entities:           {entities}")
            print(f"   • Relationships:      {relations}")
            print("-" * 60)
            print(f"💾 Vector Database (Qdrant): {q_total} chunks")
            for col, count in q_details.items():
                print(f"   • {col:<20} {count}")
            print("=" * 60)

            await asyncio.sleep(2)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        pass
