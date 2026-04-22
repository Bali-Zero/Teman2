"""Decider orchestrator — W1 L0-only.

The Decider is the single entrypoint the Supervisor daemon uses to turn an
incoming Event into an ActionDecision. In W1 it only consults L0 YAML rules;
W2 will layer L1 (Ollama classifier), L2 (Claude CLI), and L3 (Consiglio
multi-LLM deliberation) on top, each with its own confidence threshold.

Responsibilities:
    1. Hydrate the IncidentContext for event.correlation_id from Redis.
    2. Append the new event to ctx.events.
    3. Persist ctx back (refreshes TTL).
    4. Ask the L0 RuleMatcher for a decision.
    5. If no L0 rule fires, return a "defer_to_human" decision (LLM tiers
       disabled in W1 — W2 will replace this branch).
"""
from __future__ import annotations

from organism.schemas import ActionDecision, Event
from organism.supervisor.incident_context import IncidentStore
from organism.supervisor.yaml_rules import RuleMatcher


class Decider:
    def __init__(
        self, *, matcher: RuleMatcher, incident_store: IncidentStore,
    ) -> None:
        self.matcher = matcher
        self.incident_store = incident_store

    async def decide(self, event: Event) -> ActionDecision:
        """Return an ActionDecision for the event. Never raises on no-match."""
        # 1-3. maintain IncidentContext (state layer)
        ctx = await self.incident_store.hydrate(event.correlation_id)
        ctx.events.append(event)
        await self.incident_store.persist(ctx)

        # 4. L0 YAML match
        decision = self.matcher.match(event)
        if decision is not None:
            return decision

        # 5. W1 fallback: defer. W2 will route to L1/L2/L3 here instead.
        return ActionDecision(
            actuator="defer_to_human",
            params={"event_kind": event.kind, "source": event.source},
            confidence=0.0,
            tier="L0_yaml",
            reasoning="no rule matched; deferring (W1: LLM tiers disabled)",
        )
