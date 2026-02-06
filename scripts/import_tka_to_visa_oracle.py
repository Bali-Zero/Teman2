#!/usr/bin/env python3
"""
Extract TKA/Kemnaker chunks from legal_unified_hybrid export
and add them to visa_oracle collection.
"""

import os
import json
import asyncio
import hashlib
from datetime import datetime

# Load env vars
env_path = "/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/.env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line and "[" not in line:
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip().strip('"')

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

EXPORT_FILE = "/Users/antonellosiano/Projects/nuzantara/data/exports/legal_unified_hybrid_20260128_065200.json"
COLLECTION_NAME = "visa_oracle"

# Keywords to identify TKA/Kemnaker content
TKA_KEYWORDS = [
    "TKA",
    "Tenaga Kerja Asing",
    "tenaga kerja asing",
    "RPTKA",
    "Rencana Penggunaan Tenaga Kerja Asing",
    "IMTA",
    "Izin Mempekerjakan Tenaga Kerja Asing",
    "Kemnaker",
    "KEMNAKER",
    "Kementerian Ketenagakerjaan",
    "ketenagakerjaan",
    "Ketenagakerjaan",
    "pekerja asing",
    "Pekerja Asing",
    "foreign worker",
    "Foreign Worker",
    "expatriate worker",
    "expat worker",
    "work permit",
    "izin kerja",
]


def is_tka_related(text: str, metadata: dict) -> bool:
    """Check if content is TKA/Kemnaker related."""
    full_text = text + " " + str(metadata)
    for keyword in TKA_KEYWORDS:
        if keyword in full_text:
            return True
    return False


def generate_point_id(text: str, prefix: str = "tka") -> str:
    """Generate unique point ID from text hash."""
    hash_str = hashlib.md5(text.encode()).hexdigest()[:12]
    return f"{prefix}_{hash_str}"


async def main():
    print("=" * 70)
    print("IMPORT TKA/KEMNAKER CHUNKS TO VISA_ORACLE")
    print("=" * 70)

    # Connect to Qdrant
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    print("\n[1/5] Connecting to Qdrant...")
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    print(f"      Connected: {qdrant_url[:50]}...")

    # Check visa_oracle exists
    print(f"\n[2/5] Checking '{COLLECTION_NAME}' collection...")
    try:
        info = client.get_collection(COLLECTION_NAME)
        existing_points = info.points_count
        print(f"      Collection exists: {existing_points} points")
    except Exception as e:
        print(f"      ERROR: Collection doesn't exist: {e}")
        return

    # Get vector config from existing collection
    vector_size = info.config.params.vectors.size
    print(f"      Vector size: {vector_size}")

    # Load export and filter TKA content
    print("\n[3/5] Loading and filtering TKA/Kemnaker content...")
    with open(EXPORT_FILE, "r") as f:
        data = json.load(f)

    points = data.get("points", [])
    print(f"      Total points in export: {len(points):,}")

    tka_chunks = []
    for p in points:
        payload = p.get("payload", {})
        text = payload.get("text", "") or ""
        metadata = payload.get("metadata", {}) or {}

        if is_tka_related(text, metadata):
            # Enrich metadata
            enriched_metadata = {
                **metadata,
                "source_collection": "legal_unified_hybrid",
                "category": "labor_law",
                "subcategory": "tka_foreign_workers",
                "imported_at": datetime.now().isoformat(),
            }

            tka_chunks.append(
                {
                    "id": p.get("id"),
                    "text": text,
                    "metadata": enriched_metadata,
                    "vector": p.get("vector"),
                }
            )

    print(f"      Found {len(tka_chunks):,} TKA/Kemnaker chunks")

    if not tka_chunks:
        print("      No TKA chunks found. Exiting.")
        return

    # Show sample
    print("\n      Sample TKA chunk:")
    sample = tka_chunks[0]
    print(f"        Text: {sample['text'][:100]}...")
    print(f"        Has vector: {sample['vector'] is not None}")

    # Confirm import
    response = input(f"\n      Import {len(tka_chunks)} chunks to visa_oracle? (y/N): ")
    if response.lower() != "y":
        print("      Aborted.")
        return

    # Import to visa_oracle
    print(f"\n[4/5] Importing {len(tka_chunks):,} chunks to visa_oracle...")

    has_vectors = tka_chunks[0].get("vector") is not None
    batch_size = 50
    imported = 0
    skipped = 0
    errors = 0

    for i in range(0, len(tka_chunks), batch_size):
        batch = tka_chunks[i : i + batch_size]

        qdrant_points = []
        for chunk in batch:
            # Generate new ID to avoid conflicts
            point_id = generate_point_id(chunk["text"])

            payload = {
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            }

            if has_vectors and chunk.get("vector"):
                qdrant_points.append(
                    PointStruct(id=point_id, vector=chunk["vector"], payload=payload)
                )
            else:
                # Skip chunks without vectors (need re-embedding)
                skipped += 1
                continue

        if qdrant_points:
            try:
                client.upsert(collection_name=COLLECTION_NAME, points=qdrant_points)
                imported += len(qdrant_points)
            except Exception as e:
                errors += len(qdrant_points)
                print(f"      Error at batch {i}: {e}")

        if (i + batch_size) % 500 == 0 or i + batch_size >= len(tka_chunks):
            pct = (i + batch_size) / len(tka_chunks) * 100
            print(
                f"      Progress: {imported:,} imported, {skipped} skipped ({pct:.1f}%)"
            )

    # Verify
    info = client.get_collection(COLLECTION_NAME)
    final_count = info.points_count

    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"TKA chunks found: {len(tka_chunks):,}")
    print(f"Chunks imported: {imported:,}")
    print(f"Chunks skipped (no vector): {skipped}")
    print(f"Errors: {errors}")
    print(f"Final visa_oracle points: {final_count:,}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
