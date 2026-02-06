#!/usr/bin/env python3
"""
Import data to Qdrant with embedding generation.
Supports legal_unified_hybrid and TKA chunks to visa_oracle.
"""

import os
import sys
import json
import asyncio
import hashlib
from typing import List, Dict
import time

# Load env vars
env_path = "/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/.env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line and "[" not in line:
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip().strip('"')

import openai
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    OptimizersConfigDiff,
)

# Config
EXPORT_FILE = "/Users/antonellosiano/Projects/nuzantara/data/exports/legal_unified_hybrid_20260128_065200.json"
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
BATCH_SIZE = 100  # For Qdrant upsert
EMBED_BATCH_SIZE = 50  # For OpenAI API (max 2048)

# TKA Keywords
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
]


def is_tka_related(text: str, metadata: dict) -> bool:
    """Check if content is TKA/Kemnaker related."""
    full_text = (text + " " + str(metadata)).lower()
    for keyword in TKA_KEYWORDS:
        if keyword.lower() in full_text:
            return True
    return False


def generate_point_id(text: str, prefix: str = "doc") -> str:
    """Generate unique point ID from text hash."""
    hash_str = hashlib.md5(text.encode()).hexdigest()[:16]
    return f"{prefix}_{hash_str}"


async def get_embeddings(
    texts: List[str], client: openai.AsyncOpenAI
) -> List[List[float]]:
    """Get embeddings for a batch of texts."""
    try:
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"      Embedding error: {e}")
        raise


async def import_collection(
    qdrant: QdrantClient,
    openai_client: openai.AsyncOpenAI,
    points: List[Dict],
    collection_name: str,
    point_prefix: str,
    create_collection: bool = True,
):
    """Import points to a collection with embedding generation."""

    print(f"\n{'=' * 60}")
    print(f"Importing to: {collection_name}")
    print(f"{'=' * 60}")
    print(f"Points to import: {len(points):,}")

    # Create collection if needed
    if create_collection:
        print(f"\nCreating collection '{collection_name}'...")
        try:
            qdrant.delete_collection(collection_name)
        except:
            pass

        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=20000,
            ),
        )
        print("Collection created.")

    # Process in batches
    imported = 0
    errors = 0
    start_time = time.time()

    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i : i + BATCH_SIZE]

        # Extract texts for embedding
        texts = []
        for p in batch:
            text = p.get("payload", {}).get("text", "") or p.get("text", "")
            # Truncate to ~8000 chars (model limit is ~8191 tokens)
            texts.append(text[:8000] if text else "empty")

        # Generate embeddings in sub-batches
        all_embeddings = []
        for j in range(0, len(texts), EMBED_BATCH_SIZE):
            embed_batch = texts[j : j + EMBED_BATCH_SIZE]
            try:
                embeddings = await get_embeddings(embed_batch, openai_client)
                all_embeddings.extend(embeddings)
            except Exception as e:
                print(f"      Failed to embed batch {j}: {e}")
                # Use zero vectors as fallback
                all_embeddings.extend([[0.0] * VECTOR_SIZE] * len(embed_batch))
                errors += len(embed_batch)

        # Create Qdrant points
        qdrant_points = []
        for idx, p in enumerate(batch):
            payload = p.get("payload", {})
            if not payload:
                payload = {"text": p.get("text", ""), "metadata": p.get("metadata", {})}

            text = payload.get("text", "") or p.get("text", "")
            point_id = p.get("id") or generate_point_id(text, point_prefix)

            # Ensure point_id is string (Qdrant accepts string or int)
            if isinstance(point_id, str) and not point_id.startswith(point_prefix):
                # Keep original ID format
                pass

            qdrant_points.append(
                PointStruct(id=point_id, vector=all_embeddings[idx], payload=payload)
            )

        # Upsert to Qdrant
        try:
            qdrant.upsert(collection_name=collection_name, points=qdrant_points)
            imported += len(qdrant_points)
        except Exception as e:
            print(f"      Upsert error at {i}: {e}")
            errors += len(qdrant_points)

        # Progress
        elapsed = time.time() - start_time
        rate = imported / elapsed if elapsed > 0 else 0
        eta = (len(points) - imported) / rate if rate > 0 else 0

        if (i + BATCH_SIZE) % 1000 == 0 or i + BATCH_SIZE >= len(points):
            pct = (i + BATCH_SIZE) / len(points) * 100
            print(
                f"      Progress: {imported:,}/{len(points):,} ({pct:.1f}%) | "
                f"{rate:.1f} pts/s | ETA: {eta / 60:.1f}m"
            )

    # Final stats
    info = qdrant.get_collection(collection_name)
    final_count = info.points_count

    print(f"\n✅ Import complete: {collection_name}")
    print(f"   Imported: {imported:,}")
    print(f"   Errors: {errors}")
    print(f"   Final count: {final_count:,}")
    print(f"   Time: {(time.time() - start_time) / 60:.1f} minutes")

    return imported, errors


