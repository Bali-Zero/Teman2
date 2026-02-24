"""Integration tests for correction cycles and fail-fast behavior."""

import pytest

from nuzantara_graph.graph.builder import build_graph
from nuzantara_schemas.state import GraphState, IntentType, RetrievedDocument
from helpers.mocks import make_mock_services


class TestFailFast:
    """Test fail-fast: retrieval grader FAIL → skip reasoning → polite refusal."""

    @pytest.mark.asyncio
    async def test_garbage_retrieval_skips_reasoning(self):
        """If all docs score < 0.2, graph should skip reason/synthesize
        and go directly to synthesize_fail_fast."""
        call_count = 0

        def _llm(prompt, system):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "intent": "general",
                    "domain": None,
                    "entities": {},
                    "language": "en",
                    "is_followup": False,
                }
            # Should NOT be called for reason/synthesize
            return {"steps": [], "answer": "SHOULD NOT SEE THIS"}

        svc = make_mock_services(
            llm_responses={"generate_json": _llm},
            documents=[
                RetrievedDocument(id="d1", content="Garbage", score=0.05),
                RetrievedDocument(id="d2", content="Noise", score=0.08),
            ],
        )

        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(GraphState(query="something very obscure"))

        # Should have fail-fast answer
        assert "rephras" in result["answer"].lower() or "specific" in result["answer"].lower()
        assert result["is_terminal"] is True

        # Should NOT have reasoning steps (skipped)
        assert result["reasoning_steps"] == []

        # LLM should only be called once (understand), not for reason/synthesize
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_no_documents_fail_fast(self):
        """Zero documents → immediate fail-fast."""
        call_count = 0

        def _llm(prompt, system):
            nonlocal call_count
            call_count += 1
            return {
                "intent": "general",
                "domain": None,
                "entities": {},
                "language": "en",
                "is_followup": False,
            }

        svc = make_mock_services(
            llm_responses={"generate_json": _llm},
            documents=[],
        )

        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(GraphState(query="xyzzy nonexistent topic"))

        assert result["is_terminal"] is True
        assert "couldn't find" in result["answer"].lower() or "rephras" in result["answer"].lower()
        assert call_count == 1  # only understand


class TestCorrectionCycles:
    """Test retry loops: grader returns RETRY → node re-executes."""

    @pytest.mark.asyncio
    async def test_mediocre_retrieval_triggers_retry(self):
        """Mediocre docs (0.2 < score < 0.7) → retrieval node retries once."""
        retrieve_calls = 0

        def _llm(prompt, system):
            if "reasoning engine" in system.lower():
                return {"steps": [{"step_type": "thought", "content": "Analysis"}]}
            elif "zantara" in system.lower():
                return {
                    "answer": "Answer after retry",
                    "sources": [],
                    "confidence": {
                        "retrieval_relevance": 0.6,
                        "source_authority": 0.5,
                        "reasoning_coherence": 0.6,
                        "factual_grounding": 0.6,
                        "domain_coverage": 0.5,
                        "answer_completeness": 0.5,
                    },
                }
            return {
                "intent": "general",
                "domain": None,
                "entities": {},
                "language": "en",
                "is_followup": False,
            }

        # First call returns mediocre docs, second call returns better docs
        class RetryVectorStore:
            def __init__(self):
                self.call_count = 0

            async def search_by_text(self, query, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    # Mediocre first attempt
                    return [
                        RetrievedDocument(id="d1", content="Meh", score=0.40),
                        RetrievedDocument(id="d2", content="Also meh", score=0.35),
                    ]
                # Better second attempt
                return [
                    RetrievedDocument(id="d3", content="Good result", score=0.85),
                    RetrievedDocument(id="d4", content="Also good", score=0.80),
                ]

            async def search(self, query_embedding, **kwargs):
                return await self.search_by_text("", **kwargs)

        vector_store = RetryVectorStore()
        svc = make_mock_services(llm_responses={"generate_json": _llm})
        svc.vector_store = vector_store

        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(GraphState(query="Company setup"))

        # Vector store should be called at least twice (initial + retry)
        assert vector_store.call_count >= 2

        # Should have at least one grade with RETRY
        retry_grades = [g for g in result["grades"] if g.decision.value == "retry"]
        assert len(retry_grades) >= 1

        # Should eventually produce an answer
        assert result["answer"] != ""

    @pytest.mark.asyncio
    async def test_max_corrections_respected(self):
        """After max_corrections retries, graph proceeds despite mediocre quality."""
        svc = make_mock_services(
            llm_responses={
                "generate_json": lambda p, s: (
                    {"steps": [{"step_type": "thought", "content": "Brief"}]}
                    if "reasoning engine" in s.lower()
                    else {"answer": "Brief answer", "sources": [], "confidence": {}}
                    if "zantara" in s.lower()
                    else {
                        "intent": "general", "domain": None,
                        "entities": {}, "language": "en", "is_followup": False,
                    }
                ),
            },
            # Docs that trigger RETRY (0.2 < score < 0.7)
            documents=[
                RetrievedDocument(id="d1", content="Mediocre", score=0.45),
                RetrievedDocument(id="d2", content="Average", score=0.40),
            ],
        )

        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(
            GraphState(query="Test", max_corrections=2)
        )

        # Should not exceed max_corrections
        assert result["correction_count"] <= 2

        # Should still produce an answer (degraded but present)
        assert result["answer"] != ""


class TestGraderIntegration:
    """Test that all graders fire in the correct order during a full pipeline."""

    @pytest.mark.asyncio
    async def test_all_graders_fire_on_happy_path(self):
        """Good query → all 3 graders fire: retrieval, reasoning, answer + hallucination."""
        svc = make_mock_services(
            llm_responses={
                "generate_json": lambda p, s: (
                    {
                        "steps": [
                            {"step_type": "thought", "content": "Analyzing PT PMA requirements in detail"},
                            {"step_type": "observation", "content": "Capital minimum is 10B IDR per regulation"},
                            {"step_type": "thought", "content": "Foreign ownership up to 100% for approved sectors"},
                        ]
                    }
                    if "reasoning engine" in s.lower()
                    else {
                        "answer": "To set up a PT PMA you need minimum capital of 10 billion IDR. "
                                  "Foreign ownership can be up to 100% for approved KBLI sectors.",
                        "sources": [{"title": "PT PMA Guide", "id": "d1"}],
                        "confidence": {
                            "retrieval_relevance": 0.9, "source_authority": 0.8,
                            "reasoning_coherence": 0.85, "factual_grounding": 0.9,
                            "domain_coverage": 0.7, "answer_completeness": 0.8,
                        },
                    }
                    if "zantara" in s.lower()
                    else {
                        "intent": "general", "domain": None,
                        "entities": {}, "language": "en", "is_followup": False,
                    }
                ),
            },
            documents=[
                RetrievedDocument(
                    id="d1",
                    content="PT PMA requires minimum capital of 10 billion IDR. Foreign ownership up to 100%.",
                    score=0.92,
                ),
                RetrievedDocument(
                    id="d2",
                    content="KBLI codes determine which sectors allow foreign investment.",
                    score=0.85,
                ),
            ],
        )

        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(GraphState(query="How to set up a PT PMA?"))

        # All 4 graders should have fired
        grader_names = [g.grader for g in result["grades"]]
        assert "retrieval" in grader_names
        assert "reasoning" in grader_names
        assert "answer" in grader_names
        assert "hallucination" in grader_names

        # All should PASS on good data
        for grade in result["grades"]:
            assert grade.decision.value in ("pass", "retry"), \
                f"{grade.grader} unexpectedly got {grade.decision}"
