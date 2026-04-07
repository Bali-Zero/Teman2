"""Tests for RetrievalGrader."""

from backend.services.rag.grading import (
    GradeDecision,
    GradingContext,
    RetrievalGrader,
    RetrievedDoc,
)


def _make_ctx(scores: list[float]) -> GradingContext:
    return GradingContext(
        retrieved_documents=[
            RetrievedDoc(content=f"doc {i}", score=s)
            for i, s in enumerate(scores)
        ],
    )


class TestRetrievalGrader:
    def test_no_documents_fail(self) -> None:
        ctx = GradingContext()
        result = RetrievalGrader().grade(ctx)
        assert result.decision == GradeDecision.FAIL
        assert result.score == 0.0

    def test_high_relevance_pass(self) -> None:
        ctx = _make_ctx([0.9, 0.85, 0.8, 0.7])
        result = RetrievalGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS
        assert result.score >= 0.7

    def test_low_relevance_fail_fast(self) -> None:
        ctx = _make_ctx([0.1, 0.05, 0.08])
        result = RetrievalGrader().grade(ctx)
        assert result.decision == GradeDecision.FAIL
        assert result.score < 0.2

    def test_medium_relevance_retry(self) -> None:
        ctx = _make_ctx([0.6, 0.5, 0.4, 0.3])
        result = RetrievalGrader().grade(ctx)
        assert result.decision == GradeDecision.RETRY
        assert 0.2 <= result.score < 0.7

    def test_single_great_doc_pass(self) -> None:
        ctx = _make_ctx([0.95])
        result = RetrievalGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS

    def test_top_heavy_distribution(self) -> None:
        """Good top docs but bad tail — top-weighting should still pass."""
        ctx = _make_ctx([0.95, 0.9, 0.85, 0.1, 0.05, 0.02])
        result = RetrievalGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS

    def test_retry_hint_present(self) -> None:
        ctx = _make_ctx([0.5, 0.4, 0.3])
        result = RetrievalGrader().grade(ctx)
        if result.decision == GradeDecision.RETRY:
            assert result.retry_hint != ""

    def test_pass_no_retry_hint(self) -> None:
        ctx = _make_ctx([0.95, 0.9, 0.85])
        result = RetrievalGrader().grade(ctx)
        assert result.retry_hint == ""
