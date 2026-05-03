#!/usr/bin/env python3
"""
Full Knowledge Graph Extraction using Gemini Flash via Google AI Studio

Processes all documents from Qdrant and extracts entities/relations.
Estimated cost for 54K docs: ~€10-15 with Gemini Flash

Usage:
    # Run on Fly.io (SSH)
    fly ssh console -a nuzantara-rag -C "cd /app && python -m scripts.run_kg_extraction_gemini"

    # Or with options
    fly ssh console -a nuzantara-rag -C "cd /app && python -m scripts.run_kg_extraction_gemini --limit 1000 --clear"
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kg_extraction")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def clear_kg_data():
    """Clear existing KG data from database"""
    import asyncpg

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return False

    conn = await asyncpg.connect(db_url)
    try:
        edges_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
        nodes_count = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
        logger.info(f"Clearing {nodes_count} nodes and {edges_count} edges...")

        await conn.execute("DELETE FROM kg_edges")
        await conn.execute("DELETE FROM kg_nodes")
        logger.info("Cleared old data")
        return True
    finally:
        await conn.close()


async def fetch_chunks_from_qdrant(
    collection: str,
    limit: int | None = None,
    batch_size: int = 500,
):
    """Fetch all chunks from Qdrant in batches"""
    import httpx

    qdrant_url = os.environ.get("QDRANT_URL", "")
    qdrant_key = os.environ.get("QDRANT_API_KEY", "")

    headers = {"api-key": qdrant_key} if qdrant_key else {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Get collection count
        resp = await client.get(
            f"{qdrant_url}/collections/{collection}",
            headers=headers,
        )
        data = resp.json()
        total = data.get("result", {}).get("points_count", 0)
        logger.info(f"Collection '{collection}' has {total} documents")

        if limit:
            total = min(total, limit)
            logger.info(f"Limited to {limit} documents")

        # Scroll through all documents
        offset = None
        fetched = 0
        all_chunks = []

        while fetched < total:
            payload = {
                "limit": batch_size,
                "with_payload": True,
                "with_vectors": False,
            }
            if offset:
                payload["offset"] = offset

            resp = await client.post(
                f"{qdrant_url}/collections/{collection}/points/scroll",
                headers=headers,
                json=payload,
            )
            data = resp.json().get("result", {})
            points = data.get("points", [])
            offset = data.get("next_page_offset")

            if not points:
                break

            for point in points:
                chunk_id = str(point.get("id", ""))
                text = point.get("payload", {}).get("text", "") or point.get("payload", {}).get(
                    "content", ""
                )
                if text and len(text.strip()) > 20:
                    all_chunks.append((chunk_id, text))

                if limit and len(all_chunks) >= limit:
                    break

            fetched += len(points)
            logger.info(f"Fetched {fetched}/{total} documents ({len(all_chunks)} valid chunks)")

            if not offset or (limit and len(all_chunks) >= limit):
                break

        return all_chunks


async def run_extraction(
    limit: int | None = None,
    clear: bool = False,
    collection: str = "legal_unified_hybrid",
    batch_size: int = 20,
    max_concurrent: int = 10,
):
    """Run full KG extraction with Gemini Flash"""
    from backend.services.knowledge_graph import KGPipeline, PipelineConfig

    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Knowledge Graph Extraction with Gemini Flash")
    logger.info("=" * 60)

    # Verify Google AI Studio config
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_IMAGEN_API_KEY")

    logger.info(f"API Key: {'set' if api_key else 'NOT SET'}")

    if not api_key:
        logger.error("Missing GOOGLE_API_KEY or GOOGLE_IMAGEN_API_KEY!")
        return

    # Clear old data if requested
    if clear:
        await clear_kg_data()

    # Fetch chunks from Qdrant
    logger.info(f"Fetching chunks from Qdrant collection '{collection}'...")
    chunks = await fetch_chunks_from_qdrant(collection, limit)
    logger.info(f"Processing {len(chunks)} chunks...")

    if not chunks:
        logger.warning("No chunks to process!")
        return

    # Initialize pipeline with Gemini
    config = PipelineConfig(
        model="gemini-2.0-flash",
        extractor_type="gemini",
        use_coreference=True,  # Will use heuristics only, not LLM
        min_confidence=0.6,
        batch_size=batch_size,
        max_concurrent=max_concurrent,
        log_every=100,
    )

    pipeline = KGPipeline(config)

    try:
        # Run extraction
        stats = await pipeline.run(
            chunks,
            source_collection=collection,
            persist=True,
        )

        # Print results
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("")
        logger.info("=" * 60)
        logger.info("EXTRACTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Duration: {duration:.1f}s ({duration / 60:.1f} minutes)")
        logger.info(f"Chunks processed: {stats.chunks_processed}")
        logger.info(f"Entities extracted: {stats.entities_extracted}")
        logger.info(f"Relations extracted: {stats.relations_extracted}")
        logger.info(f"Entities persisted: {stats.entities_persisted}")
        logger.info(f"Relations persisted: {stats.relations_persisted}")
        logger.info(f"Duplicates merged: {stats.duplicates_merged}")
        logger.info(f"Errors: {stats.errors}")
        logger.info("")

        # Cost estimate
        # Gemini Flash: $0.075/1M input tokens, $0.30/1M output tokens
        # Average chunk ~500 tokens, prompt ~1000 tokens, output ~500 tokens
        input_tokens = len(chunks) * 1500  # prompt + context
        output_tokens = len(chunks) * 500
        cost_input = (input_tokens / 1_000_000) * 0.075
        cost_output = (output_tokens / 1_000_000) * 0.30
        total_cost = cost_input + cost_output
        logger.info(f"Estimated cost: ${total_cost:.2f} (€{total_cost * 0.92:.2f})")

        # Show entity distribution
        cache_stats = pipeline.get_cache_stats()
        logger.info("")
        logger.info("Entity Registry:")
        logger.info(f"  Total unique entities: {cache_stats['entity_registry_size']}")
        logger.info(f"  Total unique relations: {cache_stats['relation_registry_size']}")

    finally:
        await pipeline.close()


async def main():
    parser = argparse.ArgumentParser(description="KG Extraction with Gemini Flash")
    parser.add_argument("--limit", type=int, default=None, help="Limit documents to process")
    parser.add_argument("--clear", action="store_true", help="Clear old KG data first")
    parser.add_argument(
        "--collection", type=str, default="legal_unified_hybrid", help="Qdrant collection"
    )
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size for processing")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent requests")

    args = parser.parse_args()

    await run_extraction(
        limit=args.limit,
        clear=args.clear,
        collection=args.collection,
        batch_size=args.batch_size,
        max_concurrent=args.concurrency,
    )


if __name__ == "__main__":
    asyncio.run(main())
