"""
AI-Intel-Sentinel Cell — a living organ in the Nuzantara organism.

Implements the SYMBIOSIS lifecycle: sense→think→act→reflect→dream→mature.
Uses cell-core PulseLoop as the heartbeat.

This is NOT a cron script. It's a cell that lives, learns, and grows.
Every pulse:
  - SENSE: harvest arXiv, RSS, GitHub, YouTube
  - THINK: dedup, score relevance, cross-reference
  - ACT: store in KB, feed NLM, write report, send TG
  - REFLECT: what worked, what failed, what to remember
  - DREAM: consolidate episodes into LTM rules (during sleep window)
  - MATURE: lifecycle phase tracking (embrione→adulto)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from cell_core.genome import Genome
from cell_core.homeostasis import HomeostaticController
from cell_core.hgt.consumer import HGTConsumer
from cell_core.lifecycle import Maturation
from cell_core.memory_sqlite import SqliteMemoryStack
from cell_core.pulse import PulseLoop
from cell_core.safety import SafetyGate
from cell_core.types import CellConfig, PulseResult

from mata_garuda.cells.actors.sentinel_actor import SentinelActor
from mata_garuda.cells.sensors.arxiv_sensor import ArXivSensor
from mata_garuda.cells.sensors.github_sensor import GitHubSensor
from mata_garuda.cells.sensors.rss_sensor import RSSSensor
from mata_garuda.cells.sensors.youtube_sensor import YouTubeSensor
from mata_garuda.cells.thinker import SentinelThinker
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.cells")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DNA_PATH = Path(__file__).parent.parent.parent / "sentinel_dna.json"


def create_sentinel_cell() -> PulseLoop:
    """Factory: creates a fully wired SentinelCell PulseLoop."""

    config = CellConfig(
        name="ai-intel-sentinel",
        dna_path=str(DNA_PATH),
        pulse_interval_seconds=86400,  # daily pulse
        birth_date=datetime(2026, 4, 10, tzinfo=timezone.utc),
        memory_backend="sqlite",
        db_path=str(DATA_DIR / "sentinel_cell.db"),
        sleep_hours=(2, 6),  # 02:00-06:00 WITA
    )

    # Memory stack
    memory = SqliteMemoryStack(config.db_path)

    # Sensors
    sensors = [
        ArXivSensor(max_results=15),
        RSSSensor(max_per_feed=5),
        GitHubSensor(max_results=10),
        YouTubeSensor(max_channels=3, max_videos=2),
    ]

    # Thinker
    thinker = SentinelThinker()

    # Actor (needs KB for persistence + thinker for deduped items)
    kb = KnowledgeBase(db_path=DATA_DIR / "knowledge.db")
    actor = SentinelActor(kb=kb, thinker=thinker)

    # Lifecycle
    lifecycle = Maturation(birth_date=config.birth_date)

    # Safety
    safety = SafetyGate(
        disable_file="/tmp/sentinel.disabled",
        cell_name="ai-intel-sentinel",
    )

    # Homeostasis
    homeostasis = HomeostaticController(config.sleep_hours)

    # Genome + HGT Consumer — sentinel consumes news/architecture skills
    genome = Genome(db_path=str(DATA_DIR / "knowledge.db"))
    hgt_consumer = None
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
        hgt_consumer = HGTConsumer(
            redis_client, genome, cell_name="ai-intel-sentinel",
            interested_domains={"news", "architecture", "rag", "generic"},
        )
        logger.info("[hgt] Consumer initialized for ai-intel-sentinel")
    except (ImportError, Exception) as e:
        logger.info(f"[hgt] Consumer not available: {e}")

    async def on_pulse(result):
        """Post-pulse callback: log result and set readings on actor."""
        logger.info(
            f"[sentinel] Pulse #{result.pulse_number}: "
            f"health={result.health_status}, action={result.action_taken}"
        )

    # Wire the custom actor to receive readings from PulseLoop
    # PulseLoop calls actor.act(proposal) but actor needs the readings
    # We inject them via a custom PulseLoop subclass
    return _SentinelPulseLoop(
        config=config,
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
        genome=genome,
        hgt_consumer=hgt_consumer,
    )


class _SentinelPulseLoop(PulseLoop):
    """Extended PulseLoop with genome + HGT consumer for the Sentinel."""

    def __init__(
        self, *args,
        genome: Genome | None = None,
        hgt_consumer: HGTConsumer | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.genome = genome
        self.hgt_consumer = hgt_consumer

    async def single_pulse(self, *args, **kwargs) -> PulseResult:
        result = await super().single_pulse(*args, **kwargs)

        # 5b. REFLECT — record successful action as genome skill
        action = result.action_taken or ""
        if (
            self.genome
            and action
            and not result.halted
            and not result.skipped
            and result.health_status != "red"
        ):
            import time
            skill_id = f"sentinel_{action}_{int(time.time())}"
            self.genome.record_skill(
                cell="ai-intel-sentinel",
                skill_id=skill_id,
                procedure=result.action_reason or action,
                confidence=0.6,
                scope="Project",
                domain="news",
            )

        # 5c. HGT CONSUME — integrate skills from sibling cells
        if self.hgt_consumer:
            try:
                await self.hgt_consumer.ensure_group()
                await self.hgt_consumer.consume_once()
            except Exception:
                pass  # graceful degradation

        # 6b. DREAM — silence stale skills during sleep window
        if (
            self.genome
            and self.homeostasis.is_sleeping()
            and self.lifecycle.can_dream()
        ):
            self.genome.silence_stale_skills(cell="ai-intel-sentinel", unused_days=30)

        return result

    async def _run_sense_phase(self):
        """Override to capture readings for the actor."""
        readings = []
        for sensor in self.sensors:
            try:
                reading = await sensor.read()
                readings.append(reading)
            except Exception as e:
                from cell_core.types import SensorReading
                readings.append(SensorReading(
                    sensor_name=sensor.name,
                    status="red",
                    metadata={"error": str(e)},
                ))

        # Pass readings to actor so it can access the raw data
        if hasattr(self.actor, "set_readings"):
            self.actor.set_readings(readings)

        return readings


async def run_single_pulse():
    """Run one pulse of the Sentinel cell. Called by cron or manual."""
    cell = create_sentinel_cell()
    result = await cell.single_pulse()
    logger.info(f"[sentinel] Pulse complete: {result}")
    return result


def main():
    """Entry point for cron/manual execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    asyncio.run(run_single_pulse())


if __name__ == "__main__":
    main()
