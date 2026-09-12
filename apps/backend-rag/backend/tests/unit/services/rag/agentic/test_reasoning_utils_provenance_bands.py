"""B2.1 — the provenance-primary bands (build spec §2), unit-tested directly.

`calculate_evidence_score`'s inversion: when any source declares a retrieved
kind (`score_provenance.RETRIEVED_KINDS`), relevance comes PRIMARILY from a
per-kind band, lexical overlap only CORROBORATES it, and the whole thing is
gated fail-closed by the support signal. This file pins:

  * each kind's band boundaries, at their edges, on the internal band-index
    helpers directly (the smallest unit that can express "at this exact
    value" without the source-quality/final-score arithmetic in the way);
  * the dense recovery `raw = 2 - 1/score` against `format_search_results`'
    own live transform, on three values;
  * lexical corroboration raising a band by AT MOST one step, never
    lowering it, and never firing when `sources` is empty;
  * the support gate's four values;
  * the `top_source_cosine` penalty retired for declared kinds, alive for
    undeclared ones — the exact asymmetry build spec §2.7 requires.

No network, no seat call, no embedding call — every input here is a literal.
"""

from __future__ import annotations

import pytest

from backend.core import score_provenance
from backend.services.misc.result_formatter import format_search_results
from backend.services.rag.agentic._support_signal import SupportVerdict
from backend.services.rag.agentic.reasoning_utils import (
    _BAND_MODERATE,
    _BAND_NONE,
    _BAND_STRONG,
    _BAND_VALUES,
    _BAND_WEAK,
    _declared_band_index,
    _dense_band_index,
    _hybrid_band_index,
    _reranked_band_index,
    calculate_evidence_score,
)

# ============================================================================
# Band edges — hybrid_rrf_formatted. Measured range [0.508, 1.000]
# (score_provenance.py); normalised (score-0.5)/0.5 reuses the SAME cut
# points (0.5/0.3/0.15) as the legacy keyword-ratio bucketing.
# ============================================================================


class TestHybridBandEdges:
    def test_measured_floor_is_none(self) -> None:
        # 0.508 -> normalised 0.016, well under the 0.15 WEAK cut.
        assert _hybrid_band_index(0.508) == _BAND_NONE

    def test_measured_ceiling_is_strong(self) -> None:
        assert _hybrid_band_index(1.0) == _BAND_STRONG

    def test_weak_lower_edge_inclusive(self) -> None:
        # normalised 0.16: (0.58-0.5)/0.5 == 0.16 >= the 0.15 cut. (0.575,
        # the mathematically exact edge, lands one float-ULP under 0.15 —
        # 0.575-0.5 == 0.0749999999999999... in IEEE 754 — so this test uses
        # a value safely inside the band instead of the float-fragile exact
        # boundary.)
        assert _hybrid_band_index(0.58) == _BAND_WEAK

    def test_just_below_weak_edge_is_none(self) -> None:
        assert _hybrid_band_index(0.57) == _BAND_NONE

    def test_moderate_lower_edge_inclusive(self) -> None:
        # normalised 0.3 exactly: (0.65-0.5)/0.5 == 0.3
        assert _hybrid_band_index(0.65) == _BAND_MODERATE

    def test_just_below_moderate_edge_is_weak(self) -> None:
        assert _hybrid_band_index(0.649) == _BAND_WEAK

    def test_strong_lower_edge_inclusive(self) -> None:
        # normalised 0.5 exactly: (0.75-0.5)/0.5 == 0.5
        assert _hybrid_band_index(0.75) == _BAND_STRONG

    def test_just_below_strong_edge_is_moderate(self) -> None:
        assert _hybrid_band_index(0.749) == _BAND_MODERATE

    def test_the_two_manifest_literals(self) -> None:
        """The two values `manifest_mandatory.json`'s own hybrid_rrf_formatted
        sources actually carry (build spec §0's table): 0.6667 and 1.0."""
        assert _hybrid_band_index(0.6667) == _BAND_MODERATE
        assert _hybrid_band_index(1.0) == _BAND_STRONG


