"""
BALI INTEL SCRAPER - News Webhook Integration
Sends scraped news to BaliZero website for review and publication

Usage:
  python news_webhook.py --send-raw     # Send all raw scraped items
  python news_webhook.py --send-articles  # Send generated articles
  python news_webhook.py --dry-run      # Preview without sending
"""

import httpx
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
import re
import os

# Configure logging
logger.add("logs/webhook_{time}.log", rotation="1 day", retention="7 days")


class BaliZeroNewsWebhook:
    """
    Webhook integration to send scraped news to BaliZero website.
    Maps scraper output to BaliZero news API format.
    """

    def __init__(self, api_base_url: str = None):
        """
        Initialize webhook with API URL.

        Args:
            api_base_url: Base URL for BaliZero API (e.g., https://balizero.com)
                         Defaults to BALIZERO_API_URL env var or https://balizero.com
        """
        self.api_base_url = api_base_url or os.getenv(
            "BALIZERO_API_URL", "https://balizero.com"
        )
        self.news_endpoint = f"{self.api_base_url}/api/news"

        # Tier to priority mapping
        self.tier_priority_map = {
            "T1": "high",
            "T2": "medium",
            "T3": "low",
        }

        # Category mapping (scraper categories to website categories)
        self.category_map = {
            "immigration": "immigration",
            "visa": "immigration",
            "business": "business",
            "pt_pma": "business",
            "tax": "tax",
            "property": "property",
            "real_estate": "property",
            "lifestyle": "lifestyle",
            "tech": "tech",
            "legal": "business",
            "banking": "business",
            "employment": "business",
        }

        self.stats = {
            "sent": 0,
            "failed": 0,
            "skipped": 0,
        }

        logger.info(f"Initialized webhook for {self.api_base_url}")

    def _extract_metadata_from_markdown(self, content: str) -> Dict:
        """Extract metadata from markdown frontmatter."""
        metadata = {}

        # Parse YAML frontmatter
        frontmatter_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

        return metadata

    def _extract_content_body(self, content: str) -> str:
        """Extract main content body from markdown (after frontmatter and header)."""
        # Remove frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)

        # Remove markdown headers and metadata lines
        lines = []
        skip_next = False
        for line in content.split("\n"):
            if line.startswith("#"):
                continue
            if line.startswith("**Source:**") or line.startswith("**URL:**"):
                continue
            if line.startswith("**Published:**") or line.startswith("**Scraped:**"):
                continue
            if line.strip() == "---":
                continue
            lines.append(line)

        return "\n".join(lines).strip()

    def _generate_summary(self, content: str, max_length: int = 280) -> str:
        """Generate a summary from content (first paragraph or truncated)."""
        # Get first meaningful paragraph
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        if not paragraphs:
            return content[:max_length]

        summary = paragraphs[0]

        # Truncate if too long
        if len(summary) > max_length:
            summary = summary[: max_length - 3] + "..."

        return summary

    def _map_category(self, category: str) -> str:
        """Map scraper category to website category."""
        return self.category_map.get(category.lower(), "business")

    def _map_priority(self, tier: str) -> str:
        """Map scraper tier to priority."""
        return self.tier_priority_map.get(tier, "medium")

    def parse_raw_file(self, filepath: Path) -> Optional[Dict]:
        """
        Parse a raw scraped markdown file into news item format.

        Args:
            filepath: Path to markdown file

        Returns:
            Dict with news item data or None if parsing fails
        """
        try:
            content = filepath.read_text(encoding="utf-8")
            metadata = self._extract_metadata_from_markdown(content)
            body = self._extract_content_body(content)

            if not metadata.get("title") or not body:
                logger.warning(f"Missing title or content: {filepath.name}")
                return None

            # Build news item
            news_item = {
                "title": metadata.get("title", "Untitled"),
                "summary": self._generate_summary(body),
                "content": body,
                "source": metadata.get("source", "Unknown"),
                "sourceUrl": metadata.get("url", ""),
                "category": self._map_category(metadata.get("category", "business")),
                "priority": self._map_priority(metadata.get("tier", "T2")),
                "publishedAt": metadata.get("published_at")
                or metadata.get("scraped_at"),
            }

            return news_item

        except Exception as e:
            logger.error(f"Failed to parse {filepath}: {e}")
            return None

    async def send_news_item(self, item: Dict, dry_run: bool = False) -> bool:
        """
        Send a single news item to BaliZero API.

        Args:
            item: News item dict
            dry_run: If True, only log without sending

        Returns:
            True if successful, False otherwise
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would send: {item['title'][:60]}...")
            self.stats["sent"] += 1
            return True

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.news_endpoint,
                    json=item,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        logger.success(f"Sent: {item['title'][:60]}...")
                        self.stats["sent"] += 1
                        return True

                logger.error(f"API error: {response.status_code} - {response.text}")
                self.stats["failed"] += 1
                return False

        except Exception as e:
            logger.error(f"Failed to send: {item['title'][:40]}... - {e}")
            self.stats["failed"] += 1
            return False

    async def send_all_raw(
        self,
        raw_dir: Path = Path("data/raw"),
        categories: Optional[List[str]] = None,
        limit: int = 50,
        dry_run: bool = False,
    ) -> Dict:
        """
        Send all raw scraped items to BaliZero.

        Args:
            raw_dir: Directory with raw scraped files
            categories: Optional list of categories to send
            limit: Max items to send
            dry_run: Preview without sending

        Returns:
            Stats dict with sent/failed counts
        """
        logger.info("=" * 60)
        logger.info("📰 SENDING RAW SCRAPED NEWS TO BALIZERO")
        logger.info("=" * 60)

        if dry_run:
            logger.warning("🔍 DRY RUN MODE - No actual API calls")

        # Find all raw files
        files = []
        if categories:
            for cat in categories:
                cat_dir = raw_dir / cat
                if cat_dir.exists():
                    files.extend(list(cat_dir.glob("*.md")))
        else:
            files = list(raw_dir.glob("**/*.md"))

        logger.info(f"Found {len(files)} raw files")

        # Sort by date (newest first)
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Limit
        if len(files) > limit:
            logger.info(f"Limiting to {limit} items")
            files = files[:limit]

        # Parse and send
        for filepath in files:
            item = self.parse_raw_file(filepath)
            if item:
                await self.send_news_item(item, dry_run=dry_run)
            else:
                self.stats["skipped"] += 1

            # Small delay between requests
            if not dry_run:
                await asyncio.sleep(0.5)

        # Summary
        logger.info("=" * 60)
        logger.success("✅ WEBHOOK COMPLETE")
        logger.info(f"📤 Sent: {self.stats['sent']}")
        logger.info(f"❌ Failed: {self.stats['failed']}")
        logger.info(f"⏭️  Skipped: {self.stats['skipped']}")
        logger.info("=" * 60)

        return self.stats

    async def send_single(self, item: Dict, dry_run: bool = False) -> bool:
        """Send a single item dict directly."""
        return await self.send_news_item(item, dry_run=dry_run)


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Send scraped news to BaliZero")
    parser.add_argument(
        "--send-raw", action="store_true", help="Send raw scraped items"
    )
    parser.add_argument("--categories", nargs="+", help="Specific categories to send")
    parser.add_argument("--limit", type=int, default=50, help="Max items to send")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without sending"
    )
    parser.add_argument("--api-url", help="BaliZero API base URL")

    args = parser.parse_args()

    webhook = BaliZeroNewsWebhook(api_base_url=args.api_url)

    if args.send_raw:
        asyncio.run(
            webhook.send_all_raw(
                categories=args.categories, limit=args.limit, dry_run=args.dry_run
            )
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
