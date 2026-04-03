# cell/fast/homeostatic_controller.py
"""Homeostatic Controller — CELL's body regulation.

Adaptive setpoints via exponential moving average.
Stress/energy/arousal as continuous 0-1 variables.
Circadian rhythm: awake → drowsy → asleep cycle.

Inspired by Bio-RegNet (Bayesian homeostatic framework).
Runs in FAST layer: no LLM, no network, <1ms per update.
"""
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("cell.homeostasis")

# EMA smoothing factor — 0.2 means ~5-pulse memory
_EMA_ALPHA = 0.2
# Stress decay per green pulse
_STRESS_DECAY = 0.05
# Stress rise per non-green pulse (scaled by deviation)
_STRESS_RISE_BASE = 0.15
# Energy recovery per green pulse
_ENERGY_RECOVERY = 0.02
# Arousal decay toward baseline (0.5) per pulse
_AROUSAL_DECAY = 0.03


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class HomeostaticState:
    """The organism's internal physiological state."""
    stress_level: float = 0.0
    energy_level: float = 1.0
    arousal: float = 0.5
    comfort_zone: tuple[float, float] = (50.0, 200.0)
    setpoint_rt_ms: float = 100.0
    circadian_phase: str = "awake"  # "awake" | "drowsy" | "asleep"

    def __post_init__(self) -> None:
        self.stress_level = _clamp(self.stress_level)
        self.energy_level = _clamp(self.energy_level)
        self.arousal = _clamp(self.arousal)


class HomeostaticController:
    """Maintains CELL's internal equilibrium.

    Called once per pulse with the latest sensor readings.
    Outputs: updated HomeostaticState + recommended pulse interval.
    """

    def __init__(self, sleep_hours: tuple[int, int] = (2, 6)) -> None:
        """
        Args:
            sleep_hours: (start_hour_utc, end_hour_utc) for circadian sleep.
                         Default 2-6 UTC = 10:00-14:00 WITA (low traffic).
        """
        self.state = HomeostaticState()
        self._sleep_start = sleep_hours[0]
        self._sleep_end = sleep_hours[1]
        self._rt_history: list[float] = []
        self._max_history = 100

    def update(
        self,
        response_time_ms: int,
        health_status: str,
        hour_utc: int | None = None,
    ) -> HomeostaticState:
        """Process one pulse reading and update internal state."""
        rt = float(response_time_ms)

        # Track history for variance calculation
        self._rt_history.append(rt)
        if len(self._rt_history) > self._max_history:
            self._rt_history = self._rt_history[-self._max_history:]

        # 1. Update setpoint (EMA)
        self.state.setpoint_rt_ms = (
            _EMA_ALPHA * rt + (1 - _EMA_ALPHA) * self.state.setpoint_rt_ms
        )

        # 2. Update comfort zone (setpoint ± 1 sigma)
        if len(self._rt_history) >= 5:
            mean = sum(self._rt_history) / len(self._rt_history)
            variance = sum((x - mean) ** 2 for x in self._rt_history) / len(self._rt_history)
            sigma = math.sqrt(variance) if variance > 0 else 25.0
            sigma = max(sigma, 25.0)  # floor at 25ms to avoid overly tight zone
            self.state.comfort_zone = (
                max(0.0, self.state.setpoint_rt_ms - sigma),
                self.state.setpoint_rt_ms + sigma,
            )

        # 3. Update stress
        low, high = self.state.comfort_zone
        if rt < low or rt > high:
            # Outside comfort zone — stress rises proportionally to deviation
            if rt > high:
                deviation = (rt - high) / max(high, 1.0)
            else:
                deviation = (low - rt) / max(low, 1.0)
            rise = _STRESS_RISE_BASE * min(deviation, 2.0)
            self.state.stress_level = _clamp(self.state.stress_level + rise)
        else:
            # Inside comfort zone — stress decays
            self.state.stress_level = _clamp(self.state.stress_level - _STRESS_DECAY)

        # Non-green status adds stress regardless of RT
        if health_status != "green":
            bump = 0.1 if health_status == "yellow" else 0.25
            self.state.stress_level = _clamp(self.state.stress_level + bump)

        # 4. Update energy (recovers during green, stable otherwise)
        if health_status == "green":
            self.state.energy_level = _clamp(self.state.energy_level + _ENERGY_RECOVERY)

        # 5. Update arousal (trends toward 0.5 baseline, stress pushes up)
        target_arousal = 0.5 + self.state.stress_level * 0.4
        diff = target_arousal - self.state.arousal
        self.state.arousal = _clamp(self.state.arousal + diff * _AROUSAL_DECAY * 3)

        # 6. Circadian phase
        if hour_utc is None:
            hour_utc = datetime.now(timezone.utc).hour

        if self._sleep_start <= hour_utc < self._sleep_end:
            self.state.circadian_phase = "asleep"
        elif hour_utc == (self._sleep_start - 1) % 24:
            self.state.circadian_phase = "drowsy"
        elif hour_utc == self._sleep_end:
            self.state.circadian_phase = "drowsy"
        else:
            self.state.circadian_phase = "awake"

        logger.debug(
            f"Homeostasis: stress={self.state.stress_level:.2f} "
            f"energy={self.state.energy_level:.2f} "
            f"arousal={self.state.arousal:.2f} "
            f"phase={self.state.circadian_phase} "
            f"setpoint={self.state.setpoint_rt_ms:.0f}ms "
            f"zone={self.state.comfort_zone[0]:.0f}-{self.state.comfort_zone[1]:.0f}ms"
        )

        return self.state

    def record_action_cost(self, cost: float) -> None:
        """Drain energy when an action is taken."""
        self.state.energy_level = _clamp(self.state.energy_level - cost)

    def recommended_pulse_interval(self) -> int:
        """Calculate recommended pulse interval in seconds.

        - Asleep: 300s (5 min)
        - Drowsy: 120s (2 min)
        - Awake + stressed: 15s
        - Awake + calm: 60s
        """
        phase = self.state.circadian_phase
        stress = self.state.stress_level

        if phase == "asleep":
            return 300
        if phase == "drowsy":
            return 120

        # Awake: interpolate between 15s (max stress) and 60s (no stress)
        interval = int(60 - stress * 45)
        return max(15, min(60, interval))

    def is_sleeping(self) -> bool:
        """True if CELL is in sleep phase."""
        return self.state.circadian_phase == "asleep"

    def to_dict(self) -> dict:
        """Serialize state for STM/logging."""
        return {
            "stress_level": round(self.state.stress_level, 3),
            "energy_level": round(self.state.energy_level, 3),
            "arousal": round(self.state.arousal, 3),
            "comfort_zone_low": round(self.state.comfort_zone[0], 1),
            "comfort_zone_high": round(self.state.comfort_zone[1], 1),
            "setpoint_rt_ms": round(self.state.setpoint_rt_ms, 1),
            "circadian_phase": self.state.circadian_phase,
        }
