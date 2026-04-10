"""Shared fixtures — fake protocol implementations for testing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from cell_core.types import (
    CellConfig, Episode, HomeostaticState, LearnedRule, Proposal, SensorReading,
)


class FakeSensor:
    def __init__(self, name: str = "fake", status: str = "green"):
        self.name = name
        self._status = status

    async def read(self, **ctx: Any) -> SensorReading:
        return SensorReading(sensor_name=self.name, status=self._status)


class FakeThinker:
    def __init__(self, action: str = "none", confidence: float = 1.0):
        self._action = action
        self._confidence = confidence
        self.call_count = 0

    async def think(self, readings, state, memory_context) -> Proposal:
        self.call_count += 1
        return Proposal(action=self._action, reason="fake", confidence=self._confidence, tier_used=0)


class FakeActor:
    def __init__(self, allowlist: set[str] | None = None):
        self._allowlist = allowlist or {"restart_service", "alert_human"}
        self.executed: list[str] = []

    async def act(self, proposal: Proposal) -> str:
        self.executed.append(proposal.action)
        return f"executed:{proposal.action}"

    def can_execute(self, action_name: str) -> bool:
        return action_name in self._allowlist


class FakeSTM:
    def __init__(self):
        self.stored: list[tuple[str, dict]] = []

    async def store(self, event_type: str, data: dict) -> None:
        self.stored.append((event_type, data))

    async def recent(self, event_type: str, limit: int) -> list[dict]:
        return [d for et, d in self.stored if et == event_type or not event_type][:limit]


class FakeLTM:
    def __init__(self):
        self.rules: list[LearnedRule] = []

    async def store_rule(self, rule: LearnedRule) -> None:
        self.rules.append(rule)

    async def load_rules(self, limit: int) -> list[LearnedRule]:
        return self.rules[:limit]

    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]:
        if episodes:
            return [LearnedRule(rule_text="condensed rule", support_count=len(episodes))]
        return []


class FakeEpisodic:
    def __init__(self):
        self.episodes: list[Episode] = []
        self._next_id = 1

    async def store(self, episode: Episode) -> int:
        episode.id = self._next_id
        self._next_id += 1
        self.episodes.append(episode)
        return episode.id

    async def recall(self, situation: dict, limit: int) -> list[Episode]:
        return self.episodes[-limit:]

    async def recall_recent(self, hours: int, limit: int) -> list[Episode]:
        return self.episodes[-limit:]

    async def forget_weak(self, keep: int) -> int:
        if len(self.episodes) <= keep:
            return 0
        removed = len(self.episodes) - keep
        self.episodes = self.episodes[-keep:]
        return removed


@pytest.fixture
def cell_config():
    return CellConfig(
        name="test",
        dna_path="test_dna.json",
        birth_date=datetime.now(timezone.utc) - timedelta(days=50),
    )
