# apps/cell/cell/lifecycle/maturation.py
"""Maturation — thin bridge to cell-core.

Re-exports cell_core.lifecycle.Maturation with backward-compatible constructor
(age_days: int) and re-exports Phase as LifecyclePhase for existing code.
"""
import logging
from datetime import datetime, timedelta, timezone

from cell_core.lifecycle import Maturation as _CoreMaturation
from cell_core.types import Phase

logger = logging.getLogger("cell.lifecycle")

# Backward-compatible alias: CELL code uses LifecyclePhase everywhere.
LifecyclePhase = Phase


class Maturation(_CoreMaturation):
    """CELL-compatible Maturation that accepts age_days or birth_date."""

    def __init__(
        self,
        age_days: int | None = None,
        birth_date: datetime | None = None,
    ) -> None:
        if birth_date is not None:
            super().__init__(birth_date=birth_date)
        elif age_days is not None:
            # Convert age_days to a synthetic birth_date
            synthetic_birth = datetime.now(timezone.utc) - timedelta(days=age_days)
            super().__init__(birth_date=synthetic_birth)
        else:
            raise ValueError("Either age_days or birth_date must be provided")

    def log_phase(self) -> None:
        """Log current lifecycle phase (CELL-specific, not in cell-core)."""
        logger.info(
            "Maturation: phase=%s age=%dd can_act=%s can_dream=%s "
            "confidence_threshold=%s",
            self.phase.value,
            self.age_days,
            self.can_act(),
            self.can_dream(),
            self.action_confidence_threshold(),
        )
