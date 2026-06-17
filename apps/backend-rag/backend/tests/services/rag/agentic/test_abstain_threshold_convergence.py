"""
Contract guard for the RAG brain's evidence-threshold policy (domanda #31).

WHY THIS FILE EXISTS (Mythos M1 RAG-brain audit, 2026-06-14)
------------------------------------------------------------
The same ``evidence_score`` is gated by what LOOKED like one "abstain
threshold" replicated across three sites, but is really FOUR distinct gates:

  * GENERATION gate (reasoning.py)       -> flat 0.15, conservative; also
                                            drives critical-domain STRICT-ABSTAIN.
  * LABEL gate (orchestrator_response.py) -> per-domain (tax 0.10 / kbli 0.20),
                                            the #298 retrieval-score calibration.
  * CONFIDENCE-LOW / HIGH (streaming)     -> 0.15 / 0.60 zone edges.

A multi-LLM panel (Gemini synthesis + GPT-5.5 refuter, 2026-06-14) ruled that
collapsing these to ONE number is a SAFETY REGRESSION: per-domain in
reasoning.py would make the system GENERATE tax advice at evidence 0.11
(> tax 0.10) where today it correctly SUPPRESSES (< flat 0.15). So the
divergence of VALUE is INTENTIONAL. The defect was that it was implicit,
anonymous, and untested.

Therefore this test does NOT assert convergence. It pins:
  (1) the intentional divergence at the boundary cases (so a future dev who
      "tidies" reasoning.py to per-domain BREAKS the suite and is forced to
      read the panel rationale), and
  (2) the ``AbstainPolicy`` SSOT contract: all sites read named fields from
      one object instead of hardcoding their own literal.

Verified prod references (worktree mythos-m1-rag-brain, 2026-06-14):
  - reasoning.py:561  generation gate = EvidenceScoreConstants.ABSTAIN_THRESHOLD
  - reasoning.py:567-577 critical-domain STRICT-ABSTAIN gated by the same value
  - orchestrator_response.py:90-91 label flag = get_abstain_threshold(query)
  - orchestrator_streaming_core.py:356-358 zone edges 0.15 / 0.60
"""

from __future__ import annotations

import pytest

from backend.app.core.constants import EvidenceScoreConstants
from backend.services.rag.agentic._abstain_policy import (
    AbstainPolicy,
    build_abstain_policy,
)
from backend.services.rag.agentic.reasoning_utils import get_abstain_threshold

# ---------------------------------------------------------------------------
# Boundary probes — the two queries that expose the gate divergence.
# ---------------------------------------------------------------------------

# KBLI query, score in (flat 0.15, kbli 0.20): generation gate PASSES,
# label gate ABSTAINS. Generated answer carrying an abstain=True flag.
KBLI_QUERY = "Qual e il codice KBLI per ristorante?"
KBLI_SCORE = 0.18

# TAX query, score in (tax 0.10, flat 0.15): generation gate SUPPRESSES,
# per-domain label gate would NOT. This is the SAFE direction — the panel
# said keeping generation strict on tax (penalty-bearing) is correct.
TAX_QUERY = "Berapa tarif pajak PPN untuk jasa?"
TAX_SCORE = 0.11


class TestAbstainPolicySSOT:
    """The policy object centralizes the four gates without changing values."""

    def test_policy_pulls_values_from_existing_ssot(self):
        pol = build_abstain_policy(TAX_QUERY)
        # generation gate == the flat constant (NOT per-domain) — by design.
        assert pol.generation_threshold == EvidenceScoreConstants.ABSTAIN_THRESHOLD
        # label gate == the per-domain value for this query.
        assert pol.label_threshold == get_abstain_threshold(TAX_QUERY)
        assert pol.label_threshold == pytest.approx(0.10)  # tax
        # confidence edges == the named constants (no new literals invented).
        assert pol.confidence_low == EvidenceScoreConstants.CONFIDENCE_LOW
        assert pol.confidence_high == EvidenceScoreConstants.CONFIDENCE_HIGH

    def test_policy_is_frozen(self):
        pol = build_abstain_policy(KBLI_QUERY)
        with pytest.raises((AttributeError, TypeError)):
            pol.generation_threshold = 0.99  # type: ignore[misc]


