"""RSS Sensor — perceives AI newsletters and blogs."""
from __future__ import annotations

from cell_core.types import SensorReading

from mata_garuda.config import AI_RSS_FEEDS
from mata_garuda.tools.feed_tools import fetch_rss_feed, _parse_feed

import subprocess


class RSSSensor:
    """Fetches items from configured AI RSS feeds."""

    name = "rss"

    def __init__(self, feeds: list[str] | None = None, max_per_feed: int = 5):
        self._feeds = feeds or AI_RSS_FEEDS
        self._max_per_feed = max_per_feed

    async def read(self, **context) -> SensorReading:
        all_items = []
        errors = 0

        for feed_url in self._feeds:
            try:
                result = subprocess.run(
                    ["curl", "-sL", feed_url, "--connect-timeout", "10"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode == 0:
                    items = _parse_feed(result.stdout)[:self._max_per_feed]
                    for item in items:
                        item["feed_url"] = feed_url
                    all_items.extend(items)
                else:
                    errors += 1
            except Exception:
                errors += 1

        status = "green" if all_items else ("yellow" if errors < len(self._feeds) else "red")
        return SensorReading(
            sensor_name=self.name,
            status=status,
            value=all_items,
            metadata={"count": len(all_items), "feeds": len(self._feeds), "errors": errors},
        )
