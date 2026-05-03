"""Tests for the company setup subgraph."""

import pytest

from nuzantara_graph.subgraphs.company import make_company_subgraph, _identify_company_type
from nuzantara_schemas.domain.company import CompanyType
from nuzantara_schemas.state import GraphState
from helpers.mocks import make_mock_services


class TestIdentifyCompanyType:
    def test_pma_from_entities(self):
        state = GraphState(query="test", extracted_entities={"company_type": "pt_pma"})
        assert _identify_company_type(state) == CompanyType.PT_PMA

    def test_pma_from_query_foreign(self):
        state = GraphState(query="How to set up a foreign company in Bali?")
        assert _identify_company_type(state) == CompanyType.PT_PMA

    def test_pmdn_from_query(self):
        state = GraphState(query="Setting up a PT PMDN lokal")
        assert _identify_company_type(state) == CompanyType.PT_PMDN

    def test_cv_from_query(self):
        state = GraphState(query="How to register a CV in Jakarta?")
        assert _identify_company_type(state) == CompanyType.CV

    def test_firma_from_query(self):
        state = GraphState(query="What is a firma partnership?")
        assert _identify_company_type(state) == CompanyType.FIRMA

    def test_yayasan_from_query(self):
        state = GraphState(query="Setting up a foundation yayasan")
        assert _identify_company_type(state) == CompanyType.YAYASAN

    def test_default_is_pt_pma(self):
        state = GraphState(query="How to start a business in Indonesia?")
        assert _identify_company_type(state) == CompanyType.PT_PMA


class TestCompanySubgraphNode:
    @pytest.mark.asyncio
    async def test_produces_domain_document(self):
        svc = make_mock_services()
        node = make_company_subgraph(svc)
        state = GraphState(
            query="How to set up a PT PMA?",
            intent="business_setup",
            extracted_entities={"company_type": "pt_pma"},
        )
        result = await node(state)

        assert result["current_node"] == "subgraph_company"
        assert result["domain"] == "pt_pma"
        assert len(result["retrieved_documents"]) >= 1

        domain_doc = result["retrieved_documents"][0]
        assert domain_doc.source == "domain"
        assert "10,000,000,000" in domain_doc.content  # IDR 10B
        assert domain_doc.score == 0.95

    @pytest.mark.asyncio
    async def test_includes_capital_requirements(self):
        svc = make_mock_services()
        node = make_company_subgraph(svc)
        state = GraphState(
            query="PT PMA capital requirements",
            extracted_entities={"company_type": "pt_pma"},
        )
        result = await node(state)
        content = result["retrieved_documents"][0].content
        assert "10,000,000,000" in content
        assert "1,100,000" in content  # min investment USD

    @pytest.mark.asyncio
    async def test_cv_has_no_minimum_capital(self):
        svc = make_mock_services()
        node = make_company_subgraph(svc)
        state = GraphState(query="How to set up a CV in Bali?")
        result = await node(state)
        # CV query doesn't contain "foreign" so default is PT PMA
        # but let's test with explicit entity
        state2 = GraphState(
            query="CV registration",
            extracted_entities={"company_type": "cv"},
        )
        result2 = await node(state2)
        assert result2["domain"] == "cv"
        assert "No minimum capital" in result2["retrieved_documents"][0].content

    @pytest.mark.asyncio
    async def test_queries_kg_for_kbli(self):
        svc = make_mock_services(
            kg_entities=[{"entity_id": "kbli:56101", "label": "Restaurant"}],
        )
        node = make_company_subgraph(svc)
        state = GraphState(
            query="PT PMA for restaurant",
            extracted_entities={
                "company_type": "pt_pma",
                "kbli_codes": ["56101"],
            },
        )
        result = await node(state)
        assert len(result["kg_entities"]) >= 1
