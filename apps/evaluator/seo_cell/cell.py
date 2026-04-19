"""SEO Cell factory.

`create_seo_cell()` returns a PulseLoop wired with 6 stub sensors,
SEOThinker (pre_natal returns Proposal(action="none")), and SEOActor
(refuses everything outside the sprint1 whitelist).

The pre_natal gate is enforced by the thinker returning action="none" —
the base PulseLoop skips the act phase entirely when action is "none",
so the actor never runs while pre_natal. For Sprint 2 when actions
fire, we still propagate the phase to the actor via a callback on
`on_pulse` (no subclass needed — the sense-phase hooks in the base
PulseLoop are not called by the base, so overriding them is dead code,
as seen in the existing sentinel_cell.py).
"""
from __future__ import annotations

import logging

from cell_core.homeostasis import HomeostaticController
from cell_core.lifecycle import Maturation
from cell_core.memory_sqlite import SqliteMemoryStack
from cell_core.pulse import PulseLoop
from cell_core.safety import SafetyGate
from cell_core.types import CellConfig, PulseResult

from apps.evaluator.seo_cell import config
from apps.evaluator.seo_cell.actor import SEOActor
from apps.evaluator.seo_cell.sensors import (
    CannibalizationSensor,
    CompetitorSERPSensor,
    GA4Sensor,
    GSCSensor,
    KGSensor,
    WarRoomEventSensor,
)
from apps.evaluator.seo_cell.thinker import SEOThinker

logger = logging.getLogger("seo_cell")


def create_seo_cell() -> PulseLoop:
    """Factory: returns a ready-to-run PulseLoop for the SEO cell.

    Call `.single_pulse()` for one tick (cron-style) or `.run()` for
    the infinite loop. In Sprint 1 every pulse is sense-only because
    the thinker returns action="none" while pre_natal.
    """
    cell_config = CellConfig(
        name="seo-guardian",
        dna_path=str(config.DNA_PATH),
        pulse_interval_seconds=config.PULSE_INTERVAL_SECONDS,
        birth_date=config.cell_birth_date(),
        memory_backend="sqlite",
        db_path=str(config.DB_PATH),
        sleep_hours=config.SLEEP_HOURS,
    )

    memory = SqliteMemoryStack(cell_config.db_path)

    sensors = [
        GSCSensor(),
        GA4Sensor(),
        CompetitorSERPSensor(),
        KGSensor(),
        WarRoomEventSensor(),
        CannibalizationSensor(),
    ]

    thinker = SEOThinker()
    actor = SEOActor()
    lifecycle = Maturation(birth_date=cell_config.birth_date)
    safety = SafetyGate(disable_file="/tmp/seo_cell.disabled", cell_name="seo-guardian")
    homeostasis = HomeostaticController(cell_config.sleep_hours)

    async def on_pulse(result: PulseResult) -> None:
        # Propagate phase to actor for Sprint 2+ when actions can fire.
        # In Sprint 1 this is just bookkeeping.
        if thinker._last_phase is not None:
            actor.set_phase(thinker._last_phase)
        logger.info(
            "[seo_cell] pulse #%s: health=%s action=%s phase=%s",
            result.pulse_number,
            result.health_status,
            result.action_taken,
            thinker._last_phase.label if thinker._last_phase else "?",
        )

    return PulseLoop(
        config=cell_config,
        sensors=sensors,
        thinker=thinker,
        actor=actor,
        stm=memory.stm,
        ltm=memory.ltm,
        episodic=memory.episodic,
        lifecycle=lifecycle,
        safety=safety,
        homeostasis=homeostasis,
        on_pulse=on_pulse,
    )
