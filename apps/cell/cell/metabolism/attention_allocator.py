# apps/cell/cell/metabolism/attention_allocator.py
"""Attention Allocator — CELL's scarce cognitive resource.

100 units/day forces prioritization between reasoning, dreaming, and curiosity.
Low budget → pattern-only reasoning. High budget → deep Qwen 27B reasoning.

Inspired by Bio-RegNet (resource-constrained homeostasis) and BioMARS.
"""
import logging
from enum import IntEnum

logger = logging.getLogger("cell.metabolism.attention")


class AttentionCost(IntEnum):
    """Unit cost of each cognitive operation."""
    DEEP_REASONING = 5   # Qwen 27B invocation
    FAST_REASONING = 2   # Qwen 9B invocation
    DREAMING = 3         # nocturnal episode consolidation
    CURIOSITY = 2        # curiosity-driven investigation
    JOURNAL = 1          # daily journal write


class AttentionAllocator:
    """Tracks and gates cognitive resource usage.

    Budget resets daily via reset(). Should be called once per day
    (during sleep phase or at midnight UTC).
    """

    def __init__(self, daily_units: int = 100) -> None:
        self._daily_units = daily_units
        self._available = float(daily_units)
        self._spent = 0.0

    @property
    def daily_units(self) -> int:
        return self._daily_units

    def available(self) -> float:
        return max(0.0, self._available)

    @property
    def daily_spent(self) -> float:
        return self._spent

    def can_afford(self, cost: AttentionCost) -> bool:
        return self._available >= cost

    def spend(self, cost: AttentionCost) -> bool:
        """Deduct units. Returns True if spending succeeded, False if insufficient budget."""
        if self._available < cost:
            # Clamp to zero — don't go negative
            self._spent += self._available
            self._available = 0.0
            logger.debug(f"Attention budget depleted trying to spend {cost} units ({cost.name})")
            return False
        self._available -= cost
        self._spent += cost
        logger.debug(
            f"Attention: spent {cost} ({cost.name}), "
            f"available={self._available:.0f}/{self._daily_units}"
        )
        return True

    def reset(self) -> None:
        """Restore full daily budget. Call once per day."""
        logger.info(
            f"Attention budget reset: was {self._available:.0f} remaining "
            f"({self._spent:.0f} spent today)"
        )
        self._available = float(self._daily_units)
        self._spent = 0.0

    def to_dict(self) -> dict:
        return {
            "available": int(self._available),
            "spent": int(self._spent),
            "daily_units": self._daily_units,
        }
