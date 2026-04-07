"""Tests for PricingGrader."""

from backend.services.rag.grading import (
    GradeDecision,
    GradingContext,
    PricingGrader,
    RetrievedDoc,
    contains_pricing,
)


class TestContainsPricing:
    def test_usd_pattern(self) -> None:
        assert contains_pricing("Cost is USD 2,500")

    def test_dollar_pattern(self) -> None:
        assert contains_pricing("Price: $1,200,000")

    def test_idr_pattern(self) -> None:
        assert contains_pricing("Biaya IDR 10,000,000")

    def test_rupiah_pattern(self) -> None:
        assert contains_pricing("Rp. 5.000.000")

    def test_indonesian_pattern(self) -> None:
        assert contains_pricing("Modal 10 juta rupiah")

    def test_no_pricing(self) -> None:
        assert not contains_pricing("KITAS requires a sponsor company")


class TestPricingGrader:
    def test_no_pricing_na(self) -> None:
        ctx = GradingContext(answer="KITAS requires a sponsor company and RPTKA.")
        result = PricingGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS
        assert result.score == 1.0

    def test_grounded_pricing_pass(self) -> None:
        ctx = GradingContext(
            answer="KITAS costs USD 2,500 for processing.",
            retrieved_documents=[
                RetrievedDoc(content="KITAS processing fee: USD 2,500", score=0.9),
            ],
        )
        result = PricingGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS

    def test_fabricated_pricing_fail(self) -> None:
        ctx = GradingContext(
            answer="KITAS costs USD 50,000 and requires Rp. 999,999,999 deposit.",
            retrieved_documents=[
                RetrievedDoc(content="KITAS is a stay permit for foreign workers.", score=0.5),
            ],
        )
        result = PricingGrader().grade(ctx)
        assert result.decision in (GradeDecision.RETRY, GradeDecision.FAIL)
        assert result.score < 0.9

    def test_strict_threshold(self) -> None:
        """Pricing grader uses 0.9 pass threshold (strictest of all)."""
        assert PricingGrader().pass_threshold == 0.9

    def test_kg_entity_pricing_grounded(self) -> None:
        """Prices found in KG entities should count as grounded."""
        ctx = GradingContext(
            answer="The BPHTB tax is 5 juta rupiah.",
            retrieved_documents=[],
            kg_entities=[{"label": "BPHTB", "cost_range": "5 juta"}],
        )
        result = PricingGrader().grade(ctx)
        # KG grounding should help
        assert result.score > 0.0
