#!/usr/bin/env python3
"""
Populate FAQ Cache with Team Q&A

Loads 57 bilingual Q&A pairs from team_qa_bilingual.json
and caches them in Redis for instant lookup.

Strategy:
- 57 Q&A × 2 languages = 114 cached entries
- Each entry: question → answer (exact match)
- TTL: 30 days
- Cost: $0 (no API calls, just Redis storage)

Expected cache hit rate: ~60-80% for common questions
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "backend-rag"))

from backend.services.caching import NotebookLMCacheService


async def load_team_qa(file_path: Path) -> list:
    """Load bilingual Q&A dataset."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


async def populate_cache():
    """Populate Redis cache with team Q&A."""
    print("=" * 70)
    print("📦 POPULATING FAQ CACHE WITH TEAM Q&A")
    print("=" * 70)

    # Paths
    project_root = Path(__file__).parent.parent.parent
    qa_file = project_root / "data" / "team_qa" / "team_qa_bilingual.json"

    # Load Q&A
    print("\n📂 Loading team Q&A...")
    if not qa_file.exists():
        print(f"❌ Error: {qa_file} not found")
        print("   Run scripts/team_qa_extraction/create_unified_bilingual.py first")
        return

    team_qa = await load_team_qa(qa_file)
    print(f"   ✅ Loaded {len(team_qa)} bilingual Q&A pairs")

    # Initialize cache
    print("\n🔧 Initializing cache service...")
    cache = NotebookLMCacheService()
    await cache.initialize()

    if not cache.redis_client:
        print("❌ Error: Redis not connected")
        print("   Check REDIS_URL environment variable")
        return

    # Populate cache
    print("\n💾 Caching Q&A pairs...")

    cached_count = 0
    errors = []

    for i, qa in enumerate(team_qa, 1):
        # Cache English version
        success_en = await cache.set(
            question=qa["question_en"],
            answer=qa["answer_en"],
            metadata={
                "domain": qa["domain"],
                "language": "en",
                "source": qa["source"],
                "qa_id": qa["id"]
            }
        )

        if success_en:
            cached_count += 1
        else:
            errors.append(f"EN: {qa['question_en'][:50]}...")

        # Cache Indonesian version
        success_id = await cache.set(
            question=qa["question_id"],
            answer=qa["answer_id"],
            metadata={
                "domain": qa["domain"],
                "language": "id",
                "source": qa["source"],
                "qa_id": qa["id"]
            }
        )

        if success_id:
            cached_count += 1
        else:
            errors.append(f"ID: {qa['question_id'][:50]}...")

        # Progress indicator
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(team_qa)} Q&A pairs processed...")

    print(f"   ✅ Cached {cached_count} entries")

    if errors:
        print(f"\n   ⚠️  Errors: {len(errors)}")
        for err in errors[:5]:  # Show first 5 errors
            print(f"      - {err}")

    # Get cache stats
    print("\n📊 Cache statistics:")
    stats = await cache.get_stats()
    print(f"   Total keys: {stats.get('total_keys', 0)}")
    print(f"   Memory usage: {stats.get('memory_usage_mb', 0)} MB")
    print(f"   TTL: {stats.get('ttl_days', 0)} days")

    # Test cache lookup
    print("\n🧪 Testing cache lookup...")
    test_question = team_qa[0]["question_en"]
    print(f"   Query: {test_question[:60]}...")

    result = await cache.get(test_question)
    if result:
        print(f"   ✅ Cache HIT!")
        print(f"   Answer (first 100 chars): {result['answer'][:100]}...")
    else:
        print(f"   ❌ Cache MISS")

    # Close connection
    await cache.close()

    print("\n" + "=" * 70)
    print("✅ CACHE POPULATION COMPLETE")
    print("=" * 70)
    print(f"   📊 Total entries: {cached_count}")
    print(f"   🌐 Languages: English ({cached_count // 2}), Indonesian ({cached_count // 2})")
    print(f"   📁 Domains: Tax, KBLI, Visa, Property")
    print(f"   💾 Storage: ~{stats.get('memory_usage_mb', 0)} MB")
    print(f"   ⏰ TTL: 30 days")
    print("\n📊 Expected cache hit rate: 60-80% (common FAQ questions)")
    print("💰 API cost savings: ~$0.50-$1.00 per day")
    print()


if __name__ == "__main__":
    asyncio.run(populate_cache())
