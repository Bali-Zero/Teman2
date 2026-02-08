"""
RSS and Atom feed parser.

Efficiently parses news feeds for article discovery.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
import feedparser

from backend.core.logger import get_logger, LogAction
from backend.core.rate_limiter import limit_scrape_request
from urllib.parse import urlparse

logger = get_logger(__name__, component="feed_parser")


@dataclass
class FeedEntry:
    """Parsed feed entry/article."""

    title: str
    link: str
    description: Optional[str] = None
    published: Optional[datetime] = None
    author: Optional[str] = None
    categories: List[str] = None
    content: Optional[str] = None
    guid: Optional[str] = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = []


@dataclass
class Feed:
    """Parsed feed."""

    title: str
    link: str
    description: Optional[str] = None
    language: Optional[str] = None
    last_build_date: Optional[datetime] = None
    entries: List[FeedEntry] = None

    def __post_init__(self):
        if self.entries is None:
            self.entries = []


class FeedParser:
    """Parse RSS and Atom feeds."""

    async def fetch_feed(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch feed content."""
        try:
            parsed = urlparse(url)
            await limit_scrape_request(parsed.netloc)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers={
                        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
                    },
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Feed fetch failed: HTTP {response.status}",
                            action=LogAction.ERROR,
                            metadata={"url": url[:100]},
                        )
                        return None

                    content_type = response.headers.get("content-type", "").lower()

                    # Check if it's actually a feed
                    if not any(
                        t in content_type for t in ["xml", "rss", "atom", "feed"]
                    ):
                        # Try anyway, feedparser is forgiving
                        pass

                    return await response.text()

        except Exception as e:
            logger.error(
                f"Failed to fetch feed: {e}",
                action=LogAction.ERROR,
                metadata={"url": url[:100]},
            )
            return None

    def parse_feed(self, content: str) -> Feed:
        """Parse feed content."""
        parsed = feedparser.parse(content)

        feed_data = Feed(
            title=parsed.feed.get("title", ""),
            link=parsed.feed.get("link", ""),
            description=parsed.feed.get("description"),
            language=parsed.feed.get("language"),
        )

        # Parse last build date
        if "updated_parsed" in parsed.feed:
            feed_data.last_build_date = datetime(*parsed.feed.updated_parsed[:6])
        elif "published_parsed" in parsed.feed:
            feed_data.last_build_date = datetime(*parsed.feed.published_parsed[:6])

        # Parse entries
        for entry in parsed.entries:
            feed_entry = self._parse_entry(entry)
            feed_data.entries.append(feed_entry)

        return feed_data

    def _parse_entry(self, entry: Dict) -> FeedEntry:
        """Parse single feed entry."""
        # Parse published date
        published = None
        if "published_parsed" in entry:
            published = datetime(*entry.published_parsed[:6])
        elif "updated_parsed" in entry:
            published = datetime(*entry.updated_parsed[:6])

        # Get content
        content = None
        if "content" in entry:
            content = entry.content[0].value if entry.content else None
        elif "summary_detail" in entry:
            content = entry.summary_detail.value
        elif "summary" in entry:
            content = entry.summary

        return FeedEntry(
            title=entry.get("title", ""),
            link=entry.get("link", ""),
            description=entry.get("summary"),
            published=published,
            author=entry.get("author"),
            categories=[tag.term for tag in entry.get("tags", [])],
            content=content,
            guid=entry.get("id") or entry.get("guid"),
        )

    async def parse_url(self, url: str, timeout: int = 30) -> Optional[Feed]:
        """Fetch and parse feed from URL."""
        content = await self.fetch_feed(url, timeout)

        if not content:
            return None

        try:
            feed = self.parse_feed(content)

            logger.info(
                f"Parsed feed: {feed.title}",
                action=LogAction.PARSE,
                metadata={"url": url[:100], "entries": len(feed.entries)},
            )

            return feed

        except Exception as e:
            logger.error(
                f"Failed to parse feed: {e}",
                action=LogAction.ERROR,
                metadata={"url": url[:100]},
            )
            return None

    async def get_new_entries(self, url: str, since: datetime) -> List[FeedEntry]:
        """
        Get entries newer than specified date.

        Args:
            url: Feed URL
            since: Only return entries after this date

        Returns:
            List of new entries
        """
        feed = await self.parse_url(url)

        if not feed:
            return []

        new_entries = [
            entry
            for entry in feed.entries
            if entry.published is None or entry.published > since
        ]

        logger.info(
            f"Found {len(new_entries)} new entries",
            action=LogAction.FILTER,
            metadata={"total": len(feed.entries), "new": len(new_entries)},
        )

        return new_entries

    def detect_feed_url(self, html_content: str, base_url: str) -> List[str]:
        """Detect feed URLs from HTML."""
        feed_urls = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, "html.parser")

            # Look for link tags
            for link in soup.find_all("link"):
                rel = link.get("rel", [])
                if isinstance(rel, str):
                    rel = [rel]

                if any(r in rel for r in ["alternate", "feed"]):
                    type_attr = link.get("type", "").lower()

                    if any(t in type_attr for t in ["rss", "atom", "feed"]):
                        href = link.get("href")
                        if href:
                            from urllib.parse import urljoin

                            feed_urls.append(urljoin(base_url, href))

        except ImportError:
            logger.warning(
                "BeautifulSoup not available for feed detection", action=LogAction.SKIP
            )

        return list(set(feed_urls))


# Global parser instance
feed_parser = FeedParser()


async def parse_feed(url: str) -> Optional[Feed]:
    """Quick function to parse a feed."""
    return await feed_parser.parse_url(url)


async def get_new_entries(url: str, since: datetime) -> List[FeedEntry]:
    """Quick function to get new feed entries."""
    return await feed_parser.get_new_entries(url, since)


__all__ = [
    "FeedParser",
    "Feed",
    "FeedEntry",
    "feed_parser",
    "parse_feed",
    "get_new_entries",
]
