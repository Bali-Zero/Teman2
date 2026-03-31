"""SLOW Reasoner — CELL's brain.

Tiered LLM escalation:
  Tier -1: PatternIndex FAISS match (free, <1ms) — reuses past decisions
  Tier 0: Qwen 3.5 27B local (free, 1-2s)
  Tier 1: Gemini Flash API (~$0.075/MTok, 2-5s)
  Tier 2: Claude Opus API (~$15/MTok, 5-30s) — only for confirmed critical

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
    tier_used: int  # 0=qwen, 1=gemini, 2=opus
    cost_usd: float


class SlowReasoner:
    """Tiered LLM reasoner. Starts cheap, escalates if needed."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "deepseek-r1:32b",
        gemini_api_key: str = "",
        gemini_model: str = "gemini-2.5-flash",
    ) -> None:
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        self._gemini_key = gemini_api_key
        self._gemini_model = gemini_model
        self._registry = ActionRegistry()
        self._patterns = PatternIndex()

    def _build_system_prompt(self) -> str:
        actions = self._registry.all()
        action_list = "\n".join(
            f"- {name}: {a.description} (cooldown: {a.cooldown_seconds}s, max: {a.max_per_day}/day)"
            for name, a in actions.items()
        )
        return SYSTEM_PROMPT.format(actions=action_list)

    def _build_user_prompt(
        self,
        health_status: str,
        response_time_ms: int,
        error_message: str,
        recent_history: list[dict[str, Any]],
        budget_spent: float,
        budget_limit: float,
    ) -> str:
        history_str = ""
        if recent_history:
            history_str = "\n".join(
                f"  Pulse #{h.get('pulse_number', '?')}: {h.get('health_status', '?')} ({h.get('response_time_ms', 0)}ms)"
                for h in recent_history[:10]
            )

        return f"""CURRENT SITUATION:
- Health: {health_status}
- Response time: {response_time_ms}ms
- Error: {error_message or 'none'}
- Budget: ${budget_spent:.2f} / ${budget_limit:.2f} ({budget_spent/budget_limit*100:.1f}% used)

RECENT HISTORY (last 10 pulses):
{history_str or '  No history yet'}

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

    async def _call_qwen(self, system: str, user: str) -> tuple[str, float]:
        """Tier 0: DeepSeek-R1:32b local via Ollama. Free. (~32s for 256 tokens)"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._ollama_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 256},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"], 0.0  # Free

    async def _call_gemini(self, system: str, user: str) -> tuple[str, float]:
        """Tier 1: Gemini Flash via API. ~$0.075/MTok input."""
        if not self._gemini_key:
            raise ValueError("No Gemini API key configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self._gemini_model}:generateContent",
                params={"key": self._gemini_key},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"parts": [{"text": user}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 256,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Rough cost estimate: ~500 input tokens * $0.075/MTok
            return text, 0.00004

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
    ) -> ReasonerProposal:
        """Reason about the current situation and propose an action.

        Tier -1: PatternIndex FAISS match (free, <1ms)
        Tier 0:  Qwen local. Escalates to Tier 1 (Gemini) if low confidence.

        Args:
            max_tier: Maximum tier to use (0=qwen only, 1=up to gemini, 2=up to opus)
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

        system = self._build_system_prompt()
        user = self._build_user_prompt(
            health_status, response_time_ms, error_message,
            recent_history or [], budget_spent, budget_limit,
        )

        # Tier 0: Qwen local
        try:
            text, cost = await self._call_qwen(system, user)
            proposal = self._parse_response(text, tier=0, cost=cost)
            logger.info(f"Tier 0 (Qwen): action={proposal.action}, confidence={proposal.confidence:.2f}, reason={proposal.reason[:80]}")

            # If Qwen is confident enough, use its answer
            if proposal.confidence >= 0.6 or proposal.action == "none":
                self.record_pattern(health_status, response_time_ms, budget_pct, proposal,
                                    db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate_norm)
                return proposal

            # Low confidence — escalate if allowed
            if max_tier < 1:
                logger.info("Qwen low confidence but max_tier=0, using anyway")
                self.record_pattern(health_status, response_time_ms, budget_pct, proposal,
                                    db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate_norm)
                return proposal

            logger.info(f"Qwen confidence {proposal.confidence:.2f} < 0.6, escalating to Tier 1")

        except Exception as e:
            logger.warning(f"Tier 0 (Qwen) failed: {e}")
            if max_tier < 1:
                return ReasonerProposal(
                    action="alert_human",
                    reason=f"Qwen unavailable: {e}. Cannot reason about: {health_status}",
                    confidence=0.5, tier_used=0, cost_usd=0.0,
                )

        # Tier 1: Gemini Flash
        try:
            text, cost = await self._call_gemini(system, user)
            proposal = self._parse_response(text, tier=1, cost=cost)
            logger.info(f"Tier 1 (Gemini): action={proposal.action}, confidence={proposal.confidence:.2f}, reason={proposal.reason[:80]}")
            self.record_pattern(health_status, response_time_ms, budget_pct, proposal,
                                db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate_norm)
            return proposal

        except Exception as e:
            logger.warning(f"Tier 1 (Gemini) failed: {e}")
            return ReasonerProposal(
                action="alert_human",
                reason=f"Both Qwen and Gemini failed. Situation: {health_status}, {error_message}",
                confidence=0.5, tier_used=1, cost_usd=0.0,
            )
