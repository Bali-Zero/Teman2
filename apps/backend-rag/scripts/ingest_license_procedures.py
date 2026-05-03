#!/usr/bin/env python3
"""
Ingest SLHS and NPBBKC license procedure files into training_conversations_hybrid collection.

This script ONLY adds the new procedure files without recreating the collection.
Uses direct HTTP requests with dense + BM25 sparse vectors (hybrid).

Run LOCALLY:
    cd apps/backend-rag && python scripts/ingest_license_procedures.py
"""

import asyncio
import hashlib
import logging
import os
import sys
import time
from pathlib import Path

import requests

# Load .env from backend-rag root
script_dir = Path(__file__).parent
backend_rag_root = script_dir.parent
dotenv_path = backend_rag_root / ".env"

# Add backend to path
sys.path.insert(0, str(backend_rag_root / "backend"))

from dotenv import load_dotenv

load_dotenv(dotenv_path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# New license procedure files to ingest
FILES_TO_INGEST = [
    "training-data/licenses/licenses_003_slhs_procedure.md",
    "training-data/licenses/licenses_004_npbbkc_procedure.md",
]

COLLECTION_NAME = "training_conversations_hybrid"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def upsert_point(
    point_id: int, dense_vector: list, sparse_indices: list, sparse_values: list, payload: dict
) -> bool:
    """Upsert a single point to Qdrant using direct HTTP request."""
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points"
    headers = {"Content-Type": "application/json", "api-key": QDRANT_API_KEY}
    data = {
        "points": [
            {
                "id": point_id,
                "vector": {
                    "dense": dense_vector,
                    "bm25": {"indices": sparse_indices, "values": sparse_values},
                },
                "payload": payload,
            }
        ]
    }

    for attempt in range(3):
        try:
            resp = requests.put(url, headers=headers, json=data, timeout=30)
            if resp.status_code == 200:
                return True
            else:
                logger.warning(f"  ⚠️ Qdrant returned {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            if attempt < 2:
                wait_time = 5 * (attempt + 1)
                logger.warning(f"  ⚠️ Retry {attempt + 1}/3 (waiting {wait_time}s): {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"  ❌ Failed after 3 attempts: {e}")
                return False
    return False


async def search_test(query: str, embedder, bm25) -> dict:
    """Test a search query against the collection."""
    dense_vector = await embedder.generate_query_embedding(query)
    bm25.generate_sparse_vector(query)

    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/query"
    headers = {"Content-Type": "application/json", "api-key": QDRANT_API_KEY}

    data = {
        "query": dense_vector,
        "using": "dense",
        "limit": 5,
        "with_payload": ["text", "title", "category", "source"],
    }

    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"Search failed: {resp.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {}


async def ingest_files():
    """Ingest new license procedure files."""
    from core.bm25_vectorizer import BM25Vectorizer
    from core.chunker import TextChunker
    from core.embeddings import create_embeddings_generator

    logger.info("=" * 60)
    logger.info("LICENSE PROCEDURES INGESTION")
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info(f"Qdrant: {QDRANT_URL}")
    logger.info("=" * 60)

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set in .env! Required for embeddings.")
        return

    embedder = create_embeddings_generator(api_key=openai_key, provider="openai")
    bm25 = BM25Vectorizer()
    chunker = TextChunker(chunk_size=1500, chunk_overlap=200)

    base_path = backend_rag_root
    total_chunks = 0
    total_upserted = 0

    for file_path in FILES_TO_INGEST:
        full_path = base_path / file_path

        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            continue

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing: {file_path}")

        # Read file content
        content = full_path.read_text(encoding="utf-8")
        logger.info(f"  File size: {len(content)} chars (~{len(content.split())} words)")

        # Extract metadata from filename
        filename = full_path.stem
        parts = filename.split("_")
        category = parts[0] if parts else "licenses"

        # Extract title from markdown content
        title = filename
        for line in content.split("\n")[:10]:
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                break
            if line.startswith("**TITLE:"):
                title = line.replace("**TITLE:", "").replace("**", "").strip()
                break

        # Chunk the content
        chunks = chunker.chunk_text(content)
        logger.info(f"  Created {len(chunks)} chunks")

        for idx, chunk_text in enumerate(chunks):
            # Generate embeddings
            dense_embedding = await embedder.generate_query_embedding(chunk_text)

            # Generate BM25 sparse vector
            sparse_result = bm25.generate_sparse_vector(chunk_text)
            sparse_indices = sparse_result["indices"]
            sparse_values = sparse_result["values"]

            # Create unique ID based on file + chunk index
            point_id = hashlib.md5(f"{file_path}_{idx}".encode()).hexdigest()
            point_id_int = int(point_id[:16], 16)

            # Build metadata
            payload = {
                "source": file_path,
                "filename": filename,
                "title": title,
                "category": category,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "text": chunk_text,
                "data_version": "bali_zero_2025_license_procedures",
            }

            # Upsert to Qdrant
            success = upsert_point(
                point_id_int, dense_embedding, sparse_indices, sparse_values, payload
            )
            if success:
                total_upserted += 1
                if (idx + 1) % 5 == 0:
                    logger.info(f"  ✅ Progress: {idx + 1}/{len(chunks)} chunks")
            else:
                logger.error(f"  ❌ Failed chunk {idx}")

            total_chunks += 1
            time.sleep(0.3)  # Small delay between requests

        logger.info("  ✅ File complete")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"INGESTION COMPLETE: {total_upserted}/{total_chunks} chunks upserted")
    logger.info(f"Collection: {COLLECTION_NAME}")

    # Run test queries
    logger.info(f"\n{'=' * 60}")
    logger.info("RUNNING TEST QUERIES")
    logger.info("=" * 60)

    test_queries = [
        "Procedura SLHS Bali passo per passo?",
        "Documenti NPBBKC restaurant?",
        "Quanto tempo SLHS?",
        "Come ottengo SLHS license Bali?",
        "Step-by-step NPBBKC alcohol license procedure",
        "Costi licenza alcolici Bali ristorante",
    ]

    for query in test_queries:
        logger.info(f"\n🔍 Query: '{query}'")
        result = await search_test(query, embedder, bm25)
        points = (
            result.get("result", {}).get("points", [])
            if isinstance(result.get("result"), dict)
            else result.get("result", [])
        )
        if points:
            for i, point in enumerate(points[:3]):
                payload = point.get("payload", {})
                score = point.get("score", 0)
                title = payload.get("title", "N/A")
                text_preview = payload.get("text", "")[:150].replace("\n", " ")
                logger.info(f"  #{i + 1} [score={score:.4f}] {title}")
                logger.info(f"      {text_preview}...")
        else:
            logger.info("  ❌ No results found")

    logger.info(f"\n{'=' * 60}")
    logger.info("ALL DONE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(ingest_files())
