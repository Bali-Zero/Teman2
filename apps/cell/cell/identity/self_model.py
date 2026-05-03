# cell/identity/self_model.py
"""Self-Model — thin bridge to cell-core.

Re-exports SelfModel and SelfModelManager from cell_core.identity,
adding CELL-specific methods: add_preference(), add_weakness(), /dev/null guard.
"""
import logging
from pathlib import Path

from cell_core.identity import SelfModel, SelfModelManager as _CoreManager

logger = logging.getLogger("cell.identity")

_DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "self_model.json"


class SelfModelManager(_CoreManager):
    """CELL-compatible SelfModelManager with preference/weakness tracking."""

    def __init__(self, path: str | Path = _DEFAULT_PATH) -> None:
        super().__init__(path=path)

    def load(self) -> None:
        """Load self-model, with /dev/null guard for tests."""
        if str(self._path) == "/dev/null":
            logger.info("Self-model path is /dev/null, using defaults")
            return
        super().load()

    def save(self) -> None:
        """Persist self-model, skipping /dev/null."""
        if str(self._path) == "/dev/null":
            return
        super().save()

    def record_action(self, action_name: str = "") -> None:
        """Record an action. Accepts optional action_name for cell-core compat."""
        super().record_action(action_name=action_name)

    def add_preference(self, preference: str) -> None:
        """Add a learned preference (deduplicated). CELL-specific."""
        if preference not in self.model.preferences:
            self.model.preferences.append(preference)
            logger.info("Self-model: learned preference '%s'", preference)

    def add_weakness(self, weakness: str) -> None:
        """Acknowledge a limitation (deduplicated). CELL-specific."""
        if weakness not in self.model.weaknesses:
            self.model.weaknesses.append(weakness)
            logger.info("Self-model: acknowledged weakness '%s'", weakness)

    def to_prompt_context(self) -> str:
        """Format self-model as context for LLM injection (CELL-specific format)."""
        lines = [
            "SELF-MODEL (who I am):",
            f"  age_days: {self.model.age_days}",
            f"  total_pulses: {self.model.total_pulses}",
            f"  total_actions: {self.model.total_actions}",
        ]
        if self.model.capabilities:
            caps = ", ".join(
                f"{k}: {v:.0%}" for k, v in sorted(self.model.capabilities.items())
            )
            lines.append(f"  sensor_reliability: {caps}")
        if self.model.preferences:
            lines.append(f"  preferences: {'; '.join(self.model.preferences[:5])}")
        if self.model.weaknesses:
            lines.append(f"  weaknesses: {'; '.join(self.model.weaknesses[:5])}")
        return "\n".join(lines)


__all__ = ["SelfModel", "SelfModelManager"]
