"""GSC Sensor — Google Search Console query performance.

Sprint 1: stub. Returns yellow with {"stub": True, "queries": []}.
Sprint 2: pulls last-28d queries from webmasters v3 API using the SA at
.secrets/google-credentials.json (already siteOwner of balizero.com).
Emits per-query: impressions, clicks, position, CTR.

The sensor's value must include `query_count` (distinct query strings
seen in the window) so the pre_natal gate can evaluate unlock.
"""
from __future__ import annotations

from cell_core.types import SensorReading


class GSCSensor:
    name = "gsc"

    def __init__(self, window_days: int = 28) -> None:
        self._window_days = window_days

    async def read(self, **context) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={"queries": [], "query_count": 0, "clicks_total": 0},
            metadata={
                "stub": True,
                "window_days": self._window_days,
                "note": "Sprint 2 implements webmasters v3 fetch",
            },
        )
