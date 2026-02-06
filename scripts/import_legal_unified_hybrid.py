#!/usr/bin/env python3
"""
Import legal_unified_hybrid data from export file to Qdrant.
51,891 chunks of Indonesian legal documents.
"""

import os
import json
import asyncio

# Load env vars
env_path = "/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/.env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line and "[" not in line:
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip().strip('"')

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    OptimizersConfigDiff,
    HnswConfigDiff,
)

EXPORT_FILE = "/Users/antonellosiano/Projects/nuzantara/data/exports/legal_unified_hybrid_20260128_065200.json"
COLLECTION_NAME = "legal_unified_hybrid"
VECTOR_SIZE = 1536  # OpenAI text-embedding-3-small


async def main():
    print("=" * 70)
    print("IMPORT LEGAL_UNIFIED_HYBRID TO QDRANT")
    print("=" * 70)

    # Connect to Qdrant
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    print("\n[1/5] Connecting to Qdrant...")
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    print(f"      Connected: {qdrant_url[:50]}...")

    # Load export data
    print("\n[2/5] Loading export file...")
    with open(EXPORT_FILE, "r") as f:
        data = json.load(f)

    points = data.get("points", [])
    print(f"      Loaded {len(points):,} points from export")
    print(f"      Export date: {data.get('exported_at')}")

    # Check/create collection
    print(f"\n[3/5] Checking collection '{COLLECTION_NAME}'...")
    collections = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in collections:
        info = client.get_collection(COLLECTION_NAME)
        existing_points = info.points_count
        print(f"      Collection exists with {existing_points:,} points")

        if existing_points > 0:
            response = input("      ⚠️  Delete existing data? (y/N): ")
            if response.lower() == "y":
                client.delete_collection(COLLECTION_NAME)
                print("      Deleted existing collection")
            else:
                print("      Aborted.")
                return

    # Create collection with hybrid support (dense + sparse vectors)
    print("\n[4/5] Creating collection with hybrid vectors...")

    # Check if first point has vector
    sample_point = points[0] if points else {}
    has_vector = "vector" in sample_point

    if has_vector:
        print("      Export contains vectors - using them directly")
        vector_size = len(sample_point["vector"])
    else:
        print("      Export has NO vectors - will need to regenerate embeddings")
        print(f"      ⚠️  This requires OpenAI API calls for {len(points):,} chunks")
        response = input("      Continue without vectors (payload only)? (y/N): ")
        if response.lower() != "y":
            print("      Aborted. Need to add embedding generation.")
            return
        vector_size = VECTOR_SIZE

    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
        optimizers_config=OptimizersConfigDiff(
            indexing_threshold=20000,
        ),
        hnsw_config=HnswConfigDiff(
            m=16,
            ef_construct=100,
        ),
    )
    print(f"      Collection created: {COLLECTION_NAME}")

    # Import points in batches
    print(f"\n[5/5] Importing {len(points):,} points...")
    batch_size = 100
    imported = 0
    errors = 0

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]

        qdrant_points = []
        for p in batch:
            point_id = p.get("id")
            payload = p.get("payload", {})
            vector = p.get("vector")

            if vector:
                qdrant_points.append(
                    PointStruct(id=point_id, vector=vector, payload=payload)
                )
            else:
                # Create dummy vector for now (will need re-embedding)
                qdrant_points.append(
                    PointStruct(
                        id=point_id, vector=[0.0] * vector_size, payload=payload
                    )
                )

        try:
            client.upsert(collection_name=COLLECTION_NAME, points=qdrant_points)
            imported += len(qdrant_points)
        except Exception as e:
            errors += len(batch)
            print(f"      Error at batch {i}: {e}")

        if (i + batch_size) % 5000 == 0 or i + batch_size >= len(points):
            pct = (i + batch_size) / len(points) * 100
            print(f"      Progress: {imported:,}/{len(points):,} ({pct:.1f}%)")

    # Verify
    info = client.get_collection(COLLECTION_NAME)
    final_count = info.points_count

    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Points imported: {imported:,}")
    print(f"Points in collection: {final_count:,}")
    print(f"Errors: {errors}")
    print(f"Has vectors: {has_vector}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
