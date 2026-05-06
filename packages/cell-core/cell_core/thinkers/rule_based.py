"""RuleBasedThinker — zero-dependency, zero-latency Thinker.

Implements the ``cell_core.protocols.Thinker`` Protocol. Maps the worst
sensor status (and optionally the originating sensor name) into a
hardcoded action proposal. No LLM, no I/O.

Used both as the cell's primary classifier when Ollama is unavailable
(Symbiosis Law 4) and as the fallback wrapped by ``OllamaAwareThinker``.
"""
from __future__ import annotations

from typing import Any

from cell_core.types import HomeostaticState, Proposal, SensorReading

# ──────────────────────────────────────────────────────────────────
# Constants — kept private and module-level so callers can patch
# them in tests if domain-specific tuning is needed.
# ──────────────────────────────────────────────────────────────────

_HIGH_STRESS_THRESHOLD = 0.8
_STATUS_RANK = {"green": 0, "yellow": 1, "red": 2}

# Domain-specific routes: when a sensor with a known name is the worst
# offender, suggest a more specific action than the generic alert_*.
_RED_DOMAIN_ACTIONS = {
    "outbox": "drain_outbox",
    "ollama": "ollama_restart",
    "backup": "run_backup",
}


class RuleBasedThinker:
    """Deterministic Thinker."""

    name = "rule_based"

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal:
        worst = self._worst_status(readings)
        worst_sensor = self._worst_sensor_name(readings, worst)

        # All-green path: nothing to do.
        if worst == "green":
            return Proposal(
                action="none",
                reason="all sensors green",
                confidence=0.5,
                tier_used=0,
            )

        # High-stress override: any non-green signal escalates to human.
        if state.stress_level >= _HIGH_STRESS_THRESHOLD:
            return Proposal(
                action="alert_human",
                reason=(
                    f"high stress ({state.stress_level:.2f}) + "
                    f"{worst} signal from sensor '{worst_sensor}'"
                ),
                confidence=0.85,
                tier_used=0,
            )

        if worst == "red":
            domain_action = _RED_DOMAIN_ACTIONS.get(worst_sensor)
            if domain_action is not None:
                return Proposal(
                    action=domain_action,
                    reason=(
                        f"red signal on sensor '{worst_sensor}' → "
                        f"{domain_action}"
                    ),
                    confidence=0.75,
                    tier_used=0,
                )
            return Proposal(
                action="alert_human",
                reason=f"red signal from sensor '{worst_sensor}'",
                confidence=0.80,
                tier_used=0,
            )

        # worst == "yellow"
        return Proposal(
            action="alert_silent",
            reason=f"yellow signal from sensor '{worst_sensor}'",
            confidence=0.55,
            tier_used=0,
        )

    @staticmethod
    def _worst_status(readings: list[SensorReading]) -> str:
        if not readings:
            return "green"
        return max(readings, key=lambda r: _STATUS_RANK.get(r.status, 0)).status

    @staticmethod
    def _worst_sensor_name(
        readings: list[SensorReading], worst: str
    ) -> str:
        for r in readings:
            if r.status == worst:
                return r.sensor_name
        return "unknown"
