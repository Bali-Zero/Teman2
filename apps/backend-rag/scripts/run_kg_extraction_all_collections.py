#!/usr/bin/env python3
"""
Full Knowledge Graph Extraction - ALL COLLECTIONS

Processes ALL Qdrant collections to build a unified Knowledge Graph.
Total: ~54K documents across 7+ collections.

Estimated cost: ~€15-20 with Gemini Flash

Usage:
    # Run on Fly.io (SSH)
    fly ssh console -a nuzantara-rag -C "cd /app && python -m scripts.run_kg_extraction_all_collections"

    # Dry run (just show what would be processed)
    python -m scripts.run_kg_extraction_all_collections --dry-run

    # Clear old data and start fresh
    python -m scripts.run_kg_extraction_all_collections --clear

    # Limit per collection (for testing)
    python -m scripts.run_kg_extraction_all_collections --limit-per-collection 100
"""

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kg_extraction_all")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================================
# COLLECTIONS TO PROCESS
# ============================================================================
# Order: largest first for better progress visibility

COLLECTIONS_TO_PROCESS = [
    # Primary collections (main KB)
    {"name": "legal_unified_hybrid", "priority": 1, "expected_docs": 47959},
    {"name": "kbli_unified", "priority": 1, "expected_docs": 8886},
    {"name": "knowledge_base", "priority": 2, "expected_docs": 37272},
    {"name": "training_conversations_hybrid", "priority": 2, "expected_docs": 2898},
    {"name": "visa_oracle", "priority": 1, "expected_docs": 1612},
    {"name": "tax_genius_hybrid", "priority": 1, "expected_docs": 895},
    {"name": "bali_zero_pricing", "priority": 1, "expected_docs": 65},
    {"name": "bali_zero_team", "priority": 1, "expected_docs": 22},
]

# Collections to skip (backups, test, deprecated)
SKIP_COLLECTIONS = [
    "legal_unified",  # Replaced by legal_unified_hybrid
    "tax_genius",  # Replaced by tax_genius_hybrid
    "training_conversations",  # Replaced by hybrid version
    "legal_unified_backup",
    "test_collection",
]


@dataclass
class ExtractionStats:
    """Aggregated stats across all collections"""
    total_chunks: int = 0
    total_entities: int = 0
    total_relations: int = 0
    total_persisted_entities: int = 0
    total_persisted_relations: int = 0
    total_duplicates_merged: int = 0
    total_errors: int = 0
    collections_processed: int = 0
    collections_failed: list = field(default_factory=list)
    per_collection: dict = field(default_factory=dict)


async def get_collection_stats(collection: str) -> int:
    """Get document count for a collection"""
    import httpx

    qdrant_url = os.environ.get("QDRANT_URL", "")
    qdrant_key = os.environ.get("QDRANT_API_KEY", "")
    headers = {"api-key": qdrant_key} if qdrant_key else {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{qdrant_url}/collections/{collection}",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {}).get("points_count", 0)
            return 0
    except Exception as e:
        logger.warning(f"Failed to get stats for {collection}: {e}")
        return 0


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
        logger.info("✅ Cleared all KG data")
        return True
    finally:
        await conn.close()


async def get_current_kg_stats() -> dict:
    """Get current KG stats from database"""
    import asyncpg

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"nodes": 0, "edges": 0}

    try:
        conn = await asyncpg.connect(db_url)
        nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
        edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
        await conn.close()
        return {"nodes": nodes, "edges": edges}
    except Exception:
        return {"nodes": 0, "edges": 0}


async def process_collection(
    collection: str,
    limit: int | None = None,
    batch_size: int = 20,
    max_concurrent: int = 10,
) -> dict:
    """Process a single collection and return stats"""
    from scripts.run_kg_extraction_gemini import fetch_chunks_from_qdrant
    from backend.services.knowledge_graph import KGPipeline, PipelineConfig

    start_time = datetime.now()
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {collection}")
    logger.info(f"{'='*60}")

    try:
        # Fetch chunks
        chunks = await fetch_chunks_from_qdrant(collection, limit)
        if not chunks:
            logger.warning(f"No chunks found in {collection}")
            return {"success": False, "error": "No chunks", "chunks": 0}

        logger.info(f"Found {len(chunks)} valid chunks")

        # Initialize pipeline
        config = PipelineConfig(
            model="gemini-2.0-flash",
            extractor_type="gemini",
            use_coreference=True,
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

            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "success": True,
                "chunks": stats.chunks_processed,
                "entities": stats.entities_extracted,
                "relations": stats.relations_extracted,
                "persisted_entities": stats.entities_persisted,
                "persisted_relations": stats.relations_persisted,
                "duplicates_merged": stats.duplicates_merged,
                "errors": stats.errors,
                "duration_seconds": duration,
            }

            logger.info(f"✅ {collection}: {stats.entities_extracted} entities, {stats.relations_extracted} relations in {duration:.1f}s")
            return result

        finally:
            await pipeline.close()

    except Exception as e:
        logger.error(f"❌ Failed to process {collection}: {e}")
        return {"success": False, "error": str(e), "chunks": 0}


