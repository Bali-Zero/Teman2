"""L3 Consiglio v1 gate — requires 3/4 multi-LLM agreement for irreversible actions.

Called by Decider BEFORE dispatching an irreversible actuator. Consiglio v1
runs a multi-LLM deliberation (Claude + Gemini + DeepSeek + Ollama per
spec §External LLM arsenal) and returns votes. 3/4 agree → proceed. Else
→ defer_to_human (escalate via Telegram).

Only invoked for:
- rollback_deploy (can break prod for real clients)
- propose_yaml_rule (writes new rule to repo → long-lived effect)
- consolidate_redundancy (opens shared-infra PRs → cross-team review required)

For W2 shadow mode: even irreversible decisions go through this gate.
Dispatcher (W1.C) separately enforces HUMAN_ONLY_ACTUATORS blacklist
— the two layers are complementary.
"""
from __future__ import annotations

import logging
from typing import Protocol, Any

from organism.schemas import ActionDecision, Event


log = logging.getLogger(__name__)


IRREVERSIBLE_ACTUATORS = frozenset({
    "rollback_deploy",
    "propose_yaml_rule",
    "consolidate_redundancy",  # W3.C — opens shared-infra PRs, Consiglio gate required
})

REQUIRED_AGREE_VOTES = 3  # out of 4 LLMs


class ConsiglioRunner(Protocol):
    """Protocol any Consiglio-v1-compatible deliberator must satisfy.

    Real implementation lives in apps/evaluator/consiglio/. Gate doesn't
    depend on the concrete module — tests inject a mock runner.
    """
    async def deliberate(self, prompt: str) -> dict[str, Any]:
        """Returns {'votes': [{'agree': bool, 'rationale': str, 'llm': str}, ...], 'consensus': bool}"""
        ...


class ConsiglioGate:
    def __init__(self, *, runner: ConsiglioRunner):
        self.runner = runner

    @staticmethod
    def is_irreversible(decision: ActionDecision) -> bool:
        return decision.actuator in IRREVERSIBLE_ACTUATORS

    async def approve(
        self, event: Event, proposed: ActionDecision,
    ) -> ActionDecision:
        """Gate proposed irreversible decision through Consiglio deliberation.

        If proposed actuator is NOT in IRREVERSIBLE_ACTUATORS, pass-through
        unchanged (caller should not invoke this gate for reversible actions,
        but we guard defensively).
        """
        if not self.is_irreversible(proposed):
            log.info(
                "consiglio_gate: actuator=%s not irreversible, pass-through",
                proposed.actuator,
            )
            return proposed

        prompt = self._build_prompt(event, proposed)
        try:
            result = await self.runner.deliberate(prompt)
        except Exception as exc:
            log.warning("consiglio_gate: runner failed: %s", exc)
            return ActionDecision(
                actuator="defer_to_human",
                params={
                    "reason": "consiglio_runner_error",
                    "proposed": proposed.model_dump(mode="json"),
                    "error": str(exc)[:300],
                },
                confidence=0.0,
                tier="L3_consiglio",
                reasoning=f"consiglio runner error: {exc}",
            )

        votes = result.get("votes", []) if isinstance(result, dict) else []
        agree_count = sum(1 for v in votes if v.get("agree") is True)
        total = len(votes)

        if not votes:
            log.warning(
                "consiglio_gate: runner returned no votes — treating as dissent "
                "(proposed actuator=%s, correlation=%s)",
                proposed.actuator, event.correlation_id,
            )

        if agree_count >= REQUIRED_AGREE_VOTES:
            # Proposal approved. Preserve the proposed decision but re-tag tier.
            return ActionDecision(
                actuator=proposed.actuator,
                params=proposed.params,
                confidence=proposed.confidence,
                tier="L3_consiglio",
                reasoning=(
                    f"consiglio {agree_count}/{total} agree — "
                    f"{proposed.reasoning or 'no proposed reasoning'}"
                ),
            )

        # Dissent: escalate to human
        return ActionDecision(
            actuator="defer_to_human",
            params={
                "reason": "consiglio_dissent",
                "proposed": proposed.model_dump(mode="json"),
                "consiglio_result": result,
            },
            confidence=0.0,
            tier="L3_consiglio",
            reasoning=(
                f"consiglio dissent: only {agree_count}/{total} agree "
                f"(required {REQUIRED_AGREE_VOTES})"
            ),
        )

    def _build_prompt(self, event: Event, proposed: ActionDecision) -> str:
        return (
            f"Event: {event.kind} on source {event.source} "
            f"(severity {event.severity.value}, host {event.host}).\n"
            f"Proposed irreversible action: {proposed.actuator}\n"
            f"Params: {proposed.params}\n"
            f"Proposer confidence: {proposed.confidence}\n"
            f"Proposer reasoning: {proposed.reasoning or '(none)'}\n\n"
            f"Vote agree/disagree with a one-sentence rationale."
        )
