# apps/cell/cell/lifecycle/maturation.py
"""Maturation — CELL's lifecycle phase tracker.

Phases gate capabilities: embrione observes only, neonato acts with approval,
giovane acts autonomously + dreams, adulto has full autonomy, anziano stabilizes.

Inspired by developmental biology and VOYAGER's progressive skill unlocking.
"""
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("cell.lifecycle")


class LifecyclePhase(str, Enum):
    EMBRIONE = "embrione"   # day 0-3: observe only
    NEONATO = "neonato"     # day 4-14: act with high confidence
    GIOVANE = "giovane"     # day 15-30: autonomous + dreams
    ADULTO = "adulto"       # day 31-179: full autonomy
    ANZIANO = "anziano"     # day 180+: stability priority


@dataclass
class Maturation:
    """Lifecycle phase based on CELL's age in days."""
    age_days: int

    @property
    def phase(self) -> LifecyclePhase:
        if self.age_days >= 180:
            return LifecyclePhase.ANZIANO
        if self.age_days >= 31:
            return LifecyclePhase.ADULTO
        if self.age_days >= 15:
            return LifecyclePhase.GIOVANE
        if self.age_days >= 4:
            return LifecyclePhase.NEONATO
        return LifecyclePhase.EMBRIONE

    def can_act(self) -> bool:
        """Can CELL take autonomous actions?"""
        return self.phase != LifecyclePhase.EMBRIONE

    def can_dream(self) -> bool:
        """Can CELL run nocturnal consolidation?"""
        return self.phase in (
            LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO
        )

    def can_reason_deep(self) -> bool:
        """Can CELL use Qwen 27B deep reasoning?"""
        return self.phase != LifecyclePhase.EMBRIONE

    def action_confidence_threshold(self) -> float:
        """Minimum confidence required to execute an action.

        1.1 = impossible (embrione: blocks all actions).
        0.8 = neonato (high confidence only).
        0.0 = no gate (adulto/anziano).
        """
        thresholds = {
            LifecyclePhase.EMBRIONE: 1.1,
            LifecyclePhase.NEONATO: 0.8,
            LifecyclePhase.GIOVANE: 0.5,
            LifecyclePhase.ADULTO: 0.0,
            LifecyclePhase.ANZIANO: 0.0,
        }
        return thresholds[self.phase]

    def to_prompt_context(self) -> str:
        """Format lifecycle state for LLM context injection."""
        descriptions = {
            LifecyclePhase.EMBRIONE: "Embrione (day 0-3): observe and log only, no autonomous actions.",
            LifecyclePhase.NEONATO: "Neonato (day 4-14): act only with confidence >= 0.8, building episodic memory.",
            LifecyclePhase.GIOVANE: "Giovane (day 15-30): autonomous actions, dreams active, confidence >= 0.5.",
            LifecyclePhase.ADULTO: "Adulto (day 31+): full autonomy, all capabilities unlocked.",
            LifecyclePhase.ANZIANO: "Anziano (day 180+): stability priority, reduced mutation rate.",
        }
        return (
            f"LIFECYCLE: phase={self.phase.value} age={self.age_days}d — "
            f"{descriptions[self.phase]}"
        )

    def log_phase(self) -> None:
        logger.info(
            f"Maturation: phase={self.phase.value} age={self.age_days}d "
            f"can_act={self.can_act()} can_dream={self.can_dream()} "
            f"confidence_threshold={self.action_confidence_threshold()}"
        )
