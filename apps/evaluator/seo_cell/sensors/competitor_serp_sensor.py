"""Competitor SERP Sensor — our rank vs Cekindo + Emerhub for tracked queries.

Decision memo constraint: max 2 vendors (Cekindo, Emerhub), cache 7gg.
The cache is critical — daily SERP scraping would create decision
contamination (we would see competitors react to our changes before
real users do).

Sprint 1: stub. Returns yellow with empty ranks.
Sprint 2: reads cached SERP snapshots (cache key = query, TTL 7d). If
a query's cache is expired, schedules a re-scrape via a background
queue (not inline — scraping is slow and rate-limited).
"""
from __future__ import annotations

from cell_core.types import SensorReading

from apps.evaluator.seo_cell.config import COMPETITOR_DOMAINS


class CompetitorSERPSensor:
    name = "competitor_serp"

    def __init__(self, vendors: tuple[str, ...] = COMPETITOR_DOMAINS) -> None:
        self._vendors = vendors

    async def read(self, **context) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={"ranks": {}, "vendors": list(self._vendors)},
            metadata={
                "stub": True,
                "cache_ttl_days": 7,
                "note": "Sprint 2 reads cached SERP; no live scraping",
            },
        )
