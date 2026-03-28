#!/usr/bin/env python3
"""
TKA Embeddings Generator for Qdrant
Generates embeddings for KBLI TKA (Tenaga Kerja Asing) positions
for semantic search capabilities.

Usage:
    python generate_tka_embeddings.py

Environment variables:
    OPENAI_API_KEY - Required for embeddings generation
    QDRANT_URL - Qdrant server URL (default: http://localhost:6333)
    QDRANT_API_KEY - Optional Qdrant API key
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any

import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "kbli_tka"
VECTOR_SIZE = 1536  # OpenAI text-embedding-3-small
BATCH_SIZE = 100  # Process embeddings in batches
UPLOAD_BATCH_SIZE = 50  # Upload to Qdrant in batches


class OpenAIEmbedder:
    """OpenAI embedding generator."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)

        MAX_BATCH_SIZE = 2048  # OpenAI API limit
        all_embeddings = []

        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            logger.info(
                f"Generating embeddings batch {i // MAX_BATCH_SIZE + 1}: {len(batch)} texts"
            )

            response = await client.embeddings.create(model=self.model, input=batch)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            # Rate limiting - small delay between batches
            if i + MAX_BATCH_SIZE < len(texts):
                await asyncio.sleep(0.5)

        logger.info(f"✅ Generated {len(all_embeddings)} embeddings ({self.dimensions} dims)")
        return all_embeddings