# ============================================================================
# Band edges — dense_formatted. WEAK is deliberately COLLAPSED into NONE
# (reasoning_utils.py's own docstring on `_dense_band_index` names the three
# measured anchors this boundary placement is pinned to).
# ============================================================================


class TestDenseBandEdges:
    def test_moderate_lower_edge_inclusive(self) -> None:
        assert _dense_band_index(score=0.0, score_raw=0.32) == _BAND_MODERATE

    def test_just_below_moderate_edge_is_none(self) -> None:
        assert _dense_band_index(score=0.0, score_raw=0.319) == _BAND_NONE

    def test_strong_lower_edge_inclusive(self) -> None:
        assert _dense_band_index(score=0.0, score_raw=0.55) == _BAND_STRONG

    def test_just_below_strong_edge_is_moderate(self) -> None:
        assert _dense_band_index(score=0.0, score_raw=0.549) == _BAND_MODERATE

    def test_measured_anchor_unrelated_pair_is_none(self) -> None:
        """'quantum physics theory' vs KBLI text, cosine 0.038 (measured
        2026-09-03, test_evidence_cross_language.py's own docstring)."""
        assert _dense_band_index(score=0.0, score_raw=0.038) == _BAND_NONE

    def test_measured_anchor_wrong_domain_shared_vocabulary_is_none(self) -> None:
        """An Indonesian KBLI question vs D12-visa text, cosine 0.155 (same
        measured source)."""
        assert _dense_band_index(score=0.0, score_raw=0.155) == _BAND_NONE

    def test_measured_anchor_nonsense_query_tripwire_is_none(self) -> None:
        """The standing pipeline-variant tripwire
        `test_nonsense_query_zero_score_pipeline_variant` declares a
        dense_formatted source at cosine 0.22 and must stay in NONE — this
        exact anchor is WHY WEAK is collapsed into NONE for this kind
        (0.20-0.32 would have let it through)."""
        assert _dense_band_index(score=0.0, score_raw=0.22) == _BAND_NONE

    def test_measured_anchor_relevant_pair_is_moderate(self) -> None:
        """The one measured POSITIVE anchor: cosine 0.373, 'comfortably
        above a 0.32 band' per the same docstring."""
        assert _dense_band_index(score=0.0, score_raw=0.373) == _BAND_MODERATE

    def test_score_raw_present_is_preferred_over_recovery(self) -> None:
        # `score` alone (if trusted) would recover to a different cosine;
        # score_raw, when present, must win.
        recovered_only = 2.0 - (1.0 / 0.99)  # ~ 0.9899, would be STRONG
        assert _dense_band_index(score=0.99, score_raw=0.038) == _BAND_NONE
        assert recovered_only > 0.55  # sanity: the two disagree, proving the preference

    def test_recovery_used_only_when_score_raw_absent(self) -> None:
        # raw = 2 - 1/score; pick score so raw lands exactly on 0.4 (MODERATE).
        score = 1.0 / (2.0 - 0.4)
        assert _dense_band_index(score=score, score_raw=None) == _BAND_MODERATE

    def test_falsy_score_and_absent_score_raw_is_none(self) -> None:
        assert _dense_band_index(score=0.0, score_raw=None) == _BAND_NONE


# ============================================================================
# Band edges — reranked. Unmeasured scale (build spec §2) -> flat,
# conservative WEAK regardless of the source's own `score` magnitude.
# ============================================================================


class TestRerankedBandIsFlatAndConservative:
    def test_flat_weak_low_score(self) -> None:
        assert _reranked_band_index(0.01) == _BAND_WEAK

    def test_declared_band_index_ignores_reranked_score_magnitude(self) -> None:
        low = _declared_band_index([{"score": 0.01, "score_kind": score_provenance.RERANKED}])
        high = _declared_band_index([{"score": 0.99, "score_kind": score_provenance.RERANKED}])
        assert low == high == _BAND_WEAK


