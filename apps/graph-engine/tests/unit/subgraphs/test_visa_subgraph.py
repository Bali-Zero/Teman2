"""Tests for the visa/immigration subgraph."""

import pytest

from nuzantara_graph.subgraphs.visa import make_visa_subgraph, _identify_visa_type
from nuzantara_schemas.domain.visa import VisaType
from nuzantara_schemas.state import GraphState
from helpers.mocks import make_mock_services


class TestIdentifyVisaType:
    def test_kitas_from_entities(self):
        state = GraphState(query="test", extracted_entities={"visa_type": "kitas"})
        assert _identify_visa_type(state) == VisaType.KITAS

    def test_kitap_from_query(self):
        state = GraphState(query="How to get a permanent stay permit KITAP?")
        assert _identify_visa_type(state) == VisaType.KITAP

    def test_voa_from_query(self):
        state = GraphState(query="Visa on arrival for tourists")
        assert _identify_visa_type(state) == VisaType.VOA

    def test_b211a_from_query(self):
        state = GraphState(query="B211A social visa requirements")
        assert _identify_visa_type(state) == VisaType.B211A

    def test_second_home_from_query(self):
        state = GraphState(query="Indonesia second home visa for retirees")
        assert _identify_visa_type(state) == VisaType.SECOND_HOME

    def test_work_permit_implies_kitas(self):
        state = GraphState(query="How to get a work permit in Indonesia?")
        assert _identify_visa_type(state) == VisaType.KITAS

    def test_default_is_kitas(self):
        state = GraphState(query="What are the visa requirements?")
        assert _identify_visa_type(state) == VisaType.KITAS


class TestVisaSubgraphNode:
    @pytest.mark.asyncio
    async def test_produces_domain_document(self):
        svc = make_mock_services()
        node = make_visa_subgraph(svc)
        state = GraphState(
            query="KITAS requirements for work",
            intent="visa",
            extracted_entities={"visa_type": "kitas"},
        )
        result = await node(state)

        assert result["current_node"] == "subgraph_visa"
        assert result["domain"] == "kitas"
        assert len(result["retrieved_documents"]) >= 1

        domain_doc = result["retrieved_documents"][0]
        assert "KITAS" in domain_doc.content
        assert "12 months" in domain_doc.content
        assert "RPTKA" in domain_doc.content
        assert domain_doc.source == "domain"

    @pytest.mark.asyncio
    async def test_voa_no_sponsor_required(self):
        svc = make_mock_services()
        node = make_visa_subgraph(svc)
        state = GraphState(
            query="Visa on arrival Indonesia",
            extracted_entities={"visa_type": "voa"},
        )
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "Sponsor Required: No" in content
        assert "30 days" in content or "1 months" in content

    @pytest.mark.asyncio
    async def test_costs_included(self):
        svc = make_mock_services()
        node = make_visa_subgraph(svc)
        state = GraphState(
            query="KITAS cost",
            extracted_entities={"visa_type": "kitas"},
        )
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "USD" in content
