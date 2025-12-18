"""
BALI ZERO INTEL SCRAPER - Unified Multi-Category Scraper
Target: Expat & Indonesian Business Community
Cost: ~$0.0004 per article (91% cheaper than Claude-only)
"""

import json
import httpx
import asyncio
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import hashlib
from pathlib import Path
from loguru import logger
from dateutil import parser as dateparser
import re
from urllib.parse import urljoin
from pydantic import BaseModel, HttpUrl, field_validator, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser, Page

# Configure logging
logger.add("logs/scraper_{time}.log", rotation="1 day", retention="7 days")


class ScrapedItem(BaseModel):
    """Validated scraped item with Pydantic"""
    title: str
    content: str
    url: HttpUrl
    source: str
    tier: str
    category: str
    scraped_at: str
    content_id: str
    published_at: Optional[str] = "unknown"

    @field_validator('content')
    @classmethod
    def validate_content_length(cls, v):
        if len(v) < 100:
            raise ValueError(f"Content too short ({len(v)} chars, minimum 100)")
        return v

    @field_validator('title')
    @classmethod
    def validate_title_length(cls, v):
        if len(v) < 10:
            raise ValueError(f"Title too short ({len(v)} chars, minimum 10)")
        return v

    @field_validator('tier')
    @classmethod
    def validate_tier(cls, v):
        valid_tiers = ['T1', 'T2', 'T3']
        if v not in valid_tiers:
            raise ValueError(f"Invalid tier '{v}', must be one of {valid_tiers}")
        return v


