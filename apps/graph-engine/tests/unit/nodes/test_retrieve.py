"""Tests for the retrieve node."""

import pytest

from nuzantara_graph.nodes.retrieve import make_retrieve_node
from nuzantara_schemas.grading import GradeDecision, GradeResult
from nuzantara_schemas.state import GraphState, RetrievedDocument
from helpers.mocks import make_mock_services


class TestRetrieveNode:
    @pytest.mark.asyncio
    async def test_retrieves_documents(self):
        docs = [
            RetrievedDocument(id="d1", content="PT PMA setup guide", score=0.9),
            RetrievedDocument(id="d2", content="Business license info", score=0.8),
        ]
        svc = make_mock_services(documents=docs)
        node = make_retrieve_node(svc)
        state = GraphState(query="How to set up a PT PMA?")

        result = await node(state)

        assert len(result["retrieved_documents"]) == 2
        assert result["retrieved_documents"][0].id == "d1"
        assert result["current_node"] == "retrieve"

    @pytest.mark.asyncio
    async def test_enriches_query_with_entities(self):
        docs = [RetrievedDocument(id="d1", content="Test", score=0.8)]
        svc = make_mock_services(documents=docs)
        node = make_retrieve_node(svc)
        state = GraphState(
            query="How to set up a company?",
            extracted_entities={"company_type": "pt_pma", "location": "Bali"},
        )

        result = await node(state)

        assert len(result["retrieved_documents"]) == 1

    @pytest.mark.asyncio
    async def test_uses_retry_hint(self):
        docs = [RetrievedDocument(id="d1", content="Focused result", score=0.85)]
        svc = make_mock_services(documents=docs)
        node = make_retrieve_node(svc)
        state = GraphState(
            query="Company setup",
            grades=[GradeResult(
                grader="retrieval",
                decision=GradeDecision.RETRY,
                score=0.4,
                retry_hint="Focus on PT PMA capital requirements",
            )],
        )

        result = await node(state)

        assert len(result["retrieved_documents"]) == 1

    @pytest.mark.asyncio
    async def test_retrieves_kg_entities(self):
        docs = [RetrievedDocument(id="d1", content="Test", score=0.8)]
        kg_entities = [
            {"entity_id": "kbli:56101", "label": "Restoran", "description": "Restaurant business"},
        ]
        kg_rels = [
            {"source": "kbli:56101", "target": "sektor:I", "type": "belongs_to"},
        ]
        svc = make_mock_services(documents=docs, kg_entities=kg_entities, kg_relationships=kg_rels)
        node = make_retrieve_node(svc)
        state = GraphState(
            query="KBLI for restaurant",
            extracted_entities={"kbli_code": "56101"},
        )

        result = await node(state)

        assert len(result["kg_entities"]) == 1
        assert result["kg_entities"][0]["entity_id"] == "kbli:56101"

    @pytest.mark.asyncio
    async def test_handles_vector_store_failure(self):
        svc = make_mock_services()
        svc.vector_store.search_by_text = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("Qdrant down")
        )
        node = make_retrieve_node(svc)
        state = GraphState(query="Test")

        result = await node(state)

        assert result["retrieved_documents"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        svc = make_mock_services(documents=[])
        node = make_retrieve_node(svc)
        state = GraphState(query="Something obscure")

        result = await node(state)

        assert result["retrieved_documents"] == []
        assert result["kg_entities"] == []
