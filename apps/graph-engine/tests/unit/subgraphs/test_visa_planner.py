"""Tests for the visa multi-step planner."""

from __future__ import annotations

import pytest


@pytest.mark.unit
class TestPlannerTypes:
    def test_sub_question_schema(self):
        from nuzantara_graph.subgraphs.visa.types import SubQuestion

        sq = SubQuestion(idx=0, text="What is KITAS?", needs_kb=True, depends_on=[])
        assert sq.idx == 0
        assert sq.needs_kb is True
        assert sq.depends_on == []

    def test_chunk_schema(self):
        from nuzantara_graph.subgraphs.visa.types import Chunk

        c = Chunk(
            doc_id="kitas_guide_2024",
            span_start=0,
            span_end=200,
            score=0.85,
            content="KITAS is a temporary stay permit...",
        )
        assert c.doc_id == "kitas_guide_2024"
        assert c.span_end == 200

    def test_chunk_citation_format(self):
        from nuzantara_graph.subgraphs.visa.types import Chunk

        c = Chunk(
            doc_id="visa_2024",
            span_start=10,
            span_end=50,
            score=0.9,
            content="abc",
        )
        assert c.citation() == "[visa_2024:10-50]"

    def test_node_evidence_empty(self):
        from nuzantara_graph.subgraphs.visa.types import NodeEvidence, SubQuestion

        sq = SubQuestion(idx=0, text="q", needs_kb=True, depends_on=[])
        ev = NodeEvidence(sub_question=sq, chunks=[], answer_fragment="", grounded=False)
        assert ev.chunks == []
        assert ev.grounded is False

    def test_planner_state_budget(self):
        from nuzantara_graph.subgraphs.visa.types import PlannerState

        s = PlannerState(query="q", max_llm_calls=5, llm_call_count=3)
        assert s.budget_remaining() == 2
        assert s.can_call_llm() is True

        s2 = PlannerState(query="q", max_llm_calls=5, llm_call_count=5)
        assert s2.can_call_llm() is False


@pytest.mark.unit
class TestB211Rewrite:
    def test_b211_substring_rewritten(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms("Is the B211 visa still valid?")
        assert "B211" not in rewritten
        assert "KITAS" in rewritten or "e-visa" in rewritten
        assert note is not None
        assert note.doc_id == "SYSTEM:b211_rewrite"

    def test_b211a_variant_rewritten(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms("Requirements for B211A")
        assert "B211A" not in rewritten
        assert note is not None

    def test_social_visit_visa_rewritten(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms(
            "I want a social visit visa for 30 days"
        )
        assert note is not None
        lower = rewritten.lower()
        # either the phrase was replaced or the replacement tokens are present
        assert "social visit visa" not in lower or "e-visa" in lower or "kitas" in lower

    def test_no_match_pass_through(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms("KITAS for investor")
        assert rewritten == "KITAS for investor"
        assert note is None


@pytest.mark.unit
class TestDecompose:
    @pytest.mark.asyncio
    async def test_decompose_returns_sub_questions(self):
        from helpers.mocks import MockLLMGateway

        from nuzantara_graph.subgraphs.visa.decompose import decompose

        llm = MockLLMGateway(
            responses={
                "generate_json": {
                    "sub_questions": [
                        {"idx": 0, "text": "What is a KITAS?", "needs_kb": True, "depends_on": []},
                        {"idx": 1, "text": "How to apply?", "needs_kb": True, "depends_on": [0]},
                    ]
                }
            }
        )

        sub_qs = await decompose("Tell me about KITAS application", llm)
        assert len(sub_qs) == 2
        assert sub_qs[0].text == "What is a KITAS?"
        assert sub_qs[1].depends_on == [0]

    @pytest.mark.asyncio
    async def test_decompose_truncates_to_max_5(self):
        from helpers.mocks import MockLLMGateway

        from nuzantara_graph.subgraphs.visa.decompose import decompose

        llm = MockLLMGateway(
            responses={
                "generate_json": {
                    "sub_questions": [
                        {"idx": i, "text": f"Q{i}", "needs_kb": True, "depends_on": []}
                        for i in range(10)
                    ]
                }
            }
        )

        sub_qs = await decompose("x", llm)
        assert len(sub_qs) == 5

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_bad_json(self):
        from helpers.mocks import MockLLMGateway

        from nuzantara_graph.subgraphs.visa.decompose import decompose

        class BadJSONLLM(MockLLMGateway):
            async def generate_json(self, prompt, system="", **kw):
                self._call_count += 1
                raise ValueError("invalid JSON")

        llm = BadJSONLLM()
        sub_qs = await decompose("How to get KITAS?", llm)
        assert len(sub_qs) == 1
        assert sub_qs[0].text == "How to get KITAS?"
        assert sub_qs[0].needs_kb is True

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_missing_api_key(self):
        from helpers.mocks import MockLLMGateway

        from nuzantara_graph.subgraphs.visa.decompose import decompose

        class NoKeyLLM(MockLLMGateway):
            async def generate_json(self, prompt, system="", **kw):
                self._call_count += 1
                raise ValueError("NUZANTARA_GOOGLE_API_KEY is required for LLM calls")

        sub_qs = await decompose("Can I overstay?", NoKeyLLM())
        assert len(sub_qs) == 1

    @pytest.mark.asyncio
    async def test_decompose_rejects_empty(self):
        from helpers.mocks import MockLLMGateway

        from nuzantara_graph.subgraphs.visa.decompose import decompose

        llm = MockLLMGateway(responses={"generate_json": {"sub_questions": []}})
        sub_qs = await decompose("q", llm)
        assert len(sub_qs) == 1
        assert sub_qs[0].text == "q"
