"""GA4 Sensor — conversion funnel metrics per landing page.

Sprint 1: stub. Returns yellow with {"stub": True, "sessions_by_page": {}}.
Sprint 2: pulls Analytics Data API v1beta reports:
  - sessions by landing_page (last 28d)
  - conversions (whatsapp_cta click) by landing_page
  - bounce rate by landing_page

Window aligns with GSCSensor (28d) so signals correlate.
"""
from __future__ import annotations

from cell_core.types import SensorReading


class GA4Sensor:
    name = "ga4"

    def __init__(self, window_days: int = 28) -> None:
        self._window_days = window_days

    async def read(self, **context) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={"sessions_by_page": {}, "conversions_by_page": {}},
            metadata={
                "stub": True,
                "window_days": self._window_days,
                "note": "Sprint 2 implements Analytics Data API v1beta",
            },
        )