class BaliZeroScraper:
    """Unified scraper for Bali Zero Intelligence System - Async optimized"""

    def __init__(self, config_path: str = "config/categories.json", max_age_days: int = 5, max_concurrent: int = 10):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.output_dir = Path("data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Cache for deduplication
        self.cache_file = Path("data/scraper_cache.json")
        self.seen_hashes = self.load_cache()

        # Date filtering
        self.max_age_days = max_age_days

        # User-Agent rotation
        self.ua = UserAgent()

        # Async concurrency control
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Adaptive rate limiting
        self.base_delay = 1.0  # Start with 1s delay
        self.max_delay = 10.0  # Max 10s delay
        self.current_delay = self.base_delay
        self.consecutive_errors = 0
        self.request_times = []  # Track last 10 request times

        # Auto-save cache every N items
        self.cache_save_interval = 10
        self.items_since_save = 0

        # Health tracking per source
        self.source_health = {}  # {source_name: {success: int, failed: int, last_success: datetime}}
        self.health_file = Path("data/source_health.json")

        self.stats = {
            "total_found": 0,
            "filtered_old": 0,
            "filtered_duplicate": 0,
            "filtered_short": 0,
            "saved": 0
        }

        # Playwright browser (lazy initialization)
        self._browser: Optional[Browser] = None
        self._playwright = None

        logger.info(
            f"Initialized Bali Zero Scraper with {self.config['total_categories']} categories"
        )
        logger.info(f"Max article age: {max_age_days} days")
        logger.info(f"User-Agent rotation enabled ✓")
        logger.info(f"Async mode: max {max_concurrent} concurrent requests ✓")
        logger.info(f"Browser automation: Playwright (lazy init) ✓")

    def load_config(self) -> Dict:
        """Load scraper configuration"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_cache(self) -> set:
        """Load seen content hashes"""
        if self.cache_file.exists():
            with open(self.cache_file, "r") as f:
                return set(json.load(f))
        return set()

    def save_cache(self):
        """Save seen content hashes"""
        with open(self.cache_file, "w") as f:
            json.dump(list(self.seen_hashes), f)

    def content_hash(self, content: str) -> str:
        """Generate SHA-256 hash for content deduplication (first 32 chars)"""
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _adjust_rate_limit(self, success: bool, response_time: float = 0):
        """Adjust rate limiting based on response time and success rate"""
        if success:
            # Track response time
            self.request_times.append(response_time)
            if len(self.request_times) > 10:
                self.request_times.pop(0)

            # Reset consecutive errors
            self.consecutive_errors = 0

            # If average response time is fast, decrease delay
            if len(self.request_times) >= 5:
                avg_time = sum(self.request_times) / len(self.request_times)
                if avg_time < 1.0:  # Fast responses
                    self.current_delay = max(self.base_delay * 0.5, 0.5)
                elif avg_time < 2.0:  # Normal responses
                    self.current_delay = self.base_delay
                else:  # Slow responses
                    self.current_delay = min(self.base_delay * 2, self.max_delay)
        else:
            # Increase delay on errors (exponential backoff)
            self.consecutive_errors += 1
            self.current_delay = min(
                self.base_delay * (2 ** self.consecutive_errors),
                self.max_delay
            )
            logger.warning(f"⚠️  Rate limit adjusted: {self.current_delay:.1f}s (errors: {self.consecutive_errors})")

    async def _adaptive_delay(self):
        """Apply adaptive delay between requests"""
        await asyncio.sleep(self.current_delay)

    def _update_source_health(self, source_name: str, success: bool, items_count: int = 0):
        """Track health status for each source"""
        if source_name not in self.source_health:
            self.source_health[source_name] = {
                "success_count": 0,
                "failure_count": 0,
                "last_success": None,
                "total_items": 0
            }

        if success:
            self.source_health[source_name]["success_count"] += 1
            self.source_health[source_name]["last_success"] = datetime.now().isoformat()
            self.source_health[source_name]["total_items"] += items_count
        else:
            self.source_health[source_name]["failure_count"] += 1

        # Save health data periodically
        self._save_health()

    def _save_health(self):
        """Save source health data to file"""
        try:
            with open(self.health_file, "w") as f:
                json.dump(self.source_health, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save health data: {e}")

    def get_health_report(self) -> Dict:
        """Generate health report for all sources"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "sources": []
        }

        for source_name, health in self.source_health.items():
            total = health["success_count"] + health["failure_count"]
            success_rate = (health["success_count"] / total * 100) if total > 0 else 0

            report["sources"].append({
                "name": source_name,
                "success_rate": f"{success_rate:.1f}%",
                "total_items": health["total_items"],
                "last_success": health["last_success"],
                "status": "healthy" if success_rate >= 80 else "degraded" if success_rate >= 50 else "failing"
            })

        return report

    def _extract_date(self, elem, source: Dict, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publication date from element or page"""

        # Try source-specific date selectors first
        date_selectors = source.get('date_selectors', [])

        # Add common fallback selectors
        date_selectors.extend([
            'time[datetime]',
            'meta[property="article:published_time"]',
            'meta[name="publishdate"]',
            '.date',
            '.published',
            '.post-date',
            '.entry-date',
            'span[class*="date"]',
            'div[class*="date"]',
        ])

        # Try each selector
        for selector in date_selectors:
            try:
                # Try in element first
                date_elem = elem.select_one(selector)
                if not date_elem:
                    # Try in full page
                    date_elem = soup.select_one(selector)

                if date_elem:
                    # Extract date string
                    date_str = (
                        date_elem.get('datetime') or
                        date_elem.get('content') or
                        date_elem.get_text(strip=True)
                    )

                    if date_str:
                        parsed_date = self._parse_flexible_date(date_str)
                        if parsed_date:
                            return parsed_date
            except Exception as e:
                continue

        return None

    def _parse_flexible_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats including Indonesian"""

        if not date_str or len(date_str) < 5:
            return None

        # Clean the string
        date_str = date_str.strip()

        # Indonesian month mapping
        indonesian_months = {
            'januari': 'january', 'jan': 'jan',
            'februari': 'february', 'feb': 'feb',
            'maret': 'march', 'mar': 'mar',
            'april': 'april', 'apr': 'apr',
            'mei': 'may', 'may': 'may',
            'juni': 'june', 'jun': 'jun',
            'juli': 'july', 'jul': 'jul',
            'agustus': 'august', 'agu': 'aug',
            'september': 'september', 'sep': 'sep',
            'oktober': 'october', 'okt': 'oct',
            'november': 'november', 'nov': 'nov',
            'desember': 'december', 'des': 'dec',
        }

        # Replace Indonesian months with English
        date_str_lower = date_str.lower()
        for indo, eng in indonesian_months.items():
            date_str_lower = date_str_lower.replace(indo, eng)

        # Try dateutil parser (handles most formats)
        try:
            parsed = dateparser.parse(date_str_lower, fuzzy=True)
            if parsed:
                return parsed
        except:
            pass

        # Try common patterns manually
        patterns = [
            r'(\d{4})-(\d{2})-(\d{2})',  # 2025-01-15
            r'(\d{2})/(\d{2})/(\d{4})',  # 15/01/2025
            r'(\d{2})-(\d{2})-(\d{4})',  # 15-01-2025
        ]

        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        # Try different date orderings
                        for date_format in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                            try:
                                return datetime.strptime(match.group(0), date_format)
                            except:
                                continue
                except:
                    pass

        return None

    def _is_date_fresh(self, published_date: Optional[datetime]) -> bool:
        """Check if article is fresh enough (within max_age_days)"""

        if not published_date:
            # If no date found, assume it's fresh (conservative approach)
            logger.debug("No date found, assuming fresh")
            return True

        age_days = (datetime.now() - published_date).days

        if age_days > self.max_age_days:
            logger.debug(f"Article too old: {age_days} days (max: {self.max_age_days})")
            return False

        return True

    def get_headers(self) -> Dict[str, str]:
        """Get headers with rotated User-Agent"""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    async def _get_browser(self) -> Browser:
        """Get or initialize Playwright browser (lazy initialization)"""
        if self._browser is None:
            logger.info("🌐 Initializing Playwright browser...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            logger.info("✅ Playwright browser initialized")
        return self._browser

    async def _fetch_url_browser(self, url: str) -> str:
        """
        Fetch URL using Playwright browser (for JavaScript-heavy sites or redirect issues).
        Handles redirects, JavaScript execution, and dynamic content.
        """
        async with self.semaphore:
            for attempt in range(3):
                try:
                    logger.debug(f"Fetching with browser: {url} (attempt {attempt + 1}/3)")

                    browser = await self._get_browser()
                    context = await browser.new_context(
                        user_agent=self.ua.random,
                        viewport={'width': 1920, 'height': 1080}
                    )
                    page = await context.new_page()

                    # Navigate with retry
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                    # Wait for content to load
                    await page.wait_for_load_state('networkidle', timeout=10000)

                    # Get page content
                    html = await page.content()

                    await context.close()

                    logger.debug(f"✅ Browser fetch successful: {url}")
                    return html

                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise
                    wait_time = 2 ** attempt
                    logger.warning(f"Browser retry {attempt + 1}/3 failed for {url}: {e}, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)

    async def _fetch_url(self, url: str, headers: Dict, use_browser: bool = False) -> str:
        """
        Fetch URL async with automatic retry (3 attempts, exponential backoff).
        Tracks response time for adaptive rate limiting.

        Args:
            url: URL to fetch
            headers: HTTP headers
            use_browser: If True, use Playwright browser instead of httpx (for JS/redirect issues)
        """
        # Route to browser if requested
        if use_browser:
            start_time = time.time()
            try:
                result = await self._fetch_url_browser(url)
                response_time = time.time() - start_time
                self._adjust_rate_limit(success=True, response_time=response_time)
                return result
            except Exception as e:
                self._adjust_rate_limit(success=False)
                raise

        # Standard httpx fetch with response time tracking
        async with self.semaphore:
            for attempt in range(3):
                try:
                    logger.debug(f"Fetching: {url} (attempt {attempt + 1}/3)")
                    start_time = time.time()
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        response = await client.get(url, headers=headers)
                        response.raise_for_status()
                        response_time = time.time() - start_time
                        self._adjust_rate_limit(success=True, response_time=response_time)
                        return response.text
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    self._adjust_rate_limit(success=False)
                    if attempt == 2:  # Last attempt
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Retry {attempt + 1}/3 failed for {url}: {e}, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)

    async def scrape_source(self, source: Dict, category: str) -> List[Dict[str, Any]]:
        """Scrape a single source (async with optional browser automation)"""
        use_browser = source.get("use_browser", False)
        method = "🌐 Browser" if use_browser else "⚡ HTTP"
        logger.info(f"[{category}] Scraping {source['name']} (Tier {source['tier']}) via {method}")

        items = []

        try:
            # Get headers with rotated User-Agent
            headers = self.get_headers()

            # Fetch with automatic retry (async) - browser if needed
            html_content = await self._fetch_url(source["url"], headers, use_browser=use_browser)

            soup = BeautifulSoup(html_content, "html.parser")

            # Try each selector
            for selector in source["selectors"]:
                elements = soup.select(selector)

                for elem in elements[:10]:  # Max 10 per selector
                    self.stats["total_found"] += 1

                    # Extract title
                    title_elem = elem.find(["h1", "h2", "h3", "h4", "a"])
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)

                    # Extract content
                    content_elem = elem.find(["p", "div.content", "div.summary"])
                    content = (
                        content_elem.get_text(strip=True)
                        if content_elem
                        else elem.get_text(strip=True)
                    )

                    # Minimum content length filter
                    if len(content) < 100:
                        self.stats["filtered_short"] += 1
                        continue

                    # Extract link
                    link_elem = elem.find("a")
                    link = (
                        link_elem["href"]
                        if link_elem and "href" in link_elem.attrs
                        else source["url"]
                    )

                    # Make link absolute
                    if link.startswith("/"):
                        link = urljoin(source["url"], link)

                    # Extract publication date
                    published_date = self._extract_date(elem, source, soup)

                    # Date freshness filter
                    if not self._is_date_fresh(published_date):
                        self.stats["filtered_old"] += 1
                        age_days = (datetime.now() - published_date).days if published_date else "unknown"
                        logger.debug(f"Filtered old: {title[:50]}... ({age_days} days old)")
                        continue

                    # Duplicate check
                    content_id = self.content_hash(title + content[:500])
                    if content_id in self.seen_hashes:
                        self.stats["filtered_duplicate"] += 1
                        continue

                    # Article passed all filters - save it
                    items.append(
                        {
                            "title": title,
                            "content": content,
                            "url": link,
                            "source": source["name"],
                            "tier": source["tier"],
                            "category": category,
                            "published_at": published_date.isoformat() if published_date else None,
                            "scraped_at": datetime.now().isoformat(),
                            "content_id": content_id,
                        }
                    )

                    self.seen_hashes.add(content_id)
                    self.stats["saved"] += 1

                    # Auto-save cache every N items (crash resilience)
                    self.items_since_save += 1
                    if self.items_since_save >= self.cache_save_interval:
                        self.save_cache()
                        self.items_since_save = 0
                        logger.debug(f"💾 Auto-saved cache ({len(self.seen_hashes)} hashes)")

                if items:
                    break  # Found items with this selector

            logger.info(
                f"[{category}] Found {len(items)} new items from {source['name']}"
            )

            # Update health tracking
            self._update_source_health(source['name'], success=True, items_count=len(items))

            return items

        except Exception as e:
            logger.error(f"[{category}] Error scraping {source['name']}: {e}")

            # Update health tracking
            self._update_source_health(source['name'], success=False)

            return []

    async def scrape_category(self, category_key: str, limit: int = 10) -> int:
        """Scrape all sources for a category (async with parallel processing)"""

        if category_key not in self.config["categories"]:
            logger.error(f"Category '{category_key}' not found in config")
            return 0

        category = self.config["categories"][category_key]
        logger.info(
            f"📰 Scraping category: {category['name']} (Priority: {category['priority']})"
        )

        # Scrape all sources in parallel (semaphore controls concurrency)
        tasks = [self.scrape_source(source, category_key) for source in category["sources"]]
        all_items = await asyncio.gather(*tasks, return_exceptions=True)

        total_items = 0

        # Save items from all sources
        for source_items in all_items:
            if isinstance(source_items, Exception):
                logger.error(f"Source scraping failed: {source_items}")
                continue

            for item in source_items:
                self.save_raw_item(item, category_key)
                total_items += 1

                if total_items >= limit:
                    logger.info(f"[{category_key}] Reached limit of {limit} items")
                    break

            if total_items >= limit:
                break

        logger.success(f"[{category_key}] Scraped {total_items} items total")
        return total_items

    def save_raw_item(self, item: Dict, category: str):
        """Save raw scraped item to file with Pydantic validation"""

        # Validate item with Pydantic
        try:
            validated_item = ScrapedItem(**item)
        except ValidationError as e:
            logger.error(f"Validation failed for item: {e}")
            logger.debug(f"Invalid item data: {item}")
            return  # Skip invalid items

        # Create category directory
        category_dir = self.output_dir / category
        category_dir.mkdir(exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source_slug = item["source"].replace(" ", "_").replace("/", "_")
        filename = f"{timestamp}_{source_slug}.md"

        filepath = category_dir / filename

        # Format as markdown
        content = f"""---
title: {item['title']}
source: {item['source']}
tier: {item['tier']}
category: {item['category']}
url: {item['url']}
published_at: {item.get('published_at', 'unknown')}
scraped_at: {item['scraped_at']}
content_id: {item['content_id']}
---

# {item['title']}

**Source:** {item['source']} ({item['tier']})
**URL:** {item['url']}
**Published:** {item.get('published_at', 'Date not found')}
**Scraped:** {item['scraped_at']}

---

{item['content']}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.debug(f"Saved: {filepath}")

    async def scrape_all_categories(self, limit: int = 10, categories: List[str] = None):
        """Scrape all categories in parallel (async optimized)"""

        logger.info("=" * 70)
        logger.info("🚀 BALI ZERO INTEL SCRAPER - Starting Async Scraping Cycle")
        logger.info("=" * 70)

        import time
        start_time = time.time()

        # Determine which categories to scrape
        if categories:
            category_keys = [k for k in categories if k in self.config["categories"]]
        else:
            category_keys = list(self.config["categories"].keys())

        logger.info(f"📋 Scraping {len(category_keys)} categories in parallel")

        # Scrape all categories in parallel
        tasks = [self.scrape_category(category_key, limit=limit) for category_key in category_keys]
        counts = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dict
        results = {}
        total_scraped = 0
        for category_key, count in zip(category_keys, counts):
            if isinstance(count, Exception):
                logger.error(f"Category {category_key} failed: {count}")
                results[category_key] = 0
            else:
                results[category_key] = count
                total_scraped += count

        # Save cache
        self.save_cache()

        # Summary
        duration = time.time() - start_time

        logger.info("=" * 70)
        logger.info("✅ SCRAPING COMPLETE")
        logger.info(f"📊 Total Found: {self.stats['total_found']}")
        logger.info(f"✅ Saved: {self.stats['saved']}")
        logger.info(f"❌ Filtered (old): {self.stats['filtered_old']}")
        logger.info(f"❌ Filtered (duplicate): {self.stats['filtered_duplicate']}")
        logger.info(f"❌ Filtered (too short): {self.stats['filtered_short']}")
        logger.info(f"⏱️  Duration: {duration:.1f}s")
        logger.info(f"📁 Output: {self.output_dir}")
        logger.info("=" * 70)

        # Print results per category
        for category, count in results.items():
            logger.info(f"  {category:25s} → {count:3d} items")

        # Cleanup browser if initialized
        await self.cleanup()

        return {
            "success": True,
            "total_scraped": total_scraped,
            "duration_seconds": duration,
            "categories": results,
            "output_dir": str(self.output_dir),
        }

    async def cleanup(self):
        """Cleanup resources (close browser if initialized)"""
        if self._browser:
            logger.info("🧹 Closing Playwright browser...")
            await self._browser.close()
            await self._playwright.stop()
            self._browser = None
            self._playwright = None
            logger.info("✅ Browser closed")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bali Zero Intel Scraper")
    parser.add_argument("--categories", nargs="+", help="Specific categories to scrape")
    parser.add_argument("--limit", type=int, default=10, help="Max items per category")
    parser.add_argument(
        "--config", default="config/categories.json", help="Config file path"
    )

    args = parser.parse_args()

    scraper = BaliZeroScraper(config_path=args.config)
    results = scraper.scrape_all_categories(
        limit=args.limit, categories=args.categories
    )

    print(
        f"\n✅ Scraping complete: {results['total_scraped']} items in {results['duration_seconds']:.1f}s"
    )


if __name__ == "__main__":
    main()
