"""PulseLoop — the lifecycle runner.

Concrete class that orchestrates: sense→think→act→reflect→dream→mature.
Takes Protocol implementations via constructor injection.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from cell_core.homeostasis import HomeostaticController, TrendDetector
from cell_core.lifecycle import Maturation
from cell_core.protocols import Actor, EpisodicStore, LTMStore, Sensor, STMStore, Thinker
from cell_core.types import (
    CellConfig,
    Episode,
    HomeostaticState,
    Proposal,
    PulseResult,
    SensorReading,
)

logger = logging.getLogger("cell_core.pulse")


class PulseLoop:
    """The heartbeat. Orchestrates: sense→think→act→reflect→dream→mature."""

    def __init__(
        self,
        config: CellConfig,
        sensors: list[Sensor],
        thinker: Thinker,
        actor: Actor,
        stm: STMStore,
        ltm: LTMStore,
        episodic: EpisodicStore,
        lifecycle: Maturation,
        safety: Any,  # SafetyGate or any object with async check() -> SafetyCheckResult
        homeostasis: HomeostaticController | None = None,
        identity: Any | None = None,  # SelfModelManager
        on_pulse: Callable[[PulseResult], Awaitable[None]] | None = None,
    ) -> None:
        self.config = config
        self.sensors = sensors
        self.thinker = thinker
        self.actor = actor
        self.stm = stm
        self.ltm = ltm
        self.episodic = episodic
        self.lifecycle = lifecycle
        self.safety = safety
        self.homeostasis = homeostasis or HomeostaticController(config.sleep_hours)
        self.identity = identity
        self.on_pulse = on_pulse
        self.pulse_count: int = 0
        self._recent_pulses: list[dict[str, Any]] = []
        self._trend_detector = TrendDetector()

    async def run(self) -> None:
        """Infinite loop. Call this and the cell lives."""
        while True:
            result = await self.single_pulse()
            if self.on_pulse:
                await self.on_pulse(result)
            interval = self.homeostasis.recommended_pulse_interval()
            await asyncio.sleep(interval)

    async def single_pulse(self) -> PulseResult:
        """One complete lifecycle tick."""
        self.pulse_count += 1
        now = datetime.now(timezone.utc)

        # 0. SAFETY CHECK
        safety_result = await self.safety.check()
        if not safety_result.can_proceed:
            return PulseResult(
                timestamp=now,
                pulse_number=self.pulse_count,
                halted=True,
                halt_reason=safety_result.reason,
            )

        # 1. SENSE — collect all sensor readings
        readings: list[SensorReading] = []
        for sensor in self.sensors:
            try:
                reading = await sensor.read()
                readings.append(reading)
            except Exception as e:
                readings.append(SensorReading(
                    sensor_name=sensor.name,
                    status="red",
                    metadata={"error": str(e)},
                ))

        # 2. EVALUATE — fast homeostatic update
        worst_status = self._worst_status(readings)
        # Use a default response time for homeostasis when not available
        state = self.homeostasis.update(
            response_time_ms=100,  # default; organs can override via sensor metadata
            health_status=worst_status,
            hour_utc=now.hour,
        )
        trend = self._trend_detector.detect(self._recent_pulses)

        # Store in STM
        for reading in readings:
            await self.stm.store(reading.sensor_name, {
                "status": reading.status,
                "value": reading.value,
                "stress": state.stress_level,
                "energy": state.energy_level,
            })

        self._recent_pulses.append({
            "pulse": self.pulse_count,
            "health_status": worst_status,
            "stress": state.stress_level,
            "timestamp": now.isoformat(),
        })
        if len(self._recent_pulses) > 50:
            self._recent_pulses = self._recent_pulses[-50:]

        # 3. THINK — if needed
        proposal = Proposal(action="none", reason="stable", confidence=0.0, tier_used=-1)
        should_think = (
            worst_status != "green"
            or trend.monotonic_drift
            or trend.flapping
            or trend.sustained_degraded
        )
        if should_think and self.lifecycle.can_act():
            ltm_rules = await self.ltm.load_rules(limit=10)
            recent_episodes = await self.episodic.recall_recent(hours=24, limit=5)
            memory_context = {
                "ltm_rules": [r.rule_text for r in ltm_rules],
                "recent_episodes": [
                    {"action": e.action_taken, "outcome": e.outcome, "lesson": e.lesson}
                    for e in recent_episodes
                ],
            }
            proposal = await self.thinker.think(readings, state, memory_context)

        # 4. ACT — if approved
        action_taken = None
        if proposal.action != "none":
            threshold = self.lifecycle.action_confidence_threshold()
            if (
                proposal.confidence >= threshold
                and self.actor.can_execute(proposal.action)
            ):
                action_taken = await self.actor.act(proposal)

        # 5. REFLECT — store episode if significant
        if action_taken or worst_status != "green":
            emotion = self._derive_emotion(state)
            episode = Episode(
                situation={
                    "readings": [
                        {"sensor": r.sensor_name, "status": r.status}
                        for r in readings
                    ],
                    "stress": state.stress_level,
                    "energy": state.energy_level,
                },
                emotion=emotion,
                action_taken=proposal.action,
                outcome=action_taken or "no_action",
                lesson="",
            )
            await self.episodic.store(episode)

        # 6. DREAM — during sleep window
        if self.homeostasis.is_sleeping() and self.lifecycle.can_dream():
            recent = await self.episodic.recall_recent(hours=24, limit=50)
            if recent:
                new_rules = await self.ltm.condense(recent)
                for rule in new_rules:
                    await self.ltm.store_rule(rule)
                await self.episodic.forget_weak(keep=500)

        # 7. MATURE — lifecycle tick
        self.lifecycle.tick(self.pulse_count)

        # Update identity if present
        if self.identity:
            self.identity.record_pulse()
            if action_taken:
                self.identity.record_action(proposal.action)

        return PulseResult(
            timestamp=now,
            pulse_number=self.pulse_count,
            health_status=worst_status,
            action_taken=action_taken,
            action_reason=proposal.reason if action_taken else None,
            thought_tier=proposal.tier_used if should_think else None,
        )

    @staticmethod
    def _worst_status(readings: list[SensorReading]) -> str:
        rank = {"green": 0, "yellow": 1, "red": 2}
        if not readings:
            return "green"
        return max(readings, key=lambda r: rank.get(r.status, 0)).status

    @staticmethod
    def _derive_emotion(state: HomeostaticState) -> str:
        if state.stress_level > 0.8:
            return "panic"
        if state.stress_level > 0.5:
            return "stressed"
        if state.stress_level > 0.2:
            return "alert"
        return "calm"
