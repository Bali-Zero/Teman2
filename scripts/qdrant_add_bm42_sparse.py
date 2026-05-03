"""
Qdrant BM42 Sparse Vector Batch Upsert

Adds BM42 sparse vectors to existing dense-only collections.
Does NOT re-embed dense vectors — only adds sparse alongside.

Usage:
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/qdrant_add_bm42_sparse.py [--collection NAME] [--batch-size 100]

Architecture:
    1. Scroll all points from collection (with payload text)
    2. Generate BM42 sparse embeddings via FastEmbed
    3. Upsert sparse vectors with same point IDs (preserves dense)
"""

import argparse
import asyncio
import logging
import os
import time

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SPARSE_VECTOR_NAME = "bm42"
BM42_MODEL = "Qdrant/bm42-all-minilm-l6-v2-attentions"


def get_text_from_payload(payload: dict) -> str:
    """Extract text from various payload formats."""
    for key in ["content", "text", "chunk_text", "page_content", "description", "title"]:
        if key in payload and isinstance(payload[key], str) and payload[key].strip():
            return payload[key]
    # Fallback: concatenate all string values
    texts = [str(v) for v in payload.values() if isinstance(v, str) and len(v) > 10]
    return " ".join(texts[:3]) if texts else ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", help="Single collection to process (default: all)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for upsert")
    parser.add_argument("--dry-run", action="store_true", help="Count only, don't upsert")
    args = parser.parse_args()

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    if not url or not api_key:
        logger.error("Set QDRANT_URL and QDRANT_API_KEY env vars")
        return

    client = QdrantClient(url=url, api_key=api_key, timeout=120)
    bm42 = SparseTextEmbedding(model_name=BM42_MODEL)

    # Get collections
    if args.collection:
        collections = [args.collection]
    else:
        result = client.get_collections()
        collections = [c.name for c in result.collections]

    logger.info(f"Processing {len(collections)} collections")

    for coll_name in collections:
        logger.info(f"\n{'='*60}")
        logger.info(f"Collection: {coll_name}")

        # Check if sparse already configured
        coll_info = client.get_collection(coll_name)
        sparse_config = coll_info.config.params.sparse_vectors or {}

        if SPARSE_VECTOR_NAME not in sparse_config:
            logger.info(f"Adding sparse vector config '{SPARSE_VECTOR_NAME}'...")
            if not args.dry_run:
                client.update_collection(
                    collection_name=coll_name,
                    sparse_vectors_config={
                        SPARSE_VECTOR_NAME: models.SparseVectorParams(
                            modifier=models.Modifier.IDF,
                        ),
                    },
                )
            logger.info("Sparse config added")

        # Scroll and process
        total = coll_info.points_count
        logger.info(f"Total points: {total}")

        if args.dry_run:
            logger.info("DRY RUN — skipping upsert")
            continue

        processed = 0
        offset = None
        batch_points = []
        start_time = time.time()

        while True:
            result = client.scroll(
                collection_name=coll_name,
                limit=args.batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            points, next_offset = result

            if not points:
                break

            for point in points:
                text = get_text_from_payload(point.payload or {})
                if not text:
                    continue

                # Generate BM42 sparse embedding
                sparse = list(bm42.embed([text]))[0]

                batch_points.append(
                    models.PointVectors(
                        id=point.id,
                        vector={
                            SPARSE_VECTOR_NAME: models.SparseVector(
                                indices=sparse.indices.tolist(),
                                values=sparse.values.tolist(),
                            ),
                        },
                    )
                )

            # Batch upsert
            if batch_points:
                client.update_vectors(
                    collection_name=coll_name,
                    points=batch_points,
                )
                processed += len(batch_points)
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  Processed {processed}/{total} ({processed*100//max(total,1)}%) "
                    f"at {rate:.0f} docs/sec"
                )
                batch_points = []

            offset = next_offset
            if offset is None:
                break

        elapsed = time.time() - start_time
        logger.info(f"Done: {processed} points in {elapsed:.0f}s ({processed/max(elapsed,1):.0f}/sec)")

    logger.info("\n=== ALL COLLECTIONS PROCESSED ===")


if __name__ == "__main__":
    main()
