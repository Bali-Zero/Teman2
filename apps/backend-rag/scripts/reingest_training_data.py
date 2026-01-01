#!/usr/bin/env python3
"""
Re-ingest corrected training data files into training_conversations_hybrid collection.

Run on Fly.io:
    fly ssh console -a nuzantara-rag
    cd /app && python scripts/reingest_training_data.py
"""

import asyncio
import hashlib
import logging
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Files to re-ingest (corrected with Bali Zero 2025 prices)
FILES_TO_REINGEST = [
    "training-data/business/business_028_pt_pma_restaurant_setup.md",
    "training-data/business/business_029_pt_pma_villa_rental.md",
    "training-data/business/business_032_pt_lokal_vs_pt_pma.md",
    "training-data/visa/visa_003_e28a_investor_kitas.md",
]

COLLECTION_NAME = "training_conversations_hybrid"


async def reingest_files():
    """Re-ingest corrected training data files."""
    from dotenv import load_dotenv
    load_dotenv()

    from core.bm25_vectorizer import BM25Vectorizer
    from core.chunker import TextChunker
    from core.embeddings import create_embeddings_generator
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, SparseVector

    # Initialize services
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        logger.error("QDRANT_URL not set")
        return

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    embedder = create_embeddings_generator()
    bm25 = BM25Vectorizer()
    chunker = TextChunker(chunk_size=1500, chunk_overlap=200)

    # Get base path
    base_path = Path(__file__).parent.parent

    total_chunks = 0
    total_upserted = 0

    for file_path in FILES_TO_REINGEST:
        full_path = base_path / file_path

        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {file_path}")

        # Read file content
        content = full_path.read_text(encoding="utf-8")

        # Extract metadata from filename
        filename = full_path.stem
        parts = filename.split("_")
        category = parts[0] if parts else "unknown"  # business, visa

        # Chunk the content
        chunks = chunker.chunk_text(content)
        logger.info(f"  Created {len(chunks)} chunks")

        # Delete existing chunks from this file
        # We use filename as part of the ID to find existing points
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]

        # Prepare points for upsert
        points = []
        for idx, chunk_text in enumerate(chunks):
            # Generate embeddings
            dense_embedding = embedder.generate_query_embedding(chunk_text)

            # Generate BM25 sparse vector
            sparse_indices, sparse_values = bm25.encode(chunk_text)

            # Create unique ID based on file + chunk index
            point_id = hashlib.md5(f"{file_path}_{idx}".encode()).hexdigest()
            point_id_int = int(point_id[:16], 16)

            # Build metadata
            metadata = {
                "source": file_path,
                "filename": filename,
                "category": category,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "text": chunk_text,
                "data_version": "bali_zero_2025_corrected",
            }

            point = PointStruct(
                id=point_id_int,
                vector={
                    "dense": dense_embedding,
                    "bm25": SparseVector(indices=sparse_indices, values=sparse_values),
                },
                payload=metadata,
            )
            points.append(point)

        total_chunks += len(chunks)

        # Upsert to Qdrant
        if points:
            try:
                client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points,
                    wait=True,
                )
                total_upserted += len(points)
                logger.info(f"  ✅ Upserted {len(points)} chunks to {COLLECTION_NAME}")
            except Exception as e:
                logger.error(f"  ❌ Upsert failed: {e}")

    logger.info(f"\n{'='*60}")
    logger.info(f"COMPLETED: {total_upserted}/{total_chunks} chunks upserted")
    logger.info(f"Collection: {COLLECTION_NAME}")


if __name__ == "__main__":
    asyncio.run(reingest_files())
