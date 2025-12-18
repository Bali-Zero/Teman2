"""
Clean ricerca chunks from Qdrant and PostgreSQL before re-ingestion.
Only removes chunks with source="ricerca", preserves original 16k docs.
"""

import asyncio
import logging
import os
from pathlib import Path

import asyncpg
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Collections that may contain ricerca chunks
COLLECTIONS = [
    "tax_genius",
    "kbli_unified",
    "visa_oracle",
    "legal_unified",
    "bali_zero_pricing",
]


def delete_ricerca_from_qdrant(collection: str) -> int:
    """Delete all points with source='ricerca' from a collection."""
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    # Use scroll to find all ricerca points
    deleted = 0
    offset = None

    while True:
        # Scroll through points with filter
        scroll_body = {
            "filter": {"must": [{"key": "source", "match": {"value": "ricerca"}}]},
            "limit": 100,
            "with_payload": False,
            "with_vector": False,
        }
        if offset:
            scroll_body["offset"] = offset

        resp = requests.post(
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            headers=headers,
            json=scroll_body,
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error(f"Scroll failed for {collection}: {resp.text}")
            break

        data = resp.json().get("result", {})
        points = data.get("points", [])

        if not points:
            break

        # Delete these points
        point_ids = [p["id"] for p in points]
        delete_resp = requests.post(
            f"{QDRANT_URL}/collections/{collection}/points/delete",
            headers=headers,
            json={"points": point_ids},
            timeout=30,
        )

        if delete_resp.status_code == 200:
            deleted += len(point_ids)
            logger.info(f"   Deleted {len(point_ids)} points from {collection}")
        else:
            logger.error(f"Delete failed: {delete_resp.text}")

        offset = data.get("next_page_offset")
        if not offset:
            break

    return deleted


async def clean_postgres_ricerca(conn) -> int:
    """Delete ricerca records from parent_documents."""
    # Get count first
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM parent_documents WHERE metadata::text LIKE '%ricerca%'"
    )

    if count > 0:
        await conn.execute(
            "DELETE FROM parent_documents WHERE metadata::text LIKE '%ricerca%'"
        )
        logger.info(f"   Deleted {count} records from PostgreSQL")

    return count


async def main():
    logger.info("🧹 CLEANING RICERCA CHUNKS")
    logger.info("=" * 60)

    # 1. Clean Qdrant
    logger.info("\n📦 Cleaning Qdrant collections...")
    total_qdrant = 0
    for collection in COLLECTIONS:
        logger.info(f"\n   Collection: {collection}")
        deleted = delete_ricerca_from_qdrant(collection)
        total_qdrant += deleted

    logger.info(f"\n   Total deleted from Qdrant: {total_qdrant}")

    # 2. Clean PostgreSQL
    logger.info("\n🗄️  Cleaning PostgreSQL...")
    conn = await asyncpg.connect(DB_URL)
    try:
        total_pg = await clean_postgres_ricerca(conn)
    finally:
        await conn.close()

    logger.info("\n" + "=" * 60)
    logger.info("🏁 CLEANUP COMPLETE")
    logger.info(f"   Qdrant: {total_qdrant} chunks deleted")
    logger.info(f"   PostgreSQL: {total_pg} records deleted")
    logger.info("\nNow run: python scripts/ingest_ricerca.py")


if __name__ == "__main__":
    asyncio.run(main())