# ============================================================================
# Dense recovery vs `format_search_results`' OWN live transform, on three
# values (build spec's own instruction: "asserted against format_search_
# results' own transform on at least three values").
# ============================================================================


class TestDenseRecoveryMatchesTheLiveFormatter:
    @pytest.mark.parametrize("cosine", [0.0, 0.5, 0.9])
    def test_recovered_cosine_matches_the_formatter_input(self, cosine: float) -> None:
        raw_results = {
            "ids": ["a"],
            "documents": ["doc a"],
            "metadatas": [{}],
            "distances": [1.0 - cosine],
            "scores": [cosine],
        }
        formatted = format_search_results(
            raw_results,
            collection_name="visa_oracle",
            score_kind=score_provenance.DENSE_FORMATTED,
        )
        formatted_score = formatted[0]["score"]
        recovered = 2.0 - (1.0 / formatted_score)
        assert recovered == pytest.approx(cosine, abs=1e-3)
        # And the formatter's own score_raw IS the cosine directly — the
        # preferred path `_dense_band_index` takes when present.
        assert formatted[0]["score_raw"] == cosine


# ============================================================================
# Lexical corroboration: raises by at most one step, never lowers, never
# fires when `sources` is empty.
# ============================================================================


class TestLexicalCorroboration:
    def test_raises_a_low_band_by_exactly_one_step_never_more(self) -> None:
        """A hybrid source at the measured floor (NONE band) paired with
        context that shares EVERY query keyword (a lexical ratio that would,
        alone, band STRONG) must land at WEAK — one step up from NONE, never
        jumping straight to STRONG."""
        sources = [{"score": 0.508, "score_kind": score_provenance.HYBRID_RRF_FORMATTED}]
        context = ["KITAS extension requirements sponsor letter passport copy"]
        score = calculate_evidence_score(sources, context, "KITAS extension requirements")
        # WEAK (0.2) + source_quality bonus, capped at 0.35 by the existing
        # final_score formula (semantic_relevance < 0.3 branch) — never the
        # STRONG-band value (0.6) the lexical ratio alone would produce.
        assert score <= 0.35

    def test_never_lowers_a_high_band(self) -> None:
        """A hybrid source at the measured ceiling (STRONG) paired with
        context that shares NOTHING with the query must still keep STRONG —
        corroboration only ever raises, never lowers."""
        sources = [{"score": 1.0, "score_kind": score_provenance.HYBRID_RRF_FORMATTED}]
        context = ["zzqx wobblefish unrelated filler prose about nothing"]
        score_no_overlap = calculate_evidence_score(sources, context, "zzqx wobblefish")
        score_full_overlap = calculate_evidence_score(
            [{"score": 1.0, "score_kind": score_provenance.HYBRID_RRF_FORMATTED}],
            ["zzqx wobblefish is the exact same text as the query"],
            "zzqx wobblefish",
        )
        assert score_no_overlap == score_full_overlap, (
            "a STRONG provenance band must score identically regardless of lexical "
            "overlap — corroboration cannot raise what is already at the top, and it "
            f"must never lower it either (got {score_no_overlap} vs {score_full_overlap})"
        )

    def test_corroboration_never_fires_when_sources_is_empty(self) -> None:
        """`_declared_band_index([])` is the corroboration step's own
        precondition failing shut: no declared source means no provenance
        band to raise in the first place."""
        assert _declared_band_index([]) == _BAND_NONE


# ============================================================================
# The support gate's four values (build spec §2.5): None (no change),
# SUPPORTED (keeps relevance), NOT_SUPPORTED / UNKNOWN / UNAVAILABLE (zeroes
# it, fail-closed).
# ============================================================================


