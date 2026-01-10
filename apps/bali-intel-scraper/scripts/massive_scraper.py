#!/usr/bin/env python3
"""
MASSIVE SCRAPER - Scrape 790+ fonti in parallelo
=================================================
Usa TUTTE le fonti da unified_sources.json + extended_sources.json
Non solo sto cazzo di Google News RSS.
"""

import asyncio
import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

try:
    import trafilatura

    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False
    logger.warning("trafilatura not installed - using basic extraction")

try:
    from playwright.async_api import async_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("playwright not installed - JS sites won't render")


@dataclass
class ScrapedArticle:
    """Single scraped article"""

    url: str
    title: str
    content: str
    source_name: str
    source_tier: str
    category: str
    published_date: Optional[datetime] = None
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.md5(
                (self.title + self.content[:500]).encode()
            ).hexdigest()


@dataclass
class ScrapeStats:
    """Scraping statistics"""

    total_sources: int = 0
    sources_scraped: int = 0
    sources_failed: int = 0
    articles_found: int = 0
    articles_deduplicated: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def elapsed(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()


class MassiveScraper:
    """
    Scrape 790+ fonti in parallelo.
    - T1 (government): scrape con rispetto
    - T2 (news): scrape aggressivo
    - T3 (blogs/forums): scrape veloce
    """

    def __init__(
        self,
        config_dir: str = "../config",
        max_concurrent: int = 50,
        timeout: int = 15,
        max_articles_per_source: int = 10,
    ):
        self.config_dir = Path(config_dir)
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_articles_per_source = max_articles_per_source
        self.sources = []
        self.stats = ScrapeStats()
        self.seen_hashes = set()
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def load_sources(self) -> int:
        """Load all sources from config files"""
        sources = []

        # Load unified_sources.json
        unified_path = self.config_dir / "unified_sources.json"
        if unified_path.exists():
            with open(unified_path) as f:
                data = json.load(f)
                for category, cat_data in data.get("categories", {}).items():
                    for source in cat_data.get("sources", []):
                        sources.append(
                            {**source, "category": category, "config_file": "unified"}
                        )

        # Load extended_sources.json
        extended_path = self.config_dir / "extended_sources.json"
        if extended_path.exists():
            with open(extended_path) as f:
                data = json.load(f)
                for category, cat_data in data.get("categories", {}).items():
                    # Extended has nested structure
                    for subcategory, subsources in cat_data.items():
                        if isinstance(subsources, list):
                            for source in subsources:
                                sources.append(
                                    {
                                        **source,
                                        "category": category,
                                        "subcategory": subcategory,
                                        "config_file": "extended",
                                    }
                                )

        # Deduplicate by URL
        seen_urls = set()
        unique_sources = []
        for s in sources:
            url = s.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(s)

        self.sources = unique_sources
        self.stats.total_sources = len(unique_sources)
        logger.info(f"Loaded {len(unique_sources)} unique sources from config")
        return len(unique_sources)

    async def fetch_page(self, url: str, use_playwright: bool = False) -> Optional[str]:
        """Fetch page content"""
        try:
            if use_playwright and HAS_PLAYWRIGHT:
                return await self._fetch_with_playwright(url)
            else:
                return await self._fetch_with_httpx(url)
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None

    async def _fetch_with_httpx(self, url: str) -> Optional[str]:
        """Simple HTTP fetch"""
        async with self.semaphore:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
        return None

    async def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """Fetch JS-rendered page with Playwright"""
        async with self.semaphore:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=self.timeout * 1000)
                    await page.wait_for_load_state("networkidle", timeout=5000)
                    content = await page.content()
                    return content
                finally:
                    await browser.close()
        return None

    def extract_articles(
        self,
        html: str,
        base_url: str,
        source_name: str,
        source_tier: str,
        category: str,
    ) -> list[ScrapedArticle]:
        """Extract articles from page"""
        articles = []
        soup = BeautifulSoup(html, "lxml")
        domain = urlparse(base_url).netloc

        # Find article links - common patterns
        article_links = set()

        # Look for <article> tags
        for article in soup.find_all("article"):
            link = article.find("a", href=True)
            if link:
                article_links.add(link["href"])

        # Look for common article patterns
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Common article URL patterns
            if any(
                pattern in href
                for pattern in [
                    "/berita/",
                    "/news/",
                    "/article/",
                    "/post/",
                    "/tag/",
                    "/category/",
                    "/search",
                    "-20",
                    "-202",  # date patterns
                ]
            ):
                article_links.add(href)

        # Normalize URLs
        normalized = set()
        for link in article_links:
            if link.startswith("/"):
                link = f"https://{domain}{link}"
            elif not link.startswith("http"):
                link = f"https://{domain}/{link}"
            if domain in link:  # Only same-domain links
                normalized.add(link)

        # Extract content from each article (limited)
        for url in list(normalized)[: self.max_articles_per_source]:
            title = self._extract_title_from_url(url)
            if title:
                articles.append(
                    ScrapedArticle(
                        url=url,
                        title=title,
                        content="",  # Will be enriched later
                        source_name=source_name,
                        source_tier=source_tier,
                        category=category,
                    )
                )

        return articles

    def _extract_title_from_url(self, url: str) -> Optional[str]:
        """Extract title from URL slug"""
        path = urlparse(url).path
        # Get last path segment
        segments = [s for s in path.split("/") if s]
        if segments:
            slug = segments[-1]
            # Remove file extension
            slug = re.sub(r"\.(html|php|aspx?)$", "", slug)
            # Remove common prefixes
            slug = re.sub(r"^(article|berita|news)-?", "", slug)
            # Replace separators with spaces
            title = re.sub(r"[-_]", " ", slug)
            # Clean up
            title = re.sub(r"\d{8,}", "", title)  # Remove date numbers
            title = title.strip().title()
            if len(title) > 10:  # Minimum title length
                return title
        return None

    async def scrape_source(self, source: dict) -> list[ScrapedArticle]:
        """Scrape a single source"""
        url = source.get("url", "")
        name = source.get("name", "Unknown")
        tier = source.get("tier", "T3")
        category = source.get("category", "general")

        # Determine if we need Playwright (JS-heavy sites)
        needs_js = any(
            domain in url
            for domain in [
                "instagram.com",
                "facebook.com",
                "twitter.com",
                "linkedin.com",
                "crunchbase.com",
            ]
        )

        try:
            html = await self.fetch_page(url, use_playwright=needs_js)
            if html:
                articles = self.extract_articles(html, url, name, tier, category)
                self.stats.sources_scraped += 1
                self.stats.articles_found += len(articles)
                if articles:
                    logger.info(f"✅ [{tier}] {name}: {len(articles)} articles")
                return articles
            else:
                self.stats.sources_failed += 1
                return []
        except Exception as e:
            self.stats.sources_failed += 1
            logger.debug(f"❌ {name}: {e}")
            return []

    def deduplicate(self, articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        """Remove duplicate articles by content hash"""
        unique = []
        for article in articles:
            if article.content_hash not in self.seen_hashes:
                self.seen_hashes.add(article.content_hash)
                unique.append(article)

        self.stats.articles_deduplicated = len(articles) - len(unique)
        return unique

    async def scrape_all(
        self,
        categories: Optional[list[str]] = None,
        tiers: Optional[list[str]] = None,
    ) -> list[ScrapedArticle]:
        """Scrape all sources in parallel"""

        # Filter sources
        sources_to_scrape = self.sources
        if categories:
            sources_to_scrape = [
                s for s in sources_to_scrape if s.get("category") in categories
            ]
        if tiers:
            sources_to_scrape = [s for s in sources_to_scrape if s.get("tier") in tiers]

        logger.info(f"🚀 Scraping {len(sources_to_scrape)} sources...")

        # Scrape in parallel
        tasks = [self.scrape_source(s) for s in sources_to_scrape]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)

        # Deduplicate
        unique_articles = self.deduplicate(all_articles)

        logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║                    MASSIVE SCRAPE COMPLETE                    ║
