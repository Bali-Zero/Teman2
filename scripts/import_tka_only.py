#!/usr/bin/env python3
"""
Import only TKA/Kemnaker chunks to visa_oracle.
"""

import os
import sys
import json
import asyncio
import hashlib
import time

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

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
from qdrant_client.models import PointStruct

EXPORT_FILE = "/Users/antonellosiano/Projects/nuzantara/data/exports/legal_unified_hybrid_20260128_065200.json"
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
BATCH_SIZE = 50

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
    full_text = (text + " " + str(metadata)).lower()
    for keyword in TKA_KEYWORDS:
        if keyword.lower() in full_text:
            return True
    return False


async def main():
    print("=" * 60, flush=True)
    print("IMPORT TKA/KEMNAKER CHUNKS TO VISA_ORACLE", flush=True)
    print("=" * 60, flush=True)

    # Initialize clients
    print("\n[1/4] Initializing...", flush=True)
    qdrant = QdrantClient(
        url=os.environ.get("QDRANT_URL"), api_key=os.environ.get("QDRANT_API_KEY")
    )
    openai_client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    print("      Done", flush=True)

    # Load and filter TKA chunks
    print("\n[2/4] Loading and filtering TKA chunks...", flush=True)
    with open(EXPORT_FILE, "r") as f:
        data = json.load(f)

    all_points = data.get("points", [])
    print(f"      Total points: {len(all_points):,}", flush=True)

    tka_chunks = []
    for p in all_points:
        payload = p.get("payload", {})
        text = payload.get("text", "") or ""
        metadata = payload.get("metadata", {}) or {}

        if is_tka_related(text, metadata):
            tka_chunks.append(
                {
                    "text": text,
                    "metadata": {
                        **metadata,
                        "source_collection": "legal_unified_hybrid",
                        "category": "labor_law",
                        "subcategory": "tka_foreign_workers",
                    },
                }
            )

    print(f"      TKA chunks found: {len(tka_chunks):,}", flush=True)

    # Check visa_oracle
    print("\n[3/4] Checking visa_oracle...", flush=True)
    info = qdrant.get_collection("visa_oracle")
    print(f"      Current points: {info.points_count}", flush=True)

    # Import with embeddings
    print(f"\n[4/4] Importing {len(tka_chunks):,} TKA chunks...", flush=True)

    imported = 0
    errors = 0
    start_time = time.time()

    for i in range(0, len(tka_chunks), BATCH_SIZE):
        batch = tka_chunks[i : i + BATCH_SIZE]

        # Get texts
        texts = [c["text"][:8000] if c["text"] else "empty" for c in batch]

        # Generate embeddings
        try:
            response = await openai_client.embeddings.create(
                model=EMBEDDING_MODEL, input=texts
            )
            embeddings = [item.embedding for item in response.data]
        except Exception as e:
            print(f"      Embedding error at {i}: {e}", flush=True)
            errors += len(batch)
            continue

        # Create points with UUID IDs and named vectors
        import uuid

        points = []
        for idx, chunk in enumerate(batch):
            # Generate UUID from hash for consistency
            hash_bytes = hashlib.md5(chunk["text"].encode()).digest()
            point_uuid = str(uuid.UUID(bytes=hash_bytes))
            # visa_oracle uses named vectors: "dense" for embeddings
            points.append(
                PointStruct(
                    id=point_uuid,
                    vector={"dense": embeddings[idx]},  # Named vector
                    payload={"text": chunk["text"], "metadata": chunk["metadata"]},
                )
            )

        # Upsert
        try:
            qdrant.upsert(collection_name="visa_oracle", points=points)
            imported += len(points)
        except Exception as e:
            print(f"      Upsert error at {i}: {e}", flush=True)
            errors += len(points)

        # Progress
        if (i + BATCH_SIZE) % 500 == 0 or i + BATCH_SIZE >= len(tka_chunks):
            elapsed = time.time() - start_time
            pct = (i + BATCH_SIZE) / len(tka_chunks) * 100
            print(
                f"      Progress: {imported:,}/{len(tka_chunks):,} ({pct:.1f}%) - {elapsed:.0f}s",
                flush=True,
            )

    # Final
    info = qdrant.get_collection("visa_oracle")

    print("\n" + "=" * 60, flush=True)
    print("IMPORT COMPLETE", flush=True)
    print("=" * 60, flush=True)
    print(f"TKA chunks imported: {imported:,}", flush=True)
    print(f"Errors: {errors}", flush=True)
    print(f"visa_oracle total: {info.points_count:,} points", flush=True)
    print(f"Time: {(time.time() - start_time) / 60:.1f} minutes", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
