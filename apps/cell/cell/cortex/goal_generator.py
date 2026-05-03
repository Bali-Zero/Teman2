"""GoalGenerator — multi-source agenda hub for CELL.

Aggregates signals from four sources (Curiosity, Critic, Dreamer gaps,
decayed Skills) into scored Goals. Tracks pursuit, resolution, and
capacity enforcement. Goals are the bridge between exploration and action.

Sources and their default priorities:
- curiosity: 0.5 — exploratory insights
- critic: 0.8 — calibration failures demand attention
- dreamer_gap: 0.6 — knowledge gaps from consolidation
- skill_decay: 0.7 — decaying skills need attention
- maturity_gap: 0.9 — lifecycle barriers (reserved for AchievementGate)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_PRIORITY: dict[str, float] = {
    "curiosity": 0.5,
    "critic": 0.8,
    "dreamer_gap": 0.6,
    "skill_decay": 0.7,
    "maturity_gap": 0.9,
}

DEFAULT_MAX_ACTIVE = 20
DEDUP_SIMILARITY_THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# Trigram helpers
# ---------------------------------------------------------------------------


def _trigrams(text: str) -> set[str]:
    """Return set of 3-character sliding-window substrings."""
    t = text.lower().strip()
    if len(t) < 3:
        return {t} if t else set()
    return {t[i : i + 3] for i in range(len(t) - 2)}


def _jaccard(a: str, b: str) -> float:
    """Jaccard similarity of trigram sets of two strings."""
    set_a = _trigrams(a)
    set_b = _trigrams(b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Goal dataclass
# ---------------------------------------------------------------------------


@dataclass
class Goal:
    """A single goal in CELL's agenda."""

    id: str
    source: str
    question: str
    motivation: str
    priority: float
    feasibility: float
    novelty: float
    score: float
    status: str  # 'pending'|'investigating'|'resolved'|'abandoned'|'archived'
    findings: str
    related_skill_id: int | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# GoalGenerator
# ---------------------------------------------------------------------------


