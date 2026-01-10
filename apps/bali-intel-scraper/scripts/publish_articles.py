#!/usr/bin/env python3
"""
Publish articles to Intelligence/News Room backend
"""

import asyncio
import json
import aiohttp
from pathlib import Path
from loguru import logger

BACKEND_URL = "https://nuzantara-rag.fly.dev"
API_KEY = "zantara-secret-2024"


async def publish_article(article_file: Path, main_news_position: int = None):
    """Publish single article to backend"""

    # Read article data
    with open(article_file, "r") as f:
        article = json.load(f)

    # Prepare payload
    payload = {
        "title": article["title"],
        "content": article["enriched_content"],
        "category": article["category"],
        "source": article["source"],
        "source_url": article["source_url"],
        "image_url": article["image_url"],
        "relevance_score": article["relevance_score"],
        "published_at": article["published_at"],
        "seo_metadata": article["seo_metadata"],
    }

    # Add main news position if specified
    if main_news_position:
        payload["main_news_position"] = main_news_position

    logger.info(f"Publishing: {article['title'][:50]}...")
    if main_news_position:
        logger.info(f"  → Main News slot {main_news_position}")
    else:
        logger.info("  → Generic (no main slot)")

    # Send to backend
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BACKEND_URL}/api/intel/scraper/submit",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status in [200, 201]:
                result = await resp.json()
                logger.success(f"✅ Published: {article['title'][:50]}")
                return result
            else:
                error = await resp.text()
                logger.error(f"❌ Failed ({resp.status}): {error}")
                return None


async def main():
    logger.info("=" * 70)
    logger.info("📰 PUBLISHING 3 ARTICLES TO INTELLIGENCE/NEWS ROOM")
    logger.info("=" * 70)

    articles = [
        ("data/pending_articles/9734b0ead0de.json", 3),  # dehuman → main slot 3
        ("data/pending_articles/0ac53d1ec30e.json", 4),  # deportation → main slot 4
        ("data/pending_articles/f5eeffd81984.json", None),  # golden → generic
    ]

    results = []
    for article_file, position in articles:
        result = await publish_article(Path(article_file), position)
        results.append(result)
        await asyncio.sleep(2)  # Rate limiting

    logger.info("=" * 70)
    logger.info(f"✅ COMPLETE: {sum(1 for r in results if r)} published")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
