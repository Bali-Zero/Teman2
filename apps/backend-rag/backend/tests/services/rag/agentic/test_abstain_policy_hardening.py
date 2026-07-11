"""
Hardening suite for the evidence-threshold policy (domanda #31 close-out).

Complements ``test_abstain_threshold_convergence.py`` (which pins the SSOT
contract and the panel-ruled divergence). This file adds what the 2026-07-05
abstain-SSOT mandate asked for and #1414 did not cover:

  1. GOLDEN MATRIX — explicit literal expectations for every gate at the
     EXACT boundaries (==0.10 tax, ==0.12 visa, ==0.15 flat, ==0.20 kbli,
     ==0.60 zone edge). Boundary semantics differ by edge and are pinned
     as prod implements them: the abstain/label gates and the zone LOW edge
     are strict ``<`` (score == threshold PASSES the gate), while the zone
     HIGH edge is ``<=`` (score == 0.60 is still "cautious" for untrusted).
     The expectations are hardcoded literals (golden), never recomputed from
     the code under test: the matrix was green on the pre-change tree and
     must stay green after any refactor of the policy plumbing — same input,
     same abstain/cautious/confident decision, forever (or the diff is a
     behavior change, not a refactor).
  2. LABEL-GATE END-TO-END — ``OrchestratorResponseBuilder.build_core_result``
     abstain flag + ``abstain_reason`` bucketing (the previous test file for
     that module was an auto-generated skeleton with 4 skips).
  3. ENV-OVERRIDE RANGE GUARD — ``DOMAIN_ABSTAIN_THRESHOLDS`` entries outside
     [0.0, 1.0] (including nan/inf) are skipped with a warning instead of
     silently disabling (negative) or forcing (>1) abstain for a whole domain.
  4. FIFTH GATE NAMING — reasoning.py's context-quality minimum reads the
     named ``CONTEXT_QUALITY_MIN`` from the policy module instead of a bare
     ``EvidenceScoreConstants.ABSTAIN_THRESHOLD`` (same value, named source).
"""

from __future__ import annotations

import math
import pathlib
from types import SimpleNamespace

import pytest

import backend.services.rag.agentic.reasoning_utils as reasoning_utils_mod
from backend.app.core.constants import EvidenceScoreConstants
from backend.services.rag.agentic._abstain_policy import build_abstain_policy
from backend.services.rag.agentic.orchestrator_response import (
    OrchestratorResponseBuilder,
)
from backend.services.rag.agentic.reasoning_utils import (
    _parse_domain_threshold_overrides,
    classify_query_domain,
    get_abstain_threshold,
)
from backend.services.tools.definitions import AgentState

# ---------------------------------------------------------------------------
# Domain fixture queries. Each MUST route to its intended domain — asserted
# inside the golden test so classifier drift cannot silently retarget the
# matrix at the wrong thresholds.
# ---------------------------------------------------------------------------
QUERIES: dict[str, str] = {
    "tax": "Berapa tarif pajak PPN untuk jasa?",
    "visa": "Come rinnovo il mio KITAS?",
    "kbli": "Qual e il codice KBLI per ristorante?",
    "pricing": "Quanto costa aprire una PT PMA?",
    "default": "Hello, how are you today?",
}


# ---------------------------------------------------------------------------
# 1. GOLDEN MATRIX — (domain, score) -> (generation_abstains, label_abstains,
#    confidence_zone with trusted=False). Literals only.
#    Thresholds under test: generation flat 0.15 · label tax 0.10 / visa 0.12 /
#    kbli 0.20 / pricing 0.15 / default 0.15 · zone edges 0.15 / 0.60.
# ---------------------------------------------------------------------------
GOLDEN_MATRIX: list[tuple[str, float, bool, bool, str]] = [
    # --- tax: label 0.10 < generation 0.15 (panel-ruled divergence) ---
    ("tax", 0.00, True, True, "abstain"),
    ("tax", 0.09, True, True, "abstain"),
    ("tax", 0.10, True, False, "abstain"),  # == label threshold -> label passes
    ("tax", 0.11, True, False, "abstain"),  # the panel's canonical case
    ("tax", 0.15, False, False, "cautious"),  # == generation & zone-low edge
    ("tax", 0.60, False, False, "cautious"),  # == zone-high edge
    ("tax", 0.61, False, False, "confident"),
    # --- visa: label 0.12 ---
    ("visa", 0.11, True, True, "abstain"),
    ("visa", 0.12, True, False, "abstain"),  # == label threshold
    ("visa", 0.15, False, False, "cautious"),
    # --- kbli: label 0.20 > generation 0.15 (opposite divergence sign) ---
    ("kbli", 0.14, True, True, "abstain"),
    ("kbli", 0.15, False, True, "cautious"),  # divergence band lower edge
    ("kbli", 0.19, False, True, "cautious"),  # divergence band upper interior
    ("kbli", 0.20, False, False, "cautious"),  # == label threshold
    # --- pricing: label 0.15 == generation (no divergence) ---
    ("pricing", 0.14, True, True, "abstain"),
    ("pricing", 0.15, False, False, "cautious"),
    # --- default: label 0.15 == generation (no divergence) ---
    ("default", 0.14, True, True, "abstain"),
    ("default", 0.15, False, False, "cautious"),
    ("default", 1.00, False, False, "confident"),
]


