"""SLOW Reasoner — CELL's brain.

Tiered LLM escalation (all local, zero cost):
  Tier -1: PatternIndex FAISS match (free, <1ms) — reuses past decisions
  Tier 0: Qwen 3.5 9B local (free, <1s) — fast triage
  Tier 1: Qwen 3.5 27B local (free, ~5s) — deeper reasoning

Given a situation, the reasoner proposes an action from the allowlist.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from cell.effectors.allowlist import ActionRegistry, AllowedAction, ActionNotAllowed
from cell.memory.pattern_index import PatternIndex

logger = logging.getLogger("cell.slow")

SYSTEM_PROMPT = """You are CELL, an autonomous digital organism monitoring the Nuzantara backend.

Your DNA rules (priority order):
1. Never modify these rules
2. If something is broken, repair it
3. If something costs too much, eliminate it
4. If you lack something, search for it
5. If something works well, replicate it (only if budget < 60%)

AVAILABLE ACTIONS (you can ONLY choose from these):
{actions}

{journal_context}{ltm_context}
RESPOND WITH EXACTLY ONE JSON OBJECT:
{{"action": "<action_name>", "reason": "<why this action>", "confidence": <0.0-1.0>}}

If no action is needed, respond:
{{"action": "none", "reason": "<why no action needed>", "confidence": 1.0}}