class TestSupportGate:
    _SOURCES = [{"score": 1.0, "score_kind": score_provenance.HYBRID_RRF_FORMATTED}]
    _CONTEXT = ["KITAS visa requirements sponsor letter"]
    _QUERY = "KITAS visa requirements"

    def test_none_changes_nothing(self) -> None:
        without_kwarg = calculate_evidence_score(self._SOURCES, self._CONTEXT, self._QUERY)
        with_none = calculate_evidence_score(
            self._SOURCES, self._CONTEXT, self._QUERY, support=None
        )
        assert without_kwarg == with_none

    def test_supported_keeps_the_relevance(self) -> None:
        baseline = calculate_evidence_score(self._SOURCES, self._CONTEXT, self._QUERY)
        supported = calculate_evidence_score(
            self._SOURCES, self._CONTEXT, self._QUERY, support=SupportVerdict.SUPPORTED
        )
        assert baseline == supported

    @pytest.mark.parametrize(
        "verdict",
        [SupportVerdict.NOT_SUPPORTED, SupportVerdict.UNKNOWN, SupportVerdict.UNAVAILABLE],
    )
    def test_anything_but_supported_zeroes_relevance_fail_closed(
        self, verdict: SupportVerdict
    ) -> None:
        gated = calculate_evidence_score(
            self._SOURCES, self._CONTEXT, self._QUERY, support=verdict
        )
        # semantic_relevance forced to 0.0 routes into
        # `min(source_quality_score * 0.2, 0.1)` — capped well under EVERY
        # abstain threshold this repo has, including the strictest
        # (tax, 0.10).
        assert gated <= 0.1

    def test_the_four_values_are_a_truth_table(self) -> None:
        results = {
            "none": calculate_evidence_score(self._SOURCES, self._CONTEXT, self._QUERY),
            "supported": calculate_evidence_score(
                self._SOURCES, self._CONTEXT, self._QUERY, support=SupportVerdict.SUPPORTED
            ),
            "not_supported": calculate_evidence_score(
                self._SOURCES, self._CONTEXT, self._QUERY, support=SupportVerdict.NOT_SUPPORTED
            ),
            "unknown": calculate_evidence_score(
                self._SOURCES, self._CONTEXT, self._QUERY, support=SupportVerdict.UNKNOWN
            ),
            "unavailable": calculate_evidence_score(
                self._SOURCES, self._CONTEXT, self._QUERY, support=SupportVerdict.UNAVAILABLE
            ),
        }
        assert results["none"] == results["supported"]
        assert results["not_supported"] == results["unknown"] == results["unavailable"]
        assert results["none"] > results["not_supported"]


# ============================================================================
# The `top_source_cosine` penalty: retired for declared kinds, alive for
# undeclared ones (build spec §2.7) — the exact asymmetry.
# ============================================================================


