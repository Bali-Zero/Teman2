"""TierGatingPolicy — Sprint 3 routing decisions for SEO actions.

The actor does not call into LLMs or review queues directly. Instead, it
asks this policy "where does this proposal go?" and the policy returns a
:class:`RoutingDecision` naming the handler module + whether human or
Zero-specific approval is required.

Four tiers, mirrored verbatim from ``dna.json`` and the v2.1 decision memo:

* ``LOW``      — autonomous, executed via gemini_seo_optimizer.
* ``MED``      — autonomous, fed into the newsroom queue as an article draft.
* ``HIGH``     — queued in ``review_handler`` for Telegram approve/reject SLA.
* ``CRITICAL`` — queued in ``review_handler`` **and** requires Zero explicit
                  approval.

The policy is fail-closed: unknown actions default to ``CRITICAL``, and a
proposal's ``tier_used`` hint can only *tighten* the tier, never loosen it.
Pre-natal phase forbids all routing except the no-op.

This module deliberately imports nothing from any LLM client. The only
cross-app references are module *paths* (strings) handed back to the
actor, which can import them at execution time with its own
environment/settings available.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from cell_core.types import Proposal

from apps.evaluator.seo_cell.phase import SEOPhase

logger = logging.getLogger("seo_cell.tier_gating_policy")

Tier = Literal["LOW", "MED", "HIGH", "CRITICAL"]

TIERS: tuple[Tier, ...] = ("LOW", "MED", "HIGH", "CRITICAL")

_TIER_RANK: dict[Tier, int] = {
    "LOW": 0,
    "MED": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}


class RoutingTarget(str, Enum):
    """Where the actor should send the proposal."""

    NO_OP = "NO_OP"
    DIRECT_APPLY = "DIRECT_APPLY"
    NEWSROOM_QUEUE = "NEWSROOM_QUEUE"
    REVIEW_HANDLER = "REVIEW_HANDLER"
    REFUSED_PRE_NATAL = "REFUSED_PRE_NATAL"


# ── Action → tier table ────────────────────────────────────────────────

# Kept as explicit tables (not regex) so the contract is auditable. Any
# new action must be added here; anything not present is CRITICAL by
# default (fail-closed).

_LOW_ACTIONS: frozenset[str] = frozenset({
    "publish_schema",
    "refresh_meta",
    "fix_canonical",
    "refresh_og_tags",
})

_MED_ACTIONS: frozenset[str] = frozenset({
    "queue_article_draft",
})

_HIGH_ACTIONS: frozenset[str] = frozenset({
    "publish_article",
    "update_published_article",
    "retire_published_article",
})

_CRITICAL_ACTIONS: frozenset[str] = frozenset({
    "remove_page",
    "rewrite_funnel",
    "change_canonical_policy",
    "robots_txt_change",
    "sitemap_policy_change",
})


def infer_tier(action_name: str) -> Tier:
    """Map an action name to its tier. Unknown actions fall through to CRITICAL."""
    if action_name in _LOW_ACTIONS:
        return "LOW"
    if action_name in _MED_ACTIONS:
        return "MED"
    if action_name in _HIGH_ACTIONS:
        return "HIGH"
    if action_name in _CRITICAL_ACTIONS:
        return "CRITICAL"
    logger.warning(
        "[tier_gating] unknown action %r → defaulting to CRITICAL",
        action_name,
    )
    return "CRITICAL"


# ── Decision dataclass ────────────────────────────────────────────────

@dataclass(frozen=True)
class RoutingDecision:
    action: str
    tier: Tier
    target: RoutingTarget
    handler_module: str
    requires_human_approval: bool
    requires_zero_approval: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "tier": self.tier,
            "target": self.target.value,
            "handler_module": self.handler_module,
            "requires_human_approval": self.requires_human_approval,
            "requires_zero_approval": self.requires_zero_approval,
            "reason": self.reason,
        }


# ── Policy class ──────────────────────────────────────────────────────

class TierGatingPolicy:
    """Translate a :class:`Proposal` into a :class:`RoutingDecision`.

    Stateless by design — one instance per cell is plenty but a fresh
    instance per call is also fine.
    """

    # Handler module paths. Strings, not imports — the actor resolves
    # them at execution time with its own env.
    DIRECT_APPLY_HANDLER = (
        "apps.bali_intel_scraper.scripts.gemini_seo_optimizer"
    )
    NEWSROOM_QUEUE_HANDLER = "apps.war_room.queue.newsroom_queue"
    REVIEW_HANDLER_MODULE = "backend.services.review.review_handler"

    def decide(self, proposal: Proposal, *, phase: SEOPhase) -> RoutingDecision:
        action = proposal.action

        # No-op short-circuit — safe in any phase.
        if action == "none":
            return RoutingDecision(
                action=action,
                tier="LOW",
                target=RoutingTarget.NO_OP,
                handler_module="",
                requires_human_approval=False,
                requires_zero_approval=False,
                reason="proposal.action == 'none'",
            )

        # Phase guard — pre_natal refuses everything (except the no-op
        # above, which already returned).
        if phase.pre_natal:
            inferred = infer_tier(action)
            return RoutingDecision(
                action=action,
                tier=inferred,
                target=RoutingTarget.REFUSED_PRE_NATAL,
                handler_module="",
                requires_human_approval=False,
                requires_zero_approval=False,
                reason="pre_natal gate blocks all routing",
            )

        inferred = infer_tier(action)
        hinted = _tier_from_hint(proposal.tier_used)
        # Fail-closed merge: pick the stricter of the two.
        tier: Tier = inferred
        if hinted is not None and _TIER_RANK[hinted] > _TIER_RANK[inferred]:
            tier = hinted
            merge_note = f"hint({hinted})≻inferred({inferred})"
        else:
            merge_note = f"inferred({inferred})"

        if tier == "LOW":
            return RoutingDecision(
                action=action,
                tier=tier,
                target=RoutingTarget.DIRECT_APPLY,
                handler_module=self.DIRECT_APPLY_HANDLER,
                requires_human_approval=False,
                requires_zero_approval=False,
                reason=f"LOW autonomous — {merge_note}",
            )
        if tier == "MED":
            return RoutingDecision(
                action=action,
                tier=tier,
                target=RoutingTarget.NEWSROOM_QUEUE,
                handler_module=self.NEWSROOM_QUEUE_HANDLER,
                requires_human_approval=False,
                requires_zero_approval=False,
                reason=f"MED autonomous → newsroom queue — {merge_note}",
            )
        if tier == "HIGH":
            return RoutingDecision(
                action=action,
                tier=tier,
                target=RoutingTarget.REVIEW_HANDLER,
                handler_module=self.REVIEW_HANDLER_MODULE,
                requires_human_approval=True,
                requires_zero_approval=False,
                reason=f"HIGH → review_handler SLA — {merge_note}",
            )
        # CRITICAL
        return RoutingDecision(
            action=action,
            tier="CRITICAL",
            target=RoutingTarget.REVIEW_HANDLER,
            handler_module=self.REVIEW_HANDLER_MODULE,
            requires_human_approval=True,
            requires_zero_approval=True,
            reason=f"CRITICAL → review_handler + Zero — {merge_note}",
        )


# ── helpers ────────────────────────────────────────────────────────────

def _tier_from_hint(tier_used: int | None) -> Tier | None:
    """Map a numeric tier hint from Proposal.tier_used to a Tier name.

    Convention: 0 and 1 both mean LOW (cell-core sets tier_used=1 on
    "I used tier 1 reasoning", which in SEO-land = autonomous LOW), 2
    = MED, 3 = HIGH, 4 = CRITICAL. Out-of-range values are ignored —
    the inferred tier is the source of truth, the hint can only tighten.
    """
    if tier_used is None:
        return None
    mapping: dict[int, Tier] = {
        0: "LOW",
        1: "LOW",
        2: "MED",
        3: "HIGH",
        4: "CRITICAL",
    }
    return mapping.get(int(tier_used))


__all__ = [
    "RoutingDecision",
    "RoutingTarget",
    "Tier",
    "TIERS",
    "TierGatingPolicy",
    "infer_tier",
]