class QdrantClient:
    """Simple Qdrant client for upserting points."""

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self.url = (url or os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL).rstrip("/")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.timeout = 60.0

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.url}/collections/{collection_name}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Error checking collection: {e}")
                return False

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = VECTOR_SIZE,
        distance: str = "Cosine",
    ) -> bool:
        """Create a new collection."""
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "vectors": {
                        "size": vector_size,
                        "distance": distance,
                    }
                }
                response = await client.put(
                    f"{self.url}/collections/{collection_name}",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                logger.info(f"✅ Created collection '{collection_name}'")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to create collection: {e}")
                return False

    async def upsert_points(
        self,
        collection_name: str,
        points: list[dict[str, Any]],
        batch_size: int = UPLOAD_BATCH_SIZE,
    ) -> dict[str, Any]:
        """Upsert points in batches."""
        total = len(points)
        total_upserted = 0
        errors = []

        async with httpx.AsyncClient() as client:
            for i in range(0, total, batch_size):
                batch = points[i : i + batch_size]

                payload = {"points": batch}
                url = f"{self.url}/collections/{collection_name}/points"

                try:
                    response = await client.put(
                        url,
                        json=payload,
                        headers=self._get_headers(),
                        params={"wait": "true"},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    total_upserted += len(batch)
                    logger.info(
                        f"📤 Upserted batch {i // batch_size + 1}: {len(batch)}/{total} points"
                    )
                except Exception as e:
                    error_msg = str(e)
                    if hasattr(e, "response") and hasattr(e.response, "text"):
                        error_msg = f"{error_msg}: {e.response.text}"
                    errors.append(error_msg)
                    logger.error(f"❌ Batch {i // batch_size + 1} failed: {error_msg}")

                # Small delay between batches
                if i + batch_size < total:
                    await asyncio.sleep(0.2)

        return {
            "success": len(errors) == 0,
            "total_upserted": total_upserted,
            "errors": errors,
        }

    async def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """Get collection statistics."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.url}/collections/{collection_name}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json().get("result", {})
                return {
                    "exists": True,
                    "points_count": data.get("points_count", 0),
                    "vector_size": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("size", 0),
                    "distance": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("distance", "Unknown"),
                }
            except Exception as e:
                return {"exists": False, "error": str(e)}


def create_tka_text(kbli: dict[str, Any]) -> str:
    """Create descriptive text for TKA positions."""
    code = kbli["code"]
    title = kbli["title"]
    category_name = kbli["categoryName"]
    category_id = kbli["categoryId"]
    total_positions = kbli["totalInCategory"]
    selected_positions = kbli["selectedForThisCode"]
    isco_groups = kbli.get("iscoGroupsSelected", [])
    positions = kbli.get("relevantPositions", [])

    # Build positions text
    positions_text = []
    for pos in positions:
        isco = pos.get("isco", "")
        title_en = pos.get("titleEn", "")
        title_id = pos.get("titleId", "")
        positions_text.append(f"- {title_en} ({title_id}) - ISCO {isco}")

    text = f"""KBLI {code} - {title}
Category: {category_name} (ID: {category_id})
Foreign Worker Eligible Positions (TKA):
{chr(10).join(positions_text)}
Total positions in category: {total_positions}
Selected positions: {selected_positions}
Methodology: ISCO-based selection from Kepmen 228/2019
ISCO Groups: {", ".join(isco_groups)}
"""
    return text.strip()


import uuid


def create_qdrant_point(kbli: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    """Create a Qdrant point from KBLI data."""
    code = kbli["code"]

    # Create positions array for payload
    positions = [
        {
            "isco": pos.get("isco", ""),
            "title_en": pos.get("titleEn", ""),
            "title_id": pos.get("titleId", ""),
        }
        for pos in kbli.get("relevantPositions", [])
    ]

    # Create descriptive text
    text = create_tka_text(kbli)

    # Generate a deterministic UUID from the KBLI code
    # This ensures the same KBLI always gets the same ID
    id_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"kbli-tka-{code}")

    point = {
        "id": str(id_uuid),
        "vector": embedding,
        "payload": {
            "kbli_code": code,
            "kbli_title": kbli["title"],
            "category_id": kbli["categoryId"],
            "category_name": kbli["categoryName"],
            "total_positions": kbli["totalInCategory"],
            "selected_positions": kbli["selectedForThisCode"],
            "isco_groups": kbli.get("iscoGroupsSelected", []),
            "positions": positions,
            "text": text,
        },
    }
    return point


async def load_tka_data(filepath: str) -> list[dict[str, Any]]:
    """Load TKA data from JSON file."""
    logger.info(f"Loading TKA data from {filepath}")
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    tka_assignments = data.get("tka_assignments", [])
    logger.info(f"✅ Loaded {len(tka_assignments)} KBLI entries with TKA positions")
    return tka_assignments


async def generate_embeddings_for_kbli(
    kbli_list: list[dict[str, Any]],
    embedder: OpenAIEmbedder,
) -> list[list[float]]:
    """Generate embeddings for all KBLI entries."""
    texts = [create_tka_text(kbli) for kbli in kbli_list]
    logger.info(f"Generating embeddings for {len(texts)} KBLI entries")

    embeddings = await embedder.generate_embeddings(texts)
    return embeddings


async def main():
    """Main function to generate and upload TKA embeddings."""
    start_time = time.time()

    # File path
    data_file = "/Users/nuzantara/Desktop/TKA_ISCO_FINAL.json"

    # Check if file exists
    if not os.path.exists(data_file):
        logger.error(f"❌ Data file not found: {data_file}")
        sys.exit(1)

    # Initialize clients
    try:
        embedder = OpenAIEmbedder()
        qdrant = QdrantClient()
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        sys.exit(1)

    logger.info(f"🔗 Qdrant URL: {qdrant.url}")
    logger.info(f"📦 Collection: {COLLECTION_NAME}")
    logger.info(f"🤖 Embedding model: {embedder.model} ({embedder.dimensions} dims)")

    # Step 1: Load TKA data
    kbli_list = await load_tka_data(data_file)

    if not kbli_list:
        logger.error("❌ No KBLI data found")
        sys.exit(1)

    # Step 2: Check/create collection
    collection_exists = await qdrant.collection_exists(COLLECTION_NAME)
    if not collection_exists:
        logger.info(f"Collection '{COLLECTION_NAME}' does not exist. Creating...")
        created = await qdrant.create_collection(COLLECTION_NAME)
        if not created:
            logger.error("❌ Failed to create collection")
            sys.exit(1)
    else:
        logger.info(f"✅ Collection '{COLLECTION_NAME}' already exists")

    # Step 3: Generate embeddings
    logger.info("\n" + "=" * 50)
    logger.info("STEP 1: Generating embeddings")
    logger.info("=" * 50)

    embeddings = await generate_embeddings_for_kbli(kbli_list, embedder)

    # Step 4: Create Qdrant points
    logger.info("\n" + "=" * 50)
    logger.info("STEP 2: Creating Qdrant points")
    logger.info("=" * 50)

    points = []
    for _i, (kbli, embedding) in enumerate(zip(kbli_list, embeddings, strict=False)):
        point = create_qdrant_point(kbli, embedding)
        points.append(point)

    logger.info(f"✅ Created {len(points)} Qdrant points")

    # Step 5: Upsert to Qdrant
    logger.info("\n" + "=" * 50)
    logger.info("STEP 3: Upserting to Qdrant")
    logger.info("=" * 50)

    result = await qdrant.upsert_points(COLLECTION_NAME, points)

    if result["success"]:
        logger.info(f"✅ Successfully upserted {result['total_upserted']} points")
    else:
        logger.error("❌ Upsert completed with errors")
        logger.error(f"Total upserted: {result['total_upserted']}")
        logger.error(f"Errors: {result['errors']}")

    # Step 6: Verify collection stats
    logger.info("\n" + "=" * 50)
    logger.info("STEP 4: Verification")
    logger.info("=" * 50)

    stats = await qdrant.get_collection_stats(COLLECTION_NAME)
    if stats.get("exists"):
        logger.info("📊 Collection statistics:")
        logger.info(f"   - Points count: {stats['points_count']}")
        logger.info(f"   - Vector size: {stats['vector_size']}")
        logger.info(f"   - Distance: {stats['distance']}")
    else:
        logger.warning(f"⚠️ Could not get collection stats: {stats.get('error')}")

    # Summary
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 50)
    logger.info("SUMMARY")
    logger.info("=" * 50)
    logger.info(f"✅ Total KBLI entries processed: {len(kbli_list)}")
    logger.info(f"✅ Total embeddings generated: {len(embeddings)}")
    logger.info(f"✅ Total points upserted: {result['total_upserted']}")
    logger.info(f"⏱️  Total time: {elapsed:.2f}s")
    logger.info(f"🔗 Collection: {COLLECTION_NAME}")

    return result["success"]


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
