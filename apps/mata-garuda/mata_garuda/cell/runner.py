"""Runner — builds and runs the PulseLoop for Mata Garuda.

Entry points:
  python -m mata_garuda.cell.runner          # run forever
  python -m mata_garuda.cell.runner --once   # single pulse
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from cell_core import CellConfig, PulseLoop, Maturation, SafetyGate, PulseResult
from cell_core.genome import Genome
from cell_core.hgt.publisher import HGTPublisher
from cell_core.homeostasis import HomeostaticController
from cell_core.identity import SelfModelManager

from mata_garuda.cell.actor import MetaChainActor
from mata_garuda.cell.memory_bridge import BridgeSTM, KnowledgeBridgeLTM, ReflectionEpisodicStore
from mata_garuda.cell.sensors import FitnessSensor, GapStreamSensor, RegulationSensor
from mata_garuda.cell.thinker import PassthroughThinker
from mata_garuda.runtime.knowledge import KnowledgeBase

# Organo: cell-core PulseLoop runner → dispatches MG agents via MetaChainActor.
# Importing mata_garuda.agents populates the registry via @register_agent
# decorators — without it, get_agent(display_name) returns None and the actor
# fails with "Agent 'Regulation Watcher' not registered".
import mata_garuda.agents  # noqa: F401

logger = logging.getLogger("mata_garuda.cell")

MG_BIRTH_DATE = datetime(2026, 4, 1, tzinfo=timezone.utc)
MG_DNA_PATH = str(Path(__file__).parent.parent / "dna.json")
MG_KB_PATH = str(Path(__file__).parent.parent.parent / "data" / "knowledge.db")
MG_SELF_MODEL_PATH = str(Path(__file__).parent.parent.parent / "data" / "self_model.json")


class MataGarudaPulseLoop(PulseLoop):
    """PulseLoop + DNA recording for Mata Garuda.

    Adds two genome hooks to the standard pulse cycle:
    - REFLECT (step 5): records a skill when an action succeeds
    - DREAM  (step 6): silences stale low-confidence skills
    """

    def __init__(
        self, *args, genome: Genome,
        hgt_publisher: HGTPublisher | None = None, **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.genome = genome
        self.hgt_publisher = hgt_publisher

    async def single_pulse(self) -> PulseResult:
        result = await super().single_pulse()

        # 5b. REFLECT — record successful action as genome skill
        action = result.action_taken or ""
        if (
            action
            and not result.halted
            and not result.skipped
            and not action.startswith("[ERROR]")
            and result.health_status != "red"
        ):
            skill_id = f"{action}_{int(time.time())}"
            self.genome.record_skill(
                cell="mata-garuda",
                skill_id=skill_id,
                procedure=result.action_reason or action,
                confidence=0.6,
                scope="Project",
                domain="news",  # Mata Garuda primarily produces news/intel skills
            )

            # 5c. HGT PUBLISH — share high-confidence skills with sibling cells
            if self.hgt_publisher:
                try:
                    await self.hgt_publisher.publish({
                        "id": skill_id,
                        "procedure": result.action_reason or action,
                        "confidence": 0.6,
                        "scope": "Project",
                        "type": "skill",
                        "domain": "news",
                    })
                except Exception:
                    pass  # graceful degradation: Redis down = skill stays local

        # 6b. DREAM — silence skills unused for 30+ days with confidence < 0.4
        if self.homeostasis.is_sleeping() and self.lifecycle.can_dream():
            n = self.genome.silence_stale_skills(cell="mata-garuda", unused_days=30)
            if n:
                logger.info(f"[genome] silenced {n} stale skills during dream phase")

        return result


def build_pulse_loop(
    dna_path: str = MG_DNA_PATH,
    kb_path: str = MG_KB_PATH,
    self_model_path: str = MG_SELF_MODEL_PATH,
) -> MataGarudaPulseLoop:
    """Build a fully wired MataGarudaPulseLoop with DNA recording."""
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
    genome = Genome(db_path=kb_path)

    # HGT Publisher — optional, graceful degradation if Redis unavailable
    hgt_publisher = None
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
        hgt_publisher = HGTPublisher(redis_client, cell_name="mata-garuda")
        logger.info("[hgt] Publisher initialized for mata-garuda")
    except (ImportError, Exception) as e:
        logger.info(f"[hgt] Publisher not available: {e}")

    # Identity
    identity = SelfModelManager(path=self_model_path)
    identity.load()

    return MataGarudaPulseLoop(
        config=config,
        sensors=[
            RegulationSensor(),
            FitnessSensor(agent_name="Regulation Watcher"),
            GapStreamSensor(),
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
        genome=genome,
        hgt_publisher=hgt_publisher,
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
        if result.halted:
            logger.warning(f"Pulse #{result.pulse_number}: HALTED reason={result.halt_reason}")
        elif result.skipped:
            logger.info(f"Pulse #{result.pulse_number}: SKIPPED reason={result.skip_reason}")
        else:
            logger.info(f"Pulse #{result.pulse_number}: status={result.health_status} action={result.action_taken}")
    else:
        logger.info("Starting PulseLoop (Ctrl+C to stop)...")
        await pl.run()


if __name__ == "__main__":
    once = "--once" in sys.argv
    asyncio.run(main(once=once))
