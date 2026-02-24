"""Tests for the synthesize node."""

import pytest

from nuzantara_graph.nodes.synthesize import make_synthesize_node, make_synthesize_direct_node
from nuzantara_schemas.state import GraphState, ReasoningStep, RetrievedDocument
from helpers.mocks import make_mock_services


class TestSynthesizeNode:
    @pytest.mark.asyncio
    async def test_generates_answer_with_confidence(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "answer": "To set up a PT PMA in Bali, you need minimum capital of 10 billion IDR.",
                "sources": [{"title": "PT PMA Guide", "id": "d1"}],
                "confidence": {
                    "retrieval_relevance": 0.9,
                    "source_authority": 0.8,
                    "reasoning_coherence": 0.85,
                    "factual_grounding": 0.9,
                    "domain_coverage": 0.7,
                    "answer_completeness": 0.8,
                },
            }
        })
        node = make_synthesize_node(svc)
        state = GraphState(
            query="How to set up a PT PMA?",
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="Analyzing PT PMA requirements"),
                ReasoningStep(step_type="observation", content="Minimum capital is 10B IDR"),
            ],
            retrieved_documents=[
                RetrievedDocument(id="d1", content="PT PMA setup guide", score=0.9),
            ],
        )

        result = await node(state)

        assert "PT PMA" in result["answer"]
        assert len(result["sources"]) == 1
        assert result["confidence"].overall > 0.7
        assert result["confidence"].is_high_confidence

    @pytest.mark.asyncio
    async def test_clamps_invalid_confidence_values(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "answer": "Test answer",
                "sources": [],
                "confidence": {
                    "retrieval_relevance": 1.5,  # should clamp to 1.0
                    "source_authority": -0.3,     # should clamp to 0.0
                    "reasoning_coherence": "invalid",  # should default to 0.0
                    "factual_grounding": 0.8,
                    "domain_coverage": 0.7,
                    "answer_completeness": 0.6,
                },
            }
        })
        node = make_synthesize_node(svc)
        state = GraphState(
            query="Test",
            reasoning_steps=[ReasoningStep(step_type="thought", content="Test")],
        )

        result = await node(state)

        assert result["confidence"].retrieval_relevance == 1.0
        assert result["confidence"].source_authority == 0.0
        assert result["confidence"].reasoning_coherence == 0.0

    @pytest.mark.asyncio
    async def test_handles_llm_failure(self):
        svc = make_mock_services()
        svc.llm.generate_json = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("LLM down")
        )
        node = make_synthesize_node(svc)
        state = GraphState(query="Test", reasoning_steps=[])

        result = await node(state)

        assert "unable to generate" in result["answer"].lower() or "apologize" in result["answer"].lower()
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_missing_confidence_defaults_to_zero(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "answer": "Simple answer",
                "sources": [],
                "confidence": {},
            }
        })
        node = make_synthesize_node(svc)
        state = GraphState(query="Test", reasoning_steps=[])

        result = await node(state)

        assert result["confidence"].overall == 0.0
        assert result["confidence"].is_low_confidence


class TestSynthesizeDirectNode:
    @pytest.mark.asyncio
    async def test_greeting_response(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "answer": "Hello! I'm Zantara, your Indonesian business assistant. How can I help?",
            }
        })
        node = make_synthesize_direct_node(svc)
        state = GraphState(query="Hello!")

        result = await node(state)

        assert "Hello" in result["answer"] or "help" in result["answer"].lower()
        assert result["is_terminal"] is True

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        svc = make_mock_services()
        svc.llm.generate_json = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("fail")
        )
        node = make_synthesize_direct_node(svc)
        state = GraphState(query="Hi")

        result = await node(state)

        assert "Hello" in result["answer"]
        assert result["is_terminal"] is True
