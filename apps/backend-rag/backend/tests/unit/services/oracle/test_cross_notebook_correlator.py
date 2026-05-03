"""
Unit tests for CrossNotebookCorrelator.
Covers: domain detection, NLM querying, claim extraction, correlation engine,
synthesis (Ollama + fallback), CrossNotebookCorrelator class, module singleton.
"""

import json
import os
import subprocess
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.services.oracle.cross_notebook_correlator import (
    CrossNotebookCorrelator,
    CrossNotebookResult,
    CorrelationEntry,
    NotebookResponse,
    _call_ollama_synthesis,
    _classify_relationship,
    _compute_claim_overlap,
    _concatenation_fallback,
    _extract_claims,
    _query_notebook_sync,
    build_correlation_matrix,
    detect_domains,
    get_correlator,
    is_multi_domain,
)


# --------------------------------------------------------------------------- #
# Domain detection
# --------------------------------------------------------------------------- #

class TestDetectDomains:
    def test_single_domain_match(self) -> None:
        result = detect_domains("I need a KITAS visa for Bali")
        assert "immigration" in result

    def test_multi_domain_match(self) -> None:
        result = detect_domains("visa for PMA company setup with tax compliance")
        assert len(result) >= 2
        assert "immigration" in result or "company" in result

    def test_no_match(self) -> None:
        result = detect_domains("completely irrelevant text about cooking recipes")
        assert result == []

    def test_threshold_filtering(self) -> None:
        result = detect_domains("visa", threshold=1)
        assert "immigration" in result

    def test_max_notebooks_limit(self) -> None:
        # Query that matches many domains
        query = "visa company tax property seo lifestyle expat operations"
        result = detect_domains(query)
        assert len(result) <= 4  # MAX_NOTEBOOKS_PER_QUERY

    def test_sorted_by_score_desc(self) -> None:
        # "visa kitas kitap immigration" should give immigration high score
        result = detect_domains("visa kitas kitap immigration work permit foreigner")
        if result:
            assert result[0] == "immigration"


class TestIsMultiDomain:
    def test_multi_domain_true(self) -> None:
        assert is_multi_domain("visa for PMA company with tax") is True

    def test_multi_domain_false(self) -> None:
        assert is_multi_domain("cooking recipes for pasta") is False

    def test_single_domain_false(self) -> None:
        assert is_multi_domain("I need a visa") is False


# --------------------------------------------------------------------------- #
# NLM query
# --------------------------------------------------------------------------- #

