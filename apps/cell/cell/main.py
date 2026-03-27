"""CELL — Entry point. Runs the pulse loop. This is the organism."""
import asyncio
import logging
import os
import signal
import sys

import httpx
import redis.asyncio as aioredis

from cell.core.config import settings
from cell.core.dna import DNALoader
from cell.core.dna_interpreter import DNAInterpreter
from cell.core.pulse import PulseEngine
from cell.core.safety import SafetyGate
from cell.effectors.fly_effector import FlyEffector
from cell.effectors.logs_effector import LogsEffector
from cell.effectors.telegram import TelegramAlerter
from cell.metabolism.tracker import MetabolismTracker
from cell.sensors.health_sensor import HealthSensor
from cell.slow.reasoner import SlowReasoner

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

    dna_loader = DNALoader()
    dna_hash = dna_loader.compute_hash()
    logger.info(f"DNA loaded. Hash: {dna_hash[:16]}...")

    dna = dna_loader.load()
    constraints = dna["constraints"]
    metabolism = MetabolismTracker(
        daily_limit=constraints["max_daily_budget_usd"],
        partitions=constraints["budget_partitions"],
    )

    # SLOW layer — the brain
    reasoner = SlowReasoner(
        gemini_api_key=os.environ.get("GOOGLE_API_KEY", ""),
    )
    interpreter = DNAInterpreter()
    logger.info("SLOW layer initialized (Qwen local + Gemini Flash)")

    # Safety gate — real Redis kill switch
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    safety_gate = SafetyGate(redis=redis_client)
    logger.info(f"Safety gate connected to Redis: {redis_url.split('@')[-1]}")

    async with httpx.AsyncClient() as http_client:
        health_sensor = HealthSensor(client=http_client, url=settings.backend_health_url)

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
        )

        logger.info("CELL organism online. Starting pulse loop. Brain: ACTIVE.")
        pulse_count = 0

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

            except Exception as e:
                logger.error(f"Pulse #{pulse_count} error: {e}", exc_info=True)

            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=settings.pulse_interval_seconds)
                break
            except asyncio.TimeoutError:
                pass

    await redis_client.aclose()
    from cell.core.db import close_pool
    await close_pool()
    logger.info("CELL organism shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
