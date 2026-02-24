"""Tests for GraphState Pydantic validation."""

import pytest
from pydantic import ValidationError

from nuzantara_schemas.state import (
    ChannelType,
    GraphState,
    IntentType,
    ReasoningStep,
    RetrievedDocument,
    TokenUsage,
)


class TestGraphStateCreation:
    def test_minimal_state(self):
        state = GraphState(query="How do I set up a PT PMA?")
        assert state.query == "How do I set up a PT PMA?"
        assert state.intent == IntentType.GENERAL
        assert state.channel == ChannelType.WEB
        assert state.user_id == "anonymous"
        assert state.correction_count == 0
        assert state.max_corrections == 2
        assert state.is_terminal is False
        assert state.run_id  # auto-generated UUID

    def test_full_state(self):
        state = GraphState(
            query="What visa do I need?",
            user_id="user_123",
            channel=ChannelType.TELEGRAM,
            intent=IntentType.VISA,
            domain="visa",
            detected_language="en",
        )
        assert state.channel == ChannelType.TELEGRAM
        assert state.intent == IntentType.VISA

    def test_unique_run_ids(self):
        s1 = GraphState(query="test1")
        s2 = GraphState(query="test2")
        assert s1.run_id != s2.run_id


class TestGraphStateValidation:
    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError, match="query must not be empty"):
            GraphState(query="")

    def test_whitespace_query_rejected(self):
        with pytest.raises(ValidationError, match="query must not be empty"):
            GraphState(query="   ")

    def test_query_stripped(self):
        state = GraphState(query="  hello world  ")
        assert state.query == "hello world"

    def test_correction_count_cannot_exceed_max(self):
        with pytest.raises(ValidationError, match="correction_count.*exceeds"):
            GraphState(query="test", correction_count=3, max_corrections=2)

    def test_correction_at_max_is_valid(self):
        state = GraphState(query="test", correction_count=2, max_corrections=2)
        assert state.correction_count == 2

    def test_negative_correction_count_rejected(self):
        with pytest.raises(ValidationError):
            GraphState(query="test", correction_count=-1)

    def test_invalid_channel_rejected(self):
        with pytest.raises(ValidationError):
            GraphState(query="test", channel="sms")

    def test_invalid_intent_rejected(self):
        with pytest.raises(ValidationError):
            GraphState(query="test", intent="unknown_intent")


class TestRetrievedDocument:
    def test_valid_document(self):
        doc = RetrievedDocument(id="doc1", content="hello", score=0.85)
        assert doc.score == 0.85

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            RetrievedDocument(id="doc1", content="hello", score=1.5)

    def test_score_negative(self):
        with pytest.raises(ValidationError):
            RetrievedDocument(id="doc1", content="hello", score=-0.1)


class TestReasoningStep:
    def test_valid_step(self):
        step = ReasoningStep(step_type="thought", content="Analyzing query...")
        assert step.tool_name is None

    def test_confidence_range(self):
        with pytest.raises(ValidationError):
            ReasoningStep(step_type="thought", content="test", confidence=1.5)


class TestTokenUsage:
    def test_valid_usage(self):
        usage = TokenUsage(
            node="understand", model="gemini-2.0-flash",
            input_tokens=100, output_tokens=50, cost_usd=0.001,
        )
        assert usage.input_tokens == 100

    def test_negative_tokens_rejected(self):
        with pytest.raises(ValidationError):
            TokenUsage(
                node="understand", model="test",
                input_tokens=-1, output_tokens=0, cost_usd=0.0,
            )


class TestGraphStateProperties:
    def test_total_tokens(self):
        state = GraphState(query="test")
        state.add_token_usage("understand", "gemini", 100, 50, 0.001)
        state.add_token_usage("reason", "gemini", 200, 100, 0.002)
        assert state.total_tokens == 450

    def test_total_cost(self):
        state = GraphState(query="test")
        state.add_token_usage("understand", "gemini", 100, 50, 0.001)
        state.add_token_usage("reason", "gemini", 200, 100, 0.002)
        assert state.total_cost_usd == pytest.approx(0.003)

    def test_last_grade_none(self):
        state = GraphState(query="test")
        assert state.last_grade is None

    def test_last_grade(self):
        from nuzantara_schemas.grading import GradeDecision, GradeResult

        state = GraphState(query="test")
        state.grades.append(
            GradeResult(grader="retrieval", decision=GradeDecision.PASS, score=0.9)
        )
        state.grades.append(
            GradeResult(grader="answer", decision=GradeDecision.RETRY, score=0.3)
        )
        assert state.last_grade.grader == "answer"
        assert state.last_grade.decision == GradeDecision.RETRY


class TestGraphStateSerialization:
    def test_json_round_trip(self):
        state = GraphState(
            query="How to open a restaurant in Bali?",
            intent=IntentType.BUSINESS_SETUP,
            channel=ChannelType.WEB,
        )
        json_str = state.model_dump_json()
        restored = GraphState.model_validate_json(json_str)
        assert restored.query == state.query
        assert restored.intent == state.intent
        assert restored.run_id == state.run_id

    def test_dict_round_trip(self):
        state = GraphState(query="test", user_id="u1")
        d = state.model_dump()
        assert isinstance(d, dict)
        restored = GraphState.model_validate(d)
        assert restored.user_id == "u1"
