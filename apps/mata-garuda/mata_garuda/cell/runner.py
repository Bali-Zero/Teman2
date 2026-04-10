"""Runner — builds and runs the PulseLoop for Mata Garuda.

Entry points:
  python -m mata_garuda.cell.runner          # run forever
  python -m mata_garuda.cell.runner --once   # single pulse
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from cell_core import CellConfig, PulseLoop, Maturation, SafetyGate
from cell_core.homeostasis import HomeostaticController
from cell_core.identity import SelfModelManager

from mata_garuda.cell.actor import MetaChainActor
from mata_garuda.cell.memory_bridge import BridgeSTM, KnowledgeBridgeLTM, ReflectionEpisodicStore
from mata_garuda.cell.sensors import FitnessSensor, RegulationSensor
from mata_garuda.cell.thinker import PassthroughThinker
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.cell")

MG_BIRTH_DATE = datetime(2026, 4, 1, tzinfo=timezone.utc)
MG_DNA_PATH = str(Path(__file__).parent.parent / "dna.json")
MG_KB_PATH = str(Path(__file__).parent.parent.parent / "data" / "knowledge.db")
MG_SELF_MODEL_PATH = str(Path(__file__).parent.parent.parent / "data" / "self_model.json")


def build_pulse_loop(
    dna_path: str = MG_DNA_PATH,
    kb_path: str = MG_KB_PATH,
    self_model_path: str = MG_SELF_MODEL_PATH,
) -> PulseLoop:
    """Build a fully wired PulseLoop for Mata Garuda."""
    config = CellConfig(
        name="mata-garuda",
        dna_path=dna_path,
        pulse_interval_seconds=3600,  # hourly
        birth_date=MG_BIRTH_DATE,
        memory_backend="sqlite",
        db_path=kb_path,
        sleep_hours=(2, 6),  # UTC — 10:00-14:00 WITA
    )

    kb = KnowledgeBase(db_path=Path(kb_path))

    # Identity
    identity = SelfModelManager(path=self_model_path)
    identity.load()

    return PulseLoop(
        config=config,
        sensors=[
            RegulationSensor(),
            FitnessSensor(agent_name="Regulation Watcher"),
        ],
        thinker=PassthroughThinker(),
        actor=MetaChainActor(kb=kb),
        stm=BridgeSTM(),
        ltm=KnowledgeBridgeLTM(kb),
        episodic=ReflectionEpisodicStore(kb),
        lifecycle=Maturation(birth_date=MG_BIRTH_DATE),
        safety=SafetyGate(
            disable_file="/tmp/mata-garuda.disabled",
            cell_name="mata-garuda",
        ),
        homeostasis=HomeostaticController(sleep_hours=config.sleep_hours),
        identity=identity,
    )


async def main(once: bool = False) -> None:
    """Entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logger.info("Building Mata Garuda PulseLoop...")

    pl = build_pulse_loop()
    lifecycle = pl.lifecycle
    logger.info(
        f"MG alive: age={lifecycle.age_days}d phase={lifecycle.phase.value} "
        f"can_act={lifecycle.can_act()} can_dream={lifecycle.can_dream()}"
    )

    if once:
        result = await pl.single_pulse()
        logger.info(f"Pulse #{result.pulse_number}: status={result.health_status} action={result.action_taken}")
    else:
        logger.info("Starting PulseLoop (Ctrl+C to stop)...")
        await pl.run()


if __name__ == "__main__":
    once = "--once" in sys.argv
    asyncio.run(main(once=once))
