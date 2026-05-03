"""SentinelThinker — normalizes, scores, and cross-references harvested items.

Implements cell_core.protocols.Thinker.
"""
from __future__ import annotations

import logging
from typing import Any

from cell_core.types import HomeostaticState, Proposal, SensorReading

from mata_garuda.workers.base_worker import content_hash

logger = logging.getLogger("mata_garuda.cells")


class SentinelThinker:
    """Reasons about sensor readings: dedup, score, cross-reference."""

    def __init__(self, seen_hashes: set[str] | None = None):
        self._seen = seen_hashes or set()

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal:
        """Process all sensor readings into a unified collection of items."""
        all_items = []
        sources_ok = 0
        sources_fail = 0

        for reading in readings:
            if reading.status == "red":
                sources_fail += 1
                continue
            sources_ok += 1

            items = reading.value or []
            if not isinstance(items, list):
                continue

            for item in items:
                # Normalize to common schema
                title = item.get("title", "")
                url = item.get("url", "")
                h = content_hash(f"{title}{url}")

                if h in self._seen:
                    continue
                self._seen.add(h)

                all_items.append({
                    "title": title,
                    "url": url,
                    "source": item.get("source", reading.sensor_name),
                    "content": item.get("abstract", item.get("description", item.get("content", "")))[:800],
                    "sensor": reading.sensor_name,
                    "hash": h,
                })

        if not all_items:
            return Proposal(
                action="none",
                reason=f"No new items ({sources_ok} sources ok, {sources_fail} failed)",
                confidence=0.0,
                tier_used=0,
            )

        return Proposal(
            action="publish_all",
            reason=f"{len(all_items)} new items from {sources_ok} sources (deduped from {sum(r.metadata.get('count', 0) for r in readings if r.status != 'red')} raw)",
            confidence=0.9,
            tier_used=1,
            cost_usd=0.0,
        )

    def get_deduped_items(self, readings: list[SensorReading]) -> list[dict]:
        """Extract all unique items from readings (called by Actor after think approves)."""
        items = []
        seen = set()

        for reading in readings:
            if reading.status == "red" or not reading.value:
                continue
            for item in reading.value:
                title = item.get("title", "")
                url = item.get("url", "")
                h = content_hash(f"{title}{url}")
                if h in seen:
                    continue
                seen.add(h)
                items.append({
                    "title": title,
                    "url": url,
                    "source": item.get("source", reading.sensor_name),
                    "content": item.get("abstract", item.get("description", item.get("content", "")))[:800],
                    "sensor": reading.sensor_name,
                })

        return items
