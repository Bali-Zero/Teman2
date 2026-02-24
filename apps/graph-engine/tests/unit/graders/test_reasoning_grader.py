"""Tests for the reasoning grader."""

import pytest

from nuzantara_graph.graders.reasoning_grader import ReasoningGrader, make_reasoning_grader
from nuzantara_schemas.grading import GradeDecision
from nuzantara_schemas.state import GraphState, ReasoningStep


class TestReasoningGrader:
    def setup_method(self):
        self.grader = ReasoningGrader()

    def test_good_reasoning_passes(self):
        state = GraphState(
            query="Test",
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="Analyzing the query about PT PMA requirements in detail"),
                ReasoningStep(step_type="observation", content="The minimum capital requirement is 10 billion IDR according to government regulation"),
                ReasoningStep(step_type="thought", content="This applies to all foreign-owned companies regardless of sector"),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_shallow_reasoning_retries(self):
        state = GraphState(
            query="Test",
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="Hmm, not sure"),
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.RETRY
        assert result.retry_hint != ""

    def test_no_reasoning_fails_fast(self):
        state = GraphState(query="Test", reasoning_steps=[])
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.FAIL
        assert result.score == 0.0

    def test_thoughts_only_can_pass(self):
        """Thoughts-only (no observations) but detailed enough can still pass."""
        state = GraphState(
            query="Test",
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="The user is asking about visa requirements for Indonesia, specifically for the KITAS work permit"),
                ReasoningStep(step_type="thought", content="Based on the retrieved documents, a KITAS requires a sponsoring company registered in Indonesia"),
                ReasoningStep(step_type="thought", content="The application process takes approximately 4-6 weeks and requires multiple documents"),
            ],
        )
        result = self.grader.grade(state)
        # has_thoughts=True, no observations: +0.15, count>=3: +0.3, avg_length high: +0.35 = 0.80
        assert result.decision == GradeDecision.PASS


class TestReasoningGraderNode:
    @pytest.mark.asyncio
    async def test_node_appends_grade(self):
        node = make_reasoning_grader()
        state = GraphState(
            query="Test",
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="Detailed analysis of the business setup process"),
                ReasoningStep(step_type="observation", content="Capital requirement is 10B IDR minimum"),
                ReasoningStep(step_type="thought", content="This is consistent with recent regulatory changes"),
            ],
        )
        result = await node(state)
        assert len(result["grades"]) == 1
        assert result["grades"][0].grader == "reasoning"