class TestIntentionalDivergenceIsPinned:
    """The divergence is a documented contract, not an accident."""

    def test_kbli_018_generation_allows_but_label_abstains(self):
        pol = build_abstain_policy(KBLI_QUERY)
        # 0.18 >= 0.15 -> generation gate does NOT suppress (answer produced)
        assert pol.generation_abstains(KBLI_SCORE) is False
        # 0.18 < 0.20 (kbli) -> final flag IS abstain
        assert pol.label_abstains(KBLI_SCORE) is True
        # stream zone is not the hard "abstain" zone (0.18 >= 0.15)
        assert pol.confidence_zone(KBLI_SCORE, trusted=False) != "abstain"
        # The divergence is SIGNALLED, not hidden.
        assert pol.is_divergent is True

    def test_tax_011_generation_suppresses_safely(self):
        pol = build_abstain_policy(TAX_QUERY)
        # 0.11 < 0.15 -> generation gate SUPPRESSES (the SAFE behavior the
        # panel said to keep: don't generate tax advice on 0.11 evidence).
        assert pol.generation_abstains(TAX_SCORE) is True
        # per-domain label gate alone would NOT abstain (0.11 >= 0.10) — which
        # is exactly why generation must NOT adopt the per-domain value here.
        assert pol.label_abstains(TAX_SCORE) is False
        assert pol.is_divergent is True

    def test_default_domain_has_no_divergence(self):
        # A generic query: per-domain falls back to 0.15 == generation gate,
        # so the two gates agree and is_divergent is False.
        pol = build_abstain_policy("Hello, how are you?")
        assert pol.generation_threshold == pol.label_threshold == pytest.approx(0.15)
        assert pol.is_divergent is False


class TestPanelGuardrail:
    """Tripwire: collapsing generation->per-domain re-introduces the tax risk.

    This is the test the panel asked for — it must FAIL if someone makes the
    generation gate use the per-domain threshold, because that flips tax @
    0.11 from SUPPRESS to GENERATE (the safety regression).
    """

    def test_generation_gate_must_not_become_per_domain_for_tax(self):
        pol = build_abstain_policy(TAX_QUERY)
        # If a future refactor sets generation_threshold = per-domain (0.10),
        # generation_abstains(0.11) would become False. Pin it True.
        assert pol.generation_abstains(TAX_SCORE) is True, (
            "Generation gate must stay STRICTER than the per-domain label "
            "gate on tax. See _abstain_policy.py docstring + the 2026-06-14 "
            "Mythos M1 panel ruling: generating tax advice at 0.11 evidence "
            "is a safety regression."
        )


def test_abstain_policy_type_is_named_contract():
    # Cheap guard that the SSOT object exists and exposes the four named gates
    # (so the three decision sites have something concrete to read from).
    pol = build_abstain_policy(KBLI_QUERY)
    assert isinstance(pol, AbstainPolicy)
    for field in (
        "generation_threshold",
        "label_threshold",
        "confidence_low",
        "confidence_high",
    ):
        assert hasattr(pol, field)


class TestThreeSitesAreWiredToTheSSOT:
    """Static guard: the three decision sites read from build_abstain_policy.

    Source-level assertions (not runtime) so they cannot be dodged by mocking.
    If a future edit re-hardcodes a literal at one of these sites, the wiring
    assertion here breaks — the SSOT stops being the single source.
    """

    import pathlib

    _AGENTIC = (
        pathlib.Path(__file__).resolve().parents[5]
        / "backend"
        / "services"
        / "rag"
        / "agentic"
    )

    def _src(self, name: str) -> str:
        return (self._AGENTIC / name).read_text(encoding="utf-8")

    def test_reasoning_uses_generation_threshold_from_policy(self):
        src = self._src("reasoning.py")
        assert "build_abstain_policy(query).generation_threshold" in src
        # The decision branches must compare against the policy-derived var,
        # not a re-hardcoded constant. Both pipelines (sync + streaming) wired.
        assert src.count("build_abstain_policy(query).generation_threshold") == 2
        assert "evidence_score < generation_threshold" in src

    def test_orchestrator_response_uses_label_threshold_from_policy(self):
        src = self._src("orchestrator_response.py")
        assert "build_abstain_policy(query_str)" in src
        assert "policy.label_threshold" in src
        # The bare get_abstain_threshold call was replaced by the policy.
        assert "abstain_threshold = get_abstain_threshold(" not in src

    def test_streaming_uses_confidence_zone_from_policy(self):
        src = self._src("orchestrator_streaming_core.py")
        assert "build_abstain_policy(" in src
        assert "policy.confidence_zone(" in src
        # The old hardcoded zone literals must be gone from the decision.
        assert "if evidence_score < 0.15:" not in src
        assert "evidence_score <= 0.60 and not trusted" not in src
