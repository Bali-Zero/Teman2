"""KG Sensor — Knowledge Graph coverage per tracked query.

The thinker uses this to identify queries where we have strong KG
support (>= 10 facts on a relevant entity) but weak on-page SEO — a
candidate for LOW/MED-tier actor (content refresh, schema injection).

Sprint 1: stub. Returns yellow with empty coverage.
Sprint 2: queries the KG via
apps/backend-rag/backend/services/graphrag/ for each GSC query string,
returning {query: {entity_canonical, fact_count, last_updated}}.
"""
from __future__ import annotations

from cell_core.types import SensorReading


class KGSensor:
    name = "kg"

    async def read(self, **context) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={"coverage": {}},
            metadata={
                "stub": True,
                "note": "Sprint 2 queries graphrag entity linker",
            },
        )
