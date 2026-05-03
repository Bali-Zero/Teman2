"""Tests for the property acquisition subgraph."""

import pytest

from nuzantara_graph.subgraphs.property import make_property_subgraph, _identify_property_right
from nuzantara_schemas.domain.property import PropertyRight
from nuzantara_schemas.state import GraphState
from helpers.mocks import make_mock_services


class TestIdentifyPropertyRight:
    def test_hak_pakai_from_entities(self):
        state = GraphState(query="test", extracted_entities={"property_type": "hak_pakai"})
        assert _identify_property_right(state) == PropertyRight.HAK_PAKAI

    def test_hgb_from_query(self):
        state = GraphState(query="HGB land title for company")
        assert _identify_property_right(state) == PropertyRight.HGB

    def test_hak_milik_from_query(self):
        state = GraphState(query="Can foreigner get hak milik?")
        assert _identify_property_right(state) == PropertyRight.HAK_MILIK

    def test_strata_from_query(self):
        state = GraphState(query="Buying an apartment with strata title")
        assert _identify_property_right(state) == PropertyRight.STRATA_TITLE

    def test_leasehold_from_query(self):
        state = GraphState(query="Long term lease in Bali")
        assert _identify_property_right(state) == PropertyRight.LEASEHOLD

    def test_default_is_hak_pakai(self):
        state = GraphState(query="How to buy property in Bali as a foreigner?")
        assert _identify_property_right(state) == PropertyRight.HAK_PAKAI


class TestPropertySubgraphNode:
    @pytest.mark.asyncio
    async def test_produces_domain_document(self):
        svc = make_mock_services()
        node = make_property_subgraph(svc)
        state = GraphState(
            query="How to buy property in Bali with hak pakai?",
            intent="property",
        )
        result = await node(state)

        assert result["current_node"] == "subgraph_property"
        assert result["domain"] == "hak_pakai"
        assert len(result["retrieved_documents"]) >= 1

        domain_doc = result["retrieved_documents"][0]
        assert "HAK PAKAI" in domain_doc.content
        assert "Foreigner Eligible: Yes" in domain_doc.content
        assert "30 years" in domain_doc.content

    @pytest.mark.asyncio
    async def test_hak_milik_not_foreigner_eligible(self):
        svc = make_mock_services()
        node = make_property_subgraph(svc)
        state = GraphState(
            query="Can I get hak milik?",
            extracted_entities={"property_type": "hak_milik"},
        )
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "Foreigner Eligible: No" in content
        assert "Indonesian citizens ONLY" in content

    @pytest.mark.asyncio
    async def test_hgb_requires_pt(self):
        svc = make_mock_services()
        node = make_property_subgraph(svc)
        state = GraphState(
            query="HGB for my company",
            extracted_entities={"property_type": "hgb"},
        )
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "Requires PT company" in content

    @pytest.mark.asyncio
    async def test_bphtb_mentioned(self):
        svc = make_mock_services()
        node = make_property_subgraph(svc)
        state = GraphState(query="Buying property Bali hak pakai")
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "BPHTB" in content
