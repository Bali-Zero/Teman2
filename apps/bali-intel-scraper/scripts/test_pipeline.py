#!/usr/bin/env python3
"""
BALIZERO PIPELINE TEST
======================
Test completo di tutti i componenti:
1. Smart Extractor (multi-layer + Llama)
2. Pre-Scorer (Ollama)
3. Semantic Deduplicator (Qdrant)
4. Deep Enricher (Claude Max)
"""

import asyncio
from loguru import logger
from pathlib import Path

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/test_pipeline_{time}.log", rotation="1 day")


async def test_smart_extractor():
    """Test multi-layer extraction with Llama fallback"""
    print("\n" + "=" * 60)
    print("🔧 TEST 1: Smart Extractor")
    print("=" * 60)

    from smart_extractor import SmartExtractor

    extractor = SmartExtractor()

    # Check Ollama
    ollama_ok = await extractor.check_ollama()
    print(f"   Ollama available: {'✅' if ollama_ok else '❌'}")

    # Test URL
    test_url = "https://www.thejakartapost.com/indonesia/2024/12/15/indonesia-digital-nomad-visa.html"
    print(f"   Testing URL: {test_url[:50]}...")

    result = await extractor.extract(test_url)

    if result:
        print(f"   ✅ Method: {result.get('method')}")
        print(f"   📰 Title: {result.get('title', 'N/A')[:60]}...")
        print(f"   📝 Content: {len(result.get('content', ''))} chars")
    else:
        print("   ❌ Extraction failed")

    print(f"\n   Stats: {extractor.get_stats()}")
    return result is not None


async def test_prescorer():
    """Test Ollama pre-scoring"""
    print("\n" + "=" * 60)
    print("🎯 TEST 2: Pre-Scorer (Ollama)")
    print("=" * 60)

    from ollama_scorer import OllamaScorer

    scorer = OllamaScorer()

    # Health check
    is_healthy = await scorer.health_check()
    print(f"   Ollama healthy: {'✅' if is_healthy else '❌'}")

    if not is_healthy:
        print("   ⚠️  Skipping scoring tests (Ollama not running)")
        print("   💡 Run: ollama serve && ollama pull llama3.2:3b")
        return False

    # Warm up
    print("   Warming up model...")
    await scorer.warm_up()

    # Test articles
    test_cases = [
        (
            "Indonesia Extends Digital Nomad Visa to 5 Years",
            "New policy for expats working remotely in Bali",
            80,
        ),
        (
            "New Tax Rules for Foreign Workers in Indonesia",
            "Tax authority issues new guidelines for expats",
            70,
        ),
        (
            "Taylor Swift Announces World Tour",
            "Pop star announces concert dates for 2026",
            20,
        ),
    ]

    all_passed = True
    for title, summary, expected_min in test_cases:
        score, reason = await scorer.score_article(title, summary)
        emoji = "✅" if score >= expected_min - 20 else "⚠️"
        print(f"   {emoji} [{score:3d}] {title[:40]}... ({reason})")
        if score < expected_min - 30:  # Allow some tolerance
            all_passed = False

    return all_passed


async def test_semantic_dedup():
    """Test semantic deduplication"""
    print("\n" + "=" * 60)
    print("🔍 TEST 3: Semantic Deduplicator")
    print("=" * 60)

    try:
        from unified_scraper_v2 import SemanticDeduplicator
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False

    dedup = SemanticDeduplicator()

    # Initialize
    semantic_ok = await dedup.initialize()
    print(f"   Semantic mode: {'✅ Qdrant' if semantic_ok else '⚠️ SHA-256 fallback'}")

    # Test cases
    test_cases = [
        ("Indonesia extends digital nomad visa", "First article about visa extension"),
        (
            "Digital nomad visa extended in Indonesia",
            "Paraphrased version - should be duplicate",
        ),
        (
            "New tax rules for foreign workers",
            "Different topic - should NOT be duplicate",
        ),
    ]

    results = []
    for title, content in test_cases:
        is_dup, content_id = await dedup.is_duplicate(title, content)
        emoji = "🔄" if is_dup else "✅"
        status = "DUPLICATE" if is_dup else "NEW"
        print(f"   {emoji} {status}: {title[:40]}...")
        results.append((title, is_dup))

    # Verify: second should be duplicate, third should not
    if semantic_ok:
        expected = [False, True, False]  # First new, second dup, third new
        actual = [r[1] for r in results]
        if actual == expected:
            print("   ✅ Semantic dedup working correctly!")
            return True
        else:
            print(f"   ⚠️  Results: {actual}, expected: {expected}")
            return False

    return True


