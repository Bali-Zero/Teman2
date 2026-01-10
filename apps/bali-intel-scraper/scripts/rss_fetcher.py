"""
Google News RSS Fetcher for Bali Zero Intel Feed
Fetches fresh news from Google News RSS and sends to BaliZero website

Features:
- Multi-topic RSS fetching (immigration, business, tax, property, AI/tech)
- Professional 5-dimension scoring (Relevance, Authority, Recency, Accuracy, Geographic)
- Optional Ollama enhancement for edge cases
- Bilingual keyword matching (English + Bahasa Indonesia)
"""

import httpx
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from loguru import logger
import re
from pathlib import Path

# Import professional scorer
from professional_scorer import score_article, ScoreResult

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/rss_fetcher_{time}.log", rotation="1 day", retention="7 days")


class GoogleNewsRSSFetcher:
    """Fetch news from Google News RSS for Indonesia/Bali-related topics"""

    # Topics to search for (query, category)
    TOPICS = [
        # Immigration
        ("Indonesia visa KITAS regulation", "immigration"),
        ("Bali visa immigration", "immigration"),
        ("Indonesia golden visa", "immigration"),
        ("digital nomad visa Indonesia", "immigration"),
        # Business
        ("Indonesia PT PMA foreign investment", "business"),
        ("Indonesia business regulation BKPM", "business"),
        ("Bali business startup", "business"),
        ("Indonesia KBLI OSS", "business"),
        # Tax
        ("Indonesia tax regulation pajak", "tax"),
        ("Indonesia NPWP tax", "tax"),
        ("Indonesia corporate tax PPh", "tax"),
        # Property
        ("Bali property real estate", "property"),
        ("Indonesia land ownership foreigner", "property"),
        ("Bali villa investment", "property"),
        # AI/Tech
        ("Indonesia AI artificial intelligence", "tech"),
        ("Indonesia startup technology funding", "tech"),
        ("Indonesia fintech digital economy", "tech"),
        ("Indonesia kecerdasan buatan", "tech"),
        # Lifestyle (lower priority)
        ("Bali expat news", "lifestyle"),
        ("Bali digital nomad", "lifestyle"),
    ]

    def __init__(self, max_age_days: int = 7):
        self.max_age_days = max_age_days
        self.base_url = "https://news.google.com/rss/search"

    def _build_rss_url(self, query: str) -> str:
        """Build Google News RSS URL for a query"""
        from urllib.parse import quote_plus
        encoded_query = quote_plus(query)  # Proper URL encoding
        return f"{self.base_url}?q={encoded_query}&hl=en-ID&gl=ID&ceid=ID:en"

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse RSS pubDate to datetime"""
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
            except ValueError:
                return None

    def _is_fresh(self, pub_date: Optional[datetime]) -> bool:
        """Check if article is within max_age_days"""
        if not pub_date:
            return True
        cutoff = datetime.utcnow() - timedelta(days=self.max_age_days)
        return pub_date > cutoff

    def _extract_source(self, item: ET.Element) -> str:
        """Extract source name from RSS item"""
        source = item.find("source")
        if source is not None:
            return source.text or "Unknown"
        return "Google News"

    def _clean_title(self, title: str) -> str:
        """Remove source suffix from title"""
        return re.sub(r"\s+-\s+[\w\s]+$", "", title).strip()

    async def fetch_topic(self, query: str, category: str) -> List[Dict]:
        """Fetch news for a single topic"""
        url = self._build_rss_url(query)
        items = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                root = ET.fromstring(response.content)
                channel = root.find("channel")

                if channel is None:
                    return items

                for item in channel.findall("item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_date_elem = item.find("pubDate")
                    desc_elem = item.find("description")

                    if title_elem is None or link_elem is None:
                        continue

                    pub_date = None
                    if pub_date_elem is not None:
                        pub_date = self._parse_date(pub_date_elem.text)

                    if not self._is_fresh(pub_date):
                        continue

                    title = self._clean_title(title_elem.text or "Untitled")
                    source = self._extract_source(item)

                    # Extract summary from description
                    summary = ""
                    if desc_elem is not None and desc_elem.text:
                        summary = re.sub(r"<[^>]+>", "", desc_elem.text).strip()
                        if len(summary) > 300:
                            summary = summary[:297] + "..."

                    news_item = {
                        "title": title,
                        "summary": summary or f"Latest news from {source}",
                        "content": summary,
                        "source": source,
                        "sourceUrl": link_elem.text,
                        "category": category,
                        "priority": "medium",
                        "publishedAt": pub_date.isoformat() if pub_date else None,
                        "_pub_date": pub_date,  # For scoring
                    }

                    items.append(news_item)

                logger.info(f"[{category}] Found {len(items)} items for '{query}'")

        except Exception as e:
            logger.error(f"Error fetching {query}: {e}")

        return items

    async def fetch_all(
        self,
        limit_per_topic: int = 5,
        min_score: int = 35,
        use_ollama: bool = False,
    ) -> List[Dict]:
        """
        Fetch news from all topics with professional scoring.

        Args:
            limit_per_topic: Max items per topic before dedup
            min_score: Minimum score to include (0-100)
            use_ollama: Use Ollama for edge case enhancement
        """
        logger.info("=" * 70)
        logger.info("📰 BALI INTEL FEED - Professional News Fetcher")
        logger.info(f"📅 Max age: {self.max_age_days} days | Min score: {min_score}")
        logger.info("=" * 70)

        all_items = []

        # Fetch from all topics
        # NOTE: Deduplication is handled by semantic deduplicator in pipeline
        # Simple title-based dedup here can filter legitimate articles with similar titles
        for query, category in self.TOPICS:
            items = await self.fetch_topic(query, category)
            all_items.extend(items)

        logger.info(f"\n📊 Total unique items before scoring: {len(all_items)}")

        # Score all items
        logger.info("\n🎯 SCORING with Professional 5-Dimension System...")
        scored_items = []
        filtered_count = 0

        for item in all_items:
            result: ScoreResult = await score_article(
                title=item["title"],
                content=item.get("summary", ""),
                source=item["source"],
                source_url=item.get("sourceUrl", ""),
                published_at=item.get("_pub_date"),
                use_ollama=use_ollama,
            )

            # Apply score and priority
            item["relevance_score"] = result.final_score
            item["score_breakdown"] = result.explanation
            item["matched_keywords"] = result.matched_keywords
            item["priority"] = result.priority
            item["category"] = result.matched_category  # Use detected category

            # Remove internal fields
            item.pop("_pub_date", None)

            if result.final_score >= min_score:
                scored_items.append(item)
                status = "✅" if result.priority == "high" else "○"
                logger.info(
                    f"  {status} [{result.final_score:3d}] {item['title'][:55]}..."
                )
                logger.debug(f"      {result.explanation}")
            else:
                filtered_count += 1
                logger.debug(
                    f"  ❌ [{result.final_score:3d}] {item['title'][:55]}... (filtered)"
                )

        # Sort by score
        scored_items.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Show summary
        logger.info("\n📈 Scoring complete:")
        logger.info(f"   ✅ Passed: {len(scored_items)}")
        logger.info(f"   ❌ Filtered: {filtered_count}")

        # Category breakdown
        categories = {}
        priorities = {"high": 0, "medium": 0, "low": 0}
        for item in scored_items:
            cat = item["category"]
            categories[cat] = categories.get(cat, 0) + 1
            priorities[item["priority"]] = priorities.get(item["priority"], 0) + 1

        logger.info("\n📂 By Category:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            logger.info(f"   {cat}: {count}")

        logger.info(
            f"\n🎯 By Priority: HIGH={priorities['high']} MED={priorities['medium']} LOW={priorities['low']}"
        )

        return scored_items


async def send_to_balizero(
    items: List[Dict],
    api_url: str = "https://balizero.com",
    api_key: str = None,
    dry_run: bool = False,
):
    """Send items to BaliZero API"""
    endpoint = f"{api_url}/api/news"

    if dry_run:
        logger.warning("🔍 DRY RUN MODE - Not sending to API")
        for item in items:
            logger.info(
                f"  Would send: [{item['relevance_score']}] {item['title'][:55]}..."
            )
        return {"sent": len(items), "failed": 0, "duplicates": 0}

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    sent = 0
    failed = 0
    duplicates = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for item in items:
            try:
                # Prepare payload (remove internal scoring fields)
                payload = {
                    "title": item["title"],
                    "summary": item.get("summary"),
                    "content": item.get("content"),
                    "source": item["source"],
                    "source_url": item.get("sourceUrl"),
                    "category": item["category"],
                    "priority": item["priority"],
                    "published_at": item.get("publishedAt"),
                }

                response = await client.post(endpoint, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        if data.get("duplicate"):
                            duplicates += 1
                            logger.debug(f"⏭️ Duplicate: {item['title'][:50]}...")
                        else:
                            sent += 1
                            logger.success(f"✅ Sent: {item['title'][:50]}...")
                    else:
                        logger.error(f"❌ API rejected: {data}")
                        failed += 1
                else:
                    logger.error(
                        f"❌ HTTP {response.status_code}: {response.text[:100]}"
                    )
                    failed += 1

            except Exception as e:
                logger.error(f"❌ Error sending: {e}")
                failed += 1

            await asyncio.sleep(0.3)  # Rate limit

    return {"sent": sent, "failed": failed, "duplicates": duplicates}


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Bali Intel Feed - Professional News Fetcher"
    )
    parser.add_argument(
        "--max-age", type=int, default=7, help="Max article age in days"
    )
    parser.add_argument("--limit", type=int, default=5, help="Items per topic")
    parser.add_argument("--min-score", type=int, default=35, help="Min score (0-100)")
    parser.add_argument("--api-url", default="https://balizero.com", help="API URL")
    parser.add_argument("--api-key", default=None, help="API key")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without sending"
    )
    parser.add_argument("--send", action="store_true", help="Send to API")
    parser.add_argument(
        "--use-ollama", action="store_true", help="Use Ollama for edge cases"
    )

    args = parser.parse_args()

    fetcher = GoogleNewsRSSFetcher(max_age_days=args.max_age)
    items = await fetcher.fetch_all(
        limit_per_topic=args.limit,
        min_score=args.min_score,
        use_ollama=args.use_ollama,
    )

    if not items:
        logger.warning("No items passed scoring threshold!")
        return

    # Print items
    logger.info("\n" + "=" * 70)
    logger.info("📋 FINAL NEWS LIST")
    logger.info("=" * 70)
    for i, item in enumerate(items, 1):
        logger.info(
            f"  {i:2d}. [{item['relevance_score']:3d}] [{item['priority'].upper():6s}] "
            f"[{item['category']:12s}] {item['title'][:45]}..."
        )
        logger.info(f"      Source: {item['source']}")

    if args.send or args.dry_run:
        logger.info("\n" + "=" * 70)
        result = await send_to_balizero(
            items,
            api_url=args.api_url,
            api_key=args.api_key,
            dry_run=args.dry_run,
        )
        logger.info(
            f"\n📊 Results: Sent={result['sent']}, Failed={result['failed']}, Duplicates={result['duplicates']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
