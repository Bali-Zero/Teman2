#!/usr/bin/env python3
"""
BALIZERO INTEL FEED - Complete Pipeline
=========================================
Unified script that runs the complete news intelligence pipeline:

1. Fetch RSS from Google News (16 topic queries)
2. Score with Professional 5-Dimension System
3. Deep Enrich with Claude Max (fetch full article + write BaliZero article)
4. Send enriched articles to BaliZero API

Usage:
    python run_intel_feed.py --mode full        # Complete pipeline with deep enrichment
    python run_intel_feed.py --mode quick       # Quick mode (RSS + score only, no deep enrichment)
    python run_intel_feed.py --mode enrich-only # Only enrich pending articles in DB
"""

import asyncio
import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from loguru import logger

# Import our modules
from rss_fetcher import GoogleNewsRSSFetcher, send_to_balizero

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/intel_feed_{time}.log", rotation="1 day", retention="7 days")


async def run_quick_mode(
    max_age: int = 7,
    limit_per_topic: int = 5,
    min_score: int = 50,
    api_url: str = "https://balizero.com",
    api_key: Optional[str] = None,
    use_ollama: bool = False,
    dry_run: bool = False,
) -> Dict:
    """
    QUICK MODE: RSS fetch + professional scoring + send (no deep enrichment)
    Fast, cheap, for regular updates.
    """
    logger.info("=" * 70)
    logger.info("🚀 BALIZERO INTEL FEED - QUICK MODE")
    logger.info(f"📅 {datetime.now().isoformat()}")
    logger.info("=" * 70)

    fetcher = GoogleNewsRSSFetcher(max_age_days=max_age)
    items = await fetcher.fetch_all(
        limit_per_topic=limit_per_topic, min_score=min_score, use_ollama=use_ollama
    )

    if not items:
        logger.warning("No items passed scoring threshold")
        return {"mode": "quick", "sent": 0, "filtered": 0}

    # Send to API
    result = await send_to_balizero(
        items, api_url=api_url, api_key=api_key, dry_run=dry_run
    )

    logger.info("=" * 70)
    logger.info("✅ QUICK MODE COMPLETE")
    logger.info(
        f"📊 Sent: {result['sent']} | Duplicates: {result['duplicates']} | Failed: {result['failed']}"
    )
    logger.info("=" * 70)

    return {"mode": "quick", **result}


async def run_full_mode(
    max_age: int = 7,
    limit_per_topic: int = 3,
    min_score: int = 60,
    api_url: str = "https://balizero.com",
    api_key: Optional[str] = None,
    use_ollama: bool = False,
    dry_run: bool = False,
    max_enrich: int = 5,
) -> Dict:
    """
    FULL MODE: RSS fetch + scoring + deep enrichment with Claude Max
    Slower, but produces complete BaliZero Executive Brief articles.
    """
    logger.info("=" * 70)
    logger.info("🔬 BALIZERO INTEL FEED - FULL MODE (Deep Enrichment)")
    logger.info(f"📅 {datetime.now().isoformat()}")
    logger.info("⚠️  Using Claude Max subscription via CLI")
    logger.info("=" * 70)

    # Step 1: Fetch and score RSS
    fetcher = GoogleNewsRSSFetcher(max_age_days=max_age)
    items = await fetcher.fetch_all(
        limit_per_topic=limit_per_topic, min_score=min_score, use_ollama=use_ollama
    )

    if not items:
        logger.warning("No items passed scoring threshold")
        return {"mode": "full", "fetched": 0, "enriched": 0, "sent": 0}

    logger.info(f"\n📋 {len(items)} items passed initial scoring (≥{min_score})")

    # Step 2: Select top items for deep enrichment
    # Sort by score and take top N
    items_sorted = sorted(
        items, key=lambda x: x.get("relevance_score", 0), reverse=True
    )
    items_to_enrich = items_sorted[:max_enrich]

    logger.info(f"🔬 Selected top {len(items_to_enrich)} for deep enrichment")

    # Step 3: Deep enrich with Claude
    try:
        from article_deep_enricher import ArticleDeepEnricher
    except ImportError as e:
        logger.error(f"Cannot import deep enricher: {e}")
        logger.warning("Falling back to quick mode...")
        return await run_quick_mode(
            max_age, limit_per_topic, min_score, api_url, api_key, use_ollama, dry_run
        )

    enricher = ArticleDeepEnricher(api_url=api_url)

    enriched_count = 0
    sent_count = 0
    failed_count = 0

    for item in items_to_enrich:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"🔬 Enriching: {item['title'][:50]}...")

        # Deep enrich
        enriched = await enricher.enrich_article(
            title=item.get("title", ""),
            summary=item.get("summary", ""),
            source_url=item.get("sourceUrl", ""),
            source=item.get("source", "Unknown"),
            category=item.get("category", "business"),
            published_at=item.get("publishedAt"),
        )

        if enriched:
            enriched_count += 1

            # Send to API
            if not dry_run:
                result = await enricher.send_to_api(enriched, api_key=api_key)
                if result.get("success") and not result.get("duplicate"):
                    sent_count += 1
                elif result.get("duplicate"):
                    logger.info("⏭️ Already in database")
                else:
                    failed_count += 1
            else:
                logger.info(f"🔍 DRY RUN - Would send: {enriched.headline[:40]}...")
                sent_count += 1

            # Rate limit for Claude
            await asyncio.sleep(5)
        else:
            failed_count += 1

    # Step 4: Send remaining items (not deep enriched) in quick mode
    remaining_items = items_sorted[max_enrich:]
    if remaining_items and not dry_run:
        logger.info(
            f"\n📤 Sending {len(remaining_items)} remaining items (quick mode)..."
        )
        quick_result = await send_to_balizero(
            remaining_items, api_url=api_url, api_key=api_key, dry_run=dry_run
        )
        sent_count += quick_result.get("sent", 0)

    logger.info("\n" + "=" * 70)
    logger.info("✅ FULL MODE COMPLETE")
    logger.info(
        f"📊 Fetched: {len(items)} | Deep Enriched: {enriched_count} | Sent: {sent_count} | Failed: {failed_count}"
    )
    logger.info("=" * 70)

    return {
        "mode": "full",
        "fetched": len(items),
        "enriched": enriched_count,
        "sent": sent_count,
        "failed": failed_count,
    }