async def main():
    print("=" * 70)
    print("IMPORT WITH EMBEDDING GENERATION")
    print("=" * 70)
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Vector size: {VECTOR_SIZE}")

    # Initialize clients
    print("\n[1/4] Initializing clients...")

    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")

    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY not found")
        return

    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    openai_client = openai.AsyncOpenAI(api_key=openai_api_key)

    print(f"      Qdrant: {qdrant_url[:50]}...")
    print("      OpenAI: ✅")

    # Load export data
    print("\n[2/4] Loading export data...")
    with open(EXPORT_FILE, "r") as f:
        data = json.load(f)

    all_points = data.get("points", [])
    print(f"      Total points: {len(all_points):,}")

    # Separate TKA chunks
    print("\n[3/4] Separating TKA/Kemnaker chunks...")
    tka_points = []
    legal_points = []

    for p in all_points:
        payload = p.get("payload", {})
        text = payload.get("text", "") or ""
        metadata = payload.get("metadata", {}) or {}

        if is_tka_related(text, metadata):
            # Enrich metadata for TKA
            enriched_payload = {
                "text": text,
                "metadata": {
                    **metadata,
                    "source_collection": "legal_unified_hybrid",
                    "category": "labor_law",
                    "subcategory": "tka_foreign_workers",
                },
            }
            tka_points.append({"id": p.get("id"), "payload": enriched_payload})

        # All points go to legal_unified_hybrid
        legal_points.append(p)

    print(f"      Legal points: {len(legal_points):,}")
    print(f"      TKA points: {len(tka_points):,}")

    # Estimate cost
    total_chunks = len(legal_points) + len(tka_points)
    est_tokens = total_chunks * 500  # avg tokens per chunk
    est_cost = est_tokens / 1_000_000 * 0.02  # $0.02 per 1M tokens

    print(
        f"\n      Estimated cost: ~${est_cost:.2f} ({est_tokens / 1_000_000:.1f}M tokens)"
    )

    # Auto-confirm if --yes flag
    if "--yes" not in sys.argv:
        response = input("\n      Proceed with import? (y/N): ")
        if response.lower() != "y":
            print("      Aborted.")
            return
    else:
        print("\n      Auto-confirmed (--yes flag)")

    # Import legal_unified_hybrid
    print("\n[4/4] Starting imports...")

    legal_imported, legal_errors = await import_collection(
        qdrant=qdrant,
        openai_client=openai_client,
        points=legal_points,
        collection_name="legal_unified_hybrid",
        point_prefix="legal",
        create_collection=True,
    )

    # Import TKA to visa_oracle (append, don't recreate)
    # First check if visa_oracle exists
    try:
        info = qdrant.get_collection("visa_oracle")
        print(f"\nvisa_oracle exists with {info.points_count} points")
        create_visa = False
    except:
        print("\nvisa_oracle doesn't exist, will create")
        create_visa = True

    tka_imported, tka_errors = await import_collection(
        qdrant=qdrant,
        openai_client=openai_client,
        points=tka_points,
        collection_name="visa_oracle",
        point_prefix="tka",
        create_collection=create_visa,
    )

    # Final summary
    print("\n" + "=" * 70)
    print("IMPORT COMPLETE - SUMMARY")
    print("=" * 70)
    print(f"legal_unified_hybrid: {legal_imported:,} imported, {legal_errors} errors")
    print(f"visa_oracle (TKA):    {tka_imported:,} imported, {tka_errors} errors")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
