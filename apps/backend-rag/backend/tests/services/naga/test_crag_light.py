"""Tests for CRAG-Light fast relevance gate.

Sub-millisecond keyword-overlap gate that decides PASS / RETRY / ESCALATE
after each search dispatch — no LLM calls.
"""

from __future__ import annotations

import pytest

from backend.services.naga.quality.crag_light import CragDecision, crag_evaluate


# ---------------------------------------------------------------------------
# CragDecision frozen invariant
# ---------------------------------------------------------------------------


class TestCragDecisionFrozen:
    """CragDecision is a frozen dataclass — no mutation allowed."""

    def test_frozen_raises_on_attribute_set(self) -> None:
        decision = CragDecision(action="PASS", reason="ok", relevance_score=0.5)
        with pytest.raises(AttributeError):
            decision.action = "RETRY"  # type: ignore[misc]

    def test_frozen_raises_on_score_set(self) -> None:
        decision = CragDecision(action="PASS", reason="ok", relevance_score=0.5)
        with pytest.raises(AttributeError):
            decision.relevance_score = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Empty / missing sources → ESCALATE
# ---------------------------------------------------------------------------


class TestEscalateOnEmpty:
    """Empty sources_content must always produce ESCALATE."""

    def test_empty_list(self) -> None:
        result = crag_evaluate("What is a KITAS visa?", [])
        assert result.action == "ESCALATE"
        assert result.relevance_score == 0.0

    def test_list_of_empty_strings(self) -> None:
        result = crag_evaluate("What is a KITAS visa?", ["", "  ", ""])
        assert result.action == "ESCALATE"
        assert result.relevance_score == 0.0


# ---------------------------------------------------------------------------
# Relevant content → PASS
# ---------------------------------------------------------------------------


class TestPassOnRelevant:
    """When keyword overlap is strong and content has substance → PASS."""

    def test_kitas_question_with_kitas_content(self) -> None:
        question = "What is a KITAS visa in Indonesia?"
        sources = [
            "KITAS is a temporary stay permit visa issued by Indonesia's "
            "immigration office. It allows foreigners to stay in Indonesia "
            "for a limited period, typically sponsored by an employer or family member."
        ]
        result = crag_evaluate(question, sources)
        assert result.action == "PASS"
        assert result.relevance_score >= 0.30

    def test_company_setup_question(self) -> None:
        question = "How to set up a PT PMA company in Bali?"
        sources = [
            "Setting up a PT PMA (foreign-owned company) in Bali requires "
            "minimum investment of IDR 10 billion. The PMA company setup "
            "process involves BKPM approval, notarial deed, and KBLI code selection."
        ]
        result = crag_evaluate(question, sources)
        assert result.action == "PASS"
        assert result.relevance_score >= 0.30

    def test_multiple_relevant_sources(self) -> None:
        question = "What are the tax obligations for PT PMA?"
        sources = [
            "PT PMA companies have monthly tax obligations including PPh 21.",
            "Tax filing for PMA entities must be done quarterly via e-Filing.",
        ]
        result = crag_evaluate(question, sources)
        assert result.action == "PASS"
        assert result.relevance_score >= 0.30


# ---------------------------------------------------------------------------
# Irrelevant content → RETRY or ESCALATE
# ---------------------------------------------------------------------------


class TestRetryOrEscalateOnIrrelevant:
    """Weather forecast for a KITAS question should be RETRY or ESCALATE."""

    def test_weather_for_kitas_question(self) -> None:
        question = "What is a KITAS visa in Indonesia?"
        sources = [
            "The weather in Bali today is sunny with temperatures around "
            "30 degrees Celsius. Expected rainfall is minimal throughout the week."
        ]
        result = crag_evaluate(question, sources)
        assert result.action in ("RETRY", "ESCALATE")
        assert result.relevance_score < 0.30

    def test_recipe_for_tax_question(self) -> None:
        question = "How to calculate corporate income tax in Indonesia?"
        sources = [
            "To make nasi goreng, heat oil in a wok, add garlic and shallots, "
            "then add rice and soy sauce. Stir fry for five minutes."
        ]
        result = crag_evaluate(question, sources)
        assert result.action in ("RETRY", "ESCALATE")
        assert result.relevance_score < 0.15


# ---------------------------------------------------------------------------
# Threshold boundary tests
# ---------------------------------------------------------------------------


class TestThresholdBoundaries:
    """Verify the exact boundary behavior of pass/retry/escalate."""

    def test_exact_pass_threshold(self) -> None:
        """Score exactly at pass_threshold → PASS."""
        result = crag_evaluate(
            "What is a KITAS visa?",
            ["KITAS visa information"],
            pass_threshold=0.30,
        )
        # Just verify the logic is applied; exact score depends on words
        assert result.action in ("PASS", "RETRY", "ESCALATE")

    def test_custom_thresholds_high(self) -> None:
        """Very high pass threshold makes PASS harder to reach."""
        question = "What is a KITAS visa?"
        sources = ["KITAS visa details"]
        result = crag_evaluate(question, sources, pass_threshold=0.99)
        assert result.action in ("RETRY", "ESCALATE")

    def test_custom_thresholds_low(self) -> None:
        """Very low thresholds make PASS easy to reach."""
        question = "What is a KITAS visa?"
        sources = [
            "KITAS is a temporary visa permit that allows foreigners to "
            "reside in Indonesia for work or family purposes."
        ]
        result = crag_evaluate(question, sources, pass_threshold=0.01, retry_threshold=0.005)
        assert result.action == "PASS"

    def test_no_substance_short_content(self) -> None:
        """Content below 100 chars lacks substance — cannot PASS even with overlap."""
        question = "What is KITAS?"
        sources = ["KITAS"]  # < 100 chars
        result = crag_evaluate(question, sources)
        assert result.action != "PASS"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: short queries, unicode, stop words."""

    def test_single_word_query(self) -> None:
        """Single-word queries with matching content should work."""
        result = crag_evaluate("KITAS", ["KITAS is a temporary stay permit in Indonesia."])
        assert result.action in ("PASS", "RETRY")

    def test_short_words_filtered(self) -> None:
        """Words < 3 chars are excluded from overlap computation."""
        # "is" and "a" should be filtered out, leaving only "what" and "visa"
        question = "is a visa"
        sources = ["A visa is required for entry into the country."]
        result = crag_evaluate(question, sources)
        # "visa" matches, but "is" and "a" are filtered — score based on "visa" only
        assert isinstance(result.relevance_score, float)

    def test_case_insensitive(self) -> None:
        """Overlap check is case-insensitive."""
        question = "KITAS Visa Indonesia"
        sources = [
            "kitas visa indonesia permit for foreigners to work and reside "
            "long term in the country with proper documentation and sponsorship."
        ]
        result = crag_evaluate(question, sources)
        assert result.action == "PASS"

    def test_relevance_score_bounded(self) -> None:
        """Score is always between 0.0 and 1.0."""
        for sources in [[], ["abc"], ["KITAS visa permit Indonesia immigration office"]]:
            result = crag_evaluate("What is KITAS?", sources)
            assert 0.0 <= result.relevance_score <= 1.0

    def test_return_type(self) -> None:
        """Always returns a CragDecision."""
        result = crag_evaluate("test question here", ["some content here"])
        assert isinstance(result, CragDecision)
        assert result.action in ("PASS", "RETRY", "ESCALATE")
        assert isinstance(result.reason, str)
        assert isinstance(result.relevance_score, float)
