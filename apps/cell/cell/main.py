"""CELL — Entry point. Runs the pulse loop. This is the organism."""
import asyncio
import logging
import os
import signal
import sys

import httpx
import redis.asyncio as aioredis

from cell.core.config import settings
from cell.core.db import create_patterns_table
from cell.core.dna import DNALoader
from cell.core.dna_interpreter import DNAInterpreter
from cell.core.pulse import PulseEngine
from cell.core.safety import SafetyGate
from cell.effectors.fly_effector import FlyEffector
from cell.effectors.logs_effector import LogsEffector
from cell.effectors.telegram import TelegramAlerter
from cell.metabolism.tracker import MetabolismTracker
from cell.effectors.local_effector import LocalEffector
from cell.fast.trend_detector import TrendDetector
from cell.memory.long_term import LongTermMemory
from cell.memory.short_term import ShortTermMemory
from cell.sensors.backup_sensor import BackupSensor
from cell.sensors.cron_sensor import CronSensor
from cell.sensors.database_sensor import DatabaseSensor
from cell.sensors.error_rate_sensor import ErrorRateSensor
from cell.sensors.health_sensor import HealthSensor
from cell.sensors.ollama_sensor import OllamaSensor
from cell.sensors.qdrant_sensor import QdrantSensor
from cell.sensors.vercel_sensor import VercelSensor
from cell.slow.reasoner import SlowReasoner
from cell.core.db import create_episodes_table
from cell.fast.homeostatic_controller import HomeostaticController
from cell.memory.episodic import EpisodicMemory
from cell.identity.self_model import SelfModelManager
from cell.memory.dreamer import Dreamer
from cell.identity.journal import Journal
from cell.metabolism.attention_allocator import AttentionAllocator
from cell.lifecycle.maturation import Maturation
from cell.core.db import create_dreams_table, create_journal_table

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CELL] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cell")

_shutdown = asyncio.Event()


def _handle_signal(sig: int, frame: object) -> None:
    logger.info(f"Received signal {sig}, shutting down...")
    _shutdown.set()


