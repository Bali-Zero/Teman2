"""Integration tests — full graph execution end-to-end with mocked services."""

import pytest

from nuzantara_graph.graph.builder import build_graph
from nuzantara_schemas.state import GraphState, IntentType, RetrievedDocument
from helpers.mocks import make_mock_services


class TestFullGraphExecution:
    """End-to-end graph execution tests.

    These compile and invoke the full graph with mock services,
    verifying that state flows correctly through all nodes.
    """

    @pytest.mark.asyncio
    async def test_general_query_full_pipeline(self):
        """General query: understand → retrieve → grade → reason → grade → synthesize → grade → halluc → END."""
        svc = make_mock_services(
            llm_responses={
                "generate_json": _cycling_llm_response(),
            },
            documents=[
                RetrievedDocument(id="d1", content="PT PMA requires 10B IDR capital", score=0.9),
                RetrievedDocument(id="d2", content="Foreign ownership up to 100%", score=0.85),
            ],
        )

        graph = build_graph(services=svc)
        compiled = graph.compile()

        initial_state = GraphState(query="How do I set up a PT PMA in Bali?")
        result = await compiled.ainvoke(initial_state)

        # Should have flowed through understand
        assert result["current_node"] == "grade_hallucination"  # last node is hallucination grader

        # Should have retrieved documents
        assert len(result["retrieved_documents"]) == 2

        # Should have reasoning steps
        assert len(result["reasoning_steps"]) > 0

        # Should have an answer
        assert result["answer"] != ""

        # Confidence should be set
        assert result["confidence"].overall > 0

    @pytest.mark.asyncio
    async def test_greeting_direct_path(self):
        """Greeting: understand → synthesize_direct → END."""
        call_count = 0

        def _greeting_llm(prompt, system):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # understand node
                return {
                    "intent": "greeting",
                    "domain": None,
                    "entities": {},
                    "language": "en",
                    "is_followup": False,
                }
            else:
                # synthesize_direct node
                return {
                    "answer": "Hello! I'm Zantara. How can I help you?",
                }

        svc = make_mock_services(llm_responses={"generate_json": _greeting_llm})

        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(GraphState(query="Hello!"))

        assert result["intent"] == IntentType.GREETING
        assert "Hello" in result["answer"] or "help" in result["answer"].lower()
        assert result["is_terminal"] is True
        # Should NOT have gone through retrieve/reason
        assert result["retrieved_documents"] == []
        assert result["reasoning_steps"] == []

    @pytest.mark.asyncio
    async def test_visa_query_routes_through_subgraph(self):
        """Visa query: understand → subgraph_visa (placeholder) → reason → ... → END."""
        call_count = 0

        def _visa_llm(prompt, system):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "intent": "visa",
                    "domain": "kitas",
                    "entities": {"visa_type": "kitas"},
                    "language": "en",
                    "is_followup": False,
                }
            elif "reasoning engine" in system.lower():
                return {
                    "steps": [
                        {"step_type": "thought", "content": "KITAS requires sponsor"},
                    ]
                }
            elif "zantara" in system.lower():
                return {
                    "answer": "KITAS requires a sponsor company in Indonesia.",
                    "sources": [{"title": "Visa Guide", "id": "v1"}],
                    "confidence": {
                        "retrieval_relevance": 0.8,
                        "source_authority": 0.7,
                        "reasoning_coherence": 0.8,
                        "factual_grounding": 0.8,
                        "domain_coverage": 0.9,
                        "answer_completeness": 0.7,
                    },
                }

        svc = make_mock_services(llm_responses={"generate_json": _visa_llm})

        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(GraphState(query="What are KITAS requirements?"))

        assert result["intent"] == IntentType.VISA
        assert result["answer"] != ""

    @pytest.mark.asyncio
    async def test_state_preserved_through_graph(self):
        """Verify that immutable fields (run_id, query, user_id) are preserved."""
        svc = make_mock_services(
            llm_responses={"generate_json": _cycling_llm_response()},
            documents=[RetrievedDocument(id="d1", content="Test", score=0.8)],
        )

        graph = build_graph(services=svc)
        compiled = graph.compile()

        initial = GraphState(
            query="Test query",
            user_id="user_42",
            channel="telegram",
        )
        result = await compiled.ainvoke(initial)

        assert result["run_id"] == initial.run_id
        assert result["query"] == "Test query"
        assert result["user_id"] == "user_42"
        assert result["channel"] == "telegram"


def _cycling_llm_response():
    """Returns a callable that produces different responses based on call context."""
    call_count = 0

    def _respond(prompt, system):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # understand
            return {
                "intent": "general",
                "domain": None,
                "entities": {},
                "language": "en",
                "is_followup": False,
            }
        elif "reasoning engine" in system.lower():
            # reason node (system prompt starts with "reasoning engine")
            return {
                "steps": [
                    {"step_type": "thought", "content": "Analyzing the query"},
                    {"step_type": "observation", "content": "Found relevant info"},
                ]
            }
        elif "zantara" in system.lower():
            # synthesize node (system prompt mentions "Zantara")
            return {
                "answer": "Here is the answer to your question.",
                "sources": [{"title": "Source", "id": "s1"}],
                "confidence": {
                    "retrieval_relevance": 0.8,
                    "source_authority": 0.7,
                    "reasoning_coherence": 0.8,
                    "factual_grounding": 0.75,
                    "domain_coverage": 0.7,
                    "answer_completeness": 0.7,
                },
            }

    return _respond
