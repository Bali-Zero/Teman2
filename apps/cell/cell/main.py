"""CELL — Entry point. Runs the pulse loop. This is the organism."""
import asyncio
import logging
import signal
import sys

import httpx

from cell.core.config import settings
from cell.core.dna import DNALoader
from cell.core.pulse import PulseEngine
from cell.core.safety import SafetyGate
from cell.metabolism.tracker import MetabolismTracker
from cell.sensors.health_sensor import HealthSensor

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

    async with httpx.AsyncClient() as http_client:
        health_sensor = HealthSensor(client=http_client, url=settings.backend_health_url)

        # Safety gate with mock Redis for now (real Redis in Task 9)
        from unittest.mock import AsyncMock

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        safety_gate = SafetyGate(redis=mock_redis)

        engine = PulseEngine(
            dna_loader=dna_loader,
            safety_gate=safety_gate,
            health_sensor=health_sensor,
            metabolism=metabolism,
            dna_expected_hash=dna_hash,
        )

        logger.info("CELL organism online. Starting pulse loop.")
        pulse_count = 0

        while not _shutdown.is_set():
            pulse_count += 1
            try:
                result = await engine.single_pulse()
                if result.halted:
                    logger.critical(f"ORGANISM HALTED: {result.halt_reason}")
                    sys.exit(1)
                logger.info(
                    f"Pulse #{pulse_count} complete. "
                    f"Health: {result.health_status.value if result.health_status else 'N/A'}"
                )
            except Exception as e:
                logger.error(f"Pulse #{pulse_count} error: {e}", exc_info=True)

            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=settings.pulse_interval_seconds)
                break
            except asyncio.TimeoutError:
                pass

    logger.info("CELL organism shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
