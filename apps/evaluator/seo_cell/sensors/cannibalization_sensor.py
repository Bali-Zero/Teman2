"""Cannibalization — stub; relocation to thinker layer planned for Sprint 3.

Per Sprint 2d decision (commit 082b2f56e + test_sensors_stub.py header):
cannibalization is a DERIVED signal, not an independent sensor. It needs
the GSC rows (query × landing_page pairs) plus semantic clustering — both
thinker-layer work. Sensors are stateless and parallel; they cannot join
across each other's output.

Scheduled move: in Sprint 3 (thinker build-out) cannibalization detection
becomes a post-processing step over the GSCSensor reading, reusing the
RAG embedding model (text-embedding-3-small, 1536d; CLAUDE.md §6 FROZEN).
This stub stays so the 6-sensor contract in test_sensors_stub.py keeps
passing until Sprint 3 formally relocates it.
"""
from __future__ import annotations

from cell_core.types import SensorReading


class CannibalizationSensor:
    name = "cannibalization"

    async def read(self, **context) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={"clusters": []},
            metadata={
                "stub": True,
                "embedding_model": "text-embedding-3-small",
                "note": "Sprint 2 clusters GSC (query, page) pairs",
            },
        )
