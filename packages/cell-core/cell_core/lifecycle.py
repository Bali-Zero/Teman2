"""Maturation — lifecycle phase tracker.

Phases gate capabilities: embrione observes only, neonato acts cautiously,
giovane acts autonomously + dreams, adulto has full autonomy, anziano stabilizes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from cell_core.types import Phase

logger = logging.getLogger("cell_core.lifecycle")

_THRESHOLDS = {
    Phase.EMBRIONE: 1.1,
    Phase.NEONATO: 0.8,
    Phase.GIOVANE: 0.5,
    Phase.ADULTO: 0.0,
    Phase.ANZIANO: 0.0,
}

_DESCRIPTIONS = {
    Phase.EMBRIONE: "Embrione (day 0-3): observe and log only, no autonomous actions.",
    Phase.NEONATO: "Neonato (day 4-14): act only with confidence >= 0.8, building episodic memory.",
    Phase.GIOVANE: "Giovane (day 15-30): autonomous actions, dreams active, confidence >= 0.5.",
    Phase.ADULTO: "Adulto (day 31-179): full autonomy, all capabilities unlocked.",
    Phase.ANZIANO: "Anziano (day 180+): stability priority, reduced mutation rate.",
}


class Maturation:
    """Lifecycle phase based on age in days."""

    def __init__(self, birth_date: datetime) -> None:
        self.birth_date = birth_date
        self.total_pulses: int = 0

    @property
    def age_days(self) -> int:
        now = datetime.now(timezone.utc)
        birth = self.birth_date
        if birth.tzinfo is None:
            birth = birth.replace(tzinfo=timezone.utc)
        return (now - birth).days

    @property
    def phase(self) -> Phase:
        days = self.age_days
        if days >= 180:
            return Phase.ANZIANO
        if days >= 31:
            return Phase.ADULTO
        if days >= 15:
            return Phase.GIOVANE
        if days >= 4:
            return Phase.NEONATO
        return Phase.EMBRIONE

    def can_act(self) -> bool:
        return self.phase != Phase.EMBRIONE

    def can_dream(self) -> bool:
        return self.phase in (Phase.GIOVANE, Phase.ADULTO, Phase.ANZIANO)

    def can_reason_deep(self) -> bool:
        return self.phase in (Phase.GIOVANE, Phase.ADULTO, Phase.ANZIANO)

    def action_confidence_threshold(self) -> float:
        return _THRESHOLDS[self.phase]

    def tick(self, pulse_count: int) -> None:
        self.total_pulses = pulse_count

    def to_prompt_context(self) -> str:
        return (
            f"LIFECYCLE: phase={self.phase.value} age={self.age_days}d — "
            f"{_DESCRIPTIONS[self.phase]}"
        )
