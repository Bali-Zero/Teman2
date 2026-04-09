"""Protocol definitions — the contracts every organ must implement."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from cell_core.types import (
    Episode,
    HomeostaticState,
    LearnedRule,
    Proposal,
    SensorReading,
)


@runtime_checkable
class Sensor(Protocol):
    """Perceives one aspect of the environment."""
    name: str
    async def read(self, **context: Any) -> SensorReading: ...


@runtime_checkable
class Thinker(Protocol):
    """Reasons about sensor readings and proposes actions."""
    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal: ...


@runtime_checkable
class Actor(Protocol):
    """Executes a proposed action."""
    async def act(self, proposal: Proposal) -> str: ...
    def can_execute(self, action_name: str) -> bool: ...


@runtime_checkable
class STMStore(Protocol):
    """Short-term memory — volatile, TTL-based."""
    async def store(self, event_type: str, data: dict[str, Any]) -> None: ...
    async def recent(self, event_type: str, limit: int) -> list[dict[str, Any]]: ...


@runtime_checkable
class LTMStore(Protocol):
    """Long-term memory — persistent learned rules."""
    async def store_rule(self, rule: LearnedRule) -> None: ...
    async def load_rules(self, limit: int) -> list[LearnedRule]: ...
    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]: ...


@runtime_checkable
class EpisodicStore(Protocol):
    """Episodic memory — significant moments with ACT-R activation."""
    async def store(self, episode: Episode) -> int: ...
    async def recall(self, situation: dict[str, Any], limit: int) -> list[Episode]: ...
    async def recall_recent(self, hours: int, limit: int) -> list[Episode]: ...
    async def forget_weak(self, keep: int) -> int: ...
