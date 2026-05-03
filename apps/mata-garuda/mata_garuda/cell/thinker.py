"""PassthroughThinker — MG decides internally, PulseLoop just gates.

MG's real reasoning happens inside MetaChain (the Actor). The Thinker's job
is simpler: look at sensor readings and decide IF we should run at all.
"""
from __future__ import annotations

import logging

from cell_core.types import HomeostaticState, Proposal, SensorReading

logger = logging.getLogger("mata_garuda.cell")


class PassthroughThinker:
    """Decides whether to trigger a MetaChain run based on sensor state."""

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict,
    ) -> Proposal:
        # During sleep, don't run agents (dream phase handles consolidation)
        if state.circadian_phase == "asleep":
            return Proposal(action="none", reason="sleeping — dream phase only", confidence=1.0, tier_used=-1)

        # Check regulation source
        source_reading = next(
            (r for r in readings if r.sensor_name == "regulation_source"), None
        )
        if source_reading and source_reading.status == "red":
            return Proposal(action="none", reason="regulation source unreachable", confidence=0.9, tier_used=-1)

        # Check fitness — if very low, prioritize running to recover
        fitness_reading = next(
            (r for r in readings if r.sensor_name.startswith("fitness:")), None
        )
        if fitness_reading and fitness_reading.status == "red":
            return Proposal(
                action="run_regulation_watcher",
                reason=f"fitness critical ({fitness_reading.value}), need recovery run",
                confidence=0.7,
                tier_used=0,
            )

        # Default: run the watcher (it's what MG does)
        return Proposal(
            action="run_regulation_watcher",
            reason="routine harvest cycle",
            confidence=0.9,
            tier_used=0,
        )
