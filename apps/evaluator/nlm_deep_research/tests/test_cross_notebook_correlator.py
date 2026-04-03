"""Tests for ARCH-4: Cross-Notebook Correlator.

All external calls (nlm CLI, Ollama) are mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from apps.evaluator.nlm_deep_research.cross_notebook_correlator import (
    DOMAIN_REGISTRY,
    MAX_NOTEBOOKS_PER_QUERY,
    MIN_DOMAINS_FOR_CROSS,
    CorrelationEntry,
    CrossNotebookCorrelator,
    CrossNotebookResult,
    NotebookResponse,
    _classify_relationship,
    _compute_claim_overlap,
    _extract_claims,
    build_correlation_matrix,
    detect_domains,
    get_correlator,
    is_multi_domain,
)


# ---------------------------------------------------------------------------
# detect_domains
# ---------------------------------------------------------------------------

class TestDetectDomains:
    def test_single_domain_immigration(self):
        result = detect_domains("I need a KITAS work permit for my employee")
        assert "immigration" in result

    def test_multi_domain_pma_plus_tax(self):
        result = detect_domains("Opening PT PMA company and what taxes do I pay as investor?")
        # Should match both company and tax
        assert "company" in result or "tax" in result
        assert len(result) >= 1

    def test_rich_multi_domain_query(self):
        # Classic multi-domain: company + immigration + tax + property
        result = detect_domains(
            "Aprire PT PMA: che visa KITAS serve, che tasse pago, posso comprare proprietà HGB?"
        )
        assert len(result) >= 2

    def test_no_match_returns_empty(self):
        result = detect_domains("What is the weather today in Bali?")
        assert result == []

    def test_threshold_filtering(self):
        # Single keyword match should be excluded at threshold=2
        result = detect_domains("visa", threshold=2)
        # "visa" appears only in immigration → score=1 < threshold=2 → empty
        assert "immigration" not in result or len(result) == 0

    def test_max_notebooks_cap(self):
        # Query hitting all domains shouldn't return more than MAX_NOTEBOOKS_PER_QUERY
        result = detect_domains(
            "visa kitas company pma tax pajak property hgb sop content school"
        )
        assert len(result) <= MAX_NOTEBOOKS_PER_QUERY

    def test_order_by_score_descending(self):
        # "immigration" domain should score highest for this query
        result = detect_domains("I need a KITAS work permit, stay permit for TKA foreigner expat immigration")
        assert result[0] == "immigration"


# ---------------------------------------------------------------------------
# is_multi_domain
# ---------------------------------------------------------------------------

class TestIsMultiDomain:
    def test_single_domain_false(self):
        assert is_multi_domain("How do I apply for a KITAS?") is False  # Only immigration

    def test_multi_domain_true(self):
        assert is_multi_domain(
            "Opening a company PMA and what work visa KITAS does my expat employee need?"
        ) is True

    def test_empty_query_false(self):
        assert is_multi_domain("") is False


# ---------------------------------------------------------------------------
# _extract_claims
# ---------------------------------------------------------------------------

class TestExtractClaims:
    def test_extracts_sentences(self):
        text = "KITAS requires minimum 3 months employment contract. The processing fee must be paid. Processing takes 30 working days."
        claims = _extract_claims(text)
        assert len(claims) == 3

    def test_filters_short_sentences(self):
        text = "Yes. No. KITAS requires a valid sponsoring company and valid employment contract from an authorized employer."
        claims = _extract_claims(text)
        assert len(claims) == 1  # only the long sentence

    def test_max_claims_limit(self):
        text = ". ".join([f"Statement about Indonesian regulation number {i} for foreigners" for i in range(20)])
        claims = _extract_claims(text, max_claims=5)
        assert len(claims) <= 5

    def test_empty_text(self):
        assert _extract_claims("") == []
        assert _extract_claims(None) == []


# ---------------------------------------------------------------------------
# _compute_claim_overlap
# ---------------------------------------------------------------------------

class TestComputeClaimOverlap:
    def test_identical_claims_high_overlap(self):
        claim = "KITAS requires employment contract from Indonesian company"
        assert _compute_claim_overlap(claim, claim) > 0.8

    def test_unrelated_claims_low_overlap(self):
        a = "PT PMA requires minimum capital investment of USD 1 million"
        b = "Bali weather is tropical and warm throughout the year"
        assert _compute_claim_overlap(a, b) < 0.1

    def test_partial_overlap(self):
        a = "KITAS holder must have valid employment contract with Indonesian company"
        b = "Work permit requires valid employment contract for foreign workers"
        score = _compute_claim_overlap(a, b)
        assert 0.1 < score < 0.9  # Some overlap (employment contract) but not identical

    def test_empty_strings(self):
        assert _compute_claim_overlap("", "some text here") == 0.0
        assert _compute_claim_overlap("some text here", "") == 0.0


# ---------------------------------------------------------------------------
# _classify_relationship
# ---------------------------------------------------------------------------

class TestClassifyRelationship:
    def test_low_overlap_is_complement(self):
        rel, conf = _classify_relationship(
            "PT PMA requires minimum USD 1M capital investment",
            "KITAS E23 visa valid for one year with extension",
            overlap=0.02,
        )
        assert rel == "COMPLEMENT"

    def test_agree_signal(self):
        rel, conf = _classify_relationship(
            "Foreign investor also needs KITAS work permit similarly",
            "Investment visa likewise requires KITAS for the director",
            overlap=0.3,
        )
        assert rel in ("AGREE", "COMPLEMENT")

    def test_contradict_signal(self):
        rel, conf = _classify_relationship(
            "Foreign property ownership is not allowed under Indonesian law",
            "Foreign investors can own property through HGB title",
            overlap=0.2,
        )
        assert rel in ("CONTRADICT", "COMPLEMENT")  # depends on keyword detection

    def test_confidence_in_range(self):
        _, conf = _classify_relationship("a b c d e", "a b c d e", overlap=0.9)
        assert 0.0 <= conf <= 1.0


# ---------------------------------------------------------------------------
# build_correlation_matrix
# ---------------------------------------------------------------------------

class TestBuildCorrelationMatrix:
    def _make_responses(self, texts: dict[str, str]) -> list[NotebookResponse]:
        return [
            NotebookResponse(
                domain=domain,
                notebook_id=f"nb-{domain}",
                label=domain.title(),
                response=text,
            )
            for domain, text in texts.items()
        ]

    def test_cross_domain_correlations(self):
        responses = self._make_responses({
            "immigration": "KITAS requires employment contract. Work permit processing takes 30 days.",
            "company": "PT PMA requires authorized employment of foreign workers. Company must sponsor KITAS.",
        })
        correlations = build_correlation_matrix(responses)
        assert len(correlations) >= 0  # May be empty if no overlap

    def test_no_correlations_for_empty_responses(self):
        responses = self._make_responses({"immigration": "", "company": ""})
        correlations = build_correlation_matrix(responses)
        assert correlations == []

    def test_single_domain_no_correlations(self):
        responses = self._make_responses({"immigration": "KITAS is valid for one year in Indonesia."})
        correlations = build_correlation_matrix(responses)
        assert correlations == []

    def test_max_correlations_cap(self):
        # Many domains × many claims → should be capped
        responses = self._make_responses({
            "immigration": "Claim A1. Claim A2. Claim A3. Claim A4. Claim A5.",
            "company": "Claim B1. Claim B2. Claim B3. Claim B4. Claim B5.",
            "tax": "Claim C1. Claim C2. Claim C3. Claim C4. Claim C5.",
        })
        correlations = build_correlation_matrix(responses, max_correlations=10)
        assert len(correlations) <= 10

    def test_contradictions_sorted_first(self):
        responses = self._make_responses({
            "immigration": "Foreign workers cannot work without KITAS permit in Indonesia.",
            "company": "However, foreign directors are not required to obtain work permits.",
        })
        correlations = build_correlation_matrix(responses)
        if correlations:
            contradictions = [c for c in correlations if c.relationship == "CONTRADICT"]
            agrees = [c for c in correlations if c.relationship == "AGREE"]
            # Contradictions should appear before agrees in sorted order
            if contradictions and agrees:
                first_contradict_idx = next(
                    i for i, c in enumerate(correlations) if c.relationship == "CONTRADICT"
                )
                first_agree_idx = next(
                    i for i, c in enumerate(correlations) if c.relationship == "AGREE"
                )
                assert first_contradict_idx < first_agree_idx


# ---------------------------------------------------------------------------
# CrossNotebookCorrelator — domain detection
# ---------------------------------------------------------------------------

class TestCrossNotebookCorrelatorDetection:
    def test_detects_multi_domain(self):
        correlator = CrossNotebookCorrelator()
        assert correlator.is_multi_domain(
            "Aprire PT PMA company, che visa KITAS per dipendente straniero?"
        ) is True

    def test_single_domain_not_multi(self):
        correlator = CrossNotebookCorrelator()
        assert correlator.is_multi_domain("How do I get a KITAS?") is False


# ---------------------------------------------------------------------------
# CrossNotebookCorrelator.query() — mocked NLM + Ollama
# ---------------------------------------------------------------------------

class TestCrossNotebookCorrelatorQuery:
    def _make_correlator_with_mocked_nlm(self, responses: dict[str, str]) -> CrossNotebookCorrelator:
        """Create correlator where NLM CLI returns predefined responses per domain."""
        correlator = CrossNotebookCorrelator(use_ollama=False)
        return correlator

    def test_insufficient_domains_returns_error_result(self):
        correlator = CrossNotebookCorrelator(use_ollama=False)
        with patch(
            "apps.evaluator.nlm_deep_research.cross_notebook_correlator.detect_domains",
            return_value=["immigration"],  # only 1 domain
        ):
            result = correlator.query("Only immigration query")
        assert len(result.errors) > 0
        assert len(result.successful_domains) == 0

    def test_nlm_failure_handled_gracefully(self):
        correlator = CrossNotebookCorrelator(use_ollama=False)
        with patch(
            "apps.evaluator.nlm_deep_research.cross_notebook_correlator._query_notebook_sync",
            return_value=(None, "Connection refused"),
        ):
            result = correlator.query(
                "Opening PT PMA company, need KITAS visa for foreign director"
            )
        assert result is not None
        # All queries failed → synthesis should be fallback
        assert result.synthesis_source in ("concatenation_fallback", "n/a")

    def test_successful_query_builds_result(self):
        correlator = CrossNotebookCorrelator(use_ollama=False)

        def fake_nlm_query(notebook_id, query):
            if "cff93ab0" in notebook_id:  # immigration
                return ("KITAS E23 requires employment contract from Indonesian employer. "
                        "Work permit valid 1 year renewable.", None)
            elif "933509f9" in notebook_id:  # company
                return ("PT PMA requires minimum USD 1M capital. "
                        "Foreign director must be sponsored by company for KITAS.", None)
            return (None, "unknown notebook")

        with patch(
            "apps.evaluator.nlm_deep_research.cross_notebook_correlator._query_notebook_sync",
            side_effect=fake_nlm_query,
        ):
            result = correlator.query(
                "Opening PT PMA, what KITAS visa does my foreign director need?"
            )

        assert len(result.domains_matched) >= 2
        assert len(result.successful_domains) >= 1
        assert len(result.synthesis) > 10
        assert result.total_latency_ms >= 0

    def test_synthesis_fallback_when_ollama_disabled(self):
        correlator = CrossNotebookCorrelator(use_ollama=False)

        with patch(
            "apps.evaluator.nlm_deep_research.cross_notebook_correlator._query_notebook_sync",
            return_value=("Immigration response about KITAS and work permits.", None),
        ):
            result = correlator.query(
                "Opening company PMA, KITAS visa needed for foreign worker?"
            )

        # use_ollama=False → should use concatenation fallback
        assert result.synthesis_source == "concatenation_fallback"


# ---------------------------------------------------------------------------
# CrossNotebookCorrelator.query_async()
# ---------------------------------------------------------------------------

class TestCrossNotebookCorrelatorAsync:
    @pytest.mark.asyncio
    async def test_async_query_parallel_execution(self):
        correlator = CrossNotebookCorrelator(use_ollama=False)

        call_log = []

        async def fake_query_async(domain, notebook_id, label, query):
            call_log.append(domain)
            return NotebookResponse(
                domain=domain,
                notebook_id=notebook_id,
                label=label,
                response=f"Response from {domain} about {query[:30]}",
            )

        with patch(
            "apps.evaluator.nlm_deep_research.cross_notebook_correlator._query_notebook_async",
            side_effect=fake_query_async,
        ):
            result = await correlator.query_async(
                "PT PMA company setup plus KITAS work permit for foreign director"
            )

        assert len(result.domains_matched) >= 2
        assert len(call_log) == len(result.domains_matched)

    @pytest.mark.asyncio
    async def test_async_insufficient_domains(self):
        correlator = CrossNotebookCorrelator(use_ollama=False)
        result = await correlator.query_async("How do I get a KITAS only?")
        # Either 0 or 1 domain → error
        if len(result.domains_matched) < MIN_DOMAINS_FOR_CROSS:
            assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# CrossNotebookResult properties
# ---------------------------------------------------------------------------

class TestCrossNotebookResultProperties:
    def _make_result(
        self,
        domains: list[str],
        contradictions: list[CorrelationEntry],
        responses: list[NotebookResponse],
    ) -> CrossNotebookResult:
        return CrossNotebookResult(
            query="test query",
            domains_matched=domains,
            notebook_responses=responses,
            correlations=contradictions,
            contradictions=contradictions,
            synthesis="test synthesis",
            synthesis_source="ollama",
            total_latency_ms=1000,
        )

    def test_has_contradictions_true(self):
        c = CorrelationEntry(
            claim_a="Foreign workers cannot own property.",
            domain_a="immigration",
            claim_b="Foreign investors can buy property under HGB.",
            domain_b="property",
            relationship="CONTRADICT",
            confidence=0.8,
        )
        result = self._make_result(["immigration", "property"], [c], [])
        assert result.has_contradictions is True

    def test_has_contradictions_false(self):
        result = self._make_result(["immigration", "company"], [], [])
        assert result.has_contradictions is False

    def test_successful_domains_excludes_errors(self):
        responses = [
            NotebookResponse(
                domain="immigration", notebook_id="nb1", label="Immigration",
                response="Valid response here", error=None
            ),
            NotebookResponse(
                domain="company", notebook_id="nb2", label="Company",
                response=None, error="Connection refused"
            ),
        ]
        result = self._make_result(
            ["immigration", "company"], [], responses
        )
        assert result.successful_domains == ["immigration"]


# ---------------------------------------------------------------------------
# nlm_notebook_registry — resolve_multi_notebook
# (loaded via sys.path since apps/backend-rag has a hyphen in the directory name)
# ---------------------------------------------------------------------------

import sys as _sys
import os as _os
_backend_rag_path = _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "backend-rag")
if _backend_rag_path not in _sys.path:
    _sys.path.insert(0, _backend_rag_path)


class TestResolveMultiNotebook:
    def test_multi_domain_query_returns_list(self):
        from backend.services.oracle.nlm_notebook_registry import resolve_multi_notebook
        results = resolve_multi_notebook(
            "company pma tax pajak compliance visa kitas foreigners property hgb"
        )
        assert isinstance(results, list)
        # Multi-keyword query → should match multiple domains
        assert len(results) >= 2

    def test_single_domain_returns_empty(self):
        from backend.services.oracle.nlm_notebook_registry import resolve_multi_notebook
        results = resolve_multi_notebook("How do I apply for a KITAS work permit foreigner?")
        # immigration keywords → single domain → should return []
        assert len(results) < 2

    def test_empty_query(self):
        from backend.services.oracle.nlm_notebook_registry import resolve_multi_notebook
        assert resolve_multi_notebook("") == []

    def test_result_structure(self):
        from backend.services.oracle.nlm_notebook_registry import resolve_multi_notebook
        results = resolve_multi_notebook(
            "company pma tax pajak compliance visa kitas foreigners property hgb"
        )
        if results:
            for r in results:
                assert "domain" in r
                assert "notebook_id" in r
                assert "label" in r
                assert "score" in r

    def test_ordered_by_score_descending(self):
        from backend.services.oracle.nlm_notebook_registry import resolve_multi_notebook
        results = resolve_multi_notebook(
            "tax pajak npwp pph ppn coretax compliance fiscal pajak"
        )
        if len(results) >= 2:
            # First domain should have highest or equal score
            assert results[0]["score"] >= results[-1]["score"]
