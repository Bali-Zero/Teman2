#!/usr/bin/env python3
"""
BALIZERO INTEL FEED - Complete Pipeline
=========================================
Unified script that runs the complete news intelligence pipeline:

1. Fetch articles from sources (RSS, Web Scraping, or Both)
2. Score with Professional 5-Dimension System + LLAMA
3. Validate with Claude
4. Deep Enrich with Claude Max (fetch full article + write BaliZero article)
5. Generate cover images with Gemini (via browser automation)
6. SEO/AEO Optimization
7. Telegram Approval
8. Publish to BaliZero API

Usage:
    python run_intel_feed.py --mode massive     # 790+ sources web scraping + full pipeline
    python run_intel_feed.py --mode full        # Google News RSS + deep enrichment
    python run_intel_feed.py --mode quick       # RSS + score only, no deep enrichment
    python run_intel_feed.py --mode enrich-only # Only enrich pending articles in DB
"""

import asyncio
import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger

# Import our modules
from rss_fetcher import GoogleNewsRSSFetcher, send_to_balizero
from unified_scraper import BaliZeroScraperV2
from intel_pipeline import IntelPipeline, PipelineArticle

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

    # Initialize Telegram approval system
    from telegram_approval import TelegramApproval
    telegram = TelegramApproval() if not dry_run else None

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

            # Send to Telegram for approval (HTML formatted)
            if telegram and not dry_run:
                try:
                    article_data = {
                        "title": enriched.headline,
                        "content": enriched.executive_brief,
                        "enriched_content": f"{enriched.facts}\n\n{enriched.bali_zero_take}",
                        "category": enriched.category,
                        "source": item.get("source", "Unknown"),
                        "source_url": item.get("sourceUrl", ""),
                        "image_url": enriched.cover_image or "",
                    }

                    pending = await telegram.submit_for_approval(
                        article=article_data,
                        seo_metadata=enriched.seo_metadata or {},
                        enriched_content=f"{enriched.facts}\n\n{enriched.bali_zero_take}",
                    )

                    if pending.telegram_message_id:
                        logger.success(f"   📱 Telegram sent! Message ID: {pending.telegram_message_id}")
                        sent_count += 1
                    else:
                        logger.warning("   ⚠️ Telegram notification failed (check config)")
                except Exception as e:
                    logger.error(f"   ❌ Telegram error: {e}")

            # Send to Intelligence/News Room (backend staging)
            if not dry_run:
                result = await enricher.send_to_api(enriched, api_key=api_key)
                if result.get("success") and not result.get("duplicate"):
                    logger.info("   📰 Sent to Intelligence/News Room")
                elif result.get("duplicate"):
                    logger.info("   ⏭️ Already in database")
                else:
                    # Don't count as failure if Telegram worked
                    if not (telegram and sent_count > 0):
                        failed_count += 1
            else:
                logger.info(f"   🔍 DRY RUN - Would send: {enriched.headline[:40]}...")

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


