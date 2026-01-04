#!/usr/bin/env python3
"""
Test script for the new LLM-based Knowledge Graph extraction pipeline.
Tests extraction on a small sample of documents.

Usage:
    python scripts/test_kg_pipeline_llm.py [--sample 10] [--persist] [--clear-old]
"""

import argparse
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.knowledge_graph import KGExtractor, KGPipeline
from backend.services.knowledge_graph.pipeline import PipelineConfig


async def fetch_sample_chunks(collection: str, limit: int) -> list[tuple[str, str]]:
    """Fetch sample chunks from Qdrant"""
    import httpx

    qdrant_url = os.environ.get("QDRANT_URL", "")
    qdrant_key = os.environ.get("QDRANT_API_KEY", "")

    headers = {"api-key": qdrant_key} if qdrant_key else {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{qdrant_url}/collections/{collection}/points/scroll",
            headers=headers,
            json={
                "limit": limit,
                "with_payload": True,
                "with_vectors": False,
            },
        )

        data = resp.json().get("result", {})
        points = data.get("points", [])

        chunks = []
        for point in points:
            chunk_id = str(point.get("id", ""))
            text = point.get("payload", {}).get("text", "") or point.get("payload", {}).get(
                "content", ""
            )
            if text and len(text.strip()) > 50:
                chunks.append((chunk_id, text))

        return chunks


async def clear_old_kg_data():
    """Clear old KG data from database"""
    import asyncpg

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set, skipping clear")
        return

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute("DELETE FROM kg_edges")
        await conn.execute("DELETE FROM kg_nodes")
        print("✅ Cleared old KG data")
    finally:
        await conn.close()


async def test_single_extraction(text: str, chunk_id: str = "test"):
    """Test extraction on a single text sample"""
    print("\n" + "=" * 60)
    print(f"Testing extraction on chunk: {chunk_id[:50]}...")
    print("=" * 60)
    print(f"\nText preview ({len(text)} chars):")
    print(text[:500] + "..." if len(text) > 500 else text)

    extractor = KGExtractor()

    # Extract entities and relations
    result = await extractor.extract(text, chunk_id)

    print("\n📊 Extraction Results:")
    print(f"  Entities: {len(result.entities)}")
    print(f"  Relations: {len(result.relations)}")

    if result.entities:
        print("\n📋 Entities:")
        for e in result.entities:
            attrs = json.dumps(e.attributes) if e.attributes else "{}"
            print(f"  [{e.type.value}] {e.name} (conf: {e.confidence:.2f})")
            print(f"    mention: {e.mention}")
            if e.attributes:
                print(f"    attrs: {attrs}")

    if result.relations:
        print("\n🔗 Relations:")
        for r in result.relations:
            print(f"  {r.source_id} --[{r.type.value}]--> {r.target_id}")
            print(f"    evidence: {r.evidence[:80]}...")
            print(f"    confidence: {r.confidence:.2f}")

    return result


async def test_pipeline(sample_size: int = 10, persist: bool = False, clear_old: bool = False):
    """Test the full pipeline on sample documents"""
    print("🚀 Testing LLM-based KG Pipeline")
    print(f"  Sample size: {sample_size}")
    print(f"  Persist to DB: {persist}")
    print(f"  Clear old data: {clear_old}")

    if clear_old and persist:
        await clear_old_kg_data()

    # Fetch sample chunks
    print(f"\n📥 Fetching {sample_size} sample chunks from Qdrant...")
    chunks = await fetch_sample_chunks("legal_unified_hybrid", sample_size)
    print(f"  Retrieved {len(chunks)} chunks")

    if not chunks:
        print("❌ No chunks found!")
        return

    # Test single extraction first
    await test_single_extraction(chunks[0][1], chunks[0][0])

    # Run full pipeline
    print("\n" + "=" * 60)
    print("Running full pipeline on all samples...")
    print("=" * 60)

    config = PipelineConfig(
        model="claude-sonnet-4-20250514",
        two_stage_extraction=False,  # Use combined extraction (faster)
        use_coreference=True,
        min_confidence=0.6,
        batch_size=5,
        max_concurrent=3,
    )

    pipeline = KGPipeline(config)

    try:
        stats = await pipeline.run(
            chunks,
            source_collection="legal_unified_hybrid",
            persist=persist,
        )

        print("\n📊 Pipeline Statistics:")
        for key, value in stats.to_dict().items():
            print(f"  {key}: {value}")

        print("\n🗃️ Cache Statistics:")
        cache_stats = pipeline.get_cache_stats()
        for key, value in cache_stats.items():
            print(f"  {key}: {value}")

        # Show unique entities
        print(f"\n📋 Unique Entities ({len(pipeline.entity_registry)}):")
        for eid, entity in list(pipeline.entity_registry.items())[:20]:
            print(f"  [{entity.type.value}] {entity.name}")

        if len(pipeline.entity_registry) > 20:
            print(f"  ... and {len(pipeline.entity_registry) - 20} more")

        # Show relation count
        print(f"\n🔗 Unique Relations: {len(pipeline.relation_registry)}")
        for rid in list(pipeline.relation_registry)[:10]:
            print(f"  {rid}")

        if len(pipeline.relation_registry) > 10:
            print(f"  ... and {len(pipeline.relation_registry) - 10} more")

    finally:
        await pipeline.close()

    print("\n✅ Pipeline test completed!")


async def main():
    parser = argparse.ArgumentParser(description="Test KG Pipeline")
    parser.add_argument("--sample", type=int, default=10, help="Number of samples to process")
    parser.add_argument("--persist", action="store_true", help="Persist results to database")
    parser.add_argument("--clear-old", action="store_true", help="Clear old KG data first")

    args = parser.parse_args()

    await test_pipeline(
        sample_size=args.sample,
        persist=args.persist,
        clear_old=args.clear_old,
    )


if __name__ == "__main__":
    asyncio.run(main())