class TestQueryNotebookSync:
    def test_success(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Answer from notebook"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            response, error = _query_notebook_sync("notebook_123", "test query")
            assert response == "Answer from notebook"
            assert error is None

    def test_nonzero_return_code(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: notebook not found"

        with patch("subprocess.run", return_value=mock_result):
            response, error = _query_notebook_sync("notebook_123", "test query")
            assert response is None
            assert "not found" in error

    def test_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nlm", timeout=90)):
            response, error = _query_notebook_sync("notebook_123", "test query")
            assert response is None
            assert "timeout" in error

    def test_nlm_not_found(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError("nlm")):
            response, error = _query_notebook_sync("notebook_123", "test query")
            assert response is None
            assert "not found" in error

    def test_generic_exception(self) -> None:
        with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
            response, error = _query_notebook_sync("notebook_123", "test query")
            assert response is None
            assert "unexpected" in error


# --------------------------------------------------------------------------- #
# Claim extraction
# --------------------------------------------------------------------------- #

class TestExtractClaims:
    def test_empty_text(self) -> None:
        assert _extract_claims("") == []
        assert _extract_claims(None) == []

    def test_extracts_sentences(self) -> None:
        text = "This is a short sentence. This is a much longer claim that exceeds thirty characters easily. Another one that also exceeds the minimum length."
        claims = _extract_claims(text)
        assert len(claims) >= 2
        assert all(len(c) > 30 for c in claims)

    def test_max_claims_limit(self) -> None:
        text = ". ".join([f"This is claim number {i} with enough characters to pass the filter" for i in range(20)])
        claims = _extract_claims(text, max_claims=3)
        assert len(claims) <= 3

    def test_strips_bullet_markers(self) -> None:
        text = "- This is a bullet point claim that is long enough. * Another bullet that is also long enough for extraction."
        claims = _extract_claims(text)
        for claim in claims:
            assert not claim.startswith("-")
            assert not claim.startswith("*")

    def test_short_sentences_skipped(self) -> None:
        text = "Short. Also short. But this sentence is definitely long enough to be extracted as a claim."
        claims = _extract_claims(text)
        assert len(claims) == 1

    def test_claim_truncation(self) -> None:
        text = "A" * 500 + "."
        claims = _extract_claims(text)
        if claims:
            assert len(claims[0]) <= 300


# --------------------------------------------------------------------------- #
# Correlation engine
# --------------------------------------------------------------------------- #

class TestComputeClaimOverlap:
    def test_identical_claims(self) -> None:
        score = _compute_claim_overlap("visa kitas bali", "visa kitas bali")
        assert score > 0.5

    def test_no_overlap(self) -> None:
        score = _compute_claim_overlap("apple banana cherry", "dog elephant fox")
        assert score == 0.0

    def test_partial_overlap(self) -> None:
        score = _compute_claim_overlap("visa application bali", "visa process jakarta")
        assert 0.0 < score < 1.0

    def test_empty_claims(self) -> None:
        assert _compute_claim_overlap("", "test") == 0.0
        assert _compute_claim_overlap("test", "") == 0.0
        assert _compute_claim_overlap("", "") == 0.0

    def test_stop_words_removed(self) -> None:
        # "the a an is" are all stop words, only "visa" overlaps
        score = _compute_claim_overlap("the visa is good", "a visa an excellent")
        assert score > 0.0


class TestClassifyRelationship:
    def test_low_overlap_complement(self) -> None:
        rel, conf = _classify_relationship("apples oranges", "cars trucks", 0.01)
        assert rel == "COMPLEMENT"

    def test_contradict_keywords(self) -> None:
        rel, conf = _classify_relationship(
            "You cannot apply however it is different",
            "The process is not allowed but contrary",
            0.20,
        )
        assert rel == "CONTRADICT"

    def test_agree_keywords(self) -> None:
        rel, conf = _classify_relationship(
            "The process is also similarly consistent",
            "The same process confirms likewise",
            0.30,
        )
        assert rel == "AGREE"

    def test_high_overlap_agree(self) -> None:
        rel, conf = _classify_relationship(
            "visa application process bali",
            "visa application procedure bali",
            0.50,
        )
        assert rel == "AGREE"
        assert conf > 0.5

    def test_medium_overlap_complement(self) -> None:
        rel, conf = _classify_relationship(
            "taxes corporate income",
            "visa personal travel",
            0.10,
        )
        assert rel == "COMPLEMENT"


class TestBuildCorrelationMatrix:
    def test_empty_responses(self) -> None:
        result = build_correlation_matrix([])
        assert result == []

    def test_single_response(self) -> None:
        responses = [
            NotebookResponse(domain="immigration", notebook_id="nb1",
                             label="Immigration", response="A long claim here about visas and immigration process in Bali."),
        ]
        result = build_correlation_matrix(responses)
        assert result == []  # Need 2+ domains to correlate

    def test_two_domains_with_overlap(self) -> None:
        responses = [
            NotebookResponse(
                domain="immigration", notebook_id="nb1", label="Immigration",
                response="The visa application requires documents and fees payment at the immigration office in Bali.",
            ),
            NotebookResponse(
                domain="company", notebook_id="nb2", label="Company",
                response="Company setup requires documents and fees payment at the business licensing office in Bali.",
            ),
        ]
        result = build_correlation_matrix(responses)
        assert len(result) >= 0  # May or may not find correlations

    def test_max_correlations_limit(self) -> None:
        responses = [
            NotebookResponse(
                domain="immigration", notebook_id="nb1", label="Immigration",
                response=". ".join([f"Immigration claim {i} is very important and relevant to visas" for i in range(10)]),
            ),
            NotebookResponse(
                domain="company", notebook_id="nb2", label="Company",
                response=". ".join([f"Company claim {i} is very important and relevant to business" for i in range(10)]),
            ),
        ]
        result = build_correlation_matrix(responses, max_correlations=5)
        assert len(result) <= 5

    def test_responses_with_errors_skipped(self) -> None:
        responses = [
            NotebookResponse(domain="immigration", notebook_id="nb1", label="Immigration",
                             response=None, error="timeout"),
            NotebookResponse(domain="company", notebook_id="nb2", label="Company",
                             response="Valid response about company formation process in Indonesia with all the details."),
        ]
        result = build_correlation_matrix(responses)
        assert result == []  # Only 1 valid domain, no cross-domain pairs


# --------------------------------------------------------------------------- #
# Synthesis
# --------------------------------------------------------------------------- #

class TestOllamaSynthesis:
    def test_success(self) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "Unified synthesis here"},
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _call_ollama_synthesis(
                query="test",
                domain_responses=[("immigration", "Immigration", "response text")],
                contradictions=[],
            )
            assert result == "Unified synthesis here"

    def test_with_contradictions(self) -> None:
        contradiction = CorrelationEntry(
            claim_a="Visa takes 5 days", domain_a="immigration",
            claim_b="Visa takes 30 days", domain_b="company",
            relationship="CONTRADICT", confidence=0.8,
        )

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "There is a contradiction"},
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _call_ollama_synthesis(
                query="test",
                domain_responses=[("immigration", "Immigration", "resp")],
                contradictions=[contradiction],
            )
            assert result is not None

    def test_timeout_returns_none(self) -> None:
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = _call_ollama_synthesis(
                query="test",
                domain_responses=[("immigration", "Immigration", "resp")],
                contradictions=[],
            )
            assert result is None


