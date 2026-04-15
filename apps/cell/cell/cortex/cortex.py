"""Cortex — Phase 3+4 orchestrator.

Thin coordinator that owns 6 components and exposes 4 hooks for PulseEngine.
All hooks are best-effort: if any fail, they log a warning but do NOT block the pulse.
Lifecycle-gated: each component activates only when maturation phase allows.
"""
import logging
from typing import Any

import httpx

from cell.lifecycle.maturation import LifecyclePhase, Maturation
from cell.lifecycle.achievement_gate import AchievementGate
from cell.cortex.skill_library import SkillLibrary
from cell.cortex.critic import CriticAgent
from cell.cortex.curiosity_engine import CuriosityEngine
from cell.cortex.goal_generator import GoalGenerator
from cell.cortex.strategy_mutator import StrategyMutator

logger = logging.getLogger("cell.cortex")

# Phase activation tuples (NEVER use >= on LifecyclePhase, it's alphabetical)
_CRITIC_PHASES = (LifecyclePhase.NEONATO, LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO)
_CURIOSITY_PHASES = (LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO)
_GOALS_PHASES = (LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO)
_MUTATOR_PHASES = (LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO)
_SKILL_USE_PHASES = (LifecyclePhase.NEONATO, LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO)


class Cortex:
    """Phase 3+4 orchestrator with 4 hooks for PulseEngine integration.

    Parameters
    ----------
    pool : asyncpg pool
        Database connection pool.
    reasoner : SlowReasoner
        The reasoning engine (for mutation sandbox).
    episodic : EpisodicMemory
        Episodic memory store.
    self_model : SelfModelManager
        Persistent identity model.
    journal : Journal
        Daily narrative journal.
    attention : AttentionAllocator
        Cognitive budget tracker.
    maturation : Maturation
        Lifecycle phase tracker.
    ollama_client : httpx.AsyncClient | None
        Reusable HTTP client for Ollama calls (Golden Rule #10).
    """

    def __init__(
        self,
        pool: Any,
        reasoner: Any,
        episodic: Any,
        self_model: Any,
        journal: Any,
        attention: Any,
        maturation: Maturation,
        ollama_client: httpx.AsyncClient | None = None,
        ollama_url: str = "http://127.0.0.1:11434",
        ollama_model: str = "qwen3:4b",
    ) -> None:
        self._pool = pool
        self._reasoner = reasoner
        self._episodic = episodic
        self._self_model = self_model
        self._journal = journal
        self._attention = attention
        self._maturation = maturation

        self.skills = SkillLibrary(pool=pool)
        self.critic = CriticAgent(pool=pool, skill_library=self.skills, http_client=ollama_client, ollama_url=ollama_url, ollama_model=ollama_model)
        self.curiosity = CuriosityEngine(pool=pool, http_client=ollama_client, ollama_url=ollama_url, ollama_model=ollama_model)
        self.goals = GoalGenerator(pool=pool, http_client=ollama_client, ollama_url=ollama_url, ollama_model=ollama_model)
        self.mutator = StrategyMutator(pool=pool, library=self.skills, reasoner=reasoner, http_client=ollama_client, ollama_url=ollama_url, ollama_model=ollama_model)
        self.gate = AchievementGate(base=maturation, pool=pool, self_model=self_model)
        logger.info("Cortex initialized: phase=%s", maturation.phase.value)

    async def before_reasoning(self, situation: dict[str, Any]) -> str:
        """Hook 1: recall top-K skills for system prompt augmentation."""
        if self._maturation.phase not in _SKILL_USE_PHASES:
            return ""
        try:
            skills = await self.skills.recall(situation, k=3)
            return self.skills.format_for_prompt(skills)
        except Exception as e:
            logger.warning("Cortex.before_reasoning failed: %s", e)
            return ""

    async def after_action(
        self,
        episode_data: Any,
        proposal: Any,
        action: str | None,
        episode_id: int | None,
        current_pulse: int,
    ) -> None:
        """Hook 2: critic register + evaluate pending expectations."""
        if self._maturation.phase not in _CRITIC_PHASES:
            return
        try:
            if action and action != "none":
                use_llm = self._maturation.phase != LifecyclePhase.NEONATO
                await self.critic.register_expectation(
                    action=action,
                    proposal=proposal,
                    episode_id=episode_id,
                    current_pulse=current_pulse,
                    use_llm=use_llm,
                )
            critiques = await self.critic.evaluate_pending(current_pulse=current_pulse)
            if critiques:
                for c in critiques:
                    if c.weakness_tag:
                        self._self_model.add_weakness(c.weakness_tag)
        except Exception as e:
            logger.warning("Cortex.after_action failed: %s", e)

    async def during_idle(self, state: dict[str, Any]) -> None:
        """Hook 3: curiosity + goal pursuit when stable."""
        phase = self._maturation.phase
        if phase not in _CURIOSITY_PHASES:
            return
        if state.get("stress", 1.0) > 0.3 or state.get("attention_remaining", 0) < 5:
            return
        try:
            allow_mining = phase in (LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO)
            findings = await self.curiosity.explore(
                state,
                attention_budget=int(state.get("attention_remaining", 10)),
                allow_mining=allow_mining,
            )
            actionable = [f for f in findings if f.actionable]
            if actionable and phase in _GOALS_PHASES:
                await self.goals.collect(curiosity_findings=actionable)
            if state.get("attention_remaining", 0) >= 5 and phase in _GOALS_PHASES:
                await self.goals.pursue_next(reasoner=self._reasoner)
        except Exception as e:
            logger.warning("Cortex.during_idle failed: %s", e)

    async def during_sleep(self) -> dict[str, Any]:
        """Hook 4: decay, maturity check, mutation cycle, rollback monitor."""
        summary: dict[str, Any] = {
            "decayed": 0,
            "rollbacks": 0,
            "mutations_proposed": 0,
            "promoted": 0,
            "missing_for_next": [],
            "effective_phase": "unknown",
        }
        try:
            summary["decayed"] = await self.skills.decay()
            await self.skills.enforce_capacity()

            effective, details = await self.gate.effective_phase()
            summary["effective_phase"] = effective.value
            summary["missing_for_next"] = details.get("missing_for_next", [])

            rolled_back = await self.mutator.check_rollbacks()
            summary["rollbacks"] = len(rolled_back)

            # Mutation cycle (adulto/anziano only)
            if self._maturation.phase in _MUTATOR_PHASES:
                max_rate = 1 if self._maturation.phase == LifecyclePhase.ANZIANO else 3
                today_count = await self.mutator.mutations_today()
                remaining = max_rate - today_count
                if remaining > 0:
                    signals = await self._collect_mutation_signals()
                    for signal in signals[:remaining]:
                        proposal = await self.mutator.propose_from_signal(signal, self._reasoner)
                        if proposal:
                            summary["mutations_proposed"] += 1
                            result = await self.mutator.sandbox_test(proposal, self._reasoner, self._episodic)
                            await self.mutator.commit_or_rollback(result)
                            if result.promoted:
                                summary["promoted"] += 1

            critic_tags = await self.critic.detect_weaknesses_for(self._self_model)
            await self.goals.collect(critic_signals=critic_tags)
            await self.goals.archive_old()
        except Exception as e:
            logger.warning("Cortex.during_sleep failed: %s", e, exc_info=True)
        return summary

    async def _collect_mutation_signals(self) -> list[dict[str, Any]]:
        """Build signal list from Critic weaknesses, completed goals, decayed skills."""
        signals: list[dict[str, Any]] = []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT weakness_tag, COUNT(*) as freq
                    FROM cell_critiques
                    WHERE weakness_tag IS NOT NULL AND created_at > NOW() - INTERVAL '7 days'
                    GROUP BY weakness_tag HAVING COUNT(*) >= 3
                    ORDER BY freq DESC LIMIT 3
                """)
                for r in rows:
                    signals.append({
                        "source": "critic_failure",
                        "motivation": f"weakness_tag={r['weakness_tag']}",
                        "parent_skill_id": None,
                        "urgency": float(r["freq"]) / 10.0,
                    })

                rows = await conn.fetch("""
                    SELECT id, question FROM cell_goals
                    WHERE status = 'resolved' AND related_skill_id IS NULL
                      AND completed_at > NOW() - INTERVAL '7 days'
                    ORDER BY score DESC LIMIT 3
                """)
                for r in rows:
                    signals.append({
                        "source": "goal_completion",
                        "motivation": f"goal_id={r['id']}: {r['question'][:80]}",
                        "parent_skill_id": None,
                        "urgency": 0.5,
                    })

                rows = await conn.fetch("""
                    SELECT skill_id, parent_skill_id, reason FROM cell_skill_audit
                    WHERE action = 'apoptosed' AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY created_at DESC LIMIT 3
                """)
                for r in rows:
                    signals.append({
                        "source": "skill_decay",
                        "motivation": f"decayed skill {r['skill_id']}: {r['reason']}",
                        "parent_skill_id": r["parent_skill_id"] or r["skill_id"],
                        "urgency": 0.4,
                    })
        except Exception as e:
            logger.warning("Cortex._collect_mutation_signals failed: %s", e)

        signals.sort(key=lambda s: s.get("urgency", 0), reverse=True)
        return signals[:10]
