"""TierGatingPolicy — Sprint 3 Actor routing.

Decision (dna.json, v2.1 memo):

    LOW       autonomous — schema injection, meta-description refresh,
                            canonical fix (executed via
                            gemini_seo_optimizer.py)
    MED       autonomous → newsroom_queue (new article drafts)
    HIGH      review_handler.py SLA worker (Telegram approve/reject)
    CRITICAL  review_handler.py + mandatory Zero approval

Pre-natal override: regardless of tier, no routing fires while
``SEOPhase.pre_natal`` is True — the policy returns a REFUSED routing.

These tests pin the decision function's signature and output contract
so Sprint 4 can wire it into the actor without reinventing the API.
"""
from __future__ import annotations

import pytest

from cell_core.types import Phase, Proposal

from apps.evaluator.seo_cell.phase import SEOPhase
from apps.evaluator.seo_cell.tier_gating_policy import (
    TIERS,
    RoutingDecision,
    RoutingTarget,
    TierGatingPolicy,
    infer_tier,
)


# ─── fixtures / helpers ─────────────────────────────────────────────────

def _prop(action: str, tier_used: int = 1, confidence: float = 0.8) -> Proposal:
    return Proposal(
        action=action,
        reason="test",
        confidence=confidence,
        tier_used=tier_used,
    )


# ─── infer_tier ─────────────────────────────────────────────────────────

def test_infer_tier_low_for_schema_meta_canonical():
    for action in ("publish_schema", "refresh_meta", "fix_canonical"):
        assert infer_tier(action) == "LOW", action


def test_infer_tier_med_for_queue_article_draft():
    assert infer_tier("queue_article_draft") == "MED"


def test_infer_tier_high_for_publish_article():
    # Publishing a whole article is a content decision requiring human sign-off.
    assert infer_tier("publish_article") == "HIGH"


def test_infer_tier_critical_for_sitewide_changes():
    for action in ("remove_page", "rewrite_funnel", "change_canonical_policy"):
        assert infer_tier(action) == "CRITICAL", action


def test_infer_tier_unknown_defaults_to_critical():
    # Fail-closed: an unknown action is never auto-applied.
    assert infer_tier("yolo_delete_everything") == "CRITICAL"


def test_tiers_constant_has_exactly_four_levels():
    assert TIERS == ("LOW", "MED", "HIGH", "CRITICAL")


# ─── policy.decide: phase guard ────────────────────────────────────────

def test_policy_refuses_in_pre_natal_regardless_of_tier():
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.EMBRIONE, pre_natal=True)
    decision = policy.decide(_prop("publish_schema"), phase=phase)
    assert decision.target == RoutingTarget.REFUSED_PRE_NATAL
    assert decision.tier == "LOW"
    assert decision.requires_human_approval is False


def test_policy_refuses_none_action_cleanly():
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    decision = policy.decide(_prop("none"), phase=phase)
    assert decision.target == RoutingTarget.NO_OP
    assert decision.requires_human_approval is False


# ─── policy.decide: tier routing ───────────────────────────────────────

def test_policy_routes_low_to_direct_apply():
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    decision = policy.decide(_prop("publish_schema"), phase=phase)
    assert decision.target == RoutingTarget.DIRECT_APPLY
    assert decision.tier == "LOW"
    assert decision.requires_human_approval is False
    assert decision.handler_module == "apps.bali_intel_scraper.scripts.gemini_seo_optimizer"


def test_policy_routes_med_to_newsroom_queue():
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    decision = policy.decide(_prop("queue_article_draft"), phase=phase)
    assert decision.target == RoutingTarget.NEWSROOM_QUEUE
    assert decision.tier == "MED"
    assert decision.requires_human_approval is False


def test_policy_routes_high_to_review_handler_sla():
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    decision = policy.decide(_prop("publish_article"), phase=phase)
    assert decision.target == RoutingTarget.REVIEW_HANDLER
    assert decision.tier == "HIGH"
    assert decision.requires_human_approval is True
    assert decision.handler_module == "backend.services.review.review_handler"


def test_policy_routes_critical_to_review_handler_plus_zero():
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    decision = policy.decide(_prop("remove_page"), phase=phase)
    assert decision.target == RoutingTarget.REVIEW_HANDLER
    assert decision.tier == "CRITICAL"
    assert decision.requires_human_approval is True
    assert decision.requires_zero_approval is True
    assert decision.handler_module == "backend.services.review.review_handler"


# ─── review_handler reuse: import-only, no modification ────────────────

def test_policy_points_at_existing_review_handler_file():
    """Guard against a rename on the backend-rag side breaking the
    contract silently.

    We don't importlib-import the module because importing
    ``backend.services.review.review_handler`` pulls backend settings
    which require production env vars (JWT, API keys). Instead, we
    resolve the dotted path to a file on disk and verify that file
    exists and defines a ``ReviewHandler`` class — a deliberately weak
    static check that is nonetheless sufficient to catch a rename.
    """
    from pathlib import Path

    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    decision = policy.decide(_prop("publish_article"), phase=phase)

    repo_root = Path(__file__).resolve().parents[4]
    rel = decision.handler_module.replace(".", "/") + ".py"
    handler_file = repo_root / "apps" / "backend-rag" / rel
    assert handler_file.is_file(), (
        f"review_handler expected at {handler_file} — module path stale?"
    )
    src = handler_file.read_text()
    assert "class ReviewHandler" in src, (
        "ReviewHandler class missing from review_handler module"
    )


# ─── decision contract ─────────────────────────────────────────────────

def test_routing_decision_is_serialisable():
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    decision = policy.decide(_prop("publish_article"), phase=phase)
    d = decision.to_dict()
    assert d["target"] == "REVIEW_HANDLER"
    assert d["tier"] == "HIGH"
    assert d["requires_human_approval"] is True
    assert d["requires_zero_approval"] is False
    assert "publish_article" in d["action"]


def test_policy_explicit_tier_override_is_respected_if_more_restrictive():
    """A proposal can carry a tier_used hint; the policy uses the
    STRICTER of (inferred tier, proposal.tier_used)."""
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    # action infers LOW, but proposal.tier_used=3 (HIGH) — policy must
    # prefer HIGH because stricter.
    prop = Proposal(
        action="publish_schema",
        reason="test",
        confidence=0.9,
        tier_used=3,
    )
    decision = policy.decide(prop, phase=phase)
    assert decision.tier == "HIGH"
    assert decision.target == RoutingTarget.REVIEW_HANDLER


def test_policy_hint_cannot_loosen_tier():
    """If inferred tier is CRITICAL, a hint of LOW (tier_used=0) must
    NOT downgrade to LOW — fail-closed."""
    policy = TierGatingPolicy()
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    prop = Proposal(
        action="remove_page",  # CRITICAL
        reason="test",
        confidence=0.9,
        tier_used=0,  # LOW hint — ignored
    )
    decision = policy.decide(prop, phase=phase)
    assert decision.tier == "CRITICAL"


# ─── no LLM in this path either ────────────────────────────────────────

def test_policy_does_not_pull_llm_modules_on_import():
    import importlib
    import sys
    before = set(sys.modules)
    importlib.import_module("apps.evaluator.seo_cell.tier_gating_policy")
    newly = set(sys.modules) - before
    forbidden = {m for m in newly if "llm" in m.lower() or "openai" in m.lower()
                 or "anthropic" in m.lower() or "ollama" in m.lower()}
    assert not forbidden, f"TierGatingPolicy pulled LLM modules: {forbidden}"
