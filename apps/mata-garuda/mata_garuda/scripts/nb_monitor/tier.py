"""Tier classifier for nb_monitor.

Decision rules from spec §5 / brainstorm question 3-D HYBRID:

    ALIVE: read_freq_7d >= 5 AND (psr is None OR psr >= 0.95) AND age_days > 7
    DYING: read_freq_7d < 1 AND age_days > 14 AND (psr is None OR psr < 0.7)
    IDLE:  everything else (including bootstrap NB age_days <= 7)

`psr is None` branches are NEUTRAL — missing data must not auto-downgrade.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    ALIVE = "ALIVE"
    IDLE = "IDLE"
    DYING = "DYING"


@dataclass(frozen=True)
class TierInputs:
    read_freq_7d: int | None
    push_success_rate: float | None
    age_days: int


def classify(inputs: TierInputs) -> Tier:
    rf7_raw = inputs.read_freq_7d
    rf7 = rf7_raw or 0
    psr = inputs.push_success_rate
    age = inputs.age_days

    psr_alive_ok = psr is None or psr >= 0.95

    if rf7 >= 5 and psr_alive_ok and age > 7:
        return Tier.ALIVE

    if (
        rf7_raw is not None
        and rf7 < 1
        and age > 14
        and (psr is None or psr < 0.7)
    ):
        return Tier.DYING

    return Tier.IDLE