class TestGoldenMatrix:
    @pytest.mark.parametrize(
        ("domain", "score", "gen_abstains", "label_abstains", "zone"),
        GOLDEN_MATRIX,
        ids=[f"{d}-{s:.2f}" for d, s, *_ in GOLDEN_MATRIX],
    )
    def test_golden_decision(
        self,
        domain: str,
        score: float,
        gen_abstains: bool,
        label_abstains: bool,
        zone: str,
    ) -> None:
        query = QUERIES[domain]
        # Guard: the fixture query really routes to the intended domain.
        assert classify_query_domain(query) == domain
        pol = build_abstain_policy(query)
        assert pol.generation_abstains(score) is gen_abstains
        assert pol.label_abstains(score) is label_abstains
        assert pol.confidence_zone(score, trusted=False) == zone

    def test_trusted_skips_cautious_but_not_abstain(self) -> None:
        pol = build_abstain_policy(QUERIES["default"])
        # Below the low edge, trusted tools do NOT rescue the answer.
        assert pol.confidence_zone(0.10, trusted=True) == "abstain"
        # Inside the cautious band, trusted flips the zone to confident.
        assert pol.confidence_zone(0.30, trusted=True) == "confident"
        assert pol.confidence_zone(0.30, trusted=False) == "cautious"
        # At the high edge (== 0.60) trusted is confident, untrusted cautious.
        assert pol.confidence_zone(0.60, trusted=True) == "confident"

    def test_empty_query_falls_back_to_default_domain(self) -> None:
        pol = build_abstain_policy("")
        assert pol.query_domain == "default"
        assert pol.label_threshold == pytest.approx(0.15)
        assert pol.is_divergent is False


# ---------------------------------------------------------------------------
# 2. LABEL-GATE END-TO-END — build_core_result abstain flag + reason buckets.
# ---------------------------------------------------------------------------
_TOKENS = SimpleNamespace(prompt_tokens=0, completion_tokens=0, total_tokens=0, cost_usd=0.0)


def _core_result(query: str, evidence_score: float | None):
    state = AgentState(query=query, final_answer="stub answer")
    state.evidence_score = evidence_score
    return OrchestratorResponseBuilder().build_core_result(
        state=state,
        sources=[],
        extracted_entities={},
        model_used="test-model",
        token_usage=_TOKENS,
        timings={},
        start_time=0.0,
    )


class TestLabelGateEndToEnd:
    def test_score_below_005_is_no_relevant_context(self) -> None:
        result = _core_result(QUERIES["tax"], 0.03)
        assert result.abstain is True
        assert result.abstain_reason == "no_relevant_context"

    def test_score_below_flat_threshold_is_low_confidence(self) -> None:
        result = _core_result(QUERIES["tax"], 0.08)  # < tax 0.10 and < 0.15
        assert result.abstain is True
        assert result.abstain_reason == "low_confidence"

    def test_kbli_divergence_band_is_below_domain_threshold(self) -> None:
        # 0.18 passes the flat 0.15 but fails the kbli 0.20 label gate.
        result = _core_result(QUERIES["kbli"], 0.18)
        assert result.abstain is True
        assert result.abstain_reason == "below_domain_threshold"

    def test_kbli_above_domain_threshold_answers(self) -> None:
        result = _core_result(QUERIES["kbli"], 0.25)
        assert result.abstain is False
        assert result.abstain_reason is None

    def test_tax_divergence_band_label_does_not_abstain(self) -> None:
        # 0.12 >= tax 0.10: the LABEL gate passes. (The GENERATION gate would
        # have suppressed upstream at < 0.15 — panel-ruled, pinned in the
        # convergence suite. This asserts the label side of that contract.)
        result = _core_result(QUERIES["tax"], 0.12)
        assert result.abstain is False
        assert result.abstain_reason is None

    def test_none_evidence_score_abstains_as_zero(self) -> None:
        result = _core_result(QUERIES["default"], None)
        assert result.abstain is True
        assert result.abstain_reason == "no_relevant_context"
        assert result.evidence_score == 0.0


