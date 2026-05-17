"""
Robots.txt compliance checker.

Respects robots.txt rules including:
- Disallow directives
- Crawl-delay
- Sitemap references
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse

import aiohttp
from protego import Protego

from backend.core.cache import cache
from backend.core.logger import get_logger, LogAction
from backend.core.rate_limiter import get_registry

logger = get_logger(__name__, component="robots_checker")


@dataclass
class RobotsRules:
    """Parsed robots.txt rules."""

    url: str
    allowed: bool
    crawl_delay: float | None = None
    sitemaps: list[str] = None
    fetched_at: datetime = None

    def __post_init__(self):
        if self.sitemaps is None:
            self.sitemaps = []
        if self.fetched_at is None:
            self.fetched_at = datetime.now()


class RobotsChecker:
    """Check and respect robots.txt rules."""

    def __init__(self, user_agent: str = "BaliIntelBot/1.0", cache_ttl_hours: int = 24):
        self.user_agent = user_agent
        self.cache_ttl = cache_ttl_hours * 3600
        self._rules_cache: dict[str, RobotsRules] = {}
        self._crawl_delays: dict[str, float] = {}

    def _get_robots_url(self, url: str) -> str:
        """Get robots.txt URL from page URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _get_cache_key(self, robots_url: str) -> str:
        """Generate cache key for robots.txt."""
        return f"robots:{robots_url}"

    async def fetch_robots_txt(self, robots_url: str) -> str | None:
        """Fetch robots.txt content."""
        try:
            async with aiohttp.ClientSession() as session, session.get(
                robots_url,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"User-Agent": self.user_agent},
            ) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 404:
                    # No robots.txt means allow all
                    return ""
                else:
                    logger.warning(
                        f"Unexpected status {response.status} for {robots_url}",
                        action=LogAction.ERROR,
                    )
                    return None

        except Exception as e:
            logger.warning(f"Failed to fetch {robots_url}: {e}", action=LogAction.ERROR)
            return None

    async def get_rules(self, url: str) -> RobotsRules:
        """Get robots.txt rules for URL."""
        robots_url = self._get_robots_url(url)

        # Check cache first
        cache_key = self._get_cache_key(robots_url)

        cached = await cache.get(cache_key)
        if cached:
            return RobotsRules(**cached)

        # Check memory cache
        if robots_url in self._rules_cache:
            rules = self._rules_cache[robots_url]
            # Check if still fresh
            age = datetime.now() - rules.fetched_at
            if age < timedelta(hours=24):
                return rules

        # Fetch fresh rules
        content = await self.fetch_robots_txt(robots_url)

        if content is None:
            # Fetch failed, assume allowed with conservative defaults
            rules = RobotsRules(
                url=robots_url,
                allowed=True,
                crawl_delay=5.0,  # Conservative delay
            )
        elif content == "":
            # No robots.txt, allow all
            rules = RobotsRules(url=robots_url, allowed=True, crawl_delay=None)
        else:
            # Parse robots.txt
            try:
                rp = Protego.parse(content)

                allowed = rp.can_fetch(url, self.user_agent)
                crawl_delay = rp.crawl_delay(self.user_agent)
                sitemaps = list(rp.sitemaps)

                rules = RobotsRules(
                    url=robots_url,
                    allowed=allowed,
                    crawl_delay=crawl_delay,
                    sitemaps=sitemaps,
                )

            except Exception as e:
                logger.warning(
                    f"Failed to parse robots.txt: {e}", action=LogAction.ERROR
                )
                rules = RobotsRules(url=robots_url, allowed=True, crawl_delay=5.0)

        # Cache rules
        self._rules_cache[robots_url] = rules
        await cache.set(
            cache_key,
            {
                "url": rules.url,
                "allowed": rules.allowed,
                "crawl_delay": rules.crawl_delay,
                "sitemaps": rules.sitemaps,
                "fetched_at": rules.fetched_at.isoformat(),
            },
            ttl=self.cache_ttl,
        )

        # Setup rate limiter for crawl delay
        if rules.crawl_delay:
            parsed = urlparse(url)
            host = parsed.netloc

            registry = get_registry()
            registry.create_bucket(
                name=f"crawl_delay:{host}", rate=1.0 / rules.crawl_delay, capacity=1
            )

        return rules

    async def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        rules = await self.get_rules(url)
        return rules.allowed

    async def check_and_delay(self, url: str) -> bool:
        """
        Check if can fetch and apply crawl delay.

        Returns True if allowed and delay has been applied.
        """
        rules = await self.get_rules(url)

        if not rules.allowed:
            logger.info(
                f"URL blocked by robots.txt: {url[:100]}", action=LogAction.SKIP
            )
            return False

        # Apply crawl delay
        if rules.crawl_delay:
            parsed = urlparse(url)
            host = parsed.netloc

            registry = get_registry()
            bucket = registry.get_bucket(f"crawl_delay:{host}")

            if bucket:
                await bucket.acquire(tokens=1)

        return True

    async def get_sitemaps(self, url: str) -> list[str]:
        """Get sitemap URLs from robots.txt."""
        rules = await self.get_rules(url)
        return rules.sitemaps

    async def get_crawl_delay(self, url: str) -> float | None:
        """Get crawl delay for URL."""
        rules = await self.get_rules(url)
        return rules.crawl_delay

    async def is_indexing_allowed(self, url: str) -> bool:
        """Check if indexing is allowed for URL."""
        # This would require more detailed parsing
        # For now, use same as can_fetch
        return await self.can_fetch(url)

    async def get_stats(self) -> dict:
        """Get checker statistics."""
        return {
            "cached_rules": len(self._rules_cache),
            "hosts_with_delays": len(self._crawl_delays),
        }

    async def clear_cache(self) -> None:
        """Clear all cached rules."""
        self._rules_cache.clear()
        self._crawl_delays.clear()

        # Clear cache entries
        keys = await cache.keys("robots:*")
        for key in keys:
            await cache.delete(key)

        logger.info("Robots cache cleared", action=LogAction.DELETE)


# Global checker instance
robots_checker = RobotsChecker()


async def can_fetch(url: str) -> bool:
    """Quick check if URL can be fetched."""
    return await robots_checker.can_fetch(url)


async def check_and_delay(url: str) -> bool:
    """Check and apply crawl delay."""
    return await robots_checker.check_and_delay(url)


__all__ = [
    "RobotsChecker",
    "RobotsRules",
    "robots_checker",
    "can_fetch",
    "check_and_delay",
]
