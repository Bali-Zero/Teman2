"""SelfModel — the organism knows itself.

Persistent identity that survives restarts: lifetime counters,
sensor reliability scores, learned preferences, acknowledged weaknesses.
Stored as JSON file — simple, local, fast.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cell_core.identity")


@dataclass
class SelfModel:
    """The organism's understanding of itself."""
    capabilities: dict[str, float] = field(default_factory=dict)
    preferences: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    personality_traits: dict[str, float] = field(default_factory=dict)
    sensor_history: dict[str, list[bool]] = field(default_factory=dict)
    age_days: int = 0
    total_pulses: int = 0
    total_actions: int = 0
    birth_date: str = ""

    def __post_init__(self) -> None:
        if not self.birth_date:
            self.birth_date = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": self.capabilities,
            "preferences": self.preferences,
            "weaknesses": self.weaknesses,
            "personality_traits": self.personality_traits,
            "sensor_history": self.sensor_history,
            "age_days": self.age_days,
            "total_pulses": self.total_pulses,
            "total_actions": self.total_actions,
            "birth_date": self.birth_date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelfModel:
        return cls(
            capabilities=data.get("capabilities", {}),
            preferences=data.get("preferences", []),
            weaknesses=data.get("weaknesses", []),
            personality_traits=data.get("personality_traits", {}),
            sensor_history=data.get("sensor_history", {}),
            age_days=data.get("age_days", 0),
            total_pulses=data.get("total_pulses", 0),
            total_actions=data.get("total_actions", 0),
            birth_date=data.get("birth_date", ""),
        )


class SelfModelManager:
    """Manages loading, updating, and saving the self-model."""

    def __init__(self, path: str | Path = "data/self_model.json") -> None:
        self._path = Path(path)
        self.model = SelfModel()
        self._sensor_history: dict[str, list[bool]] = {}

    def load(self) -> None:
        if not self._path.exists():
            logger.info(f"Self-model not found at {self._path}, using defaults")
            return
        try:
            data = json.loads(self._path.read_text())
            self.model = SelfModel.from_dict(data)
            self._sensor_history = {k: list(v) for k, v in self.model.sensor_history.items()}
        except Exception as e:
            logger.warning(f"Failed to load self-model: {e}")

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.model.to_dict(), indent=2))
            tmp.replace(self._path)
        except Exception as e:
            logger.warning(f"Failed to save self-model: {e}")

    def record_pulse(self) -> None:
        self.model.total_pulses += 1
        if self.model.birth_date:
            try:
                birth = datetime.fromisoformat(self.model.birth_date)
                now = datetime.now(timezone.utc)
                self.model.age_days = (now - birth).days
            except (ValueError, TypeError):
                pass

    def record_action(self, action_name: str) -> None:
        self.model.total_actions += 1

    def update_sensor_reliability(self, sensor_name: str, success: bool) -> None:
        if sensor_name not in self._sensor_history:
            self._sensor_history[sensor_name] = []
        history = self._sensor_history[sensor_name]
        history.append(success)
        if len(history) > 100:
            self._sensor_history[sensor_name] = history[-100:]
            history = self._sensor_history[sensor_name]
        self.model.capabilities[sensor_name] = sum(history) / len(history)
        self.model.sensor_history = dict(self._sensor_history)

    def to_prompt_context(self) -> str:
        lines = [
            "SELF-MODEL:",
            f"  age_days: {self.model.age_days}",
            f"  total_pulses: {self.model.total_pulses}",
            f"  total_actions: {self.model.total_actions}",
        ]
        if self.model.capabilities:
            caps = ", ".join(f"{k}: {v:.0%}" for k, v in sorted(self.model.capabilities.items()))
            lines.append(f"  sensor_reliability: {caps}")
        if self.model.preferences:
            lines.append(f"  preferences: {', '.join(self.model.preferences)}")
        if self.model.weaknesses:
            lines.append(f"  weaknesses: {', '.join(self.model.weaknesses)}")
        return "\n".join(lines)
