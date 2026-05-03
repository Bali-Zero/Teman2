"""Tests for the reason node."""

import pytest

from nuzantara_graph.nodes.reason import make_reason_node
from nuzantara_schemas.grading import GradeDecision, GradeResult
from nuzantara_schemas.state import GraphState, ReasoningStep, RetrievedDocument
from helpers.mocks import make_mock_services


class TestReasonNode:
    @pytest.mark.asyncio
    async def test_produces_reasoning_steps(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "steps": [
                    {"step_type": "thought", "content": "User is asking about PT PMA setup"},
                    {"step_type": "observation", "content": "Minimum capital is 10 billion IDR"},
                    {"step_type": "thought", "content": "The location Bali doesn't affect capital requirements"},
                ]
            }
        })
        node = make_reason_node(svc)
        state = GraphState(
            query="How to set up a PT PMA?",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="PT PMA requires 10B IDR capital", score=0.9),
            ],
        )

        result = await node(state)

        assert len(result["reasoning_steps"]) == 3
        assert result["reasoning_steps"][0].step_type == "thought"
        assert result["reasoning_steps"][1].step_type == "observation"
        assert result["current_node"] == "reason"

    @pytest.mark.asyncio
    async def test_includes_kg_context(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "steps": [
                    {"step_type": "thought", "content": "Using KG data"},
                ]
            }
        })
        node = make_reason_node(svc)
        state = GraphState(
            query="KBLI for restaurant",
            retrieved_documents=[],
            kg_entities=[
                {"entity_id": "kbli:56101", "label": "Restoran", "description": "Food service"},
            ],
        )

        result = await node(state)

        assert len(result["reasoning_steps"]) == 1

    @pytest.mark.asyncio
    async def test_uses_retry_hint(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "steps": [
                    {"step_type": "thought", "content": "Focusing on tax implications as requested"},
                ]
            }
        })
        node = make_reason_node(svc)
        state = GraphState(
            query="Company setup costs",
            retrieved_documents=[
                RetrievedDocument(id="d1", content="Setup info", score=0.8),
            ],
            grades=[GradeResult(
                grader="reasoning",
                decision=GradeDecision.RETRY,
                score=0.4,
                retry_hint="Focus on tax implications specifically",
            )],
        )

        result = await node(state)

        assert len(result["reasoning_steps"]) >= 1

    @pytest.mark.asyncio
    async def test_handles_llm_failure(self):
        svc = make_mock_services()
        svc.llm.generate_json = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("LLM error")
        )
        node = make_reason_node(svc)
        state = GraphState(query="Test", retrieved_documents=[])

        result = await node(state)

        assert len(result["reasoning_steps"]) == 1
        assert "failed" in result["reasoning_steps"][0].content.lower()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_steps_from_llm(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {"steps": []}
        })
        node = make_reason_node(svc)
        state = GraphState(query="Test", retrieved_documents=[])

        result = await node(state)

        assert result["reasoning_steps"] == []
