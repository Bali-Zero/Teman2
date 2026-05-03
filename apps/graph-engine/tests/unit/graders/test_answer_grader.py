"""Tests for the answer grader."""

from nuzantara_graph.graders.answer_grader import AnswerGrader
from nuzantara_schemas.grading import ConfidenceScores, GradeDecision
from nuzantara_schemas.state import GraphState


class TestAnswerGrader:
    def setup_method(self):
        self.grader = AnswerGrader()

    def test_good_answer_passes(self):
        state = GraphState(
            query="Test",
            answer="To set up a PT PMA in Bali, you need: 1) Minimum capital of 10 billion IDR, "
                   "2) A local partner is not required for 100% foreign ownership sectors, "
                   "3) KBLI codes that allow foreign investment. The process typically takes 4-6 weeks.",
            sources=[{"title": "PT PMA Guide", "id": "d1"}],
            confidence=ConfidenceScores(
                retrieval_relevance=0.9, source_authority=0.8,
                reasoning_coherence=0.85, factual_grounding=0.9,
                domain_coverage=0.7, answer_completeness=0.8,
            ),
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_short_answer_retries(self):
        state = GraphState(
            query="Test",
            answer="Yes, you can do that.",
            sources=[],
            confidence=ConfidenceScores(retrieval_relevance=0.5),
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.RETRY

    def test_empty_answer_fails_fast(self):
        state = GraphState(query="Test", answer="")
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.FAIL

    def test_refusal_answer_penalized(self):
        state = GraphState(
            query="Test",
            answer="I'm unable to answer this question at this time.",
            confidence=ConfidenceScores(),
        )
        result = self.grader.grade(state)
        # Short + no sources + low confidence + refusal → low score
        assert result.score < 0.5

    def test_high_confidence_boosts_score(self):
        state = GraphState(
            query="Test",
            answer="A detailed answer about KITAS visa requirements in Indonesia.",
            sources=[{"id": "s1"}],
            confidence=ConfidenceScores(
                retrieval_relevance=0.9, source_authority=0.9,
                reasoning_coherence=0.9, factual_grounding=0.9,
                domain_coverage=0.9, answer_completeness=0.9,
            ),
        )
        result = self.grader.grade(state)
        assert result.score >= 0.7
