# cell/fast/homeostatic_controller.py
"""Homeostatic Controller — thin bridge to cell-core.

Re-exports HomeostaticController and HomeostaticState from cell-core,
adding CELL-specific to_dict() and hour_utc default.
"""
from datetime import datetime, timezone
from typing import Any

from cell_core.homeostasis import HomeostaticController as _CoreController
from cell_core.types import HomeostaticState


class HomeostaticController(_CoreController):
    """CELL-compatible HomeostaticController with to_dict() and optional hour_utc."""

    def update(
        self,
        response_time_ms: int,
        health_status: str,
        hour_utc: int | None = None,
    ) -> HomeostaticState:
        """Update with optional hour_utc (defaults to current UTC hour)."""
        if hour_utc is None:
            hour_utc = datetime.now(timezone.utc).hour
        return super().update(
            response_time_ms=response_time_ms,
            health_status=health_status,
            hour_utc=hour_utc,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for STM/logging (CELL-specific, not in cell-core)."""
        return {
            "stress_level": round(self.state.stress_level, 3),
            "energy_level": round(self.state.energy_level, 3),
            "arousal": round(self.state.arousal, 3),
            "comfort_zone_low": round(self.state.comfort_zone[0], 1),
            "comfort_zone_high": round(self.state.comfort_zone[1], 1),
            "setpoint_rt_ms": round(self.state.setpoint_rt_ms, 1),
            "circadian_phase": self.state.circadian_phase,
        }


__all__ = ["HomeostaticController", "HomeostaticState"]
