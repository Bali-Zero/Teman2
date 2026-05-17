"""
Sitemap.xml parser for efficient URL discovery.

Supports:
- Standard sitemaps
- Sitemap indexes
- Compressed sitemaps (.gz)
- RSS/Atom as sitemaps
"""

import gzip
from dataclasses import dataclass
from datetime import datetime
from collections.abc import AsyncGenerator
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import aiohttp
from backend.core.logger import get_logger, LogAction
from backend.core.rate_limiter import limit_scrape_request
import contextlib

logger = get_logger(__name__, component="sitemap_parser")


@dataclass
class SitemapEntry:
    """Single sitemap entry."""

    url: str
    lastmod: datetime | None = None
    changefreq: str | None = None
    priority: float | None = None


@dataclass
class Sitemap:
    """Parsed sitemap."""

    url: str
    entries: list[SitemapEntry]
    is_index: bool = False
    sitemaps: list[str] = None  # For index sitemaps

    def __post_init__(self):
        if self.sitemaps is None:
            self.sitemaps = []


class SitemapParser:
    """Parse XML sitemaps."""

    NAMESPACES = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
        "video": "http://www.google.com/schemas/sitemap-video/1.1",
    }

    async def fetch_sitemap(self, url: str) -> str | None:
        """Fetch sitemap content."""
        try:
            parsed = urlparse(url)
            await limit_scrape_request(parsed.netloc)

            async with aiohttp.ClientSession() as session, session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    logger.warning(
                        f"Sitemap fetch failed: HTTP {response.status}",
                        action=LogAction.ERROR,
                        metadata={"url": url[:100]},
                    )
                    return None

                content = await response.read()

                # Handle gzip
                if (
                    url.endswith(".gz")
                    or response.headers.get("content-encoding") == "gzip"
                ):
                    content = gzip.decompress(content)

                return content.decode("utf-8")

        except Exception as e:
            logger.error(
                f"Failed to fetch sitemap: {e}",
                action=LogAction.ERROR,
                metadata={"url": url[:100]},
            )
            return None

    def parse_sitemap(self, content: str, base_url: str) -> Sitemap:
        """Parse sitemap XML content."""
        try:
            root = ET.fromstring(content)

            # Check if it's a sitemap index
            if root.tag.endswith("sitemapindex"):
                return self._parse_sitemap_index(root, base_url)

            # Regular sitemap
            return self._parse_urlset(root, base_url)

        except ET.ParseError as e:
            logger.error(f"Failed to parse sitemap XML: {e}", action=LogAction.ERROR)
            return Sitemap(url=base_url, entries=[], is_index=False)

    def _parse_sitemap_index(self, root: ET.Element, base_url: str) -> Sitemap:
        """Parse sitemap index."""
        sitemaps = []

        for sitemap_elem in root.findall(".//sm:sitemap", self.NAMESPACES):
            loc = sitemap_elem.find("sm:loc", self.NAMESPACES)
            if loc is not None and loc.text:
                sitemaps.append(loc.text)

        # Also try without namespace
        if not sitemaps:
            for sitemap_elem in root.findall(".//sitemap"):
                loc = sitemap_elem.find("loc")
                if loc is not None and loc.text:
                    sitemaps.append(loc.text)

        return Sitemap(url=base_url, entries=[], is_index=True, sitemaps=sitemaps)

    def _parse_urlset(self, root: ET.Element, base_url: str) -> Sitemap:
        """Parse URL set."""
        entries = []

        # Try with namespace
        for url_elem in root.findall(".//sm:url", self.NAMESPACES):
            entry = self._parse_url_entry(url_elem, True)
            if entry:
                entries.append(entry)

        # Try without namespace
        if not entries:
            for url_elem in root.findall(".//url"):
                entry = self._parse_url_entry(url_elem, False)
                if entry:
                    entries.append(entry)

        return Sitemap(url=base_url, entries=entries, is_index=False)

    def _parse_url_entry(
        self, url_elem: ET.Element, use_namespace: bool
    ) -> SitemapEntry | None:
        """Parse single URL entry."""
        ns = "sm:" if use_namespace else ""

        loc = url_elem.find(f"{ns}loc", self.NAMESPACES if use_namespace else {})
        if loc is None or not loc.text:
            return None

        url = loc.text

        # Parse lastmod
        lastmod = None
        lastmod_elem = url_elem.find(
            f"{ns}lastmod", self.NAMESPACES if use_namespace else {}
        )
        if lastmod_elem is not None and lastmod_elem.text:
            with contextlib.suppress(ValueError):
                lastmod = datetime.fromisoformat(
                    lastmod_elem.text.replace("Z", "+00:00")
                )

        # Parse changefreq
        changefreq = None
        cf_elem = url_elem.find(
            f"{ns}changefreq", self.NAMESPACES if use_namespace else {}
        )
        if cf_elem is not None and cf_elem.text:
            changefreq = cf_elem.text

        # Parse priority
        priority = None
        pri_elem = url_elem.find(
            f"{ns}priority", self.NAMESPACES if use_namespace else {}
        )
        if pri_elem is not None and pri_elem.text:
            with contextlib.suppress(ValueError):
                priority = float(pri_elem.text)

        return SitemapEntry(
            url=url, lastmod=lastmod, changefreq=changefreq, priority=priority
        )

    async def discover_urls(
        self, sitemap_url: str, since: datetime | None = None, max_urls: int = 10000
    ) -> AsyncGenerator[SitemapEntry, None]:
        """
        Discover URLs from sitemap and sub-sitemaps.

        Args:
            sitemap_url: URL of sitemap
            since: Only return URLs modified since this date
            max_urls: Maximum URLs to return
        """
        urls_found = 0
        sitemaps_to_process = [sitemap_url]
        processed_sitemaps: set[str] = set()

        while sitemaps_to_process and urls_found < max_urls:
            current_url = sitemaps_to_process.pop(0)

            if current_url in processed_sitemaps:
                continue

            processed_sitemaps.add(current_url)

            content = await self.fetch_sitemap(current_url)
            if not content:
                continue

            sitemap = self.parse_sitemap(content, current_url)

            if sitemap.is_index:
                # Add sub-sitemaps to queue
                for sub_sitemap in sitemap.sitemaps:
                    if sub_sitemap not in processed_sitemaps:
                        sitemaps_to_process.append(sub_sitemap)

                logger.info(
                    f"Found {len(sitemap.sitemaps)} sub-sitemaps",
                    action=LogAction.FETCH,
                    metadata={"sitemap": current_url[:100]},
                )
            else:
                # Yield entries
                for entry in sitemap.entries:
                    if since and entry.lastmod and entry.lastmod < since:
                        continue

                    yield entry
                    urls_found += 1

                    if urls_found >= max_urls:
                        break

        logger.info(
            f"Sitemap discovery complete: {urls_found} URLs",
            action=LogAction.END,
            metadata={"sitemap": sitemap_url[:100]},
        )

    async def get_sitemap_from_robots(self, base_url: str) -> list[str]:
        """Find sitemap URLs from robots.txt."""
        from backend.scrapers.robots_checker import robots_checker

        return await robots_checker.get_sitemaps(base_url)


# Global parser instance
sitemap_parser = SitemapParser()


async def discover_urls(
    sitemap_url: str, since: datetime | None = None, max_urls: int = 10000
) -> list[SitemapEntry]:
    """Quick function to discover URLs from sitemap."""
    urls = []
    async for entry in sitemap_parser.discover_urls(sitemap_url, since, max_urls):
        urls.append(entry)
    return urls


__all__ = [
    "SitemapParser",
    "Sitemap",
    "SitemapEntry",
    "sitemap_parser",
    "discover_urls",
]