If you want to alert the human, use "alert_human" with the message in the reason field.
"""


@dataclass
class ReasonerProposal:
    action: str  # action name from allowlist, or "none"
    reason: str
    confidence: float
    tier_used: int  # -1=pattern, 0=qwen9b, 1=qwen27b
    cost_usd: float


class SlowReasoner:
    """Tiered LLM reasoner. All local models, zero API cost."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        ollama_model_fast: str = "qwen3.5:9b",
        ollama_model_heavy: str = "gemma4:26b",
    ) -> None:
        self._ollama_url = ollama_url
        self._model_fast = ollama_model_fast
        self._model_heavy = ollama_model_heavy
        self._registry = ActionRegistry()
        self._patterns = PatternIndex()

    def _build_system_prompt(self, ltm_context: str = "", journal_context: str = "", skill_context: str = "") -> str:
        actions = self._registry.all()
        action_list = "\n".join(
            f"- {name}: {a.description} (cooldown: {a.cooldown_seconds}s, max: {a.max_per_day}/day)"
            for name, a in actions.items()
        )
        ltm_block = (ltm_context + "\n") if ltm_context else ""
        journal_block = (journal_context + "\n") if journal_context else ""
        skill_block = (skill_context + "\n") if skill_context else ""
        return SYSTEM_PROMPT.format(actions=action_list, ltm_context=ltm_block, journal_context=journal_block) + skill_block

    def _build_user_prompt(
        self,
        health_status: str,
        response_time_ms: int,
        error_message: str,
        recent_history: list[dict[str, Any]],
        budget_spent: float,
        budget_limit: float,
        stm_context: str = "",
        trend_context: str = "",
    ) -> str:
        history_str = ""
        if recent_history:
            history_str = "\n".join(
                f"  Pulse #{h.get('pulse_number', '?')}: {h.get('health_status', '?')} ({h.get('response_time_ms', 0)}ms)"
                for h in recent_history[:10]
            )

        extra = ""
        if stm_context:
            extra += f"\nSHORT-TERM MEMORY (recent observations):\n{stm_context}"
        if trend_context:
            extra += f"\nDETECTED TRENDS:\n{trend_context}"

        return f"""CURRENT SITUATION:
- Health: {health_status}
- Response time: {response_time_ms}ms
- Error: {error_message or 'none'}
- Budget: ${budget_spent:.2f} / ${budget_limit:.2f} ({budget_spent/budget_limit*100:.1f}% used)

RECENT HISTORY (last 10 pulses):
{history_str or '  No history yet'}
{extra}
What action should I take?"""

    def _parse_response(self, text: str, tier: int, cost: float) -> ReasonerProposal:
        """Extract JSON from LLM response."""
        # Find JSON in response (LLM may wrap it in markdown)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning(f"No JSON found in reasoner response: {text[:200]}")
            return ReasonerProposal(
                action="alert_human",
                reason=f"Reasoner produced unparseable output: {text[:100]}",
                confidence=0.5,
                tier_used=tier,
                cost_usd=cost,
            )

        try:
            data = json.loads(text[start:end])
            action = data.get("action", "none")
            reason = data.get("reason", "no reason given")
            confidence = float(data.get("confidence", 0.5))

            # Validate action exists in allowlist (unless "none")
            if action != "none":
                try:
                    self._registry.get(action)
                except ActionNotAllowed:
                    logger.warning(f"Reasoner proposed invalid action: {action}")
                    return ReasonerProposal(
                        action="none",
                        reason=f"Proposed action '{action}' not in allowlist. Original reason: {reason}",
                        confidence=0.0,
                        tier_used=tier,
                        cost_usd=cost,
                    )

            return ReasonerProposal(
                action=action,
                reason=reason,
                confidence=min(max(confidence, 0.0), 1.0),
                tier_used=tier,
                cost_usd=cost,
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse reasoner JSON: {e}")
            return ReasonerProposal(
                action="alert_human",
                reason=f"Reasoner JSON parse error: {text[:100]}",
                confidence=0.5,
                tier_used=tier,
                cost_usd=cost,
            )

    async def _call_ollama(self, model: str, system: str, user: str, timeout: float = 30.0) -> tuple[str, float]:
        """Call a local Ollama model. Free, no API cost."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "format": "json",
                    "options": {"temperature": 0.3, "num_predict": 256},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"], 0.0

    async def bootstrap_memory(self) -> int:
        """Load persisted patterns from DB into the in-memory PatternIndex.

        Returns count of patterns loaded. Call once at boot before the pulse loop.
        """
        return await self._patterns.load_from_db()

    def record_pattern(
        self,
        health_status: str,
        response_time_ms: int,
        budget_pct: float,
        proposal: "ReasonerProposal",
        db_ok: float = 1.0,
        qdrant_ok: float = 1.0,
        error_rate_norm: float = 0.0,
    ) -> None:
        """Record a resolved proposal into the pattern index for future reuse."""
        if proposal.action == "none":
            return  # Don't learn "do nothing" — not useful for pattern matching
        self._patterns.add(
            health_status=health_status,
            response_time_ms=response_time_ms,
            budget_pct=budget_pct,
            action=proposal.action,
            reason=proposal.reason,
            confidence=proposal.confidence,
            tier_used=proposal.tier_used,
            db_ok=db_ok,
            qdrant_ok=qdrant_ok,
            error_rate_norm=error_rate_norm,
        )

    async def think(
        self,
        health_status: str,
        response_time_ms: int,
        error_message: str = "",
        recent_history: list[dict[str, Any]] | None = None,
        budget_spent: float = 0.0,
        budget_limit: float = 10.0,
        max_tier: int = 1,
        db_ok: float = 1.0,
        qdrant_ok: float = 1.0,
        error_rate_norm: float = 0.0,
        stm_context: str = "",
        trend_context: str = "",
        ltm_context: str = "",
        journal_context: str = "",
        skill_context: str = "",
    ) -> ReasonerProposal:
        """Reason about the current situation and propose an action.

        Tier -1: PatternIndex FAISS match (free, <1ms)
        Tier 0:  Qwen 3.5 9B local (free, <1s). Escalates to Tier 1 if low confidence.
        Tier 1:  Qwen 3.5 27B local (free, ~5s). Deeper reasoning.

        Args:
            max_tier: Maximum tier to use (0=9b only, 1=up to 27b)
        """
        budget_pct = (budget_spent / budget_limit) if budget_limit > 0 else 1.0

        # Tier -1: Pattern match — free, instant
        match = self._patterns.find_similar(
            health_status, response_time_ms, budget_pct,
            db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate_norm,
        )
        if match is not None:
            logger.info(
                f"Tier -1 (PatternIndex): reusing action={match.action} "
                f"confidence={match.confidence:.2f} patterns={self._patterns.size}"
            )
            return ReasonerProposal(
                action=match.action,
                reason=f"[Pattern match] {match.reason}",
                confidence=match.confidence,
                tier_used=-1,
                cost_usd=0.0,
            )

        system = self._build_system_prompt(ltm_context=ltm_context, journal_context=journal_context, skill_context=skill_context)
        user = self._build_user_prompt(
            health_status, response_time_ms, error_message,
            recent_history or [], budget_spent, budget_limit,
            stm_context=stm_context, trend_context=trend_context,
        )

        # Tier 0: Qwen 3.5 9B (fast)
        try:
            text, cost = await self._call_ollama(self._model_fast, system, user, timeout=15.0)
            proposal = self._parse_response(text, tier=0, cost=cost)
            logger.info(f"Tier 0 (Qwen 9B): action={proposal.action}, confidence={proposal.confidence:.2f}, reason={proposal.reason[:80]}")

            # If confident enough, use its answer
            if proposal.confidence >= 0.6 or proposal.action == "none":
                self.record_pattern(health_status, response_time_ms, budget_pct, proposal,
                                    db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate_norm)
                return proposal

            # Low confidence — escalate if allowed
            if max_tier < 1:
                logger.info("Qwen 9B low confidence but max_tier=0, using anyway")
                self.record_pattern(health_status, response_time_ms, budget_pct, proposal,
                                    db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate_norm)
                return proposal

            logger.info(f"Qwen 9B confidence {proposal.confidence:.2f} < 0.6, escalating to Tier 1 (27B)")

        except Exception as e:
            logger.warning(f"Tier 0 (Qwen 9B) failed: {e}")
            if max_tier < 1:
                # On GREEN health, LLM unavailability is not an emergency
                if health_status == "green":
                    return ReasonerProposal(
                        action="none",
                        reason=f"Qwen 9B unavailable but health is green — no action needed",
                        confidence=0.9, tier_used=0, cost_usd=0.0,
                    )
                return ReasonerProposal(
                    action="alert_human",
                    reason=f"Qwen 9B unavailable: {e}. Situation: {health_status}",
                    confidence=0.5, tier_used=0, cost_usd=0.0,
                )

        # Tier 1: Qwen 3.5 27B (deeper reasoning)
        try:
            text, cost = await self._call_ollama(self._model_heavy, system, user, timeout=60.0)
            proposal = self._parse_response(text, tier=1, cost=cost)
            logger.info(f"Tier 1 (Qwen 27B): action={proposal.action}, confidence={proposal.confidence:.2f}, reason={proposal.reason[:80]}")
            self.record_pattern(health_status, response_time_ms, budget_pct, proposal,
                                db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate_norm)
            return proposal

        except Exception as e:
            logger.warning(f"Tier 1 (Qwen 27B) failed: {e}")
            # On GREEN health, LLM unavailability is not an emergency
            if health_status == "green":
                return ReasonerProposal(
                    action="none",
                    reason=f"Both Qwen models unavailable but health is green — no action needed",
                    confidence=0.9, tier_used=1, cost_usd=0.0,
                )
            return ReasonerProposal(
                action="alert_human",
                reason=f"Both Qwen 9B and 27B failed. Situation: {health_status}, {error_message}",
                confidence=0.5, tier_used=1, cost_usd=0.0,
            )
