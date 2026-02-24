"""Integration tests for subgraph routing — full graph execution through domain subgraphs."""

import pytest

from nuzantara_graph.graph.builder import build_graph
from nuzantara_schemas.state import GraphState, IntentType
from helpers.mocks import make_mock_services


def _make_subgraph_llm(intent: str, domain: str | None = None):
    """Create an LLM mock that classifies to a specific intent, then reasons/synthesizes."""
    call_count = 0

    def _llm(prompt, system):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # understand node
            return {
                "intent": intent,
                "domain": domain,
                "entities": {},
                "language": "en",
                "is_followup": False,
            }
        elif "reasoning engine" in system.lower():
            return {
                "steps": [
                    {"step_type": "thought", "content": f"Analyzing {intent} query"},
                    {"step_type": "observation", "content": f"Found domain info for {domain or intent}"},
                ],
            }
        elif "zantara" in system.lower():
            return {
                "answer": f"Here is the answer about {intent}.",
                "sources": [{"title": "Domain Guide", "id": "d1"}],
                "confidence": {
                    "retrieval_relevance": 0.85,
                    "source_authority": 0.8,
                    "reasoning_coherence": 0.85,
                    "factual_grounding": 0.9,
                    "domain_coverage": 0.8,
                    "answer_completeness": 0.75,
                },
            }

    return _llm


class TestCompanySubgraphRouting:
    @pytest.mark.asyncio
    async def test_business_setup_routes_through_company(self):
        svc = make_mock_services(
            llm_responses={"generate_json": _make_subgraph_llm("business_setup", "pt_pma")},
        )
        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(
            GraphState(query="How to set up a PT PMA in Bali?")
        )

        assert result["intent"] == IntentType.BUSINESS_SETUP
        # Should have domain doc from subgraph
        domain_docs = [
            d for d in result["retrieved_documents"]
            if d.source == "domain"
        ]
        assert len(domain_docs) >= 1
        assert "PT_PMA" in domain_docs[0].content or "10,000,000,000" in domain_docs[0].content
        assert result["answer"] != ""


class TestVisaSubgraphRouting:
    @pytest.mark.asyncio
    async def test_visa_routes_through_visa_subgraph(self):
        svc = make_mock_services(
            llm_responses={"generate_json": _make_subgraph_llm("visa", "kitas")},
        )
        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(
            GraphState(query="What are KITAS requirements?")
        )

        assert result["intent"] == IntentType.VISA
        domain_docs = [d for d in result["retrieved_documents"] if d.source == "domain"]
        assert len(domain_docs) >= 1
        assert "KITAS" in domain_docs[0].content
        assert result["answer"] != ""


class TestPropertySubgraphRouting:
    @pytest.mark.asyncio
    async def test_property_routes_through_property_subgraph(self):
        svc = make_mock_services(
            llm_responses={"generate_json": _make_subgraph_llm("property", "hak_pakai")},
        )
        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(
            GraphState(query="How to buy property with hak pakai?")
        )

        assert result["intent"] == IntentType.PROPERTY
        domain_docs = [d for d in result["retrieved_documents"] if d.source == "domain"]
        assert len(domain_docs) >= 1
        assert result["answer"] != ""


class TestTaxSubgraphRouting:
    @pytest.mark.asyncio
    async def test_tax_routes_through_tax_subgraph(self):
        svc = make_mock_services(
            llm_responses={"generate_json": _make_subgraph_llm("tax", "ppn")},
        )
        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(
            GraphState(query="What is the PPN VAT rate?")
        )

        assert result["intent"] == IntentType.TAX
        domain_docs = [d for d in result["retrieved_documents"] if d.source == "domain"]
        assert len(domain_docs) >= 1
        assert result["answer"] != ""


class TestSubgraphOutputFlowsToReason:
    @pytest.mark.asyncio
    async def test_subgraph_docs_available_in_reasoning(self):
        """Verify that domain docs from subgraph are available when reason node runs."""
        svc = make_mock_services(
            llm_responses={"generate_json": _make_subgraph_llm("business_setup", "pt_pma")},
        )
        graph = build_graph(services=svc)
        compiled = graph.compile()

        result = await compiled.ainvoke(
            GraphState(query="How to set up PT PMA?")
        )

        # After full pipeline, should have both domain docs AND reasoning steps
        assert len(result["retrieved_documents"]) >= 1
        assert len(result["reasoning_steps"]) >= 1
        # Answer should be present (pipeline completed fully)
        assert result["answer"] != ""