async def run_massive_mode(
    categories: Optional[List[str]] = None,
    tiers: Optional[List[str]] = None,
    limit_per_source: int = 5,
    min_score: int = 40,
    generate_images: bool = True,
    require_approval: bool = True,
    dry_run: bool = False,
) -> Dict:
    """
    MASSIVE MODE: Scrape 790+ sources + full intel pipeline.

    This is the COMPLETE pipeline:
    1. BaliZeroScraperV2 → Fetch from 790+ configured sources
    2. LLAMA Scorer → Fast local scoring (filter noise)
    3. Claude Validator → Intelligent gate (approve/reject)
    4. Claude Max Enrichment → Full executive brief
    5. Gemini Image → Browser automation for cover images
    6. SEO/AEO → Optimize for search engines + AI
    7. Telegram Approval → Human review
    8. Publish → Send to BaliZero API
    """
    logger.info("=" * 70)
    logger.info("🚀 BALIZERO INTEL FEED - MASSIVE MODE")
    logger.info(f"📅 {datetime.now().isoformat()}")
    logger.info("=" * 70)
    logger.info("📊 Sources: 790+ web sources (unified_sources.json + extended_sources.json)")
    logger.info(f"🎯 Categories: {categories or 'ALL'}")
    logger.info(f"📈 Tiers: {tiers or ['T1', 'T2']}")
    logger.info(f"🔢 Min Score: {min_score}")
    logger.info(f"🖼️  Generate Images: {generate_images}")
    logger.info(f"✅ Require Approval: {require_approval}")
    logger.info(f"🔍 Dry Run: {dry_run}")
    logger.info("=" * 70)

    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: MASSIVE WEB SCRAPING (790+ sources)
    # ═══════════════════════════════════════════════════════════════════
    logger.info("\n" + "=" * 70)
    logger.info("📰 STEP 1: MASSIVE WEB SCRAPING")
    logger.info("=" * 70)

    # Get config path relative to this script
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "config" / "unified_sources.json"

    scraper = BaliZeroScraperV2(
        config_path=str(config_path),
        min_score=min_score,
    )

    # Initialize scraper components (SmartExtractor, OllamaScorer, SemanticDeduplicator)
    await scraper.initialize()

    # Scrape all sources
    scrape_results = await scraper.scrape_all(
        limit=limit_per_source,
        categories=categories,
    )

    logger.info(f"\n📊 Scraping Results:")
    logger.info(f"   Total Found: {scrape_results.get('stats', {}).get('total_found', 0)}")
    logger.info(f"   Saved: {scrape_results.get('stats', {}).get('saved', 0)}")
    logger.info(f"   Filtered (low score): {scrape_results.get('stats', {}).get('filtered_low_score', 0)}")
    logger.info(f"   Filtered (duplicate): {scrape_results.get('stats', {}).get('filtered_duplicate', 0)}")

    # Get scraped articles from data/raw directory
    scraped_articles = []
    raw_dir = Path("data/raw")

    if raw_dir.exists():
        for category_dir in raw_dir.iterdir():
            if category_dir.is_dir():
                for md_file in category_dir.glob("*.md"):
                    try:
                        # Parse markdown frontmatter
                        content = md_file.read_text(encoding="utf-8")
                        lines = content.split("\n")

                        # Extract frontmatter
                        article = {"content": ""}
                        in_frontmatter = False
                        content_lines = []

                        for line in lines:
                            if line.strip() == "---":
                                in_frontmatter = not in_frontmatter
                                continue
                            if in_frontmatter and ":" in line:
                                key, val = line.split(":", 1)
                                article[key.strip()] = val.strip()
                            elif not in_frontmatter:
                                content_lines.append(line)

                        article["content"] = "\n".join(content_lines)
                        article["summary"] = article["content"][:500] if article["content"] else ""

                        if article.get("title") and article.get("url"):
                            scraped_articles.append(article)
                    except Exception as e:
                        logger.debug(f"Error parsing {md_file}: {e}")

    logger.info(f"\n📋 Loaded {len(scraped_articles)} articles for pipeline processing")

    if not scraped_articles:
        logger.warning("❌ No articles to process")
        return {
            "mode": "massive",
            "scrape_results": scrape_results,
            "pipeline_results": None,
            "total_scraped": 0,
            "total_processed": 0,
        }

    # ═══════════════════════════════════════════════════════════════════
    # STEP 2-7: INTEL PIPELINE (Scoring → Validation → Enrichment → etc.)
    # ═══════════════════════════════════════════════════════════════════
    logger.info("\n" + "=" * 70)
    logger.info("🔬 STEPS 2-7: INTEL PIPELINE")
    logger.info("=" * 70)

    pipeline = IntelPipeline(
        min_llama_score=min_score,
        auto_approve_threshold=75,
        generate_images=generate_images,
        require_approval=require_approval,
        dry_run=dry_run,
    )

    # Process through pipeline
    processed_articles, stats = await pipeline.process_batch(scraped_articles)

    # ═══════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════
    logger.info("\n" + "=" * 70)
    logger.info("✅ MASSIVE MODE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"📰 Scraped: {len(scraped_articles)}")
    logger.info(f"📊 LLAMA Scored: {stats.llama_scored}")
    logger.info(f"❌ LLAMA Filtered: {stats.llama_filtered}")
    logger.info(f"🔍 Claude Validated: {stats.claude_validated}")
    logger.info(f"✅ Claude Approved: {stats.claude_approved}")
    logger.info(f"❌ Claude Rejected: {stats.claude_rejected}")
    logger.info(f"✍️  Enriched: {stats.enriched}")
    logger.info(f"🖼️  Images: {stats.images_generated}")
    logger.info(f"🔎 SEO Optimized: {stats.seo_optimized}")
    logger.info(f"📨 Pending Approval: {stats.pending_approval}")
    logger.info(f"📤 Published: {stats.published}")
    logger.info(f"⏱️  Duration: {stats.duration_seconds:.1f}s")
    logger.info("=" * 70)

    return {
        "mode": "massive",
        "scrape_results": scrape_results,
        "total_scraped": len(scraped_articles),
        "total_processed": stats.llama_scored,
        "approved": stats.claude_approved,
        "enriched": stats.enriched,
        "pending_approval": stats.pending_approval,
        "published": stats.published,
        "duration_seconds": stats.duration_seconds,
    }


async def main():
    parser = argparse.ArgumentParser(
        description="BaliZero Intel Feed - Complete News Intelligence Pipeline"
    )

    # Mode selection
    parser.add_argument(
        "--mode",
        choices=["massive", "full", "quick", "enrich-only"],
        default="quick",
        help="Pipeline mode: massive (790+ sources), full (RSS + deep enrichment), quick (RSS+score only), enrich-only (enrich DB articles)",
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

    # Massive mode options
    parser.add_argument(
        "--categories",
        nargs="+",
        help="Categories to scrape (e.g., immigration tax_bkpm property)",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image generation",
    )
    parser.add_argument(
        "--no-approval",
        action="store_true",
        help="Skip Telegram approval (auto-publish)",
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv("BALIZERO_API_KEY")

    if not api_key and not args.dry_run:
        logger.warning("No API key provided. Use --api-key or set BALIZERO_API_KEY")

    # Run selected mode
    if args.mode == "massive":
        result = await run_massive_mode(
            categories=args.categories,
            limit_per_source=args.limit,
            min_score=args.min_score,
            generate_images=not args.no_images,
            require_approval=not args.no_approval,
            dry_run=args.dry_run,
        )
    elif args.mode == "full":
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
