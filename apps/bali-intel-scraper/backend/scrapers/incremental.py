"""
Incremental scraping - only fetch new content since last run.

Tracks crawl state to avoid re-processing existing content.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.core.cache import cache
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="incremental")


@dataclass
class CrawlState:
    """State tracking for incremental crawling."""

    source_id: str
    last_crawl_time: datetime
    last_content_hash: str
    urls_seen: set[str]
    urls_crawled: set[str]
    urls_failed: dict[str, str]  # url -> error
    items_count: int = 0
    new_items_count: int = 0


class IncrementalTracker:
    """Tracks crawling state for incremental updates."""

    def __init__(self, source_prefix: str = "crawl"):
        self.source_prefix = source_prefix
        self._ttl = 30 * 24 * 3600  # 30 days

    def _get_cache_key(self, source_id: str) -> str:
        """Generate cache key for source."""
        return f"{self.source_prefix}:state:{source_id}"

    async def get_last_crawl_time(self, source_id: str) -> datetime | None:
        """Get last successful crawl time."""
        state = await self.get_state(source_id)
        return state.last_crawl_time if state else None

    async def get_state(self, source_id: str) -> CrawlState | None:
        """Retrieve crawl state from cache."""
        cache_key = self._get_cache_key(source_id)
        data = await cache.get(cache_key)

        if data:
            # Convert sets back from lists
            return CrawlState(
                source_id=data["source_id"],
                last_crawl_time=datetime.fromisoformat(data["last_crawl_time"]),
                last_content_hash=data["last_content_hash"],
                urls_seen=set(data.get("urls_seen", [])),
                urls_crawled=set(data.get("urls_crawled", [])),
                urls_failed=data.get("urls_failed", {}),
                items_count=data.get("items_count", 0),
                new_items_count=data.get("new_items_count", 0),
            )

        return None

    async def save_state(self, state: CrawlState) -> None:
        """Save crawl state to cache."""
        cache_key = self._get_cache_key(state.source_id)

        # Convert sets to lists for serialization
        data = {
            "source_id": state.source_id,
            "last_crawl_time": state.last_crawl_time.isoformat(),
            "last_content_hash": state.last_content_hash,
            "urls_seen": list(state.urls_seen),
            "urls_crawled": list(state.urls_crawled),
            "urls_failed": state.urls_failed,
            "items_count": state.items_count,
            "new_items_count": state.new_items_count,
        }

        await cache.set(cache_key, data, ttl=self._ttl)

        logger.info(
            f"Crawl state saved for {state.source_id}",
            action=LogAction.SAVE,
            metadata={
                "urls_seen": len(state.urls_seen),
                "urls_crawled": len(state.urls_crawled),
                "new_items": state.new_items_count,
            },
        )

    async def should_crawl_url(
        self,
        source_id: str,
        url: str,
        content_hash: str | None = None,
        max_age_hours: int = 24,
    ) -> bool:
        """
        Check if URL should be crawled.

        Returns True if:
        - URL not seen before
        - Content hash changed
        - Last crawl older than max_age_hours
        """
        state = await self.get_state(source_id)

        if state is None:
            return True

        # Check if URL already crawled successfully
        if url in state.urls_crawled:
            # Check if content changed
            if content_hash and content_hash != state.last_content_hash:
                return True

            # Check age
            age = datetime.now() - state.last_crawl_time
            return age > timedelta(hours=max_age_hours)

        return True

    async def mark_url_seen(
        self,
        source_id: str,
        url: str,
        success: bool = True,
        error: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        """Mark URL as seen in crawl state."""
        state = await self.get_state(source_id)

        if state is None:
            state = CrawlState(
                source_id=source_id,
                last_crawl_time=datetime.now(),
                last_content_hash=content_hash or "",
                urls_seen=set(),
                urls_crawled=set(),
                urls_failed={},
            )

        state.urls_seen.add(url)

        if success:
            state.urls_crawled.add(url)
            state.urls_failed.pop(url, None)
            state.new_items_count += 1

            if content_hash:
                state.last_content_hash = content_hash
        else:
            if error:
                state.urls_failed[url] = error

        state.items_count += 1

        await self.save_state(state)

    async def start_crawl(self, source_id: str) -> CrawlState:
        """Initialize new crawl session."""
        state = await self.get_state(source_id)

        if state is None:
            state = CrawlState(
                source_id=source_id,
                last_crawl_time=datetime.now(),
                last_content_hash="",
                urls_seen=set(),
                urls_crawled=set(),
                urls_failed={},
            )

        state.last_crawl_time = datetime.now()
        state.new_items_count = 0

        logger.info(f"Started crawl for {source_id}", action=LogAction.START)

        return state

    async def finish_crawl(self, source_id: str, success: bool = True) -> None:
        """Mark crawl as finished."""
        state = await self.get_state(source_id)

        if state:
            state.last_crawl_time = datetime.now()
            await self.save_state(state)

            logger.info(
                f"Finished crawl for {source_id}",
                action=LogAction.END,
                metadata={
                    "success": success,
                    "new_items": state.new_items_count,
                    "total_items": state.items_count,
                },
            )

    async def get_stats(self, source_id: str) -> dict:
        """Get crawl statistics for source."""
        state = await self.get_state(source_id)

        if not state:
            return {"status": "no_data"}

        age = datetime.now() - state.last_crawl_time

        return {
            "source_id": source_id,
            "last_crawl": state.last_crawl_time.isoformat(),
            "age_hours": age.total_seconds() / 3600,
            "urls_seen": len(state.urls_seen),
            "urls_crawled": len(state.urls_crawled),
            "urls_failed": len(state.urls_failed),
            "success_rate": len(state.urls_crawled) / max(len(state.urls_seen), 1),
        }

    async def reset_source(self, source_id: str) -> None:
        """Reset crawl state for source."""
        cache_key = self._get_cache_key(source_id)
        await cache.delete(cache_key)

        logger.info(f"Reset crawl state for {source_id}", action=LogAction.DELETE)


class IncrementalFeedProcessor:
    """Process feeds incrementally based on publish date."""

    def __init__(self, tracker: IncrementalTracker):
        self.tracker = tracker

    async def filter_new_items(
        self, source_id: str, items: list[dict], date_field: str = "published"
    ) -> list[dict]:
        """
        Filter items to only return new ones.

        Args:
            source_id: Source identifier
            items: List of items with date field
            date_field: Field containing publish date

        Returns:
            List of items newer than last crawl
        """
        last_crawl = await self.tracker.get_last_crawl_time(source_id)

        if last_crawl is None:
            # First crawl, return all items
            return items

        new_items = []
        for item in items:
            item_date = item.get(date_field)
            if item_date:
                try:
                    if isinstance(item_date, str):
                        item_date = datetime.fromisoformat(
                            item_date.replace("Z", "+00:00")
                        )

                    if item_date > last_crawl:
                        new_items.append(item)
                except Exception:
                    # If date parsing fails, include item
                    new_items.append(item)
            else:
                # No date, include item
                new_items.append(item)

        logger.info(
            f"Filtered {len(new_items)} new items from {len(items)} total",
            action=LogAction.FILTER,
            metadata={
                "source_id": source_id,
                "new_items": len(new_items),
                "total_items": len(items),
            },
        )

        return new_items


# Global tracker instance
tracker = IncrementalTracker()


async def should_crawl(source_id: str, url: str) -> bool:
    """Quick check if URL should be crawled."""
    return await tracker.should_crawl_url(source_id, url)


__all__ = [
    "IncrementalTracker",
    "IncrementalFeedProcessor",
    "CrawlState",
    "tracker",
    "should_crawl",
]
