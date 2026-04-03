# cell/memory/episodic.py
"""Episodic Memory — CELL remembers moments, not statistics.

Each significant event becomes an Episode with emotion, outcome, and lesson.
Retrieval uses ACT-R activation: log(recency) + frequency_bonus + similarity.
Max episodes enforced via forget_weak() — drops lowest activation.

Inspired by MemGPT (OS-inspired paging) + ACT-R (activation-based retrieval).
"""
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("cell.memory.episodic")

VALID_EMOTIONS = ("calm", "alert", "stressed", "panic")
VALID_OUTCOMES = ("success", "partial", "failure")

# ACT-R activation parameters
_RECENCY_WEIGHT = 1.0
_FREQUENCY_WEIGHT = 0.5
_BASE_ACTIVATION = 0.5


@dataclass
class Episode:
    """A single episodic memory — a moment CELL experienced."""
    situation: dict[str, Any]
    emotion: str
    action_taken: str
    outcome: str
    lesson: str
    id: int = 0
    timestamp: float = 0.0
    recall_count: int = 0
    activation: float = 0.0

    def __post_init__(self) -> None:
        if self.emotion not in VALID_EMOTIONS:
            raise ValueError(f"emotion must be one of {VALID_EMOTIONS}, got '{self.emotion}'")
        if self.outcome not in VALID_OUTCOMES:
            raise ValueError(f"outcome must be one of {VALID_OUTCOMES}, got '{self.outcome}'")
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        self.activation = self.compute_activation()

    def compute_activation(self) -> float:
        """ACT-R activation: base + log(recency_days) + frequency_bonus.

        Recent + frequently-recalled episodes have higher activation.
        """
        age_seconds = max(time.time() - self.timestamp, 1.0)
        age_days = age_seconds / 86400.0
        recency = _RECENCY_WEIGHT * (1.0 / (1.0 + math.log1p(age_days)))
        frequency = _FREQUENCY_WEIGHT * math.log1p(self.recall_count)
        return _BASE_ACTIVATION + recency + frequency


class EpisodicMemory:
    """Manages episodic storage and retrieval in PostgreSQL."""

    def __init__(self, pool: Any, max_episodes: int = 1000) -> None:
        self._pool = pool
        self._max_episodes = max_episodes

    def should_record(self, health_status: str, action_taken: str | None) -> bool:
        """Decide if this pulse is worth recording as an episode.

        Record when: non-green status, action was taken, or anomaly detected.
        Skip: routine green pulses with no action.
        """
        if health_status != "green":
            return True
        if action_taken is not None:
            return True
        return False

    async def store(self, episode: Episode) -> None:
        """Persist an episode to PostgreSQL."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_episodes
                   (timestamp, situation, emotion, action_taken, outcome, lesson, recall_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                episode.timestamp,
                json.dumps(episode.situation),
                episode.emotion,
                episode.action_taken,
                episode.outcome,
                episode.lesson,
                episode.recall_count,
            )
        logger.info(f"Episode stored: emotion={episode.emotion} action={episode.action_taken} outcome={episode.outcome}")

    async def recall(self, situation: dict[str, Any], limit: int = 5) -> list[Episode]:
        """Retrieve the most relevant episodes for a given situation.

        Retrieves recent episodes and ranks by ACT-R activation.
        Increments recall_count for retrieved episodes (strengthens memory).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, timestamp, situation, emotion, action_taken,
                          outcome, lesson, recall_count
                   FROM cell_episodes
                   ORDER BY timestamp DESC
                   LIMIT $1""",
                limit * 3,  # fetch extra, then rank by activation
            )

        if not rows:
            return []

        episodes = []
        for row in rows:
            sit = row["situation"]
            if isinstance(sit, str):
                sit = json.loads(sit)
            ep = Episode(
                id=row["id"],
                timestamp=float(row["timestamp"]),
                situation=sit,
                emotion=row["emotion"],
                action_taken=row["action_taken"],
                outcome=row["outcome"],
                lesson=row["lesson"],
                recall_count=row["recall_count"],
            )
            episodes.append(ep)

        # Sort by activation (highest first) and take top N
        episodes.sort(key=lambda e: e.activation, reverse=True)
        top = episodes[:limit]

        # Increment recall_count for retrieved episodes (fire-and-forget)
        if top:
            try:
                async with self._pool.acquire() as conn:
                    ids = [e.id for e in top if e.id > 0]
                    if ids:
                        await conn.execute(
                            "UPDATE cell_episodes SET recall_count = recall_count + 1 WHERE id = ANY($1::int[])",
                            ids,
                        )
            except Exception as e:
                logger.debug(f"Failed to update recall_count: {e}")

        return top

    async def count(self) -> int:
        """Count total episodes in storage."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM cell_episodes") or 0

    async def forget_weak(self) -> int:
        """Remove episodes when over capacity.

        Uses recall_count ASC, timestamp ASC as a proxy for low activation —
        oldest episodes with lowest recall count are dropped first.
        Returns number of episodes deleted.
        """
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM cell_episodes") or 0

        if total <= self._max_episodes:
            return 0

        to_delete = total - self._max_episodes

        # Delete oldest with lowest recall_count (proxy for low activation)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """DELETE FROM cell_episodes
                   WHERE id IN (
                       SELECT id FROM cell_episodes
                       ORDER BY recall_count ASC, timestamp ASC
                       LIMIT $1
                   )""",
                to_delete,
            )

        logger.info(f"Episodic forgetting: deleted {to_delete} weak episodes (was {total}, max {self._max_episodes})")
        return to_delete

    async def recent_lessons(self, limit: int = 5) -> list[str]:
        """Get recent lessons for context injection into reasoner."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT lesson, emotion, action_taken, outcome
                   FROM cell_episodes
                   ORDER BY timestamp DESC
                   LIMIT $1""",
                limit,
            )
        return [
            f"[{r['emotion']}] {r['action_taken']} → {r['outcome']}: {r['lesson']}"
            for r in rows
        ]

    def format_for_prompt(self, episodes: list[Episode]) -> str:
        """Format episodes as compact context for LLM injection."""
        if not episodes:
            return ""
        lines = ["EPISODIC MEMORY (past experiences):"]
        for ep in episodes[:5]:
            lines.append(
                f"  - [{ep.emotion}] {ep.action_taken} → {ep.outcome}: {ep.lesson}"
            )
        return "\n".join(lines)