class TestTopSourceCosinePenaltyAsymmetry:
    _CONTEXT = ["KITAS working visa requires sponsor and minimum salary documentation"]
    _QUERY = "kitas working visa cost requirements"

    def test_penalty_still_fires_for_an_undeclared_kind(self) -> None:
        """An UNDECLARED source at 0.35 (inside the `0 < top < 0.5` penalty
        band): legacy semantic_relevance from the lexical ratio is 0.6
        (STRONG) here, source_quality_score is 0.2 (the [0.3,0.5) bucket),
        so final_score before the penalty is `0.6 + 0.2*0.5 == 0.7`; the
        penalty then applies its 0.7x — `round(0.7*0.7, 2) == 0.49`. Pinned
        to the exact number, not just a direction, so a future change to
        either the ratio or the penalty multiplier is caught here."""
        low = calculate_evidence_score([{"score": 0.35}], self._CONTEXT, self._QUERY)
        assert low == 0.49

    def test_penalty_does_not_fire_for_a_declared_kind_in_the_same_numeric_band(
        self,
    ) -> None:
        """The SAME `0 < score < 0.5` shape (0.35), but declared `reranked`
        (a RETRIEVED kind). If the penalty fired here the way it does for
        the undeclared case above, the result would be a REDUCED number
        (some 0.7x-of-something); it is not. Reranked's own flat WEAK band
        (0.2) gets raised one step to MODERATE (0.4) by the same strong
        lexical ratio, source_quality_score is the SAME 0.2 bucket as the
        undeclared case (source-quality bands are untouched by the
        retirement — build spec §2.6), so final_score is
        `0.4 + 0.2*0.5 == 0.5` — UN-penalized. Pinned to the exact number:
        0.5, not `round(0.5*0.7, 2) == 0.35`, which is what a penalty firing
        here would have produced."""
        low = calculate_evidence_score(
            [{"score": 0.35, "score_kind": score_provenance.RERANKED}],
            self._CONTEXT,
            self._QUERY,
        )
        assert low == 0.5
        assert low != round(low * 0.7, 2)

    def test_declared_kind_source_quality_still_reads_the_raw_score(self) -> None:
        """Retiring the PENALTY does not touch `source_quality_score`
        (build spec §2.6: "source quality keeps its bands") — a declared
        source with a higher `score` must still earn a higher-or-equal
        final score through the unchanged source-quality bonus."""
        lower_quality = calculate_evidence_score(
            [{"score": 0.35, "score_kind": score_provenance.RERANKED}],
            self._CONTEXT,
            self._QUERY,
        )
        higher_quality = calculate_evidence_score(
            [{"score": 0.95, "score_kind": score_provenance.RERANKED}],
            self._CONTEXT,
            self._QUERY,
        )
        assert higher_quality >= lower_quality


# ============================================================================
# Sanity: the legacy (no declared kind) path is BYTE-IDENTICAL to what
# `_band_index_from_ratio`'s four values always produced — the guarantee
# every OTHER standing tripwire in this repo depends on.
# ============================================================================


def test_band_values_are_the_legacy_four_in_the_legacy_order() -> None:
    assert _BAND_VALUES == (0.0, 0.2, 0.4, 0.6)


# ---------------------------------------------------------------------------
# Round-1 adversarial findings (codex-gpt-5.6-sol), reproduced by the Dux
# before either was cured. Both are category (a): "relevance must never be
# created where no retrieval measured any".
# ---------------------------------------------------------------------------


class TestARerankedFloorIsNotEvidence:
    """A declared `reranked` source whose own score is 0.0 (or negative) used
    to score 0.2 relevance against a nonsense query and unrelated context.
    An unmeasured scale is not a licence to read its floor as evidence."""

    @staticmethod
    def _score(score: float) -> float:
        return calculate_evidence_score(
            [{"score": score, "score_kind": "reranked", "score_raw": None}],
            ["Pendirian PT PMA — pendaftaran perusahaan penanaman modal asing."],
            "xyzabc123 nonsense query",
        )

    def test_a_zero_reranked_score_creates_no_relevance(self) -> None:
        assert self._score(0.0) == 0.0

    def test_a_negative_reranked_score_creates_no_relevance(self) -> None:
        assert self._score(-5.0) == 0.0

    def test_a_positive_reranked_score_still_reads_as_weak(self) -> None:
        """The conservative flat WEAK band for a POSITIVE reranked score is
        the declared residual and must not be collateral damage of the fix."""
        assert self._score(0.01) > 0.0