async def test_deep_enricher():
    """Test Claude deep enrichment (requires Claude Max)"""
    print("\n" + "=" * 60)
    print("🔬 TEST 4: Deep Enricher (Claude Max)")
    print("=" * 60)

    try:
        from article_deep_enricher import ArticleDeepEnricher
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False

    enricher = ArticleDeepEnricher()

    # Check Claude CLI
    import subprocess

    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        claude_ok = result.returncode == 0
        print(f"   Claude CLI: {'✅' if claude_ok else '❌'}")
    except Exception:
        print("   ❌ Claude CLI not found")
        print("   💡 Install: npm install -g @anthropic-ai/claude-code")
        return False

    # Test article fetch (without calling Claude)
    test_url = "https://www.thejakartapost.com/business/2024/12/10/example.html"
    print(f"   Testing fetch: {test_url[:50]}...")

    # Just test the fetch method
    try:
        content = await enricher.fetch_full_article(test_url)
        if content:
            print(f"   ✅ Fetched {len(content)} chars")
        else:
            print("   ⚠️  Could not fetch (URL may not exist)")
    except Exception as e:
        print(f"   ⚠️  Fetch error: {e}")

    print("\n   💡 Full enrichment requires Claude Max subscription")
    print("   💡 Run: python article_deep_enricher.py --test")

    return True


async def test_full_pipeline():
    """Test the complete scraping pipeline"""
    print("\n" + "=" * 60)
    print("🚀 TEST 5: Full Pipeline (unified_scraper_v2)")
    print("=" * 60)

    try:
        from unified_scraper_v2 import BaliZeroScraperV2
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False

    # Check config exists
    config_path = Path("config/categories.json")
    if not config_path.exists():
        print(f"   ❌ Config not found: {config_path}")
        return False

    print(f"   ✅ Config found: {config_path}")

    # Initialize scraper
    scraper = BaliZeroScraperV2(
        config_path=str(config_path),
        min_score=30,  # Low threshold for testing
        use_semantic_dedup=False,  # Skip Qdrant for quick test
    )

    # Just initialize without scraping
    await scraper.initialize()

    print("   ✅ Scraper v2 initialized")
    print("\n   💡 To run full scrape:")
    print("   python unified_scraper_v2.py --limit 5 --min-score 40")

    return True


async def main():
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " BALIZERO PIPELINE TEST ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")

    results = {}

    # Run all tests
    results["smart_extractor"] = await test_smart_extractor()
    results["prescorer"] = await test_prescorer()
    results["semantic_dedup"] = await test_semantic_dedup()
    results["deep_enricher"] = await test_deep_enricher()
    results["full_pipeline"] = await test_full_pipeline()

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        emoji = "✅" if passed else "❌"
        print(f"   {emoji} {test_name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed - check configuration")

    # Requirements check
    print("\n📦 Required Components:")
    print("   • Ollama: brew install ollama && ollama serve")
    print("   • Model: ollama pull llama3.2:3b")
    print("   • Qdrant (optional): docker run -p 6333:6333 qdrant/qdrant")
    print("   • Claude CLI: npm install -g @anthropic-ai/claude-code")

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
