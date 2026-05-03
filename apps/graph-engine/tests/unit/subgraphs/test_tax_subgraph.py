"""Tests for the tax compliance subgraph."""

import pytest

from nuzantara_graph.subgraphs.tax import make_tax_subgraph, _identify_tax_types
from nuzantara_schemas.domain.tax import TaxType
from nuzantara_schemas.state import GraphState
from helpers.mocks import make_mock_services


class TestIdentifyTaxTypes:
    def test_ppn_from_query(self):
        state = GraphState(query="What is PPN VAT rate in Indonesia?")
        types = _identify_tax_types(state)
        assert TaxType.PPN in types

    def test_pph_21_from_query(self):
        state = GraphState(query="PPh 21 employee withholding calculation")
        types = _identify_tax_types(state)
        assert TaxType.PPH_21 in types

    def test_bphtb_from_query(self):
        state = GraphState(query="How much is BPHTB property tax?")
        types = _identify_tax_types(state)
        assert TaxType.BPHTB in types

    def test_multiple_taxes_from_query(self):
        state = GraphState(query="PPh 21 and PPN obligations for PT PMA")
        types = _identify_tax_types(state)
        assert TaxType.PPH_21 in types
        assert TaxType.PPN in types

    def test_default_returns_common_set(self):
        state = GraphState(query="What taxes does a company pay in Indonesia?")
        types = _identify_tax_types(state)
        assert len(types) >= 2  # Should return PPH_25, PPH_21, PPN


class TestTaxSubgraphNode:
    @pytest.mark.asyncio
    async def test_produces_domain_document(self):
        svc = make_mock_services()
        node = make_tax_subgraph(svc)
        state = GraphState(
            query="PPN VAT rate Indonesia",
            intent="tax",
        )
        result = await node(state)

        assert result["current_node"] == "subgraph_tax"
        assert len(result["retrieved_documents"]) >= 1

        domain_doc = result["retrieved_documents"][0]
        assert "PPN" in domain_doc.content or "VAT" in domain_doc.content
        assert "11%" in domain_doc.content
        assert domain_doc.source == "domain"

    @pytest.mark.asyncio
    async def test_pph_21_brackets_included(self):
        svc = make_mock_services()
        node = make_tax_subgraph(svc)
        state = GraphState(
            query="PPh 21 tax brackets for employees",
            extracted_entities={"tax_type": "pph_21"},
        )
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "5.0%" in content
        assert "15.0%" in content
        assert "25.0%" in content
        assert "30.0%" in content
        assert "Progressive brackets" in content

    @pytest.mark.asyncio
    async def test_bphtb_one_time(self):
        svc = make_mock_services()
        node = make_tax_subgraph(svc)
        state = GraphState(query="BPHTB property transaction tax")
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "5%" in content
        assert "one-time" in content

    @pytest.mark.asyncio
    async def test_vat_threshold_included(self):
        svc = make_mock_services()
        node = make_tax_subgraph(svc)
        state = GraphState(query="When do I need to register for PPN?")
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "4,800,000,000" in content
