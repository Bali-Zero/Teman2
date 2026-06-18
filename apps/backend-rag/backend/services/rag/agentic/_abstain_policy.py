"""
Single source of truth for the RAG brain's evidence-threshold policy.

WHY (Mythos M1 RAG-brain audit, 2026-06-14 — domanda #31)
---------------------------------------------------------
The same ``evidence_score`` was compared against thresholds scattered across
three decision sites that LOOKED like the same concept ("abstain threshold")
but are actually FOUR DISTINCT, deliberately-divergent gates:

  * GENERATION gate   — reasoning.py: should the system PRODUCE regulated
    advice at all? Conservative by design; also drives critical-domain
    STRICT-ABSTAIN. Flat 0.15 (stricter on penalty-bearing tax/legal).
  * LABEL gate        — orchestrator_response.py: how is the final result
    MARKED (``abstain`` flag)? Per-domain (tax 0.10 / visa 0.12 / kbli 0.20),
    the #298 calibration for Indonesian-language retrieval-score skew.
  * CONFIDENCE-LOW    — streaming confidence_zone lower edge (0.15).
  * CONFIDENCE-HIGH   — streaming confidence_zone upper edge (0.60).

A multi-LLM review panel (Gemini synthesis + GPT-5.5 refuter, 2026-06-14)
ruled AGAINST collapsing these into one number: making reasoning.py use the
per-domain value would make the system GENERATE tax advice at evidence 0.11
(0.11 > tax 0.10) where today it correctly SUPPRESSES (0.11 < flat 0.15) —
a safety regression in the highest-penalty domain. The divergence of VALUE
is legitimate; the defect was that it was IMPLICIT, anonymous, and untested.

This module makes the divergence EXPLICIT, NAMED, and TESTABLE without
changing any prod abstain rate: every site computes its threshold from the
SAME ``AbstainPolicy`` object, so the values stay where they are but can no
longer drift silently or be mistaken for a bug.

Verified prod references this mirrors (worktree mythos-m1-rag-brain):
  - reasoning.py:561  -> generation gate uses EvidenceScoreConstants.ABSTAIN_THRESHOLD
  - orchestrator_response.py:90 -> label gate uses get_abstain_threshold(query)
  - orchestrator_streaming_core.py:356-358 -> 0.15 / 0.60 zone edges
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.constants import EvidenceScoreConstants
from backend.services.rag.agentic.reasoning_utils import (
    classify_query_domain,
    get_abstain_threshold,
)


@dataclass(frozen=True)
class AbstainPolicy:
    """The four evidence gates for one query, computed once, named explicitly.

    Frozen: a decision site reads a field, it never recomputes a literal.
    The fields are INTENTIONALLY allowed to differ (generation vs label);
    ``is_divergent`` surfaces when they do, for observability — divergence
    is a signal to inspect, not an error.
    """

    query_domain: str
    #: GENERATION gate — suppress LLM answer / trigger strict-abstain below this.
    generation_threshold: float
    #: LABEL gate — set the final ``abstain`` flag below this (per-domain).
    label_threshold: float
    #: Streaming confidence_zone lower edge (== "abstain" zone below this).
    confidence_low: float
    #: Streaming confidence_zone upper edge ("confident" above this).
    confidence_high: float

    @property
    def is_divergent(self) -> bool:
        """True when the generation gate and the label gate disagree in VALUE.

        Not a bug — by panel ruling tax/kbli are SUPPOSED to differ here.
        Exposed so the orchestrator can emit a metric / log when a given
        query sits in the band where the two gates would decide differently.
        """
        return self.generation_threshold != self.label_threshold

    def generation_abstains(self, evidence_score: float) -> bool:
        """Would the GENERATION gate suppress the answer at this score?"""
        return evidence_score < self.generation_threshold

    def label_abstains(self, evidence_score: float) -> bool:
        """Would the final ABSTAIN flag be set at this score?"""
        return evidence_score < self.label_threshold

    def confidence_zone(self, evidence_score: float, *, trusted: bool) -> str:
        """Streaming confidence zone for this score (mirrors prod literals)."""
        if evidence_score < self.confidence_low:
            return "abstain"
        if evidence_score <= self.confidence_high and not trusted:
            return "cautious"
        return "confident"


def build_abstain_policy(query: str) -> AbstainPolicy:
    """Construct the per-query policy from the existing SSOT sources.

    Pulls the generation/confidence edges from ``EvidenceScoreConstants`` and
    the label threshold from ``get_abstain_threshold`` — i.e. it does NOT
    invent new values, it CENTRALIZES the ones already live so the three
    decision sites can stop hardcoding their own copies.
    """
    return AbstainPolicy(
        query_domain=classify_query_domain(query),
        generation_threshold=EvidenceScoreConstants.ABSTAIN_THRESHOLD,
        label_threshold=get_abstain_threshold(query),
        confidence_low=EvidenceScoreConstants.CONFIDENCE_LOW,
        confidence_high=EvidenceScoreConstants.CONFIDENCE_HIGH,
    )
