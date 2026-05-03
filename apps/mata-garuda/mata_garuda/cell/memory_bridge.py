"""Memory bridge — adapts MG's KnowledgeBase as cell-core memory protocols.

KnowledgeBridgeLTM wraps knowledge.py as LTMStore.
ReflectionEpisodicStore wraps knowledge.py as EpisodicStore (episodes = reflections).
BridgeSTM is in-memory (MG doesn't need Redis STM).

Note: KB operations run synchronously inside async methods because SQLite
connections are thread-affine (check_same_thread=True by default) and the
underlying ops are sub-millisecond local I/O. The condense() method uses
asyncio.to_thread for CPU-bound pattern extraction (no SQLite involved).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from typing import Any

from cell_core.types import Episode, LearnedRule
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.cell")


class KnowledgeBridgeLTM:
    """Wraps KnowledgeBase as cell-core LTMStore protocol."""

    def __init__(self, kb: KnowledgeBase) -> None:
        self._kb = kb

    async def store_rule(self, rule: LearnedRule) -> None:
        self._kb.store(
            agent="cell",
            entry_type="rule",
            content=rule.rule_text,
            source="ltm_condense",
            confidence=min(rule.support_count / 10.0, 1.0),
        )

    async def load_rules(self, limit: int) -> list[LearnedRule]:
        rows = self._kb.get_by_type("rule", limit)
        return [
            LearnedRule(
                rule_text=row["content"],
                support_count=int(row.get("confidence", 0.5) * 10),
                created_at=row.get("created_at", ""),
            )
            for row in rows
        ]

    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]:
        """Extract patterns from episodes — group by action+outcome."""
        def _condense() -> list[LearnedRule]:
            patterns: Counter[str] = Counter()
            for ep in episodes:
                key = f"When {ep.emotion}, {ep.action_taken} \u2192 {ep.outcome}"
                patterns[key] += 1
            return [
                LearnedRule(rule_text=pattern, support_count=count)
                for pattern, count in patterns.most_common()
                if count >= 2
            ]
        return await asyncio.to_thread(_condense)


class ReflectionEpisodicStore:
    """Wraps KnowledgeBase as cell-core EpisodicStore.

    Episodes are stored as type='episode' in the KB.
    """

    def __init__(self, kb: KnowledgeBase) -> None:
        self._kb = kb

    async def store(self, episode: Episode) -> int:
        content = json.dumps({
            "situation": episode.situation,
            "emotion": episode.emotion,
            "action_taken": episode.action_taken,
            "outcome": episode.outcome,
            "lesson": episode.lesson,
        })
        return self._kb.store(
            agent="cell",
            entry_type="episode",
            content=content,
            source=f"pulse_{episode.emotion}",
            confidence=0.5,
        )

    async def recall(self, situation: dict[str, Any], limit: int) -> list[Episode]:
        rows = self._kb.get_by_type("episode", limit)
        return self._rows_to_episodes(rows)

    async def recall_recent(self, hours: int, limit: int) -> list[Episode]:
        rows = self._kb.get_by_type("episode", limit)
        return self._rows_to_episodes(rows)

    async def forget_weak(self, keep: int) -> int:
        rows = self._kb.get_by_type("episode", 1000)
        if len(rows) <= keep:
            return 0
        to_delete = rows[keep:]
        for row in to_delete:
            self._kb._execute(
                "DELETE FROM knowledge WHERE id = ?",
                (row["id"],),
            )
        return len(to_delete)

    @staticmethod
    def _rows_to_episodes(rows: list[dict]) -> list[Episode]:
        episodes = []
        for row in rows:
            try:
                data = json.loads(row["content"])
                episodes.append(Episode(
                    id=row["id"],
                    situation=data.get("situation", {}),
                    emotion=data.get("emotion", "calm"),
                    action_taken=data.get("action_taken", ""),
                    outcome=data.get("outcome", ""),
                    lesson=data.get("lesson", ""),
                    timestamp=time.time(),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return episodes


class BridgeSTM:
    """In-memory STM for MG. No Redis needed — lightweight."""

    def __init__(self, max_entries: int = 100) -> None:
        self._store: list[tuple[str, dict[str, Any]]] = []
        self._max = max_entries

    async def store(self, event_type: str, data: dict[str, Any]) -> None:
        self._store.append((event_type, data))
        if len(self._store) > self._max:
            self._store = self._store[-self._max:]

    async def recent(self, event_type: str, limit: int) -> list[dict[str, Any]]:
        if event_type:
            filtered = [d for et, d in reversed(self._store) if et == event_type]
        else:
            filtered = [d for _, d in reversed(self._store)]
        return filtered[:limit]
