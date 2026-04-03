# cell/identity/self_model.py
"""Self-Model — CELL knows itself.

Persistent identity that survives restarts: lifetime counters,
sensor reliability scores, learned preferences, acknowledged weaknesses.
Stored as JSON file (not DB) — simple, local, fast.

Inspired by Stanford Smallville (persistent agent identity).
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cell.identity")

_DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "self_model.json"


@dataclass
class SelfModel:
    """CELL's understanding of itself."""
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
    def from_dict(cls, data: dict[str, Any]) -> "SelfModel":
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

    def __init__(self, path: str | Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self.model = SelfModel()
        self._sensor_history: dict[str, list[bool]] = {}

    def load(self) -> None:
        """Load self-model from JSON file. Creates default if missing."""
        if not self._path.exists() or str(self._path) == "/dev/null":
            logger.info(f"Self-model not found at {self._path}, using defaults")
            return
        try:
            data = json.loads(self._path.read_text())
            self.model = SelfModel.from_dict(data)
            self._sensor_history = {k: list(v) for k, v in self.model.sensor_history.items()}
            logger.info(
                f"Self-model loaded: age={self.model.age_days}d "
                f"pulses={self.model.total_pulses} "
                f"actions={self.model.total_actions}"
            )
        except Exception as e:
            logger.warning(f"Failed to load self-model: {e}")

    def save(self) -> None:
        """Persist self-model to JSON file."""
        if str(self._path) == "/dev/null":
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self.model.to_dict(), indent=2))
        except Exception as e:
            logger.warning(f"Failed to save self-model: {e}")

    def record_pulse(self) -> None:
        """Called once per pulse to update lifetime counters."""
        self.model.total_pulses += 1
        # Update age_days from birth_date
        if self.model.birth_date:
            try:
                birth = datetime.fromisoformat(self.model.birth_date)
                now = datetime.now(timezone.utc)
                self.model.age_days = (now - birth).days
            except (ValueError, TypeError):
                pass

    def record_action(self) -> None:
        """Called when an action is executed."""
        self.model.total_actions += 1

    def update_sensor_reliability(self, sensor_name: str, success: bool) -> None:
        """Track sensor reliability as rolling success rate.

        Keeps last 100 readings per sensor.
        """
        if sensor_name not in self._sensor_history:
            self._sensor_history[sensor_name] = []
        history = self._sensor_history[sensor_name]
        history.append(success)
        if len(history) > 100:
            self._sensor_history[sensor_name] = history[-100:]
        # Reliability = success rate
        self.model.capabilities[sensor_name] = sum(history) / len(history)
        # Sync history back to model for persistence
        self.model.sensor_history = dict(self._sensor_history)

    def add_preference(self, preference: str) -> None:
        """Add a learned preference (deduplicated)."""
        if preference not in self.model.preferences:
            self.model.preferences.append(preference)
            logger.info(f"Self-model: learned preference '{preference}'")

    def add_weakness(self, weakness: str) -> None:
        """Acknowledge a limitation (deduplicated)."""
        if weakness not in self.model.weaknesses:
            self.model.weaknesses.append(weakness)
            logger.info(f"Self-model: acknowledged weakness '{weakness}'")

    def to_prompt_context(self) -> str:
        """Format self-model as context for LLM injection."""
        lines = [
            "SELF-MODEL (who I am):",
            f"  age_days: {self.model.age_days}",
            f"  total_pulses: {self.model.total_pulses}",
            f"  total_actions: {self.model.total_actions}",
        ]
        if self.model.capabilities:
            caps = ", ".join(f"{k}: {v:.0%}" for k, v in sorted(self.model.capabilities.items()))
            lines.append(f"  sensor_reliability: {caps}")
        if self.model.preferences:
            lines.append(f"  preferences: {'; '.join(self.model.preferences[:5])}")
        if self.model.weaknesses:
            lines.append(f"  weaknesses: {'; '.join(self.model.weaknesses[:5])}")
        return "\n".join(lines)