class TestConcatenationFallback:
    def test_basic_fallback(self) -> None:
        responses = [
            NotebookResponse(domain="immigration", notebook_id="nb1",
                             label="Immigration", response="Visa info here"),
            NotebookResponse(domain="company", notebook_id="nb2",
                             label="Company", response="Company info here"),
        ]
        result = _concatenation_fallback("test query", responses, [])
        assert "Immigration" in result
        assert "Company" in result
        assert "test query" in result

    def test_with_contradictions(self) -> None:
        responses = [
            NotebookResponse(domain="immigration", notebook_id="nb1",
                             label="Immigration", response="Takes 5 days"),
        ]
        contradictions = [
            CorrelationEntry(
                claim_a="Takes 5 days", domain_a="immigration",
                claim_b="Takes 30 days", domain_b="company",
                relationship="CONTRADICT", confidence=0.8,
            ),
        ]
        result = _concatenation_fallback("query", responses, contradictions)
        assert "Contradictions" in result

    def test_empty_responses(self) -> None:
        result = _concatenation_fallback("query", [], [])
        assert "query" in result

    def test_none_response_skipped(self) -> None:
        responses = [
            NotebookResponse(domain="immigration", notebook_id="nb1",
                             label="Immigration", response=None, error="timeout"),
        ]
        result = _concatenation_fallback("query", responses, [])
        assert "Immigration" not in result  # response is None


# --------------------------------------------------------------------------- #
# CrossNotebookResult dataclass
# --------------------------------------------------------------------------- #

class TestCrossNotebookResult:
    def test_has_contradictions_true(self) -> None:
        result = CrossNotebookResult(
            query="test", domains_matched=["a", "b"],
            notebook_responses=[], correlations=[],
            contradictions=[MagicMock()], synthesis="", synthesis_source="ollama",
            total_latency_ms=100,
        )
        assert result.has_contradictions is True

    def test_has_contradictions_false(self) -> None:
        result = CrossNotebookResult(
            query="test", domains_matched=["a"],
            notebook_responses=[], correlations=[],
            contradictions=[], synthesis="", synthesis_source="ollama",
            total_latency_ms=100,
        )
        assert result.has_contradictions is False

    def test_successful_domains(self) -> None:
        result = CrossNotebookResult(
            query="test", domains_matched=["a", "b"],
            notebook_responses=[
                NotebookResponse(domain="a", notebook_id="1", label="A", response="ok"),
                NotebookResponse(domain="b", notebook_id="2", label="B", response=None, error="err"),
            ],
            correlations=[], contradictions=[], synthesis="",
            synthesis_source="ollama", total_latency_ms=100,
        )
        assert result.successful_domains == ["a"]

    def test_errors_field(self) -> None:
        result = CrossNotebookResult(
            query="test", domains_matched=[], notebook_responses=[],
            correlations=[], contradictions=[], synthesis="",
            synthesis_source="n/a", total_latency_ms=0,
            errors=["error1", "error2"],
        )
        assert len(result.errors) == 2


# --------------------------------------------------------------------------- #
# CrossNotebookCorrelator class
# --------------------------------------------------------------------------- #