class GoalGenerator:
    """Multi-source agenda hub that aggregates signals into scored Goals.

    Parameters
    ----------
    pool : asyncpg pool
        Database connection pool.
    ollama_url : str
        Base URL for local Ollama instance.
    ollama_model : str
        Model name for goal reasoning.
    http_client : httpx.AsyncClient | None
        Reusable HTTP client (Golden Rule #10).
    max_active : int
        Maximum number of active (pending + investigating) goals.
    """

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: Any | None = None,
        max_active: int = DEFAULT_MAX_ACTIVE,
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url.rstrip("/")
        self._ollama_model = ollama_model
        self._http_client = http_client
        self._max_active = max_active

    # -- Collect: build goals from signals ----------------------------------

    async def collect(
        self,
        critic_signals: list[Any] | None = None,
        dreamer_gaps: list[str] | None = None,
        curiosity_findings: list[Any] | None = None,
        decayed_skills: list[Any] | None = None,
    ) -> list[Goal]:
        """Aggregate signals from multiple sources into new Goals.

        Deduplicates against existing active goals by Jaccard similarity.
        Scores each goal and persists to cell_goals.

        Returns
        -------
        list[Goal]
            Newly created goals.
        """
        candidates: list[dict[str, Any]] = []

        # --- Curiosity findings ---
        for f in (curiosity_findings or []):
            question = f.question if hasattr(f, "question") else str(f)
            candidates.append({
                "source": "curiosity",
                "question": question,
                "motivation": f.finding if hasattr(f, "finding") else str(f),
                "related_skill_id": None,
            })

        # --- Critic signals (Critique objects with weakness_tag) ---
        for c in (critic_signals or []):
            tag = c.weakness_tag if hasattr(c, "weakness_tag") else str(c)
            if not tag:
                continue
            candidates.append({
                "source": "critic",
                "question": f"How to address weakness: {tag}?",
                "motivation": c.self_critique_nl if hasattr(c, "self_critique_nl") else str(c),
                "related_skill_id": None,
            })

        # --- Dreamer gaps ---
        for gap in (dreamer_gaps or []):
            candidates.append({
                "source": "dreamer_gap",
                "question": f"How to fill knowledge gap: {gap}?",
                "motivation": f"Dream consolidation identified gap: {gap}",
                "related_skill_id": None,
            })

        # --- Decayed skills ---
        for skill in (decayed_skills or []):
            name = skill.name if hasattr(skill, "name") else str(skill)
            skill_id = skill.id if hasattr(skill, "id") else None
            candidates.append({
                "source": "skill_decay",
                "question": f"Should skill '{name}' be revived or replaced?",
                "motivation": f"Skill '{name}' has decayed due to low fitness or disuse.",
                "related_skill_id": skill_id,
            })

        if not candidates:
            return []

        # Fetch existing active goal questions for dedup
        existing_questions = await self._get_active_questions()

        new_goals: list[Goal] = []
        for cand in candidates:
            # Dedup against existing goals
            is_dup = any(
                _jaccard(cand["question"], eq) >= DEDUP_SIMILARITY_THRESHOLD
                for eq in existing_questions
            )
            if is_dup:
                logger.debug("Goal deduped: '%s'", cand["question"][:60])
                continue

            # Score the goal
            priority = _SOURCE_PRIORITY.get(cand["source"], 0.5)
            feasibility = 0.9  # default
            novelty = await self._compute_novelty(cand["question"])
            score = priority * feasibility * novelty

            goal = Goal(
                id=uuid.uuid4().hex[:16],
                source=cand["source"],
                question=cand["question"],
                motivation=cand["motivation"],
                priority=priority,
                feasibility=feasibility,
                novelty=novelty,
                score=score,
                status="pending",
                findings="",
                related_skill_id=cand.get("related_skill_id"),
            )

            # Persist
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO cell_goals
                            (source, question, motivation, priority,
                             feasibility, novelty, score, status,
                             findings, related_skill_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        goal.source,
                        goal.question,
                        goal.motivation,
                        goal.priority,
                        goal.feasibility,
                        goal.novelty,
                        goal.score,
                        goal.status,
                        goal.findings,
                        goal.related_skill_id,
                    )
            except Exception as exc:
                logger.warning("Failed to persist goal: %s", exc)
                continue

            new_goals.append(goal)
            # Also add to existing questions to prevent intra-batch dups
            existing_questions.append(goal.question)

        # Enforce capacity
        await self._enforce_capacity()

        logger.info("GoalGenerator collected %d new goals from %d candidates",
                     len(new_goals), len(candidates))
        return new_goals

    # -- Pursue: work on the next goal -------------------------------------

    async def pursue_next(self, reasoner: Any | None = None) -> Goal | None:
        """Pick the top-score pending goal, investigate it, and mark resolved.

        Parameters
        ----------
        reasoner : optional
            If provided, called as ``await reasoner(goal.question)`` to
            generate findings.

        Returns
        -------
        Goal | None
            The pursued goal, or None if no pending goals exist.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, source, question, motivation, priority,
                       feasibility, novelty, score, status,
                       findings, related_skill_id, created_at, completed_at
                FROM cell_goals
                WHERE status = 'pending'
                ORDER BY score DESC
                LIMIT 1
                """
            )

        if row is None:
            return None

        goal_db_id = row["id"]

        # Mark investigating
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cell_goals SET status = 'investigating' WHERE id = $1",
                goal_db_id,
            )

        # Generate findings
        findings_text = ""
        if reasoner is not None:
            try:
                findings_text = await reasoner(row["question"])
            except Exception as exc:
                logger.warning("Reasoner failed for goal %d: %s", goal_db_id, exc)
                findings_text = f"Reasoner error: {exc}"

        # Mark resolved
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE cell_goals
                SET status = 'resolved', findings = $1, completed_at = NOW()
                WHERE id = $2
                """,
                findings_text,
                goal_db_id,
            )

        goal = Goal(
            id=str(goal_db_id),
            source=row["source"],
            question=row["question"],
            motivation=row["motivation"],
            priority=row["priority"],
            feasibility=row["feasibility"],
            novelty=row["novelty"],
            score=row["score"],
            status="resolved",
            findings=findings_text,
            related_skill_id=row["related_skill_id"],
            created_at=row["created_at"],
            completed_at=datetime.now(timezone.utc),
        )

        logger.info("Pursued goal %d: '%s' => resolved", goal_db_id, row["question"][:60])
        return goal

    # -- List active --------------------------------------------------------

    async def list_active(self) -> list[Goal]:
        """Return top-3 active goals for context injection."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, source, question, motivation, priority,
                       feasibility, novelty, score, status,
                       findings, related_skill_id, created_at, completed_at
                FROM cell_goals
                WHERE status IN ('pending', 'investigating')
                ORDER BY score DESC
                LIMIT 3
                """
            )

        return [
            Goal(
                id=str(row["id"]),
                source=row["source"],
                question=row["question"],
                motivation=row["motivation"],
                priority=row["priority"],
                feasibility=row["feasibility"],
                novelty=row["novelty"],
                score=row["score"],
                status=row["status"],
                findings=row["findings"] or "",
                related_skill_id=row["related_skill_id"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )
            for row in rows
        ]

    # -- Archive old --------------------------------------------------------

    async def archive_old(self) -> int:
        """Archive resolved goals older than 30 days.

        Returns the number of goals archived.
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE cell_goals
                SET status = 'archived'
                WHERE status = 'resolved'
                  AND completed_at < NOW() - INTERVAL '30 days'
                """
            )
        count = int(result.split()[-1])
        if count > 0:
            logger.info("Archived %d old resolved goals", count)
        return count

    # -- Novelty computation ------------------------------------------------

    async def _compute_novelty(self, question: str) -> float:
        """Compute novelty score for a question.

        Returns 1.0 if no similar question exists in the last 30 days,
        0.3 if a similar one exists (Jaccard >= threshold).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT question FROM cell_goals
                WHERE created_at > NOW() - INTERVAL '30 days'
                  AND status != 'archived'
                """
            )

        for row in rows:
            if _jaccard(question, row["question"]) >= DEDUP_SIMILARITY_THRESHOLD:
                return 0.3
        return 1.0

    # -- Capacity enforcement -----------------------------------------------

    async def _enforce_capacity(self) -> int:
        """Archive lowest-score excess goals when over capacity.

        Returns the number of goals archived.
        """
        async with self._pool.acquire() as conn:
            active_count: int = await conn.fetchval(
                """
                SELECT COUNT(*) FROM cell_goals
                WHERE status IN ('pending', 'investigating')
                """
            )

            if active_count <= self._max_active:
                return 0

            excess = active_count - self._max_active
            result = await conn.execute(
                """
                UPDATE cell_goals
                SET status = 'archived'
                WHERE id IN (
                    SELECT id FROM cell_goals
                    WHERE status IN ('pending', 'investigating')
                    ORDER BY score ASC
                    LIMIT $1
                )
                """,
                excess,
            )

        count = int(result.split()[-1])
        if count > 0:
            logger.info(
                "Goal capacity enforcement: archived %d (was %d, max %d)",
                count, active_count, self._max_active,
            )
        return count

    # -- Internal helpers ---------------------------------------------------

    async def _get_active_questions(self) -> list[str]:
        """Fetch question text of all active goals for dedup."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT question FROM cell_goals
                WHERE status IN ('pending', 'investigating')
                """
            )
        return [row["question"] for row in rows]
