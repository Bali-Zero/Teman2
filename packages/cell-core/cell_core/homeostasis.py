"""Homeostatic Controller + Trend Detector — the organism's governor.

Adaptive setpoints via EMA. Stress/energy/arousal as continuous 0-1 variables.
Circadian rhythm: awake → drowsy → asleep cycle.
Trend detection: monotonic drift, flapping, sustained degraded.
Runs in FAST layer: no LLM, no network, <1ms per update.
"""
from __future__ import annotations

import dataclasses
import logging
import math
from dataclasses import dataclass
from typing import Any

from cell_core.types import HomeostaticState

logger = logging.getLogger("cell_core.homeostasis")

_EMA_ALPHA = 0.2
_STRESS_DECAY = 0.05
_STRESS_RISE_BASE = 0.15
_ENERGY_RECOVERY = 0.02
_AROUSAL_DECAY = 0.03


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class HomeostaticController:
    """Maintains internal equilibrium. <1ms per update."""

    def __init__(self, sleep_hours: tuple[int, int] = (2, 6)) -> None:
        self.state = HomeostaticState()
        self._sleep_start = sleep_hours[0]
        self._sleep_end = sleep_hours[1]
        self._rt_history: list[float] = []
        self._max_history = 100

    def update(self, response_time_ms: int, health_status: str, hour_utc: int) -> HomeostaticState:
        rt = float(response_time_ms)
        status = health_status.value if hasattr(health_status, "value") else health_status

        self._rt_history.append(rt)
        if len(self._rt_history) > self._max_history:
            self._rt_history = self._rt_history[-self._max_history:]

        # 1. Update setpoint (EMA)
        self.state.setpoint_rt_ms = _EMA_ALPHA * rt + (1 - _EMA_ALPHA) * self.state.setpoint_rt_ms

        # 2. Update comfort zone (setpoint +/- 1 sigma)
        if len(self._rt_history) >= 5:
            mean = sum(self._rt_history) / len(self._rt_history)
            variance = sum((x - mean) ** 2 for x in self._rt_history) / len(self._rt_history)
            sigma = math.sqrt(variance) if variance > 0 else 25.0
            sigma = max(sigma, 25.0)
            self.state.comfort_zone = (max(0.0, self.state.setpoint_rt_ms - sigma), self.state.setpoint_rt_ms + sigma)

        # 3. Update stress
        low, high = self.state.comfort_zone
        if rt < low or rt > high:
            if rt > high:
                deviation = (rt - high) / max(high, 1.0)
            else:
                deviation = (low - rt) / max(low, 1.0)
            rise = _STRESS_RISE_BASE * min(deviation, 2.0)
            self.state.stress_level = _clamp(self.state.stress_level + rise)
        else:
            self.state.stress_level = _clamp(self.state.stress_level - _STRESS_DECAY)

        if status != "green":
            bump = 0.1 if status == "yellow" else 0.25
            self.state.stress_level = _clamp(self.state.stress_level + bump)

        # 4. Update energy
        if status == "green":
            self.state.energy_level = _clamp(self.state.energy_level + _ENERGY_RECOVERY)

        # 5. Update arousal
        target_arousal = 0.5 + self.state.stress_level * 0.4
        diff = target_arousal - self.state.arousal
        self.state.arousal = _clamp(self.state.arousal + diff * _AROUSAL_DECAY * 3)

        # 6. Circadian phase
        if self._sleep_start <= hour_utc < self._sleep_end:
            self.state.circadian_phase = "asleep"
        elif hour_utc == (self._sleep_start - 1) % 24 or hour_utc == self._sleep_end:
            self.state.circadian_phase = "drowsy"
        else:
            self.state.circadian_phase = "awake"

        return dataclasses.replace(self.state)

    def record_action_cost(self, cost: float) -> None:
        self.state.energy_level = _clamp(self.state.energy_level - cost)

    def recommended_pulse_interval(self) -> int:
        phase = self.state.circadian_phase
        stress = self.state.stress_level
        if phase == "asleep":
            return 300
        if phase == "drowsy":
            return 120
        interval = int(60 - stress * 45)
        return max(15, min(60, interval))

    def is_sleeping(self) -> bool:
        return self.state.circadian_phase == "asleep"


@dataclass
class TrendResult:
    monotonic_drift: bool = False
    flapping: bool = False
    sustained_degraded: bool = False
    details: dict[str, Any] | None = None


class TrendDetector:
    """Stateless trend detector. Call detect() on every pulse."""

    def __init__(self, drift_window: int = 5, flap_window: int = 6, flap_threshold: int = 3, sustained_window: int = 4) -> None:
        self._drift_window = drift_window
        self._flap_window = flap_window
        self._flap_threshold = flap_threshold
        self._sustained_window = sustained_window

    def detect(self, recent_pulses: list[dict[str, Any]]) -> TrendResult:
        if len(recent_pulses) < 2:
            return TrendResult()
        details: dict[str, Any] = {}

        # 1. Monotonic drift
        drift = False
        if len(recent_pulses) >= self._drift_window:
            window = recent_pulses[-self._drift_window:]
            rts = [p.get("response_time_ms", 0) for p in window]
            if all(rts[i] < rts[i + 1] for i in range(len(rts) - 1)) and rts[0] > 0:
                drift = True
                details["drift_rts_ms"] = rts

        # 2. Flapping
        flapping = False
        if len(recent_pulses) >= self._flap_window:
            window = recent_pulses[-self._flap_window:]
            statuses = [p.get("health_status", "green") for p in window]
            alternations = sum(1 for i in range(len(statuses) - 1) if (statuses[i] == "green") != (statuses[i + 1] == "green"))
            if alternations >= self._flap_threshold:
                flapping = True
                details["flap_alternations"] = alternations

        # 3. Sustained degraded
        sustained = False
        if len(recent_pulses) >= self._sustained_window:
            window = recent_pulses[-self._sustained_window:]
            statuses = [p.get("health_status", "green") for p in window]
            if all(s != "green" for s in statuses):
                sustained = True

        return TrendResult(monotonic_drift=drift, flapping=flapping, sustained_degraded=sustained, details=details if details else None)
