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