async def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Persistent memory bootstrap (create table before reasoner uses it)
    await create_patterns_table()
    await create_episodes_table()
    await create_dreams_table()
    await create_journal_table()

    dna_loader = DNALoader()
    dna_hash = dna_loader.compute_hash()
    logger.info(f"DNA loaded. Hash: {dna_hash[:16]}...")

    dna = dna_loader.load()
    constraints = dna["constraints"]
    metabolism = MetabolismTracker(
        daily_limit=constraints["max_daily_budget_usd"],
        partitions=constraints["budget_partitions"],
    )

    # SLOW layer — the brain (all local, zero API cost)
    reasoner = SlowReasoner()
    patterns_loaded = await reasoner.bootstrap_memory()
    logger.info(f"PatternIndex: {patterns_loaded} patterns loaded from DB")
    interpreter = DNAInterpreter()
    logger.info("SLOW layer initialized (Qwen 9B fast + Qwen 27B deep, all local)")

    # Safety gate — real Redis kill switch
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    safety_gate = SafetyGate(redis=redis_client)
    logger.info(f"Safety gate connected to Redis: {redis_url.split('@')[-1]}")

    # STM (Short-Term Memory) — Redis-backed
    stm = ShortTermMemory(redis=redis_client)

    async with httpx.AsyncClient() as http_client:
        health_sensor = HealthSensor(client=http_client, url=settings.backend_health_url)

        # Secondary sensors — reuse /health body (no extra HTTP calls)
        db_sensor = DatabaseSensor()
        qdrant_sensor = QdrantSensor()
        # ErrorRateSensor calls /api/cell/metrics on the backend (1 query, 1x/min cooldown)
        metrics_url = settings.backend_health_url.replace("/health", "/api/cell/metrics")
        error_rate_sensor = ErrorRateSensor(client=http_client, metrics_url=metrics_url)

        # New sensors — local visibility
        ollama_sensor = OllamaSensor()
        backup_sensor = BackupSensor()
        cron_sensor = CronSensor()
        vercel_sensor = VercelSensor(client=http_client)
        logger.info(f"Sensors initialized (DB, Qdrant, ErrorRate, Ollama, Backup, Cron, Vercel → {metrics_url})")

        # Telegram alerter — CELL's voice
        tg_token = os.environ.get("CELL_TELEGRAM_BOT_TOKEN", "")
        tg_chat = os.environ.get("CELL_TELEGRAM_CHAT_ID", "")
        alerter: TelegramAlerter | None = None
        if tg_token and tg_chat:
            alerter = TelegramAlerter(client=http_client, bot_token=tg_token, chat_id=tg_chat)
            logger.info("Telegram alerter initialized")
        else:
            logger.warning("CELL_TELEGRAM_BOT_TOKEN or CELL_TELEGRAM_CHAT_ID not set — alerts disabled")

        # Fly.io effector — CELL's hands (restart, scale)
        fly_token = os.environ.get("FLY_API_TOKEN", "")
        fly_effector = FlyEffector(app_name=settings.fly_app_name, api_token=fly_token)
        logs_effector = LogsEffector(app_name=settings.fly_app_name, api_token=fly_token)
        if fly_token:
            logger.info(f"Fly.io effectors initialized for app: {settings.fly_app_name}")
        else:
            logger.warning("FLY_API_TOKEN not set — restart/scale/logs actions will be no-ops")

        # Local effector — ollama_restart, run_backup
        local_effector = LocalEffector()
        logger.info("LocalEffector initialized (ollama_restart, run_backup)")

        # LTM (Long-Term Memory) — weekly condensation
        from cell.core.db import get_pool as _get_pool  # noqa: PLC0415
        ltm: LongTermMemory | None = None
        try:
            _db_pool = await _get_pool()
            ltm = LongTermMemory(pool=_db_pool)
            await ltm.ensure_table()
            logger.info("LongTermMemory initialized")
        except Exception as _e:
            logger.warning(f"LTM init failed (non-fatal): {_e}")

        # TrendDetector (FAST layer)
        trend_detector = TrendDetector()

        # Homeostatic Controller — CELL's body regulation
        # Sleep 2-6 UTC = 10:00-14:00 WITA (low traffic window)
        homeostatic = HomeostaticController(sleep_hours=(2, 6))
        logger.info("HomeostaticController initialized (sleep 02:00-06:00 UTC)")

        # Episodic Memory — moments, not statistics
        _db_pool_ep = await _get_pool()
        episodic = EpisodicMemory(pool=_db_pool_ep, max_episodes=1000)
        ep_count = await episodic.count()
        logger.info(f"EpisodicMemory initialized ({ep_count} episodes)")

        # Dreamer — nocturnal consolidation
        dreamer = Dreamer(pool=_db_pool_ep, ollama_url="http://localhost:11434")
        logger.info("Dreamer initialized")

        # Journal — daily narrative
        journal = Journal(pool=_db_pool_ep, ollama_url="http://localhost:11434")
        logger.info("Journal initialized")

        # Attention Allocator — scarce cognitive budget
        attention = AttentionAllocator(daily_units=100)
        logger.info("AttentionAllocator initialized (100 units/day)")

        # Self-Model — persistent identity
        self_model_path = settings.cell_root / "data" / "self_model.json"
        self_model = SelfModelManager(path=self_model_path)
        self_model.load()
        logger.info(
            f"SelfModel loaded: age={self_model.model.age_days}d "
            f"pulses={self_model.model.total_pulses} actions={self_model.model.total_actions}"
        )

        # Maturation — lifecycle phase gate
        maturation = Maturation(age_days=self_model.model.age_days)
        maturation.log_phase()

        engine = PulseEngine(
            dna_loader=dna_loader,
            safety_gate=safety_gate,
            health_sensor=health_sensor,
            metabolism=metabolism,
            reasoner=reasoner,
            dna_interpreter=interpreter,
            dna_expected_hash=dna_hash,
            alerter=alerter,
            fly_effector=fly_effector,
            logs_effector=logs_effector,
            local_effector=local_effector,
            db_sensor=db_sensor,
            qdrant_sensor=qdrant_sensor,
            error_rate_sensor=error_rate_sensor,
            ollama_sensor=ollama_sensor,
            backup_sensor=backup_sensor,
            cron_sensor=cron_sensor,
            vercel_sensor=vercel_sensor,
            stm=stm,
            ltm=ltm,
            trend_detector=trend_detector,
            homeostatic=homeostatic,
            episodic=episodic,
            self_model=self_model,
            dreamer=dreamer,
            journal=journal,
            attention=attention,
            maturation=maturation,
        )

        logger.info("CELL organism online. Starting pulse loop. Brain: ACTIVE.")
        pulse_count = 0
        _last_status = "green"

        while not _shutdown.is_set():
            pulse_count += 1
            try:
                result = await engine.single_pulse(pulse_number=pulse_count)
                if result.halted:
                    logger.critical(f"ORGANISM HALTED: {result.halt_reason}")
                    sys.exit(1)

                status_str = result.health_status.value if result.health_status else "N/A"
                action_str = f" → {result.action_taken}" if result.action_taken else ""
                tier_str = f" (tier {result.thought_tier})" if result.thought_tier is not None else ""
                logger.info(f"Pulse #{pulse_count} complete. Health: {status_str}{action_str}{tier_str}")
                _last_status = status_str

                # Episodic forgetting — every 1000 pulses (~17h at 60s intervals)
                if pulse_count % 1000 == 0 and pulse_count > 0:
                    try:
                        forgotten = await episodic.forget_weak()
                        if forgotten > 0:
                            logger.info(f"Episodic forgetting: {forgotten} weak episodes removed")
                    except Exception as e:
                        logger.debug(f"Episodic forgetting failed: {e}")

            except Exception as e:
                logger.error(f"Pulse #{pulse_count} error: {e}", exc_info=True)

            # Adaptive interval: homeostatic controller decides (circadian + stress-aware)
            interval = homeostatic.recommended_pulse_interval()
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass

    # Persist self-model before shutdown
    self_model.save()
    logger.info(f"Self-model saved: pulses={self_model.model.total_pulses}")

    await redis_client.aclose()
    from cell.core.db import close_pool
    await close_pool()
    logger.info("CELL organism shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
