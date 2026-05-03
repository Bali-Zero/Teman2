"""Tests for the pricing grader."""

from nuzantara_graph.graders.pricing_grader import PricingGrader
from nuzantara_schemas.grading import GradeDecision
from nuzantara_schemas.state import GraphState, RetrievedDocument


class TestPricingGrader:
    def setup_method(self):
        self.grader = PricingGrader()

    def test_no_pricing_in_answer(self):
        """If no prices are mentioned, grader is N/A → PASS."""
        state = GraphState(
            query="What is a PT PMA?",
            answer="A PT PMA is a foreign-owned limited liability company in Indonesia.",
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_grounded_usd_price_passes(self):
        state = GraphState(
            query="KITAS cost",
            answer="The KITAS application fee is approximately USD 1,200 per year.",
            retrieved_documents=[
                RetrievedDocument(
                    id="d1",
                    content="KITAS costs approximately USD 1,200 per year including processing fees.",
                    score=0.9,
                ),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_fabricated_price_fails(self):
        state = GraphState(
            query="PT PMA cost",
            answer="Setting up a PT PMA costs exactly $50,000 in fees.",
            retrieved_documents=[
                RetrievedDocument(
                    id="d1",
                    content="PT PMA setup involves various government fees and notary costs.",
                    score=0.7,
                ),
            ],
        )
        result = self.grader.grade(state)
        # $50,000 is not in source docs
        assert result.score < 0.9

    def test_idr_price_grounded(self):
        state = GraphState(
            query="Capital requirement",
            answer="Minimum capital is IDR 10,000,000,000 for a PT PMA.",
            retrieved_documents=[
                RetrievedDocument(
                    id="d1",
                    content="PT PMA requires minimum authorized capital of IDR 10,000,000,000.",
                    score=0.95,
                ),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_strict_threshold(self):
        """Pricing grader has pass_threshold=0.9 (stricter than others)."""
        assert self.grader.pass_threshold == 0.9
