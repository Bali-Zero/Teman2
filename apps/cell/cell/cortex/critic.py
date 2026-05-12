"""CriticAgent — Theory-of-Mind self-evaluation loop.

When an action is proposed, register an **Expectation** (predicted outcome).
N pulses later, compare expected vs actual outcome to generate a **Critique**.
If repeated failures are detected (3+), emit a weakness_tag and push it to
the SelfModel.

Updates ``cell_episodes.outcome`` from hardcoded "partial" to the real
observed value, closing the feedback loop from Phase 1+2.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EXPECTED_OUTCOMES = frozenset({"success", "partial", "failure"})
VALID_HEALTH = frozenset({"green", "yellow", "red"})
WEAKNESS_PATTERN_THRESHOLD = 3

# LEVA 2 (2026-05-13): when a weakness_tag accumulates >= this many critiques in
# a rolling SCAR_WINDOW_HOURS, the critic emits a "scar" row to cell_skills so
# the thinker can read it across pulses (loop persistence). Brainstorm
# convergence Gemini 3.1 Pro + DeepSeek V4 Pro:
#   N=10 / 24h: produces 1 scar in practice today (check_health 804 in 7d ~
#               115/day, > 10/24h). alert_human 11 in 7d ~ 1.6/day, < 10/24h.
#   confidence 0.7: below decisional threshold of many routes — penalises
#                   without blinding. Deterministic, NOT adaptive.
SCAR_THRESHOLD_N = 10
SCAR_WINDOW_HOURS = 24
SCAR_CONFIDENCE = 0.7

_OUTCOME_SCORE: dict[str, float] = {
    "success": 1.0,
    "partial": 0.5,
    "failure": 0.0,
}

# Heuristic expectations for each allowlisted action.
# Keys: expected_outcome, expected_rt_delta_ms, expected_health_in_n
_HEURISTIC_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "restart_service": {
        "expected_outcome": "success",
        "expected_rt_delta_ms": -200,
        "expected_health_in_n": "green",
    },
    "scale_up": {
        "expected_outcome": "success",
        "expected_rt_delta_ms": -100,
        "expected_health_in_n": "green",
    },
    "scale_down": {
        "expected_outcome": "partial",
        "expected_rt_delta_ms": 0,
        "expected_health_in_n": "green",
    },
    "read_logs": {
        "expected_outcome": "partial",
        "expected_rt_delta_ms": 0,
        "expected_health_in_n": "yellow",
    },
    "alert_silent": {
        "expected_outcome": "partial",
        "expected_rt_delta_ms": 0,
        "expected_health_in_n": "yellow",
    },
    "alert_human": {
        "expected_outcome": "partial",
        "expected_rt_delta_ms": 0,
        "expected_health_in_n": "yellow",
    },
    "ollama_restart": {
        "expected_outcome": "success",
        "expected_rt_delta_ms": 0,
        "expected_health_in_n": "green",
    },
    "run_backup": {
        "expected_outcome": "success",
        "expected_rt_delta_ms": 0,
        "expected_health_in_n": "green",
    },
    "check_health": {
        "expected_outcome": "partial",
        "expected_rt_delta_ms": 0,
        "expected_health_in_n": "green",
    },
}

_DEFAULT_HEURISTIC: dict[str, Any] = {
    "expected_outcome": "partial",
    "expected_rt_delta_ms": 0,
    "expected_health_in_n": "yellow",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Expectation:
    """A registered prediction about what an action will achieve."""

    id: int
    pulse_number: int
    episode_id: int | None
    action: str
    skill_id: int | None
    expected_outcome: str  # success|partial|failure
    expected_rt_delta_ms: int
    expected_health_in_n: str  # green|yellow|red
    n_pulses_horizon: int  # default 5
    confidence_at_proposal: float
    rationale_nl: str
    critique_id: int | None
    created_at: datetime


@dataclass
class Critique:
    """The result of comparing an expectation to reality."""

    id: int
    expectation_id: int
    pulse_number: int
    actual_outcome: str
    actual_rt_delta_ms: int
    actual_health: str
    miscalibration: float  # 0..1
    self_critique_nl: str
    weakness_tag: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# CriticAgent
# ---------------------------------------------------------------------------


class CriticAgent:
    """Theory-of-Mind loop: register expectations, evaluate outcomes.

    Parameters
    ----------
    pool : asyncpg pool
        Database connection pool.
    skill_library : optional SkillLibrary
        If provided, ``record_use`` is called on evaluation.
    ollama_url : str
        Base URL for local Ollama instance.
    ollama_model : str
        Model name for LLM-enriched expectations.
    http_client : httpx.AsyncClient | None
        Reusable HTTP client (Golden Rule #10).
    """

    def __init__(
        self,
        pool: Any,
        skill_library: Any | None = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._pool = pool
        self._library = skill_library
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

    # -- Register expectation -----------------------------------------------

    async def register_expectation(
        self,
        action: str | None,
        proposal: Any,
        episode_id: int | None,
        current_pulse: int,
        skill_id: int | None = None,
        use_llm: bool = False,
        n_horizon: int = 5,
    ) -> Expectation | None:
        """Register a predicted outcome for *action*.

        Returns ``None`` when there is nothing to predict (action is None or
        ``"none"``).
        """
        if action is None or action == "none":
            return None

        # Extract confidence from proposal (supports dataclass and dict).
        if hasattr(proposal, "confidence"):
            confidence = float(proposal.confidence)
        elif isinstance(proposal, dict):
            confidence = float(proposal.get("confidence", 0.5))
        else:
            confidence = 0.5

        # Build expectation fields.
        exp_fields: dict[str, Any] | None = None
        if use_llm:
            exp_fields = await self._expectation_via_llm(action, proposal)
        if exp_fields is None:
            exp_fields = self._expectation_via_heuristics(action)

        rationale = exp_fields.get("rationale_nl", "")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO cell_critic_expectations
                    (pulse_number, episode_id, action, skill_id,
                     expected_outcome, expected_rt_delta_ms, expected_health_in_n,
                     n_pulses_horizon, confidence_at_proposal, rationale_nl)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id, created_at
                """,
                current_pulse,
                episode_id,
                action,
                skill_id,
                exp_fields["expected_outcome"],
                exp_fields["expected_rt_delta_ms"],
                exp_fields["expected_health_in_n"],
                n_horizon,
                confidence,
                rationale,
            )

        expectation = Expectation(
            id=row["id"],
            pulse_number=current_pulse,
            episode_id=episode_id,
            action=action,
            skill_id=skill_id,
            expected_outcome=exp_fields["expected_outcome"],
            expected_rt_delta_ms=exp_fields["expected_rt_delta_ms"],
            expected_health_in_n=exp_fields["expected_health_in_n"],
            n_pulses_horizon=n_horizon,
            confidence_at_proposal=confidence,
            rationale_nl=rationale,
            critique_id=None,
            created_at=row["created_at"],
        )
        logger.info(
            "Registered expectation %d for '%s' (pulse %d, horizon %d)",
            expectation.id,
            action,
            current_pulse,
            n_horizon,
        )
        return expectation

    # -- Heuristics ---------------------------------------------------------

    def _expectation_via_heuristics(self, action: str) -> dict[str, Any]:
        """Return heuristic expectation fields for *action*."""
        base = _HEURISTIC_EXPECTATIONS.get(action, _DEFAULT_HEURISTIC)
        return {
            "expected_outcome": base["expected_outcome"],
            "expected_rt_delta_ms": base["expected_rt_delta_ms"],
            "expected_health_in_n": base["expected_health_in_n"],
            "rationale_nl": f"heuristic default for {action}",
        }

    # -- LLM enrichment -----------------------------------------------------

    async def _expectation_via_llm(
        self, action: str, proposal: Any
    ) -> dict[str, Any] | None:
        """Ask Ollama for a richer expectation. Returns None on failure."""
        reason = ""
        if hasattr(proposal, "reason"):
            reason = proposal.reason
        elif isinstance(proposal, dict):
            reason = proposal.get("reason", "")

        prompt = (
            f"Action: {action}\nReason: {reason}\n"
            "Predict the outcome as JSON with keys: "
            "expected_outcome (success|partial|failure), "
            "expected_rt_delta_ms (int), "
            "expected_health_in_n (green|yellow|red), "
            "rationale_nl (string). "
            "Respond ONLY with JSON, no markdown."
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
                    "options": {"temperature": 0.2, "num_predict": 80},
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            # PR-D3 (2026-04-30): Ollama small models occasionally wrap JSON
            # in markdown fences ("```json {...} ```") or prefix it ("Here is
            # the JSON: {...}"), causing json.loads(text) to fail and the
            # whole expectation to silently degrade to None. Use the same
            # regex extraction that strategy_mutator.py uses (line ~180):
            # find the outermost {...} block and parse only that.
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if not json_match:
                logger.info(
                    "Critic LLM returned no JSON object for '%s': %s",
                    action,
                    text[:200],
                )
                return None
            parsed = json.loads(json_match.group())

            # Validate required fields.
            outcome = parsed.get("expected_outcome", "")
            health = parsed.get("expected_health_in_n", "")
            if outcome not in VALID_EXPECTED_OUTCOMES:
                return None
            if health not in VALID_HEALTH:
                return None

            return {
                "expected_outcome": outcome,
                "expected_rt_delta_ms": int(parsed.get("expected_rt_delta_ms", 0)),
                "expected_health_in_n": health,
                "rationale_nl": str(parsed.get("rationale_nl", ""))[:500],
            }
        except Exception as exc:
            logger.warning("LLM expectation failed for '%s': %s", action, exc)
            return None

    # -- Evaluate pending expectations --------------------------------------

    async def evaluate_pending(
        self, current_pulse: int, n_horizon: int = 5
    ) -> list[Critique]:
        """Evaluate expectations whose horizon has elapsed.

        Parameters
        ----------
        current_pulse : int
            The current pulse number.
        n_horizon : int
            Not used for filtering (the per-expectation horizon is used
            instead); kept for API compatibility.

        Returns a list of newly created :class:`Critique` objects.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, pulse_number, episode_id, action, skill_id,
                       expected_outcome, expected_rt_delta_ms, expected_health_in_n,
                       n_pulses_horizon, confidence_at_proposal, rationale_nl,
                       critique_id, created_at
                FROM cell_critic_expectations
                WHERE critique_id IS NULL
                  AND pulse_number + n_pulses_horizon <= $1
                ORDER BY pulse_number ASC
                LIMIT 10
                """,
                current_pulse,
            )

        critiques: list[Critique] = []
        for row in rows:
            critique = await self._evaluate_single(dict(row))
            if critique is not None:
                critiques.append(critique)

        if critiques:
            logger.info("Evaluated %d pending expectations at pulse %d", len(critiques), current_pulse)
        return critiques

    # -- Single evaluation --------------------------------------------------

    async def _evaluate_single(self, exp: dict[str, Any]) -> Critique | None:
        """Evaluate a single expectation against actual pulse data."""
        try:
            exp_pulse = exp["pulse_number"]
            horizon = exp["n_pulses_horizon"]
            end_pulse = exp_pulse + horizon

            # Fetch pulse_log rows for the horizon window.
            async with self._pool.acquire() as conn:
                pulse_rows = await conn.fetch(
                    """
                    SELECT health_status, response_time_ms
                    FROM cell_pulse_log
                    WHERE pulse_number > $1 AND pulse_number <= $2
                    ORDER BY pulse_number ASC
                    """,
                    exp_pulse,
                    end_pulse,
                )

            # Compute actual outcome from pulse data.
            if not pulse_rows:
                actual_outcome = "partial"
                actual_rt_delta = 0
                actual_health = "yellow"
            else:
                healths = [r["health_status"] for r in pulse_rows]
                rts = [r["response_time_ms"] for r in pulse_rows]
                avg_rt = sum(rts) / len(rts) if rts else 0

                last_health = healths[-1] if healths else "yellow"
                has_red = "red" in healths

                if last_health == "green" and avg_rt < 50:
                    actual_outcome = "success"
                elif has_red:
                    actual_outcome = "failure"
                else:
                    actual_outcome = "partial"

                actual_rt_delta = int(avg_rt - abs(exp.get("expected_rt_delta_ms", 0)))
                actual_health = last_health

            # Compute miscalibration: |expected_score - actual_score|
            expected_score = _OUTCOME_SCORE.get(exp["expected_outcome"], 0.5)
            actual_score = _OUTCOME_SCORE.get(actual_outcome, 0.5)
            miscalibration = abs(expected_score - actual_score)

            # Generate self-critique text (template, NOT LLM).
            self_critique_nl = (
                f"Expected {exp['expected_outcome']} "
                f"(health={exp['expected_health_in_n']}, "
                f"rt_delta={exp['expected_rt_delta_ms']}ms), "
                f"got {actual_outcome} "
                f"(health={actual_health}, "
                f"rt_delta={actual_rt_delta}ms). "
                f"Miscalibration: {miscalibration:.2f}."
            )

            # Detect weakness: 3+ failures on same action in last 7 days.
            weakness_tag: str | None = None
            action = exp["action"]
            async with self._pool.acquire() as conn:
                failure_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM cell_critiques
                    WHERE actual_outcome = 'failure'
                      AND created_at > NOW() - INTERVAL '7 days'
                      AND expectation_id IN (
                          SELECT id FROM cell_critic_expectations
                          WHERE action = $1
                      )
                    """,
                    action,
                )
            # Include this evaluation if it is also a failure.
            total_failures = (failure_count or 0) + (1 if actual_outcome == "failure" else 0)
            if total_failures >= WEAKNESS_PATTERN_THRESHOLD:
                weakness_tag = f"repeated_failure_{action}"

            # INSERT critique.
            async with self._pool.acquire() as conn:
                crit_row = await conn.fetchrow(
                    """
                    INSERT INTO cell_critiques
                        (expectation_id, pulse_number, actual_outcome,
                         actual_rt_delta_ms, actual_health,
                         miscalibration, self_critique_nl, weakness_tag)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id, created_at
                    """,
                    exp["id"],
                    exp["pulse_number"] + exp["n_pulses_horizon"],
                    actual_outcome,
                    actual_rt_delta,
                    actual_health,
                    miscalibration,
                    self_critique_nl,
                    weakness_tag,
                )

                # UPDATE expectation with critique_id.
                await conn.execute(
                    """
                    UPDATE cell_critic_expectations
                    SET critique_id = $1
                    WHERE id = $2
                    """,
                    crit_row["id"],
                    exp["id"],
                )

                # UPDATE cell_episodes.outcome to real value.
                if exp.get("episode_id") is not None:
                    await conn.execute(
                        """
                        UPDATE cell_episodes
                        SET outcome = $1
                        WHERE id = $2
                        """,
                        actual_outcome,
                        exp["episode_id"],
                    )

            # LEVA 2: emit a scar to cell_skills when weakness_tag recurs.
            # Best-effort, never fail the critique on scar errors.
            if weakness_tag is not None:
                try:
                    await self._maybe_emit_scar(
                        weakness_tag=weakness_tag,
                        action=action,
                        expected_outcome=exp["expected_outcome"],
                        expected_health=exp["expected_health_in_n"],
                        latest_actual_outcome=actual_outcome,
                        latest_actual_health=actual_health,
                    )
                except Exception as exc:
                    logger.warning(
                        "Scar emission failed for weakness %s: %s",
                        weakness_tag,
                        exc,
                    )

            # Record skill use if skill_id is set.
            skill_id = exp.get("skill_id")
            if skill_id is not None and self._library is not None:
                await self._library.record_use(
                    skill_id, success=(actual_outcome == "success")
                )

            critique = Critique(
                id=crit_row["id"],
                expectation_id=exp["id"],
                pulse_number=exp["pulse_number"] + exp["n_pulses_horizon"],
                actual_outcome=actual_outcome,
                actual_rt_delta_ms=actual_rt_delta,
                actual_health=actual_health,
                miscalibration=miscalibration,
                self_critique_nl=self_critique_nl,
                weakness_tag=weakness_tag,
                created_at=crit_row["created_at"],
            )

            logger.debug(
                "Critique %d for exp %d: %s (miscal=%.2f%s)",
                critique.id,
                exp["id"],
                actual_outcome,
                miscalibration,
                f", weakness={weakness_tag}" if weakness_tag else "",
            )
            return critique

        except Exception as exc:
            logger.error("Failed to evaluate expectation %s: %s", exp.get("id"), exc)
            return None

    # -- Scar emission (LEVA 2) ---------------------------------------------

    async def _maybe_emit_scar(
        self,
        weakness_tag: str,
        action: str,
        expected_outcome: str,
        expected_health: str,
        latest_actual_outcome: str,
        latest_actual_health: str,
    ) -> int | None:
        """Insert a scar row in cell_skills when *weakness_tag* recurs.

        Triggered after each critique with a non-null ``weakness_tag``. The scar
        is idempotent across concurrent pulses thanks to the partial UNIQUE
        index ``uq_cell_skills_scar_tag`` (kind='scar'). Returns the inserted
        row id, or ``None`` if the count threshold was not reached or the scar
        already exists.

        Failure modes (broken DB pool, missing migration 172, unique conflict)
        do NOT propagate — the caller logs at WARNING level.
        """
        async with self._pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM cell_critiques
                WHERE weakness_tag = $1
                  AND created_at > NOW() - ($2 || ' hours')::INTERVAL
                """,
                weakness_tag,
                str(SCAR_WINDOW_HOURS),
            )
            if (count or 0) < SCAR_THRESHOLD_N:
                return None

            # Fetch last 5 actual_outcome values for this weakness_tag to give
            # the precondition signature some shape. Best-effort: missing rows
            # are tolerated.
            last_outcomes_rows = await conn.fetch(
                """
                SELECT actual_outcome FROM cell_critiques
                WHERE weakness_tag = $1
                ORDER BY id DESC
                LIMIT 5
                """,
                weakness_tag,
            )
            last_5_actual = [r["actual_outcome"] for r in last_outcomes_rows]
            # Include the current evaluation when the fetch missed it.
            if not last_5_actual or last_5_actual[0] != latest_actual_outcome:
                last_5_actual = [latest_actual_outcome, *last_5_actual][:5]

            precondition = {
                "action": action,
                "expected_outcome": expected_outcome,
                "expected_health": expected_health,
                "last_5_actual_outcomes": last_5_actual,
                "time_span_seconds": SCAR_WINDOW_HOURS * 3600,
            }

            name = f"scar:{weakness_tag}"
            trigger_nl = (
                f"After {SCAR_THRESHOLD_N}+ '{action}' actions in "
                f"{SCAR_WINDOW_HOURS}h where the cell expected "
                f"{expected_outcome}/{expected_health} but observed repeated "
                f"failure (most recent: {latest_actual_outcome}/{latest_actual_health}), "
                f"avoid '{action}' in the same situation."
            )
            rationale = (
                f"Scar emitted by CriticAgent because '{weakness_tag}' "
                f"recurred {count} times within {SCAR_WINDOW_HOURS}h "
                f">= threshold {SCAR_THRESHOLD_N}. "
                f"See migration 172_cell_skills_scar_support.sql."
            )
            # Empty embedding placeholder: scars are matched by precondition
            # JSONB in the thinker (LEVA 4), not by semantic similarity.
            empty_embedding = b""

            row = await conn.fetchrow(
                """
                INSERT INTO cell_skills
                    (name, trigger_nl, action_sequence, rationale_nl,
                     fitness, success_count, failure_count, use_count,
                     generation, parent_id, embedding, status, source,
                     kind, scope, precondition, scar_weakness_tag)
                VALUES
                    ($1, $2, '[]'::jsonb, $3,
                     $4, 0, 0, 0,
                     0, NULL, $5, 'active', 'critic_scar_emission',
                     'scar', 'Personal', $6::jsonb, $7)
                ON CONFLICT (scar_weakness_tag) WHERE kind = 'scar'
                    DO NOTHING
                RETURNING id
                """,
                name,
                trigger_nl,
                rationale,
                SCAR_CONFIDENCE,
                empty_embedding,
                json.dumps(precondition),
                weakness_tag,
            )
            if row is None:
                logger.debug(
                    "Scar %s already exists (idempotent skip)", weakness_tag
                )
                return None
            logger.info(
                "Emitted scar id=%d for weakness %s (recurrence=%d in %dh)",
                row["id"],
                weakness_tag,
                count,
                SCAR_WINDOW_HOURS,
            )
            return int(row["id"])

    # -- Weakness detection -------------------------------------------------

    async def detect_weaknesses_for(self, self_model: Any) -> list[str]:
        """Find recent weakness tags and push them to the SelfModel.

        Parameters
        ----------
        self_model : SelfModelManager
            Must expose ``add_weakness(tag: str)`` method.

        Returns
        -------
        list[str]
            Distinct weakness tags from the last 7 days.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT weakness_tag
                FROM cell_critiques
                WHERE weakness_tag IS NOT NULL
                  AND created_at > NOW() - INTERVAL '7 days'
                """
            )

        tags: list[str] = [row["weakness_tag"] for row in rows]
        for tag in tags:
            self_model.add_weakness(tag)

        if tags:
            logger.info("Detected %d weakness tags, pushed to self-model", len(tags))
        return tags
