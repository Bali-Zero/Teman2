"""Tests for the understand node."""

import pytest

from nuzantara_graph.nodes.understand import make_understand_node
from nuzantara_schemas.state import GraphState, IntentType
from helpers.mocks import make_mock_services


class TestUnderstandNode:
    @pytest.mark.asyncio
    async def test_classifies_business_setup(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "intent": "business_setup",
                "domain": "pt_pma",
                "entities": {"company_type": "pt_pma", "location": "Bali"},
                "language": "en",
                "is_followup": False,
            }
        })
        node = make_understand_node(svc)
        state = GraphState(query="How do I set up a PT PMA in Bali?")

        result = await node(state)

        assert result["intent"] == IntentType.BUSINESS_SETUP
        assert result["domain"] == "pt_pma"
        assert result["extracted_entities"]["company_type"] == "pt_pma"
        assert result["detected_language"] == "en"
        assert result["is_followup"] is False

    @pytest.mark.asyncio
    async def test_classifies_visa(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "intent": "visa",
                "domain": "kitas",
                "entities": {"visa_type": "kitas"},
                "language": "en",
                "is_followup": False,
            }
        })
        node = make_understand_node(svc)
        state = GraphState(query="What are the KITAS requirements?")

        result = await node(state)

        assert result["intent"] == IntentType.VISA
        assert result["domain"] == "kitas"

    @pytest.mark.asyncio
    async def test_classifies_greeting(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "intent": "greeting",
                "domain": None,
                "entities": {},
                "language": "en",
                "is_followup": False,
            }
        })
        node = make_understand_node(svc)
        state = GraphState(query="Hello!")

        result = await node(state)

        assert result["intent"] == IntentType.GREETING

    @pytest.mark.asyncio
    async def test_invalid_intent_defaults_to_general(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "intent": "nonexistent_intent",
                "domain": None,
                "entities": {},
                "language": "en",
                "is_followup": False,
            }
        })
        node = make_understand_node(svc)
        state = GraphState(query="Something weird")

        result = await node(state)

        assert result["intent"] == IntentType.GENERAL

    @pytest.mark.asyncio
    async def test_handles_llm_failure_gracefully(self):
        svc = make_mock_services()
        # Override to raise an error
        svc.llm.generate_json = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("LLM down")
        )
        node = make_understand_node(svc)
        state = GraphState(query="Test query")

        result = await node(state)

        assert result["intent"] == IntentType.GENERAL
        assert "error" in result

    @pytest.mark.asyncio
    async def test_detects_followup(self):
        svc = make_mock_services(llm_responses={
            "generate_json": {
                "intent": "followup",
                "domain": "pt_pma",
                "entities": {},
                "language": "en",
                "is_followup": True,
            }
        })
        node = make_understand_node(svc)
        state = GraphState(query="And what about the minimum capital?")

        result = await node(state)

        assert result["is_followup"] is True
