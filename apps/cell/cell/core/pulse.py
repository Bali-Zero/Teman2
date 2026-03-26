"""The Pulse — CELL's heartbeat.
Every 60 seconds: verify DNA → check safety → sense → evaluate → remember."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cell.core import db as cell_db
from cell.fast.health_triage import HealthStatus

logger = logging.getLogger("cell.pulse")


@dataclass
class PulseResult:
    timestamp: datetime
    halted: bool = False
    halt_reason: str = ""
    skipped: bool = False
    skip_reason: str = ""
    health_status: HealthStatus | None = None
    action_taken: str | None = None
    error: str | None = None


class PulseEngine:
    def __init__(
        self,
        dna_loader: Any,
        safety_gate: Any,
        health_sensor: Any,
        metabolism: Any,
        dna_expected_hash: str = "",
    ) -> None:
        self._dna = dna_loader
        self._safety = safety_gate
        self._health = health_sensor
        self._metabolism = metabolism
        self._dna_hash = dna_expected_hash

    async def single_pulse(self, pulse_number: int = 0) -> PulseResult:
        now = datetime.now(timezone.utc)

        # 1. DNA INTEGRITY
        if self._dna_hash and not self._dna.verify_integrity(self._dna_hash):
            logger.critical("DNA INTEGRITY FAILURE — HALTING")
            return PulseResult(timestamp=now, halted=True, halt_reason="DNA integrity check failed")

        # 2. SAFETY GATES
        safety = await self._safety.check()
        if not safety.can_proceed:
            logger.info(f"Pulse skipped: {safety.reason} — {safety.detail}")
            return PulseResult(timestamp=now, skipped=True, skip_reason=safety.reason)

        # 3. SENSE
        reading = await self._health.read()

        # 4. EVALUATE (FAST)
        if reading.reachable and reading.status_code == 200:
            status = HealthStatus.GREEN
        elif reading.reachable:
            status = HealthStatus.YELLOW
        else:
            status = HealthStatus.RED

        logger.info(
            f"Pulse: health={status.value}, reachable={reading.reachable}, "
            f"status_code={reading.status_code}, "
            f"response_time={reading.response_time_seconds:.3f}s"
        )

        # 5. ACT (embryo: observe only, no actions yet)
        action = None

        # 6. PERSIST to PostgreSQL for dashboard
        try:
            await cell_db.log_pulse(
                pulse_number=pulse_number,
                health_status=status.value,
                response_time_ms=int(reading.response_time_seconds * 1000) if reading.reachable else 0,
                dna_intact=True,
                budget_spent=self._metabolism.daily_spend,
                budget_limit=self._metabolism._daily_limit,
            )
        except Exception as e:
            logger.error(f"Pulse DB log failed: {e}")

        return PulseResult(timestamp=now, health_status=status, action_taken=action)