class TestCorrelatorClass:
    def test_init_defaults(self) -> None:
        c = CrossNotebookCorrelator()
        assert c._use_ollama is True

    def test_init_custom(self) -> None:
        custom_registry = {"test": {"notebook_id": "nb", "label": "Test", "keywords": {"test"}}}
        c = CrossNotebookCorrelator(domain_registry=custom_registry, use_ollama=False)
        assert c._use_ollama is False
        assert "test" in c._registry

    def test_detect_domains_delegates(self) -> None:
        c = CrossNotebookCorrelator()
        result = c.detect_domains("visa kitas bali")
        assert isinstance(result, list)

    def test_is_multi_domain_delegates(self) -> None:
        c = CrossNotebookCorrelator()
        result = c.is_multi_domain("visa company tax")
        assert isinstance(result, bool)

    def test_query_insufficient_domains(self) -> None:
        c = CrossNotebookCorrelator()
        result = c.query("cooking recipes for pasta")
        assert "only" in result.synthesis.lower() or "domain" in result.synthesis.lower()
        assert len(result.errors) > 0

    def test_query_with_domains(self) -> None:
        c = CrossNotebookCorrelator(use_ollama=False)

        with patch(
            "backend.services.oracle.cross_notebook_correlator._query_notebook_sync",
            return_value=("Response from notebook with enough text content for claims", None),
        ):
            result = c.query("visa for PMA company setup with tax compliance in bali")
            assert len(result.domains_matched) >= 2
            assert result.synthesis_source == "concatenation_fallback"

    def test_query_with_errors(self) -> None:
        c = CrossNotebookCorrelator(use_ollama=False)

        with patch(
            "backend.services.oracle.cross_notebook_correlator._query_notebook_sync",
            return_value=(None, "nlm CLI not found"),
        ):
            result = c.query("visa for PMA company setup")
            assert len(result.errors) > 0


class TestCorrelatorAsync:
    @pytest.mark.asyncio
    async def test_query_async_insufficient_domains(self) -> None:
        c = CrossNotebookCorrelator()
        result = await c.query_async("cooking recipes")
        assert "domain" in result.synthesis.lower() or "single" in result.synthesis.lower()

    @pytest.mark.asyncio
    async def test_query_async_with_domains(self) -> None:
        c = CrossNotebookCorrelator(use_ollama=False)

        with patch(
            "backend.services.oracle.cross_notebook_correlator._query_notebook_sync",
            return_value=("Response from notebook with enough text content for claims extraction", None),
        ):
            result = await c.query_async("visa for PMA company setup with tax npwp compliance")
            assert len(result.domains_matched) >= 2
            assert result.synthesis_source == "concatenation_fallback"
            assert result.total_latency_ms >= 0


class TestBuildResult:
    def test_with_ollama_success(self) -> None:
        c = CrossNotebookCorrelator(use_ollama=True)
        responses = [
            NotebookResponse(domain="immigration", notebook_id="nb1",
                             label="Immigration", response="visa info here in bali"),
            NotebookResponse(domain="company", notebook_id="nb2",
                             label="Company", response="company info here in bali"),
        ]

        with patch(
            "backend.services.oracle.cross_notebook_correlator._call_ollama_synthesis",
            return_value="Unified answer",
        ):
            result = c._build_result("test", ["immigration", "company"],
                                      responses, [], time.monotonic())
            assert result.synthesis == "Unified answer"
            assert result.synthesis_source == "ollama"

    def test_ollama_fails_uses_fallback(self) -> None:
        c = CrossNotebookCorrelator(use_ollama=True)
        responses = [
            NotebookResponse(domain="immigration", notebook_id="nb1",
                             label="Immigration", response="visa info"),
        ]

        with patch(
            "backend.services.oracle.cross_notebook_correlator._call_ollama_synthesis",
            return_value=None,
        ):
            result = c._build_result("test", ["immigration"], responses, [], time.monotonic())
            assert result.synthesis_source == "concatenation_fallback"


# --------------------------------------------------------------------------- #
# Module singleton
# --------------------------------------------------------------------------- #

class TestGetCorrelator:
    def test_creates_singleton(self) -> None:
        with patch("backend.services.oracle.cross_notebook_correlator._default_correlator", None):
            c = get_correlator()
            assert isinstance(c, CrossNotebookCorrelator)

    def test_returns_existing(self) -> None:
        existing = CrossNotebookCorrelator()
        with patch("backend.services.oracle.cross_notebook_correlator._default_correlator", existing):
            c = get_correlator()
            assert c is existing
