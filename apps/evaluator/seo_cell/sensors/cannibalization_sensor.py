"""Cannibalization Sensor — own URLs competing for the same query.

NEW sensor in v2.1. Flags cases where multiple balizero.com pages rank
in the top 10 for the same query — Google splits click-through across
them and none dominates. The thinker can then propose a consolidate-
and-redirect action (MED-tier, newsroom queue).

Detection: semantic clustering of (query, landing_page) pairs from the
GSC sensor output — if 2+ pages appear for queries that cluster to the
same intent, that's cannibalization.

Sprint 1: stub. Returns yellow with empty clusters.
Sprint 2: consumes GSC sensor value, embeddings via the same model we
use for RAG (text-embedding-3-small, 1536d — per CLAUDE.md §6, FROZEN).
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
