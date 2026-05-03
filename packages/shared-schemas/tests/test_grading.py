"""Tests for grading schemas."""

import pytest
from pydantic import ValidationError

from nuzantara_schemas.grading import ConfidenceScores, GradeDecision, GradeResult


class TestGradeResult:
    def test_valid_grade(self):
        grade = GradeResult(
            grader="retrieval",
            decision=GradeDecision.PASS,
            score=0.85,
            reason="Relevant documents found",
        )
        assert grade.decision == GradeDecision.PASS

    def test_retry_with_hint(self):
        grade = GradeResult(
            grader="reasoning",
            decision=GradeDecision.RETRY,
            score=0.3,
            reason="Reasoning incoherent",
            retry_hint="Focus on tax implications specifically",
        )
        assert grade.retry_hint != ""

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            GradeResult(grader="test", decision=GradeDecision.PASS, score=1.5)

    def test_score_negative(self):
        with pytest.raises(ValidationError):
            GradeResult(grader="test", decision=GradeDecision.PASS, score=-0.1)


class TestConfidenceScores:
    def test_default_scores(self):
        scores = ConfidenceScores()
        assert scores.overall == 0.0
        assert scores.is_low_confidence is True
        assert scores.is_high_confidence is False

    def test_high_confidence(self):
        scores = ConfidenceScores(
            retrieval_relevance=0.9,
            source_authority=0.8,
            reasoning_coherence=0.85,
            factual_grounding=0.9,
            domain_coverage=0.7,
            answer_completeness=0.8,
        )
        assert scores.overall > 0.7
        assert scores.is_high_confidence is True
        assert scores.is_low_confidence is False

    def test_mixed_confidence(self):
        scores = ConfidenceScores(
            retrieval_relevance=0.5,
            source_authority=0.5,
            reasoning_coherence=0.5,
            factual_grounding=0.5,
            domain_coverage=0.5,
            answer_completeness=0.5,
        )
        assert scores.overall == pytest.approx(0.5)
        assert scores.is_high_confidence is False
        assert scores.is_low_confidence is False

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            ConfidenceScores(retrieval_relevance=1.5)

    def test_weights_sum_to_one(self):
        scores = ConfidenceScores()
        total_weight = sum(scores._weights.values())
        assert total_weight == pytest.approx(1.0)
