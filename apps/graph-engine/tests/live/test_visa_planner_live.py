"""Live-tier tests for the visa multi-step planner.

These tests call a real Gemini gateway. They are skipped unless
``NUZANTARA_GOOGLE_API_KEY`` (or ``GOOGLE_API_KEY``) is set. Run them
explicitly with:

    pytest tests/live -m live -v

The goal is to verify that the planner's prompts still elicit well-
formed JSON and citation-friendly output from a real model, not to
replace the fast unit tier.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


class TestDecomposeLive:
    @pytest.mark.asyncio
    async def test_decompose_simple_query(self, live_services):
        """decompose should return at least one well-typed sub-question."""
        from nuzantara_graph.subgraphs.visa.decompose import decompose

        sub_qs = await decompose(
            "What are the KITAS requirements for a foreign investor?",
            live_services.llm,
        )
        assert len(sub_qs) >= 1
        assert all(sq.text.strip() for sq in sub_qs)
        assert all(sq.idx >= 0 for sq in sub_qs)
        # No back-edges
        for sq in sub_qs:
            for dep in sq.depends_on:
                assert dep < sq.idx

    @pytest.mark.asyncio
    async def test_decompose_multi_hop_produces_dag(self, live_services):
        """A multi-hop query should produce at least 2 sub-questions with
        at least one non-trivial depends_on edge OR return a sensible
        single-hop fallback."""
        from nuzantara_graph.subgraphs.visa.decompose import decompose

        sub_qs = await decompose(
            "I overstayed 3 days and then left Indonesia. Can I come back on an e-visa?",
            live_services.llm,
        )
        assert len(sub_qs) >= 1
        # Either the model decomposes into a DAG with edges, or it
        # returns a single atomic sub-question. Both are acceptable.
        has_edges = any(sq.depends_on for sq in sub_qs)
        assert has_edges or len(sub_qs) == 1


class TestComposeLive:
    @pytest.mark.asyncio
    async def test_composer_respects_citation_format(self, live_services):
        """Given chunks with stable doc_ids, the composer's output should
        contain at least one valid citation after enforcement."""
        from nuzantara_graph.subgraphs.visa.compose import compose
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion

        chunk = Chunk(
            doc_id="kitas_guide_2024",
            span_start=0,
            span_end=200,
            score=0.95,
            content=(
                "A KITAS (Kartu Izin Tinggal Terbatas) is a temporary stay "
                "permit valid for 12 months and extendable annually. It "
                "requires a sponsoring PT PMA and an approved RPTKA."
            ),
        )
        ev = NodeEvidence(
            sub_question=SubQuestion(idx=0, text="What is a KITAS?", depends_on=[]),
            chunks=[chunk],
            answer_fragment="",
        )
        answer = await compose(
            "How long is a KITAS valid and what do I need?",
            [ev],
            [],
            live_services.llm,
        )

        # The enforcer must either include a citation or refuse — never
        # silently pass through uncited content.
        assert (
            "kitas_guide_2024" in answer
            or "unable to cite" in answer.lower()
            or "cannot produce" in answer.lower()
        )