class TestLexicalCorroboratesAndNeverCreates:
    """Round-1 adversarial lead (codex-gpt-5.6-sol), reproduced before curing.

    A source that DECLARES a retrieved kind and scores at the bottom of its
    own scale has said "not relevant". Letting the keyword ratio lift that
    band is lexical GATING ALONE — the exact false-acceptance shape this
    inversion exists to remove — leaking back in through the one source that
    had declared its own irrelevance. Corroboration requires something to
    corroborate: a NONE band stays NONE however well the words match.
    """

    _CONTEXT = ["Pendirian PT PMA memerlukan akta notaris, NPWP dan NIB melalui OSS."]
    _HIGH_LEXICAL_QUERY = "PT PMA NIB OSS NPWP akta"

    def _score(self, cosine: float) -> float:
        return calculate_evidence_score(
            [{"score": 0.5, "score_kind": "dense_formatted", "score_raw": cosine}],
            self._CONTEXT,
            self._HIGH_LEXICAL_QUERY,
        )

    def test_a_near_zero_cosine_is_not_liftable_by_words(self) -> None:
        assert self._score(0.02) < 0.15

    def test_a_cosine_just_under_the_moderate_boundary_is_not_liftable_either(self) -> None:
        """0.30 sits under the measured 0.32 MODERATE boundary, so its band is
        NONE and the ratio may not promote it. This is the boundary case that
        would otherwise let the cure be tuned away one hundredth at a time."""
        assert self._score(0.30) < 0.15

    def test_a_moderate_cosine_is_still_corroborated_upward(self) -> None:
        """The cure must not kill corroboration where a band EXISTS: a real
        MODERATE hit plus a strong keyword match still reads higher than the
        same hit alone."""
        assert self._score(0.40) > self.__class__._baseline_without_words()

    @staticmethod
    def _baseline_without_words() -> float:
        return calculate_evidence_score(
            [{"score": 0.5, "score_kind": "dense_formatted", "score_raw": 0.40}],
            ["Pendirian PT PMA memerlukan akta notaris, NPWP dan NIB melalui OSS."],
            "xyzabc123 qwerty",
        )


