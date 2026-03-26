"""The Pulse — CELL's heartbeat.
Every 60 seconds: verify DNA → check safety → sense → evaluate → THINK → act → remember."""
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
    action_reason: str | None = None
    thought_tier: int | None = None
    error: str | None = None


class PulseEngine:
    def __init__(
        self,
        dna_loader: Any,
        safety_gate: Any,
        health_sensor: Any,
        metabolism: Any,
        reasoner: Any = None,
        dna_interpreter: Any = None,
        dna_expected_hash: str = "",
    ) -> None:
        self._dna = dna_loader
        self._safety = safety_gate
        self._health = health_sensor
        self._metabolism = metabolism
        self._reasoner = reasoner
        self._interpreter = dna_interpreter
        self._dna_hash = dna_expected_hash
        self._recent_pulses: list[dict] = []

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

        response_ms = int(reading.response_time_seconds * 1000) if reading.reachable else 0

        logger.info(
            f"Pulse: health={status.value}, reachable={reading.reachable}, "
            f"status_code={reading.status_code}, "
            f"response_time={reading.response_time_seconds:.3f}s"
        )

        # Track recent history for reasoner context
        self._recent_pulses.append({
            "pulse_number": pulse_number,
            "health_status": status.value,
            "response_time_ms": response_ms,
        })
        if len(self._recent_pulses) > 50:
            self._recent_pulses = self._recent_pulses[-50:]

        # 5. THINK (SLOW) — only if not GREEN and reasoner is available
        action = None
        action_reason = None
        thought_tier = None

        if status != HealthStatus.GREEN and self._reasoner and self._interpreter:
            try:
                proposal = await self._reasoner.think(
                    health_status=status.value,
                    response_time_ms=response_ms,
                    error_message=reading.error if not reading.reachable else "",
                    recent_history=self._recent_pulses,
                    budget_spent=self._metabolism.daily_spend,
                    budget_limit=self._metabolism._daily_limit,
                )

                thought_tier = proposal.tier_used

                # Record LLM cost
                if proposal.cost_usd > 0:
                    self._metabolism.record("llm", proposal.cost_usd, partition="incident")

                if proposal.action != "none":
                    # 6. VALIDATE against DNA
                    validation = self._interpreter.validate(
                        action_name=proposal.action,
                        budget_spent=self._metabolism.daily_spend,
                        budget_limit=self._metabolism._daily_limit,
                        confidence=proposal.confidence,
                    )

                    if validation.approved:
                        action = proposal.action
                        action_reason = proposal.reason
                        self._interpreter.record_action(proposal.action)
                        logger.info(
                            f"THINK → ACT: {proposal.action} "
                            f"(confidence={proposal.confidence:.2f}, tier={proposal.tier_used}, "
                            f"reason={proposal.reason[:60]})"
                        )
                    else:
                        logger.info(
                            f"THINK → BLOCKED: {proposal.action} — {validation.reason} "
                            f"(rule {validation.rule_violated})"
                        )
                        action_reason = f"Proposed {proposal.action} but blocked: {validation.reason}"
                else:
                    action_reason = proposal.reason
                    logger.info(f"THINK → no action needed: {proposal.reason[:80]}")

            except Exception as e:
                logger.error(f"SLOW reasoner error: {e}", exc_info=True)
                action_reason = f"Reasoner error: {e}"

        # 7. PERSIST to PostgreSQL for dashboard
        try:
            await cell_db.log_pulse(
                pulse_number=pulse_number,
                health_status=status.value,
                response_time_ms=response_ms,
                dna_intact=True,
                budget_spent=self._metabolism.daily_spend,
                budget_limit=self._metabolism._daily_limit,
                action_taken=action,
                error_message=action_reason if status != HealthStatus.GREEN else None,
            )
        except Exception as e:
            logger.error(f"Pulse DB log failed: {e}")

        return PulseResult(
            timestamp=now,
            health_status=status,
            action_taken=action,
            action_reason=action_reason,
            thought_tier=thought_tier,
        )
