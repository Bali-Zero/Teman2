"""TrendDetector — detects monotonic drift and flapping in time-series metrics.

Runs inside the FAST layer (<5ms target). Works on the in-memory
recent_pulses list already maintained by PulseEngine.

Detects:
  1. Monotonic drift    — response_time_ms rising every pulse for N consecutive readings
  2. Flapping           — health_status alternates green/non-green rapidly
  3. Sustained degraded — N consecutive non-green readings without recovery
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TrendResult:
    monotonic_drift: bool = False
    flapping: bool = False
    sustained_degraded: bool = False
    details: dict[str, Any] | None = None


class TrendDetector:
    """Stateless trend detector — call detect() on every pulse.

    Parameters
    ----------
    drift_window      Number of consecutive pulses to check for monotonic RT rise (default 5)
    flap_window       Window size for flapping detection (default 6)
    flap_threshold    Min alternations to flag as flapping (default 3)
    sustained_window  Consecutive non-green pulses to flag sustained degraded (default 4)
    """

    def __init__(
        self,
        drift_window: int = 5,
        flap_window: int = 6,
        flap_threshold: int = 3,
        sustained_window: int = 4,
    ) -> None:
        self._drift_window = drift_window
        self._flap_window = flap_window
        self._flap_threshold = flap_threshold
        self._sustained_window = sustained_window

    def detect(self, recent_pulses: list[dict[str, Any]]) -> TrendResult:
        """Analyse the tail of recent_pulses and return detected trends."""
        if len(recent_pulses) < 2:
            return TrendResult()

        details: dict[str, Any] = {}

        # 1. Monotonic drift — last N response times strictly increasing
        drift = False
        if len(recent_pulses) >= self._drift_window:
            window = recent_pulses[-self._drift_window:]
            rts = [p.get("response_time_ms", 0) for p in window]
            if all(rts[i] < rts[i + 1] for i in range(len(rts) - 1)) and rts[0] > 0:
                drift = True
                details["drift_rts_ms"] = rts

        # 2. Flapping — status alternates in last N readings
        flapping = False
        if len(recent_pulses) >= self._flap_window:
            window = recent_pulses[-self._flap_window:]
            statuses = [p.get("health_status", "green") for p in window]
            alternations = sum(
                1 for i in range(len(statuses) - 1)
                if (statuses[i] == "green") != (statuses[i + 1] == "green")
            )
            if alternations >= self._flap_threshold:
                flapping = True
                details["flap_alternations"] = alternations
                details["flap_statuses"] = statuses

        # 3. Sustained degraded — last N all non-green
        sustained = False
        if len(recent_pulses) >= self._sustained_window:
            window = recent_pulses[-self._sustained_window:]
            statuses = [p.get("health_status", "green") for p in window]
            if all(s != "green" for s in statuses):
                sustained = True
                details["sustained_statuses"] = statuses

        return TrendResult(
            monotonic_drift=drift,
            flapping=flapping,
            sustained_degraded=sustained,
            details=details if details else None,
        )
