"""CuriosityEngine — memory exploration via SQL pattern mining + LLM retrospective.

When CELL is stable, the engine explores its own memory through two strategies:
1. **Pattern mining** (cost 1): Execute a whitelisted SQL query on internal tables
   and summarize the results.
2. **Retrospective query** (cost 2): Ask an LLM a natural-language question about
   CELL's recent behaviour, seeded with aggregated data.

NO external actions — only reads from cell_pulse_log, cell_episodes, cell_dreams,
cell_journal, cell_critiques, cell_curiosity_findings, and cell_skills.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — SQL query whitelist (all SELECT, no params, no interpolation)
# ---------------------------------------------------------------------------

_QUERY_POOL: dict[str, str] = {
    "hour_of_day_rt_correlation": """
        SELECT EXTRACT(HOUR FROM created_at)::int AS hour,
               AVG(response_time_ms)::int AS avg_rt,
               COUNT(*) AS cnt
        FROM cell_pulse_log
        WHERE created_at > NOW() - INTERVAL '14 days'
        GROUP BY hour
        ORDER BY hour
    """,
    "emotion_outcome_distribution": """
        SELECT emotion, outcome, COUNT(*) AS cnt
        FROM cell_episodes
        GROUP BY emotion, outcome
        ORDER BY cnt DESC
    """,
    "action_frequency_last_week": """
        SELECT action_taken, COUNT(*) AS cnt
        FROM cell_pulse_log
        WHERE created_at > NOW() - INTERVAL '7 days'
          AND action_taken IS NOT NULL
        GROUP BY action_taken
        ORDER BY cnt DESC
    """,
    "miscalibration_by_action": """
        SELECT ce.action, AVG(cc.miscalibration)::numeric(4,3) AS avg_miscal, COUNT(*) AS cnt
        FROM cell_critiques cc
        JOIN cell_critic_expectations ce ON cc.expectation_id = ce.id
        GROUP BY ce.action
        ORDER BY avg_miscal DESC
    """,
    "dream_gap_frequency": """
        SELECT gap, COUNT(*) AS cnt
        FROM cell_dreams, jsonb_array_elements_text(gaps_identified) AS gap
        GROUP BY gap
        ORDER BY cnt DESC
        LIMIT 20
    """,
    "skill_usage_distribution": """
        SELECT name, use_count, fitness
        FROM cell_skills
        WHERE status = 'active'
        ORDER BY use_count DESC
        LIMIT 20
    """,
    "episode_count_by_day_last_week": """
        SELECT DATE(created_at) AS day, COUNT(*) AS cnt
        FROM cell_episodes
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day
    """,
    "recent_weakness_tags": """
        SELECT weakness_tag, COUNT(*) AS cnt
        FROM cell_critiques
        WHERE weakness_tag IS NOT NULL
          AND created_at > NOW() - INTERVAL '14 days'
        GROUP BY weakness_tag
        ORDER BY cnt DESC
    """,
    "recent_journal_emotions": """
        SELECT emotion_summary, COUNT(*) AS cnt
        FROM cell_journal
        WHERE created_at > NOW() - INTERVAL '14 days'
        GROUP BY emotion_summary
        ORDER BY cnt DESC
    """,
    "action_sequence_frequency": """
        SELECT a1.action_taken AS action_a,
               a2.action_taken AS action_b,
               COUNT(*) AS cnt
        FROM (
            SELECT action_taken,
                   LEAD(action_taken) OVER (ORDER BY pulse_number) AS next_action,
                   pulse_number
            FROM cell_pulse_log
            WHERE action_taken IS NOT NULL
              AND created_at > NOW() - INTERVAL '7 days'
        ) sub
        JOIN cell_pulse_log a1 ON a1.pulse_number = sub.pulse_number
        JOIN cell_pulse_log a2 ON a2.action_taken = sub.next_action
                               AND a2.pulse_number = sub.pulse_number + 1
        WHERE sub.next_action IS NOT NULL
        GROUP BY action_a, action_b
        ORDER BY cnt DESC
        LIMIT 20
    """,
}

# ---------------------------------------------------------------------------
# Natural-language question pool for retrospective queries
# ---------------------------------------------------------------------------

_QUESTION_POOL: list[str] = [
    "What patterns exist between the time of day and my response quality?",
    "Are there actions I repeatedly take that never lead to success?",
    "Which emotions correlate with my best decision-making outcomes?",
    "What are the most common knowledge gaps identified in my dreams?",
    "Am I improving at predicting outcomes over time, or getting worse?",
    "What types of situations cause me the most miscalibration?",
    "Are there action sequences that tend to compound failures?",
    "Which skills am I neglecting despite having them available?",
    "What does my journal reveal about recurring frustrations?",
    "Am I over-relying on any single action to handle diverse problems?",
    "What times of day am I most likely to encounter red health status?",
    "Do my weakness tags cluster around specific subsystems?",
    "How has my action repertoire changed over the past week?",
    "Are there episodes where my confidence was high but outcome was failure?",
    "What is the relationship between my budget usage and outcome quality?",
    "Which dream-identified gaps have I actually addressed versus ignored?",
    "Am I experiencing any cyclical patterns in health degradation?",
    "What would an outside observer say about my most wasteful behaviours?",
    "How does my episode frequency relate to system stability?",
    "If I could change one recurring behaviour, which would have the most impact?",
]

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class CuriosityFinding:
    """A single insight produced by the curiosity engine."""

    id: str
    source: str  # 'pattern_mining' | 'retrospective_query'
    question: str
    method: str
    finding: str
    actionable: bool
    information_gain: float
    related_goal_id: int | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# CuriosityEngine
# ---------------------------------------------------------------------------


class CuriosityEngine:
    """Explores CELL's memory via SQL pattern mining and LLM retrospective queries.

    Parameters
    ----------
    pool : asyncpg pool
        Database connection pool.
    ollama_url : str
        Base URL for local Ollama instance.
    ollama_model : str
        Model name for retrospective queries.
    http_client : httpx.AsyncClient | None
        Reusable HTTP client (Golden Rule #10).
    """

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url.rstrip("/")
        self._ollama_model = ollama_model
        self._http_client = http_client

    # -- Persistent HTTP client (Golden Rule #10) ---------------------------

    def _get_client(self) -> httpx.AsyncClient:
        """Return (or create) a persistent ``httpx.AsyncClient``."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client when shutting down."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    # -- Public API ---------------------------------------------------------

    async def explore(
        self,
        state: dict[str, Any],
        attention_budget: int,
        allow_mining: bool = True,
    ) -> list[CuriosityFinding]:
        """Run curiosity exploration within the given attention budget.

        Parameters
        ----------
        state : dict
            Current CELL state (passed to retrospective queries for context).
        attention_budget : int
            How many budget units to spend. Mining costs 1, retrospective costs 2.
        allow_mining : bool
            If False, skip pattern mining (only retrospective).

        Returns
        -------
        list[CuriosityFinding]
            Findings produced during this exploration round.
        """
        if attention_budget < 1:
            return []

        findings: list[CuriosityFinding] = []
        budget_remaining = attention_budget

        # Strategy 1: pattern mining (cost 1)
        if allow_mining and budget_remaining >= 1:
            finding = await self._pattern_mining()
            if finding is not None:
                findings.append(finding)
                budget_remaining -= 1

        # Strategy 2: retrospective query (cost 2)
        if budget_remaining >= 2:
            finding = await self._retrospective_query(state)
            if finding is not None:
                findings.append(finding)
                budget_remaining -= 2

        return findings

    # -- Query selection ----------------------------------------------------

    async def _select_query(self) -> str | None:
        """Pick a query from the pool not executed in the last 7 days.

        Returns the query key, or None if all have been recently used.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT method FROM cell_curiosity_findings
                WHERE source = 'pattern_mining'
                  AND created_at > NOW() - INTERVAL '7 days'
                """
            )
        recent_methods = {row["method"] for row in rows}

        for key in _QUERY_POOL:
            if key not in recent_methods:
                return key
        return None

    async def _select_question(self) -> str | None:
        """Pick a question not answered in the last 7 days.

        Returns the question text, or None if all have been recently answered.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT question FROM cell_curiosity_findings
                WHERE source = 'retrospective_query'
                  AND created_at > NOW() - INTERVAL '7 days'
                """
            )
        recent_questions = {row["question"] for row in rows}

        for q in _QUESTION_POOL:
            if q not in recent_questions:
                return q
        return None

    # -- Summarize ----------------------------------------------------------

    @staticmethod
    def _summarize_rows(query_name: str, rows: list[dict[str, Any]]) -> str:
        """Top-5 preview of query results as compact JSON."""
        preview = rows[:5]
        # Convert non-serializable types to string
        safe: list[dict[str, Any]] = []
        for row in preview:
            safe_row: dict[str, Any] = {}
            for k, v in row.items():
                if isinstance(v, (datetime,)):
                    safe_row[k] = v.isoformat()
                elif isinstance(v, bytes):
                    safe_row[k] = "<bytes>"
                else:
                    safe_row[k] = v
                    try:
                        json.dumps(v)
                    except (TypeError, ValueError):
                        safe_row[k] = str(v)
            safe.append(safe_row)
        return json.dumps({"query": query_name, "top_5": safe}, default=str)

    # -- Information gain heuristic -----------------------------------------

    @staticmethod
    def _compute_info_gain(rows: list[dict[str, Any]]) -> float:
        """Heuristic information gain: (max-min)/max of first numeric column.

        Returns a value clamped to [0.0, 1.0].
        Returns 0.0 for empty rows or rows with no numeric column.
        """
        if not rows:
            return 0.0

        # Find first numeric column
        first_row = rows[0]
        numeric_key: str | None = None
        for k, v in first_row.items():
            if isinstance(v, (int, float)):
                numeric_key = k
                break

        if numeric_key is None:
            return 0.0

        values = []
        for row in rows:
            val = row.get(numeric_key)
            if isinstance(val, (int, float)):
                values.append(float(val))

        if not values:
            return 0.0

        max_val = max(values)
        min_val = min(values)

        if max_val == 0:
            return 0.0

        gain = (max_val - min_val) / max_val
        return max(0.0, min(1.0, gain))

    # -- Pattern mining -----------------------------------------------------

    async def _pattern_mining(self) -> CuriosityFinding | None:
        """Execute a whitelisted SQL query and build a finding."""
        query_key = await self._select_query()
        if query_key is None:
            logger.debug("All curiosity queries recently used, skipping mining.")
            return None

        sql = _QUERY_POOL[query_key]
        try:
            async with self._pool.acquire() as conn:
                raw_rows = await conn.fetch(sql)
            rows = [dict(r) for r in raw_rows]
        except Exception as exc:
            logger.warning("Curiosity mining query '%s' failed: %s", query_key, exc)
            return None

        summary = self._summarize_rows(query_key, rows)
        info_gain = self._compute_info_gain(rows)
        actionable = info_gain > 0.3 and len(rows) >= 2

        finding = CuriosityFinding(
            id=uuid.uuid4().hex[:16],
            source="pattern_mining",
            question=f"What does {query_key} reveal?",
            method=query_key,
            finding=summary,
            actionable=actionable,
            information_gain=info_gain,
            related_goal_id=None,
        )

        # Persist to cell_curiosity_findings
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO cell_curiosity_findings
                        (source, question, method, finding, actionable, information_gain)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    finding.source,
                    finding.question,
                    finding.method,
                    finding.finding,
                    finding.actionable,
                    finding.information_gain,
                )
        except Exception as exc:
            logger.warning("Failed to persist curiosity finding: %s", exc)

        logger.info(
            "Curiosity mining '%s': %d rows, info_gain=%.2f, actionable=%s",
            query_key, len(rows), info_gain, actionable,
        )
        return finding

    # -- Retrospective query ------------------------------------------------

    async def _retrospective_query(
        self, state: dict[str, Any]
    ) -> CuriosityFinding | None:
        """Ask the LLM a retrospective question about CELL's behaviour."""
        question = await self._select_question()
        if question is None:
            logger.debug("All curiosity questions recently answered, skipping retrospective.")
            return None

        # Build a compact state summary for context
        state_summary = json.dumps(
            {k: v for k, v in state.items() if isinstance(v, (str, int, float, bool))},
            default=str,
        )[:500]

        prompt = (
            f"You are CELL, an autonomous digital organism. "
            f"Current state: {state_summary}\n\n"
            f"Question: {question}\n\n"
            f"Answer concisely in 2-3 sentences based on your self-knowledge."
        )

        try:
            client = self._get_client()
            resp = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._ollama_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.warning("Curiosity retrospective query failed: %s", exc)
            return None

        if not answer:
            return None

        finding = CuriosityFinding(
            id=uuid.uuid4().hex[:16],
            source="retrospective_query",
            question=question,
            method="ollama_retrospective",
            finding=answer,
            actionable=True,
            information_gain=0.5,  # default moderate gain for LLM answers
            related_goal_id=None,
        )

        # Persist
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO cell_curiosity_findings
                        (source, question, method, finding, actionable, information_gain)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    finding.source,
                    finding.question,
                    finding.method,
                    finding.finding,
                    finding.actionable,
                    finding.information_gain,
                )
        except Exception as exc:
            logger.warning("Failed to persist curiosity finding: %s", exc)

        logger.info("Curiosity retrospective: '%s' => %d chars", question, len(answer))
        return finding
