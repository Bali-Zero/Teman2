"""Tests for the retrieval grader — including fail-fast behavior."""

import pytest

from nuzantara_graph.graders.retrieval_grader import RetrievalGrader, make_retrieval_grader
from nuzantara_schemas.grading import GradeDecision
from nuzantara_schemas.state import GraphState, RetrievedDocument


class TestRetrievalGrader:
    def setup_method(self):
        self.grader = RetrievalGrader()

    def test_high_quality_docs_pass(self):
        state = GraphState(
            query="PT PMA setup",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="PT PMA guide", score=0.95),
                RetrievedDocument(id="d2", content="Business setup", score=0.88),
                RetrievedDocument(id="d3", content="Capital requirements", score=0.82),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS
        assert result.score >= 0.7

    def test_mediocre_docs_retry(self):
        state = GraphState(
            query="Something specific",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="Somewhat related", score=0.55),
                RetrievedDocument(id="d2", content="Tangentially related", score=0.45),
                RetrievedDocument(id="d3", content="Barely related", score=0.35),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.RETRY
        assert result.retry_hint != ""

    def test_garbage_docs_fail_fast(self):
        """Score < 0.2 → FAIL (fail-fast, skip reasoning entirely)."""
        state = GraphState(
            query="Very obscure question",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="Irrelevant", score=0.1),
                RetrievedDocument(id="d2", content="Also irrelevant", score=0.08),
                RetrievedDocument(id="d3", content="Noise", score=0.05),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.FAIL
        assert result.score < 0.2
        assert result.retry_hint == ""  # no retry hint on FAIL

    def test_no_documents_fail_fast(self):
        """Zero documents → score 0.0 → FAIL."""
        state = GraphState(query="Test", retrieved_documents=[])
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.FAIL
        assert result.score == 0.0

    def test_single_excellent_doc_passes(self):
        """One great doc is enough to pass."""
        state = GraphState(
            query="KBLI 56101",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="KBLI 56101 Restoran", score=0.95),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_mixed_quality_top_heavy(self):
        """Some great docs + some bad → passes if top docs are good."""
        state = GraphState(
            query="Test",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="Great", score=0.92),
                RetrievedDocument(id="d2", content="Good", score=0.85),
                RetrievedDocument(id="d3", content="OK", score=0.70),
                RetrievedDocument(id="d4", content="Bad", score=0.15),
                RetrievedDocument(id="d5", content="Terrible", score=0.05),
            ],
        )
        result = self.grader.grade(state)
        # Top 3 avg = (0.92+0.85+0.70)/3 = 0.823, overall avg = 0.534
        # Combined = 0.823*0.6 + 0.534*0.4 = 0.494 + 0.214 = 0.707
        assert result.decision == GradeDecision.PASS


class TestRetrievalGraderNode:
    @pytest.mark.asyncio
    async def test_node_appends_grade_to_state(self):
        node = make_retrieval_grader()
        state = GraphState(
            query="Test",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="Good doc", score=0.9),
            ],
        )
        result = await node(state)
        assert len(result["grades"]) == 1
        assert result["grades"][0].grader == "retrieval"

    @pytest.mark.asyncio
    async def test_node_increments_correction_on_retry(self):
        node = make_retrieval_grader()
        state = GraphState(
            query="Test",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="Meh", score=0.45),
                RetrievedDocument(id="d2", content="Meh", score=0.40),
            ],
        )
        result = await node(state)
        if result["grades"][-1].decision.value == "retry":
            assert result["correction_count"] == 1

    @pytest.mark.asyncio
    async def test_node_no_correction_on_fail_fast(self):
        node = make_retrieval_grader()
        state = GraphState(query="Test", retrieved_documents=[])
        result = await node(state)
        assert result["grades"][-1].decision == GradeDecision.FAIL
        assert "correction_count" not in result  # FAIL doesn't bump corrections