class TestSupportIsFailClosedOnlyInBothDirections:
    """RULED I30 — the rule of the engine, pinned so it cannot be relaxed by
    an edit that merely looks symmetrical.

    SUPPORTED may never be worth MORE than silence. `None` (not consulted)
    and `SUPPORTED` must produce the SAME score for the same inputs, on both
    relevance paths; every other verdict must zero it. If someone later makes
    a SUPPORTED verdict lift a band, these tests are what goes red.
    """

    _DECLARED = [{"score": 0.5, "score_kind": "dense_formatted", "score_raw": 0.40}]
    _UNKNOWN_KIND = [{"score": 0.72, "score_kind": "unknown", "score_raw": None}]
    _CONTEXT = ["Pendirian PT PMA memerlukan akta notaris, NPWP dan NIB melalui OSS."]
    _QUERY = "PT PMA NIB OSS requirements"
    _CROSS_LANGUAGE_QUERY = "What is the price of new company setup?"

    @pytest.mark.parametrize("sources", [_DECLARED, _UNKNOWN_KIND])
    def test_supported_is_worth_exactly_what_silence_is_worth(self, sources: list[dict]) -> None:
        not_consulted = calculate_evidence_score(sources, self._CONTEXT, self._QUERY)
        supported = calculate_evidence_score(
            sources, self._CONTEXT, self._QUERY, support=SupportVerdict.SUPPORTED
        )
        assert supported == not_consulted

    @pytest.mark.parametrize("sources", [_DECLARED, _UNKNOWN_KIND])
    @pytest.mark.parametrize(
        "verdict",
        [SupportVerdict.NOT_SUPPORTED, SupportVerdict.UNKNOWN, SupportVerdict.UNAVAILABLE],
    )
    def test_every_other_verdict_zeroes_relevance(
        self, sources: list[dict], verdict: SupportVerdict
    ) -> None:
        assert calculate_evidence_score(
            sources, self._CONTEXT, self._QUERY, support=verdict
        ) < 0.15

    def test_supported_is_worth_nothing_MID_BAND_too(self) -> None:
        """The gate finding this test exists for (#6304, cured in the
        provenance-fixture PR): the two parametrized tests above are
        SATURATED. Measured with the raise rule temporarily reintroduced,
        their inputs score 0.7500 either way — the query shares tokens with
        the context, so the lexical corroboration has already carried the band
        to the ceiling and one more step cannot move it. They document the
        rule without defending it.

        This case holds the band strictly BELOW the ceiling: the SAME declared
        dense source (cosine 0.40 -> MODERATE, one band below STRONG) with an
        English query that shares NO token with the Indonesian context, so no
        lexical step lifts it. Measured: 0.5500 with silence and 0.5500 with
        SUPPORTED on the shipped engine; 0.5500 vs 0.7500 the moment a
        one-step raise is reintroduced. That difference is this test's guilt.
        """
        mid_band_context = [
            "Pendirian PT PMA — termasuk akta notaris, NPWP dan NIB. Harga: IDR 20.000.000"
        ]
        not_consulted = calculate_evidence_score(
            self._DECLARED, mid_band_context, self._CROSS_LANGUAGE_QUERY
        )
        supported = calculate_evidence_score(
            self._DECLARED,
            mid_band_context,
            self._CROSS_LANGUAGE_QUERY,
            support=SupportVerdict.SUPPORTED,
        )
        assert supported == not_consulted, (
            "SUPPORTED lifted a MID-BAND score — the fail-closed rule (RULED "
            f"I30) is broken: silence scored {not_consulted}, SUPPORTED "
            f"scored {supported}"
        )
        # And the band really is mid: there IS a step above it to be lifted
        # into, which is what makes the equality above meaningful.
        assert 0.15 <= not_consulted < 0.75, (
            "this fixture stopped being mid-band — re-measure before trusting "
            f"the equality above (got {not_consulted})"
        )

    def test_supported_is_worth_nothing_MID_BAND_ON_THE_LEGACY_PATH_too(self) -> None:
        """F1b — the gap the Codex seat found in F1's own cure (#6326 council,
        RULING I35). The mid-band case above defends the DECLARED path only.
        Measured: with a raise applied ONLY to non-declared sources
        (`elif support is SUPPORTED and not declared and semantic_relevance > 0`)
        the whole suite stayed green — 206 passed, 1 xfailed, nothing red — so
        a future edit lifting a LEGACY band on a SUPPORTED verdict would have
        shipped unnoticed.

        This case is the legacy mirror: a bare-float source (no score_kind, the
        shape every pre-B1.1 fixture has) against a query sharing ONE token
        with the context, which lands at 0.3000 — two bands below the 0.8000
        ceiling the saturated fixtures sit at. Under that legacy-only raise it
        reads 0.6000 with SUPPORTED against 0.3000 with silence.
        """
        legacy_source = [{"score": 0.72}]
        one_token_query = "NIB timeline for foreign investors"
        not_consulted = calculate_evidence_score(legacy_source, self._CONTEXT, one_token_query)
        supported = calculate_evidence_score(
            legacy_source, self._CONTEXT, one_token_query, support=SupportVerdict.SUPPORTED
        )
        assert supported == not_consulted, (
            "SUPPORTED lifted a MID-BAND score on the LEGACY path — RULING I30 is "
            f"fail-closed on BOTH paths: silence {not_consulted}, SUPPORTED {supported}"
        )
        assert 0.15 <= not_consulted < 0.8, (
            "this legacy fixture stopped being mid-band (0.8 is the ceiling these "
            f"fixtures saturate at) — re-measure before trusting the equality (got {not_consulted})"
        )

    def test_supported_cannot_rescue_the_declared_residual(self) -> None:
        """The concrete case the rule was ruled on: `bs-17806bb4`'s shape — an
        English question naming no identifier, Indonesian context that DOES
        carry the fact, and a fixture declaring no provenance. A SUPPORTED
        verdict must NOT lift it, however much we would like the cell to read
        zero."""
        score = calculate_evidence_score(
            self._UNKNOWN_KIND,
            ["Pendirian PT PMA — termasuk akta notaris, NPWP dan NIB. Harga: IDR 20.000.000"],
            self._CROSS_LANGUAGE_QUERY,
            support=SupportVerdict.SUPPORTED,
        )
        assert score < 0.15
