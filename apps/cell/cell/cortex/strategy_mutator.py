"""StrategyMutator — controlled evolution with 4-layer safety chain.

Proposes, sandboxes, and commits new skill mutations.  Auto-rollback
monitors promoted skills for 24 h, reverting if fitness regresses below
the parent minus a margin.

Safety chain (all must pass):
  1. Allowlist — every action in the sequence must exist in ActionRegistry
  2. MutationFilter — regex scan for dangerous shell/SQL patterns
  3. DNAInterpreter — budget + cooldown + daily-limit deterministic checks
  4. Constitutional — combined fitness threshold (>= 0.6) from dual-track sandbox

Dual-track sandbox:
  Track A — LLM replay on 8 episodes (2 per emotion cluster)
  Track B — keyword pattern match on 100 recent episode situations
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from cell.core.dna_interpreter import DNAInterpreter
from cell.effectors.allowlist import ActionNotAllowed, ActionRegistry
from cell.fast.mutation_filter import MutationSafety, filter_mutation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SANDBOX_FITNESS_THRESHOLD = 0.6
ROLLBACK_FITNESS_MARGIN = 0.1
MAX_MUTATIONS_PER_DAY = 3

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MutationProposal:
    """A proposed skill mutation before safety checks."""

    parent_skill_id: int | None
    proposed_name: str
    proposed_trigger_nl: str
    proposed_action_sequence: list[str]
    proposed_rationale_nl: str
    motivation: str
    source: str  # "critic_failure" | "goal_completion" | "curiosity_finding" | "skill_decay"


@dataclass
class SandboxResult:
    """Result of dual-track sandbox testing."""

    proposal: MutationProposal
    llm_replay_score: float  # Track A: 0..1
    pattern_match_count: int  # Track B
    pattern_match_rate: float  # = count / 100
    estimated_fitness: float  # 0.7 * llm + 0.3 * pattern_rate
    safety_violations: list[str] = field(default_factory=list)
    dna_check: bool = True
    constitutional_check: bool = True
    promoted: bool = False
    rejected_reason: str | None = None


# ---------------------------------------------------------------------------
# StrategyMutator
# ---------------------------------------------------------------------------


class StrategyMutator:
    """Controlled evolution engine for CELL skills.

    Proposes mutations from signals (critic failures, goal completions,
    curiosity findings, skill decay), validates through a 4-layer safety
    chain, tests in a dual-track sandbox, and monitors promotions for 24 h
    with automatic rollback on fitness regression.
    """

    def __init__(
        self,
        pool: Any,
        library: Any,
        reasoner: Any = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._pool = pool
        self._library = library
        self._reasoner = reasoner
        self._registry = ActionRegistry()
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        self._http_client = http_client
        self._dna = DNAInterpreter()

    # -- HTTP client lifecycle ------------------------------------------------

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # -- Rate limiting --------------------------------------------------------

    async def mutations_today(self) -> int:
        """Count mutations created today."""
        async with self._pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_mutations WHERE created_at::date = CURRENT_DATE"
            )
        return count or 0

    # -- Proposal generation --------------------------------------------------

    async def propose_from_signal(
        self,
        signal: dict[str, Any],
        reasoner: Any = None,
    ) -> MutationProposal | None:
        """Generate a MutationProposal from a signal dict via LLM.

        Signal keys: source, motivation, parent_skill_id (optional),
        parent_skill_context (optional).
        """
        parent_skill_id = signal.get("parent_skill_id")
        parent_context = signal.get("parent_skill_context", "")
        motivation = signal.get("motivation", "unknown")
        source = signal.get("source", "unknown")

        # Build action allowlist for prompt
        all_actions = self._registry.all()
        action_list = ", ".join(sorted(all_actions.keys()))

        prompt = (
            f"You are CELL, proposing a new skill mutation.\n"
            f"ALLOWED ACTIONS: {action_list}\n"
        )
        if parent_context:
            prompt += f"PARENT SKILL: {parent_context}\n"
        prompt += (
            f"MOTIVATION: {motivation}\n"
            f"SOURCE: {source}\n\n"
            f"Respond with EXACTLY one JSON object:\n"
            f'{{"name": "<skill_name>", "trigger": "<when to activate>", '
            f'"actions": ["<action1>", "<action2>"], "rationale": "<why this helps>"}}\n'
        )

        try:
            client = self._get_client()
            resp = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._ollama_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                    "think": False,
                },
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r"\{[^{}]+\}", content, re.DOTALL)
            if not json_match:
                logger.warning("LLM response contained no JSON: %s", content[:200])
                return None

            parsed = json.loads(json_match.group())
            actions = parsed.get("actions", [])
            if not actions or not isinstance(actions, list):
                logger.warning("LLM returned empty or invalid actions list")
                return None

            return MutationProposal(
                parent_skill_id=parent_skill_id,
                proposed_name=parsed.get("name", "unnamed_mutation"),
                proposed_trigger_nl=parsed.get("trigger", ""),
                proposed_action_sequence=actions,
                proposed_rationale_nl=parsed.get("rationale", ""),
                motivation=motivation,
                source=source,
            )
        except Exception as e:
            logger.error("Failed to generate mutation proposal: %s", e)
            return None

    # -- Safety checks --------------------------------------------------------

    def _safety_check(self, proposal: MutationProposal) -> list[str]:
        """Layer 1+2: allowlist + mutation filter regex check.

        Returns list of violation strings (empty = safe).
        """
        violations: list[str] = []

        for action in proposal.proposed_action_sequence:
            # Layer 1: allowlist
            try:
                self._registry.get(action)
            except ActionNotAllowed:
                violations.append(f"allowlist_rejected:{action}")

            # Layer 2: mutation filter regex
            safety = filter_mutation(action)
            if safety == MutationSafety.UNSAFE:
                violations.append(f"mutation_filter_unsafe:{action}")
            elif safety == MutationSafety.REQUIRES_REVIEW:
                violations.append(f"mutation_filter_review:{action}")

        return violations

    # -- Dual-track sandbox ---------------------------------------------------

    async def sandbox_test(
        self,
        proposal: MutationProposal,
        reasoner: Any = None,
        episodic: Any = None,
    ) -> SandboxResult:
        """Run dual-track sandbox test with full safety chain.

        Layers 1-2: allowlist + mutation filter
        Layer 3: DNAInterpreter validation per action
        Track A: LLM replay on 8 clustered episodes
        Track B: keyword pattern match on 100 recent episodes
        Constitutional: combined fitness >= threshold
        """
        # Safety layers 1-2
        violations = self._safety_check(proposal)
        if violations:
            result = SandboxResult(
                proposal=proposal,
                llm_replay_score=0.0,
                pattern_match_count=0,
                pattern_match_rate=0.0,
                estimated_fitness=0.0,
                safety_violations=violations,
                dna_check=False,
                constitutional_check=False,
                promoted=False,
                rejected_reason=f"safety_violation: {', '.join(violations)}",
            )
            await self._write_audit(result)
            return result

        # Safety layer 3: DNA interpreter
        dna_ok = True
        for action in proposal.proposed_action_sequence:
            dna_result = self._dna.validate(
                action_name=action,
                budget_spent=0,
                budget_limit=10,
                confidence=0.7,
            )
            if not dna_result.approved:
                dna_ok = False
                violations.append(f"dna_rejected:{action}:{dna_result.reason}")

        if not dna_ok:
            result = SandboxResult(
                proposal=proposal,
                llm_replay_score=0.0,
                pattern_match_count=0,
                pattern_match_rate=0.0,
                estimated_fitness=0.0,
                safety_violations=violations,
                dna_check=False,
                constitutional_check=False,
                promoted=False,
                rejected_reason=f"dna_check_failed: {', '.join(violations)}",
            )
            await self._write_audit(result)
            return result

        # Track A: LLM replay
        llm_score = await self._track_a_replay(proposal, reasoner, episodic)

        # Track B: pattern match
        match_count, match_rate = await self._track_b_pattern(proposal)

        # Combined fitness
        estimated_fitness = 0.7 * llm_score + 0.3 * match_rate

        # Constitutional check
        constitutional = estimated_fitness >= SANDBOX_FITNESS_THRESHOLD
        promoted = constitutional and len(violations) == 0

        result = SandboxResult(
            proposal=proposal,
            llm_replay_score=llm_score,
            pattern_match_count=match_count,
            pattern_match_rate=match_rate,
            estimated_fitness=estimated_fitness,
            safety_violations=violations,
            dna_check=dna_ok,
            constitutional_check=constitutional,
            promoted=promoted,
            rejected_reason=None if promoted else "fitness_below_threshold",
        )
        await self._write_audit(result)
        return result

    async def _track_a_replay(
        self,
        proposal: MutationProposal,
        reasoner: Any = None,
        episodic: Any = None,
    ) -> float:
        """Track A: LLM replay on 8 episodes sampled by emotion cluster.

        Fetches 100 episodes with real outcomes.  Clusters by emotion
        (calm/alert/stressed/panic), samples 2 per cluster for up to 8.
        Heuristic scoring: if episode was failure AND proposed action differs
        from action_taken -> improvement.  If success AND proposed action
        matches -> improvement.
        """
        if episodic is None:
            return 0.5  # neutral default when no episodic memory available

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT emotion, action_taken, outcome, situation
                       FROM cell_episodes
                       WHERE outcome IS NOT NULL
                       ORDER BY timestamp DESC
                       LIMIT 100"""
                )
        except Exception as e:
            logger.warning("Track A: failed to fetch episodes: %s", e)
            return 0.5

        if not rows:
            return 0.5

        # Cluster by emotion, take 2 per cluster
        clusters: dict[str, list[dict]] = {}
        for row in rows:
            emotion = row["emotion"]
            if emotion not in clusters:
                clusters[emotion] = []
            if len(clusters[emotion]) < 2:
                clusters[emotion].append(dict(row))

        sample = []
        for eps in clusters.values():
            sample.extend(eps)

        if not sample:
            return 0.5

        # Heuristic scoring
        proposed_actions = set(proposal.proposed_action_sequence)
        improvements = 0
        for ep in sample:
            action_taken = ep.get("action_taken", "")
            outcome = ep.get("outcome", "partial")

            if outcome == "failure" and action_taken not in proposed_actions:
                improvements += 1
            elif outcome == "success" and action_taken in proposed_actions:
                improvements += 1

        return improvements / len(sample) if sample else 0.5

    async def _track_b_pattern(
        self,
        proposal: MutationProposal,
    ) -> tuple[int, float]:
        """Track B: keyword match trigger_nl against 100 recent episodes.

        Returns (match_count, match_rate) where rate = count / 100.
        """
        # Extract keywords from trigger_nl (words >= 4 chars, lowered)
        words = re.findall(r"[a-zA-Z]{4,}", proposal.proposed_trigger_nl.lower())
        keywords = set(words)

        if not keywords:
            return 0, 0.0

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT situation FROM cell_episodes
                       ORDER BY timestamp DESC
                       LIMIT 100"""
                )
        except Exception as e:
            logger.warning("Track B: failed to fetch episodes: %s", e)
            return 0, 0.0

        matches = 0
        for row in rows:
            situation = row["situation"]
            if isinstance(situation, str):
                try:
                    situation = json.loads(situation)
                except (json.JSONDecodeError, TypeError):
                    pass

            sit_text = json.dumps(situation).lower() if isinstance(situation, dict) else str(situation).lower()

            if any(kw in sit_text for kw in keywords):
                matches += 1

        rate = matches / 100.0
        return matches, rate

    # -- Audit ----------------------------------------------------------------

    async def _write_audit(self, result: SandboxResult) -> None:
        """Write a cell_skill_audit row for the sandbox result."""
        action = "promoted" if result.promoted else "rejected"
        reason = result.rejected_reason or "sandbox_passed"

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO cell_skill_audit
                       (skill_id, parent_skill_id, action, reason,
                        sandbox_score, pattern_match_rate,
                        safety_violations, dna_check, operator)
                       VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, 'strategy_mutator')""",
                    None,  # skill_id not yet known at audit time
                    result.proposal.parent_skill_id,
                    action,
                    reason,
                    result.estimated_fitness,
                    result.pattern_match_rate,
                    json.dumps(result.safety_violations),
                    result.dna_check,
                )
        except Exception as e:
            logger.error("Failed to write audit: %s", e)

    # -- Commit / Rollback ----------------------------------------------------

    async def commit_or_rollback(self, result: SandboxResult) -> None:
        """Commit a promoted mutation: add candidate, promote, freeze parent, monitor.

        If not promoted, does nothing (audit already written in sandbox_test).
        """
        if not result.promoted:
            return

        proposal = result.proposal

        # Add candidate skill to library
        skill_id = await self._library.add_candidate(
            name=proposal.proposed_name,
            trigger_nl=proposal.proposed_trigger_nl,
            action_sequence=proposal.proposed_action_sequence,
            rationale_nl=proposal.proposed_rationale_nl,
            parent_id=proposal.parent_skill_id,
            source=proposal.source,
        )

        # Promote to active
        await self._library.promote(skill_id)

        # Freeze parent if exists
        parent_fitness = 0.0
        if proposal.parent_skill_id is not None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT fitness FROM cell_skills WHERE id = $1",
                    proposal.parent_skill_id,
                )
                if row:
                    parent_fitness = row["fitness"]
                await conn.execute(
                    "UPDATE cell_skills SET status = 'frozen' WHERE id = $1 AND status = 'active'",
                    proposal.parent_skill_id,
                )

        # Insert mutation record with 24h monitor window
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_mutations
                   (skill_id, parent_skill_id, parent_fitness, monitor_until)
                   VALUES ($1, $2, $3, NOW() + INTERVAL '24 hours')""",
                skill_id,
                proposal.parent_skill_id,
                parent_fitness,
            )

        logger.info(
            "Committed mutation: skill_id=%d, parent=%s, parent_fitness=%.2f",
            skill_id,
            proposal.parent_skill_id,
            parent_fitness,
        )

    async def check_rollbacks(self) -> list[int]:
        """Check pending mutations past their monitor window.

        For each expired monitor:
        - If current fitness < parent_fitness - margin: rollback (apoptose new, restore parent)
        - Otherwise: mark as survived

        Returns list of rolled-back skill IDs.
        """
        rolled_back: list[int] = []

        async with self._pool.acquire() as conn:
            pending = await conn.fetch(
                """SELECT id, skill_id, parent_skill_id, parent_fitness
                   FROM cell_mutations
                   WHERE outcome IS NULL
                     AND monitor_until <= NOW()"""
            )

        for row in pending:
            mutation_id = row["id"]
            skill_id = row["skill_id"]
            parent_skill_id = row["parent_skill_id"]
            parent_fitness = row["parent_fitness"] or 0.0

            # Read current fitness of the new skill
            async with self._pool.acquire() as conn:
                current_fitness = await conn.fetchval(
                    "SELECT fitness FROM cell_skills WHERE id = $1",
                    skill_id,
                )

            current_fitness = current_fitness or 0.0
            threshold = parent_fitness - ROLLBACK_FITNESS_MARGIN

            if current_fitness < threshold:
                # Rollback: apoptose new skill, restore parent
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE cell_skills SET status = 'apoptosed' WHERE id = $1",
                        skill_id,
                    )
                    if parent_skill_id is not None:
                        await conn.execute(
                            "UPDATE cell_skills SET status = 'active' WHERE id = $1",
                            parent_skill_id,
                        )
                    await conn.execute(
                        """UPDATE cell_mutations
                           SET outcome = 'rolled_back',
                               monitored_at = NOW(),
                               final_fitness = $1
                           WHERE id = $2""",
                        current_fitness,
                        mutation_id,
                    )
                    # Audit trail
                    await conn.execute(
                        """INSERT INTO cell_skill_audit
                           (skill_id, parent_skill_id, action, reason,
                            sandbox_score, dna_check, operator)
                           VALUES ($1, $2, 'rolled_back', $3, $4, TRUE, 'strategy_mutator')""",
                        skill_id,
                        parent_skill_id,
                        f"fitness {current_fitness:.2f} < threshold {threshold:.2f}",
                        current_fitness,
                    )

                rolled_back.append(skill_id)
                logger.info(
                    "Rolled back skill %d (fitness %.2f < threshold %.2f)",
                    skill_id,
                    current_fitness,
                    threshold,
                )
            else:
                # Survived
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE cell_mutations
                           SET outcome = 'survived',
                               monitored_at = NOW(),
                               final_fitness = $1
                           WHERE id = $2""",
                        current_fitness,
                        mutation_id,
                    )
                logger.info(
                    "Mutation survived: skill %d (fitness %.2f >= threshold %.2f)",
                    skill_id,
                    current_fitness,
                    threshold,
                )

        return rolled_back