async def run_all_extractions(
    clear: bool = False,
    dry_run: bool = False,
    limit_per_collection: int | None = None,
    batch_size: int = 20,
    max_concurrent: int = 10,
    skip_existing: bool = False,
):
    """Run KG extraction on all collections"""
    start_time = datetime.now()

    logger.info("=" * 70)
    logger.info("KNOWLEDGE GRAPH EXTRACTION - ALL COLLECTIONS")
    logger.info("=" * 70)

    # Verify API key
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_IMAGEN_API_KEY")
    if not api_key and not dry_run:
        logger.error("❌ Missing GOOGLE_API_KEY or GOOGLE_IMAGEN_API_KEY!")
        return

    # Get current stats
    current_kg = await get_current_kg_stats()
    logger.info(f"\nCurrent KG: {current_kg['nodes']:,} nodes, {current_kg['edges']:,} edges")

    # Clear if requested
    if clear and not dry_run:
        await clear_kg_data()

    # Survey collections
    logger.info("\n📊 Surveying collections...")
    collections_to_process = []
    total_expected = 0

    for coll in COLLECTIONS_TO_PROCESS:
        name = coll["name"]
        actual_count = await get_collection_stats(name)

        if actual_count == 0:
            logger.warning(f"  ⚠️  {name}: EMPTY or NOT FOUND")
            continue

        collections_to_process.append({
            "name": name,
            "count": actual_count,
            "priority": coll["priority"],
        })
        total_expected += actual_count
        logger.info(f"  ✓ {name}: {actual_count:,} docs")

    logger.info(f"\n📦 Total documents to process: {total_expected:,}")
    logger.info(f"📁 Collections: {len(collections_to_process)}")

    if dry_run:
        logger.info("\n🔍 DRY RUN - No extraction performed")

        # Cost estimate
        input_tokens = total_expected * 1500
        output_tokens = total_expected * 500
        cost_input = (input_tokens / 1_000_000) * 0.075
        cost_output = (output_tokens / 1_000_000) * 0.30
        total_cost = cost_input + cost_output

        logger.info(f"\n💰 Estimated cost: ${total_cost:.2f} (€{total_cost * 0.92:.2f})")
        logger.info(f"⏱️  Estimated time: {total_expected / 60:.0f} - {total_expected / 30:.0f} minutes")
        return

    # Process each collection
    stats = ExtractionStats()

    for i, coll in enumerate(collections_to_process, 1):
        name = coll["name"]
        logger.info(f"\n[{i}/{len(collections_to_process)}] {name} ({coll['count']:,} docs)")

        result = await process_collection(
            name,
            limit=limit_per_collection,
            batch_size=batch_size,
            max_concurrent=max_concurrent,
        )

        if result["success"]:
            stats.collections_processed += 1
            stats.total_chunks += result["chunks"]
            stats.total_entities += result["entities"]
            stats.total_relations += result["relations"]
            stats.total_persisted_entities += result["persisted_entities"]
            stats.total_persisted_relations += result["persisted_relations"]
            stats.total_duplicates_merged += result["duplicates_merged"]
            stats.total_errors += result["errors"]
            stats.per_collection[name] = result
        else:
            stats.collections_failed.append(name)

        # Small delay between collections to avoid rate limits
        if i < len(collections_to_process):
            await asyncio.sleep(2)

    # Final report
    duration = (datetime.now() - start_time).total_seconds()
    final_kg = await get_current_kg_stats()

    logger.info("\n" + "=" * 70)
    logger.info("EXTRACTION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Duration: {duration:.1f}s ({duration / 60:.1f} minutes)")
    logger.info(f"Collections processed: {stats.collections_processed}/{len(collections_to_process)}")
    if stats.collections_failed:
        logger.info(f"Collections failed: {stats.collections_failed}")
    logger.info("")
    logger.info(f"Total chunks processed: {stats.total_chunks:,}")
    logger.info(f"Total entities extracted: {stats.total_entities:,}")
    logger.info(f"Total relations extracted: {stats.total_relations:,}")
    logger.info(f"Entities persisted: {stats.total_persisted_entities:,}")
    logger.info(f"Relations persisted: {stats.total_persisted_relations:,}")
    logger.info(f"Duplicates merged: {stats.total_duplicates_merged:,}")
    logger.info(f"Errors: {stats.total_errors:,}")
    logger.info("")
    logger.info(f"Final KG: {final_kg['nodes']:,} nodes, {final_kg['edges']:,} edges")

    # Cost estimate
    input_tokens = stats.total_chunks * 1500
    output_tokens = stats.total_chunks * 500
    cost_input = (input_tokens / 1_000_000) * 0.075
    cost_output = (output_tokens / 1_000_000) * 0.30
    total_cost = cost_input + cost_output
    logger.info(f"\n💰 Actual cost: ~${total_cost:.2f} (€{total_cost * 0.92:.2f})")


async def main():
    parser = argparse.ArgumentParser(
        description="KG Extraction - All Collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run to see what would be processed
    python -m scripts.run_kg_extraction_all_collections --dry-run

    # Full extraction (clear old data first)
    python -m scripts.run_kg_extraction_all_collections --clear

    # Test with limit per collection
    python -m scripts.run_kg_extraction_all_collections --limit-per-collection 50
        """,
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all existing KG data before starting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually running",
    )
    parser.add_argument(
        "--limit-per-collection",
        type=int,
        default=None,
        help="Limit documents per collection (for testing)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Batch size for LLM processing (default: 20)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max concurrent LLM requests (default: 10)",
    )

    args = parser.parse_args()

    await run_all_extractions(
        clear=args.clear,
        dry_run=args.dry_run,
        limit_per_collection=args.limit_per_collection,
        batch_size=args.batch_size,
        max_concurrent=args.concurrency,
    )


if __name__ == "__main__":
    asyncio.run(main())