async def run_enrich_only(
    api_url: str = "https://balizero.com",
    api_key: Optional[str] = None,
    limit: int = 10,
    dry_run: bool = False,
) -> Dict:
    """
    ENRICH-ONLY MODE: Enrich articles already in database that lack full content.
    Fetches pending articles from API and enriches them.
    """
    logger.info("=" * 70)
    logger.info("🔄 BALIZERO INTEL FEED - ENRICH ONLY MODE")
    logger.info("=" * 70)

    try:
        from news_enricher_claude import ClaudeNewsEnricher

        enricher = ClaudeNewsEnricher(api_url=api_url)
        result = await enricher.process_batch(limit=limit)
        return {"mode": "enrich-only", **result}
    except Exception as e:
        logger.error(f"Enrich-only mode failed: {e}")
        return {"mode": "enrich-only", "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(
        description="BaliZero Intel Feed - Complete News Intelligence Pipeline"
    )

    # Mode selection
    parser.add_argument(
        "--mode",
        choices=["full", "quick", "enrich-only"],
        default="quick",
        help="Pipeline mode: full (deep enrichment), quick (RSS+score only), enrich-only (enrich DB articles)",
    )

    # Common options
    parser.add_argument(
        "--api-url", default="https://balizero.com", help="BaliZero API URL"
    )
    parser.add_argument("--api-key", help="API key (or set BALIZERO_API_KEY env)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without sending"
    )

    # RSS options
    parser.add_argument(
        "--max-age", type=int, default=7, help="Max article age in days"
    )
    parser.add_argument("--limit", type=int, default=5, help="Items per topic")
    parser.add_argument("--min-score", type=int, default=50, help="Min score (0-100)")
    parser.add_argument(
        "--use-ollama", action="store_true", help="Use Ollama for edge cases"
    )

    # Full mode options
    parser.add_argument(
        "--max-enrich", type=int, default=5, help="Max items to deep enrich"
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv("BALIZERO_API_KEY")

    if not api_key and not args.dry_run:
        logger.warning("No API key provided. Use --api-key or set BALIZERO_API_KEY")

    # Run selected mode
    if args.mode == "full":
        result = await run_full_mode(
            max_age=args.max_age,
            limit_per_topic=args.limit,
            min_score=args.min_score,
            api_url=args.api_url,
            api_key=api_key,
            use_ollama=args.use_ollama,
            dry_run=args.dry_run,
            max_enrich=args.max_enrich,
        )
    elif args.mode == "enrich-only":
        result = await run_enrich_only(
            api_url=args.api_url,
            api_key=api_key,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    else:  # quick mode
        result = await run_quick_mode(
            max_age=args.max_age,
            limit_per_topic=args.limit,
            min_score=args.min_score,
            api_url=args.api_url,
            api_key=api_key,
            use_ollama=args.use_ollama,
            dry_run=args.dry_run,
        )

    print(f"\n📊 Final Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
