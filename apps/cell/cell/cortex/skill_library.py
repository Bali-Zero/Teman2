"""SkillLibrary — evolvable procedure store with fitness-weighted recall.

Skills are candidate procedures that CELL discovers, tests, promotes, and
eventually apoptoses when they fall below fitness thresholds or age out.
Each skill carries a pseudo-embedding for semantic recall and a fitness
score derived from success/failure counts.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = frozenset({"active", "candidate", "frozen", "apoptosed"})
EMBEDDING_DIM = 384
DECAY_DAYS_THRESHOLD = 30
DECAY_FITNESS_THRESHOLD = 0.3
DEFAULT_MAX_ACTIVE = 50

# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------


def compute_embedding(text: str) -> bytes:
    """Hash-based pseudo-embedding: 384-dim float32 from 3-gram hash.

    Produces a deterministic, normalised unit vector for any input text.
    Uses overlapping character 3-grams hashed with MD5 to populate a
    384-dimensional float32 vector, then L2-normalises to unit length.
    """
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    for i in range(len(text) - 2):
        trigram = text[i : i + 3]
        digest = hashlib.md5(trigram.encode("utf-8")).hexdigest()  # noqa: S324
        idx = int(digest[:8], 16) % EMBEDDING_DIM
        val = (int(digest[8:16], 16) / 0xFFFFFFFF) * 2 - 1  # [-1, 1]
        vec[idx] += val
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tobytes()


def cosine_similarity(a: bytes, b: bytes) -> float:
    """Cosine similarity between two byte-packed float32 vectors."""
    va = np.frombuffer(a, dtype=np.float32)
    vb = np.frombuffer(b, dtype=np.float32)
    dot = float(np.dot(va, vb))
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Skill dataclass
# ---------------------------------------------------------------------------


@dataclass
class Skill:
    """A single evolvable skill stored in the cell_skills table."""

    id: int
    name: str
    trigger_nl: str
    action_sequence: list[str]
    rationale_nl: str
    fitness: float
    success_count: int
    failure_count: int
    use_count: int
    generation: int
    parent_id: int | None
    embedding: bytes
    status: str  # 'active'|'candidate'|'frozen'|'apoptosed'
    created_at: datetime
    last_used_at: datetime | None
    last_decay_check: datetime

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_STATUSES}, got '{self.status}'"
            )
        if not isinstance(self.action_sequence, list):
            raise TypeError("action_sequence must be a list of strings")


# ---------------------------------------------------------------------------
# SkillLibrary
# ---------------------------------------------------------------------------


class SkillLibrary:
    """Evolvable procedure store backed by PostgreSQL.

    Manages the full lifecycle of skills: candidate creation, promotion,
    usage tracking, fitness-weighted semantic recall, age-based decay,
    and capacity enforcement.
    """

    def __init__(self, pool: Any, max_active: int = DEFAULT_MAX_ACTIVE) -> None:
        self._pool = pool
        self._max_active = max_active

    # -- CRUD ---------------------------------------------------------------

    async def add_candidate(
        self,
        name: str,
        trigger_nl: str,
        action_sequence: list[str],
        rationale_nl: str,
        parent_id: int | None = None,
        source: str = "unknown",
    ) -> int:
        """Insert a new candidate skill and return its id."""
        embedding = compute_embedding(trigger_nl + " " + rationale_nl)

        generation = 0
        if parent_id is not None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchval(
                    "SELECT generation FROM cell_skills WHERE id = $1",
                    parent_id,
                )
                if row is not None:
                    generation = row + 1

        async with self._pool.acquire() as conn:
            new_id: int = await conn.fetchval(
                """
                INSERT INTO cell_skills
                    (name, trigger_nl, action_sequence, rationale_nl,
                     fitness, success_count, failure_count, use_count,
                     generation, parent_id, embedding, status, source)
                VALUES ($1, $2, $3::jsonb, $4,
                        0.0, 0, 0, 0,
                        $5, $6, $7, 'candidate', $8)
                RETURNING id
                """,
                name,
                trigger_nl,
                json.dumps(action_sequence),
                rationale_nl,
                generation,
                parent_id,
                embedding,
                source,
            )
        logger.info("Added candidate skill %s (id=%d, gen=%d)", name, new_id, generation)
        return new_id

    async def promote(self, skill_id: int) -> None:
        """Promote a candidate skill to active status."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE cell_skills
                SET status = 'active'
                WHERE id = $1 AND status = 'candidate'
                """,
                skill_id,
            )
        logger.info("Promoted skill %d: %s", skill_id, result)

    async def record_use(self, skill_id: int, success: bool) -> None:
        """Record a skill invocation, updating counters and fitness."""
        async with self._pool.acquire() as conn:
            if success:
                await conn.execute(
                    """
                    UPDATE cell_skills
                    SET success_count = success_count + 1,
                        use_count = use_count + 1,
                        fitness = (success_count + 1 - failure_count)::float
                                  / GREATEST(use_count + 1, 1),
                        last_used_at = NOW()
                    WHERE id = $1
                    """,
                    skill_id,
                )
            else:
                await conn.execute(
                    """
                    UPDATE cell_skills
                    SET failure_count = failure_count + 1,
                        use_count = use_count + 1,
                        fitness = (success_count - (failure_count + 1))::float
                                  / GREATEST(use_count + 1, 1),
                        last_used_at = NOW()
                    WHERE id = $1
                    """,
                    skill_id,
                )
        logger.debug("Recorded %s for skill %d", "success" if success else "failure", skill_id)

    # -- Recall -------------------------------------------------------------

    @staticmethod
    def _situation_to_text(situation: dict[str, Any]) -> str:
        """Flatten a situation dict into searchable text."""
        parts: list[str] = []
        for key, val in sorted(situation.items()):
            parts.append(f"{key}: {val}")
        return " ".join(parts)

    async def recall(self, situation: dict[str, Any], k: int = 3) -> list[Skill]:
        """Retrieve top-k active skills most relevant to the situation.

        Scores each skill by: fitness * (0.5 + 0.5 * max(0, cosine_sim)).
        """
        sit_text = self._situation_to_text(situation)
        sit_emb = compute_embedding(sit_text)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, trigger_nl, action_sequence, rationale_nl,
                       fitness, success_count, failure_count, use_count,
                       generation, parent_id, embedding, status,
                       created_at, last_used_at, last_decay_check
                FROM cell_skills
                WHERE status = 'active'
                ORDER BY fitness DESC
                LIMIT 50
                """
            )

        scored: list[tuple[float, Skill]] = []
        for row in rows:
            action_seq = row["action_sequence"]
            if isinstance(action_seq, str):
                action_seq = json.loads(action_seq)

            skill = Skill(
                id=row["id"],
                name=row["name"],
                trigger_nl=row["trigger_nl"],
                action_sequence=action_seq,
                rationale_nl=row["rationale_nl"],
                fitness=row["fitness"],
                success_count=row["success_count"],
                failure_count=row["failure_count"],
                use_count=row["use_count"],
                generation=row["generation"],
                parent_id=row["parent_id"],
                embedding=row["embedding"],
                status=row["status"],
                created_at=row["created_at"],
                last_used_at=row["last_used_at"],
                last_decay_check=row["last_decay_check"],
            )
            sim = max(0.0, cosine_similarity(sit_emb, skill.embedding))
            score = skill.fitness * (0.5 + 0.5 * sim)
            scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in scored[:k]]

    @staticmethod
    def format_for_prompt(skills: list[Skill]) -> str:
        """Compact text representation of skills for LLM prompts (< 500 chars)."""
        if not skills:
            return ""
        lines: list[str] = []
        for s in skills:
            lines.append(
                f"- {s.name}: {s.trigger_nl} "
                f"[fit={s.fitness:.2f} use={s.use_count} gen={s.generation}]"
            )
        return "\n".join(lines)

    # -- Maintenance --------------------------------------------------------

    async def decay(self) -> int:
        """Apoptose active skills that are stale and low-fitness.

        Criteria: status='active' AND fitness < DECAY_FITNESS_THRESHOLD
        AND (last_used_at is NULL OR older than DECAY_DAYS_THRESHOLD days).

        Returns the number of skills apoptosed.
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"""
                UPDATE cell_skills
                SET status = 'apoptosed',
                    last_decay_check = NOW()
                WHERE status = 'active'
                  AND fitness < {DECAY_FITNESS_THRESHOLD}
                  AND (last_used_at IS NULL
                       OR last_used_at < NOW() - INTERVAL '{DECAY_DAYS_THRESHOLD} days')
                """
            )
        # asyncpg returns "UPDATE N"
        count = int(result.split()[-1])
        logger.info("Decay pass: apoptosed %d skills", count)
        return count

    async def enforce_capacity(self) -> int:
        """Enforce max_active limit by apoptosing lowest-fitness excess.

        Returns the number of skills apoptosed.
        """
        async with self._pool.acquire() as conn:
            active_count: int = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_skills WHERE status = 'active'"
            )
            if active_count <= self._max_active:
                return 0

            excess = active_count - self._max_active
            result = await conn.execute(
                """
                UPDATE cell_skills
                SET status = 'apoptosed'
                WHERE id IN (
                    SELECT id FROM cell_skills
                    WHERE status = 'active'
                    ORDER BY fitness ASC
                    LIMIT $1
                )
                """,
                excess,
            )
        count = int(result.split()[-1])
        logger.info("Capacity enforcement: apoptosed %d skills (was %d, max %d)",
                     count, active_count, self._max_active)
        return count