╠══════════════════════════════════════════════════════════════╣
║  Sources Total:      {self.stats.total_sources:>6}                               ║
║  Sources Scraped:    {self.stats.sources_scraped:>6}                               ║
║  Sources Failed:     {self.stats.sources_failed:>6}                               ║
║  Articles Found:     {self.stats.articles_found:>6}                               ║
║  After Dedup:        {len(unique_articles):>6}                               ║
║  Time Elapsed:       {self.stats.elapsed():>6.1f}s                              ║
╚══════════════════════════════════════════════════════════════╝
        """)

        return unique_articles

    def export_results(
        self,
        articles: list[ScrapedArticle],
        output_path: str = "data/scraped_articles.json",
    ):
        """Export results to JSON"""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "scraped_at": datetime.now().isoformat(),
            "stats": {
                "total_sources": self.stats.total_sources,
                "sources_scraped": self.stats.sources_scraped,
                "articles_found": self.stats.articles_found,
                "articles_unique": len(articles),
                "elapsed_seconds": self.stats.elapsed(),
            },
            "articles": [
                {
                    "url": a.url,
                    "title": a.title,
                    "source_name": a.source_name,
                    "source_tier": a.source_tier,
                    "category": a.category,
                    "content_hash": a.content_hash,
                }
                for a in articles
            ],
        }

        with open(output, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"📁 Exported {len(articles)} articles to {output}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Massive Scraper - 790+ fonti")
    parser.add_argument("--categories", nargs="+", help="Filter by categories")
    parser.add_argument(
        "--tiers", nargs="+", default=["T1", "T2"], help="Filter by tiers"
    )
    parser.add_argument(
        "--concurrent", type=int, default=50, help="Max concurrent requests"
    )
    parser.add_argument(
        "--output", default="data/scraped_articles.json", help="Output file"
    )
    args = parser.parse_args()

    scraper = MassiveScraper(
        config_dir="../config",
        max_concurrent=args.concurrent,
    )

    scraper.load_sources()

    articles = await scraper.scrape_all(
        categories=args.categories,
        tiers=args.tiers,
    )

    scraper.export_results(articles, args.output)

    return articles


if __name__ == "__main__":
    asyncio.run(main())