# ---------------------------------------------------------------------------
# 3. ENV-OVERRIDE RANGE GUARD — out-of-range entries must be skipped, valid
#    siblings in the same spec kept. (0.0 and 1.0 stay valid — inclusive
#    bounds, pinned by test_reasoning_utils.py.)
# ---------------------------------------------------------------------------
class TestEnvOverrideRangeGuard:
    def test_negative_value_is_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            assert _parse_domain_threshold_overrides("tax:-0.5") == {}
        assert "out-of-range" in caplog.text

    def test_value_above_one_is_skipped(self) -> None:
        assert _parse_domain_threshold_overrides("kbli:7") == {}

    def test_nan_is_skipped(self) -> None:
        assert _parse_domain_threshold_overrides("tax:nan") == {}

    def test_inf_is_skipped(self) -> None:
        assert _parse_domain_threshold_overrides("visa:inf") == {}

    def test_mixed_spec_keeps_only_in_range_entries(self) -> None:
        parsed = _parse_domain_threshold_overrides("tax:0.08,kbli:9,visa:0.5")
        assert parsed == {"tax": pytest.approx(0.08), "visa": pytest.approx(0.5)}

    def test_out_of_range_override_leaves_default_live(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A hostile/typo'd env value must NOT disable the tax abstain gate.
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "tax:-1")
        monkeypatch.setattr(
            reasoning_utils_mod,
            "_DOMAIN_THRESHOLDS",
            reasoning_utils_mod._build_domain_thresholds(),
        )
        assert get_abstain_threshold(QUERIES["tax"]) == pytest.approx(0.10)

    def test_unknown_domain_key_is_harmless(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Keys the classifier never emits are merged but unreachable — they
        # must not perturb lookups for real domains.
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "legal:0.5")
        monkeypatch.setattr(
            reasoning_utils_mod,
            "_DOMAIN_THRESHOLDS",
            reasoning_utils_mod._build_domain_thresholds(),
        )
        assert get_abstain_threshold(QUERIES["tax"]) == pytest.approx(0.10)
        assert get_abstain_threshold(QUERIES["default"]) == pytest.approx(0.15)

    def test_defaults_themselves_are_in_range(self) -> None:
        # The guard's own precondition: shipped defaults all sit in [0, 1].
        for domain, value in reasoning_utils_mod.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT.items():
            assert 0.0 <= value <= 1.0, domain
            assert math.isfinite(value), domain


# ---------------------------------------------------------------------------
# 4. FIFTH GATE NAMING — the context-quality minimum is a named policy value.
# ---------------------------------------------------------------------------
_AGENTIC = pathlib.Path(__file__).resolve().parents[5] / "backend" / "services" / "rag" / "agentic"


class TestContextQualityGateNamed:
    def test_named_constant_equals_flat_threshold(self) -> None:
        # Import inside the test: pre-migration trees lack the symbol and the
        # rest of this suite must still run.
        from backend.services.rag.agentic._abstain_policy import (
            CONTEXT_QUALITY_MIN,
        )

        assert CONTEXT_QUALITY_MIN == EvidenceScoreConstants.ABSTAIN_THRESHOLD
        assert CONTEXT_QUALITY_MIN == pytest.approx(0.15)

    def test_reasoning_has_no_bare_abstain_threshold_read(self) -> None:
        src = (_AGENTIC / "reasoning.py").read_text(encoding="utf-8")
        # Every ABSTAIN_THRESHOLD read in reasoning.py flows through the
        # policy module (build_abstain_policy / CONTEXT_QUALITY_MIN) — a bare
        # constant read is the anonymous-gate disease #1414 cured.
        assert "EvidenceScoreConstants.ABSTAIN_THRESHOLD" not in src
        assert "CONTEXT_QUALITY_MIN" in src

    def test_nlm_verifier_window_is_coupled_to_zone_edges(self) -> None:
        # The NLM verification trigger window reuses the CAUTIOUS band. It
        # must stay value-coupled to the shared zone-edge constants — a
        # freshly hardcoded 0.15/0.60 pair here would drift silently if the
        # zone edges ever move (Codex red-team finding, 2026-07-05).
        from backend.services.rag import nlm_verifier

        assert nlm_verifier.EVIDENCE_MIN == EvidenceScoreConstants.CONFIDENCE_LOW
        assert nlm_verifier.EVIDENCE_MAX == EvidenceScoreConstants.CONFIDENCE_HIGH
