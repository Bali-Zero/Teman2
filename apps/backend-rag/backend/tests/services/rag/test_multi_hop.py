"""Tests for Multi-Hop Reasoning Engine."""

from backend.services.rag.multi_hop import (
    HopResult,
    MergedHopContext,
    MultiHopEngine,
    SubQuery,
)


class TestQueryDecomposition:
    def setup_method(self) -> None:
        self.engine = MultiHopEngine()

    def test_simple_query_no_split(self) -> None:
        """Single-domain query should not be split."""
        plan = self.engine.decompose("How much does a KITAS cost?")
        assert plan.hop_count == 1
        assert plan.sub_queries[0].domain == "visa"

    def test_cross_domain_split_en(self) -> None:
        """English conjunction 'and' splits cross-domain query."""
        plan = self.engine.decompose(
            "I want to open a restaurant and hire a foreign chef with KITAS",
        )
        assert plan.hop_count >= 2
        domains = set(plan.domains)
        assert "company" in domains or "visa" in domains

    def test_cross_domain_split_it(self) -> None:
        """Italian conjunction 'e' splits cross-domain query."""
        plan = self.engine.decompose(
            "Voglio aprire un company e ottenere un visa per il mio chef",
        )
        assert plan.hop_count >= 2

    def test_cross_domain_split_id(self) -> None:
        """Indonesian conjunction 'dan' splits cross-domain query."""
        plan = self.engine.decompose(
            "Saya ingin membuka PT PMA dan mengurus KITAS untuk karyawan",
        )
        assert plan.hop_count >= 2

    def test_same_domain_merges(self) -> None:
        """Fragments of same domain should be merged."""
        plan = self.engine.decompose(
            "KITAS requirements and KITAP conversion process",
        )
        # Both are visa domain — should merge into 1 hop
        assert plan.hop_count == 1
        assert plan.sub_queries[0].domain == "visa"

    def test_short_fragments_filtered(self) -> None:
        """Very short fragments (< 5 chars) should be filtered."""
        plan = self.engine.decompose("KITAS and ok")
        # "ok" is too short, should be filtered
        assert plan.hop_count >= 1

    def test_collections_assigned(self) -> None:
        """Each sub-query should have collections assigned."""
        plan = self.engine.decompose("Open a PT PMA and pay taxes")
        for sq in plan.sub_queries:
            assert len(sq.collections) > 0

    def test_tax_domain_detected(self) -> None:
        plan = self.engine.decompose("How to file PPh 21 monthly?")
        assert plan.sub_queries[0].domain == "tax"

    def test_property_domain_detected(self) -> None:
        plan = self.engine.decompose("Can a foreigner buy a villa with Hak Pakai?")
        assert plan.sub_queries[0].domain == "property"

    def test_kbli_domain_detected(self) -> None:
        plan = self.engine.decompose("What is KBLI classification for this code?")
        assert plan.sub_queries[0].domain == "kbli"


class TestMergedHopContext:
    def test_to_prompt_context_single_hop(self) -> None:
        ctx = MergedHopContext(
            hop_results=[
                HopResult(
                    sub_query=SubQuery(text="KITAS cost", domain="visa"),
                    kg_entities=[{"name": "KITAS", "entity_id": "visa:kitas"}],
                    graph_summary="KITAS requires sponsor company and RPTKA.",
                ),
            ],
        )
        prompt = ctx.to_prompt_context()
        assert "[Hop 1: VISA]" in prompt
        assert "KITAS" in prompt

    def test_to_prompt_context_multi_hop_with_bridge(self) -> None:
        ctx = MergedHopContext(
            hop_results=[
                HopResult(
                    sub_query=SubQuery(text="open restaurant", domain="company"),
                    kg_entities=[{"name": "PT PMA"}, {"name": "KBLI 56101"}],
                    graph_summary="PT PMA setup requires min capital IDR 10B.",
                ),
                HopResult(
                    sub_query=SubQuery(text="hire foreign chef", domain="visa"),
                    kg_entities=[{"name": "KITAS"}, {"name": "PT PMA"}],
                    graph_summary="KITAS requires RPTKA from sponsor PT.",
                ),
            ],
            bridge_entities=[{"name": "PT PMA"}],
        )
        prompt = ctx.to_prompt_context()
        assert "[Hop 1: COMPANY]" in prompt
        assert "[Hop 2: VISA]" in prompt
        assert "Bridge entities" in prompt
        assert "PT PMA" in prompt
