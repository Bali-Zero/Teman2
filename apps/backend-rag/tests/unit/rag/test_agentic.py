"""
Unit tests for Agentic RAG
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agentic import (
    AgenticRAGOrchestrator,
    CalculatorTool,
    VectorSearchTool,
    clean_response,
    is_out_of_domain,
)


@pytest.fixture
def mock_genai():
    with patch("services.rag.agentic.genai") as mock:
        mock_model = MagicMock()
        mock.GenerativeModel.return_value = mock_model
        yield mock


@pytest.fixture
def orchestrator(mock_genai):
    return AgenticRAGOrchestrator(tools=[CalculatorTool()])


@pytest.mark.asyncio
async def test_calculator_tool():
    tool = CalculatorTool()
    res = await tool.execute(expression="10 + 10")
    assert "20" in res

    res_tax = await tool.execute(expression="100 * 0.1", calculation_type="tax")
    assert "Tax calculation" in res_tax


@pytest.mark.asyncio
async def test_vector_search_tool():
    mock_retriever = AsyncMock()
    # Mock the new method preferred by the tool
    mock_retriever.search_with_reranking.return_value = {"results": [{"text": "Found it"}]}

    tool = VectorSearchTool(mock_retriever)
    res = await tool.execute("query")
    assert "[1] Found it" in res


@pytest.mark.asyncio
async def test_agent_process_query_flow(orchestrator):
    """Test the ReAct loop"""
    # Mock chat session
    mock_chat = MagicMock()
    orchestrator.model.start_chat.return_value = mock_chat

    # Sequence of responses:
    # 1. Thought + Action (Calculator)
    # 2. Final Answer

    response1 = MagicMock()
    response1.text = 'THOUGHT: I need to calculate.\nACTION: calculator(expression="5 + 5")'

    response2 = MagicMock()
    response2.text = "Final Answer: The result is 10."

    mock_chat.send_message_async = AsyncMock(side_effect=[response1, response2])

    result = await orchestrator.process_query("What is 5+5?")

    # After post-processing, "Final Answer:" prefix should be removed
    assert "Final Answer:" not in result["answer"]
    assert "10" in result["answer"] or "result is 10" in result["answer"].lower()
    assert result["total_steps"] == 2
    assert result["tools_called"] == 1
    assert result["steps"][0]["tool_used"] == "calculator"
    assert "10" in result["steps"][0]["tool_result"]


def test_parse_tool_call(orchestrator):
    """Test manual tool parsing logic"""
    text = 'Some text... ACTION: vector_search(query="test query")'
    call = orchestrator._parse_tool_call(text)

    assert call is not None
    assert call.tool_name == "vector_search"
    assert call.arguments["query"] == "test query"

    text2 = 'ACTION: calculator(expression="1+1")'
    call2 = orchestrator._parse_tool_call(text2)
    assert call2.tool_name == "calculator"
    assert call2.arguments["expression"] == "1+1"


@pytest.mark.asyncio
async def test_agent_stream_flow(orchestrator):
    """Test the Streaming ReAct loop"""
    # Mock chat session
    mock_chat = MagicMock()
    orchestrator.model.start_chat.return_value = mock_chat

    # Sequence of responses:
    # 1. Thought + Action (Calculator)
    # 2. Final Answer

    response1 = MagicMock()
    response1.text = 'THOUGHT: I need to calculate.\nACTION: calculator(expression="5 + 5")'

    response2 = MagicMock()
    response2.text = "Final Answer: The result is 10."

    mock_chat.send_message_async = AsyncMock(side_effect=[response1, response2])

    events = []
    async for event in orchestrator.stream_query("What is 5+5?"):
        events.append(event)

    # Check event types
    types = [e["type"] for e in events]
    assert "metadata" in types
    assert "status" in types
    assert "tool_start" in types
    assert "tool_end" in types
    assert "token" in types
    assert "done" in types

    # Check tool execution
    tool_events = [e for e in events if e["type"] == "tool_end"]
    assert len(tool_events) == 1
    assert "10" in tool_events[0]["data"]["result"]

    # Check token streaming (simulated)
    tokens = [e["data"] for e in events if e["type"] == "token"]
    full_text = "".join(tokens)
    assert "The" in full_text
    assert "10" in full_text


def test_build_system_prompt_with_simple_explanation(orchestrator):
    """Test that _build_system_prompt includes simple explanation instructions"""
    query = "Spiegami il KITAS come se fossi un bambino"
    context = {}

    prompt = orchestrator._build_system_prompt("test_user", context, query)

    assert "SIMPLE" in prompt.upper() or "simple" in prompt.lower()
    assert len(prompt) > 100  # Should have substantial content


def test_build_system_prompt_with_expert_explanation(orchestrator):
    """Test that _build_system_prompt includes expert explanation instructions"""
    query = "Mi serve una consulenza tecnica dettagliata"
    context = {}

    prompt = orchestrator._build_system_prompt("test_user", context, query)

    assert "EXPERT" in prompt.upper() or "expert" in prompt.lower()
    assert len(prompt) > 100


def test_build_system_prompt_with_alternatives(orchestrator):
    """Test that _build_system_prompt includes alternatives format instructions"""
    query = "Non posso permettermi un PT PMA, ci sono alternative?"
    context = {}

    prompt = orchestrator._build_system_prompt("test_user", context, query)

    # Should mention numbered list or alternatives format
    assert (
        "numbered" in prompt.lower()
        or "alternativ" in prompt.lower()
        or "1)" in prompt
        or "opzioni" in prompt.lower()
    )


def test_build_system_prompt_with_forbidden_responses(orchestrator):
    """Test that _build_system_prompt includes forbidden stub responses"""
    query = "Test query"
    context = {}

    prompt = orchestrator._build_system_prompt("test_user", context, query)

    # Should mention forbidden responses
    assert (
        "FORBIDDEN" in prompt.upper() or "STUB" in prompt.upper() or "sounds good" in prompt.lower()
    )


def test_build_system_prompt_without_query(orchestrator):
    """Test that _build_system_prompt works without query (empty string)"""
    context = {}

    prompt = orchestrator._build_system_prompt("test_user", context, "")

    assert len(prompt) > 50  # Should still build a valid prompt
    # Should not crash


# ============================================================================
# CLEAN RESPONSE TESTS
# ============================================================================


def test_clean_response_removes_thought_markers():
    """Test that clean_response removes THOUGHT: markers"""
    response = "THOUGHT: I need to think about this.\nFinal Answer: The answer is 10."
    cleaned = clean_response(response)
    assert "THOUGHT:" not in cleaned
    assert "The answer is 10" in cleaned


def test_clean_response_removes_observation_markers():
    """Test that clean_response removes Observation: markers"""
    response = "Observation: None\nFinal Answer: Here is the answer."
    cleaned = clean_response(response)
    assert "Observation:" not in cleaned
    assert "Here is the answer" in cleaned


def test_clean_response_removes_okay_patterns():
    """Test that clean_response removes 'Okay, since/given...' patterns"""
    response = "Okay, given no specific observation, I will proceed.\nThe answer is KITAS."
    cleaned = clean_response(response)
    assert "Okay, given" not in cleaned.lower()
    assert "KITAS" in cleaned


def test_clean_response_removes_stub_responses():
    """Test that clean_response removes stub responses"""
    response = "Zantara has provided the final answer."
    cleaned = clean_response(response)
    assert "Zantara has provided the final answer" not in cleaned


def test_clean_response_removes_next_thought_patterns():
    """Test that clean_response removes 'Next thought:' patterns"""
    response = "Next thought: I should search.\nFinal Answer: The result is here."
    cleaned = clean_response(response)
    assert "Next thought:" not in cleaned
    assert "The result is here" in cleaned


def test_clean_response_preserves_valid_content():
    """Test that clean_response preserves valid answer content"""
    response = "Come italiano per lavorare a Bali hai bisogno di un KITAS. Le opzioni principali sono: E31A, E33G, E28A."
    cleaned = clean_response(response)
    assert "KITAS" in cleaned
    assert "E31A" in cleaned
    assert "E33G" in cleaned
    assert len(cleaned) > 50


def test_clean_response_handles_empty_string():
    """Test that clean_response handles empty strings"""
    assert clean_response("") == ""
    assert clean_response("   ") == ""


# ============================================================================
# OUT-OF-DOMAIN DETECTION TESTS
# ============================================================================


def test_is_out_of_domain_personal_data():
    """Test detection of personal data queries"""
    query = "Qual è il codice fiscale di Mario Rossi?"
    is_ood, reason = is_out_of_domain(query)
    assert is_ood is True
    assert reason == "personal_data"


def test_is_out_of_domain_realtime_info():
    """Test detection of real-time information queries"""
    query = "Che tempo fa a Bali oggi?"
    is_ood, reason = is_out_of_domain(query)
    assert is_ood is True
    assert reason == "realtime_info"


def test_is_out_of_domain_off_topic():
    """Test detection of off-topic queries"""
    query = "Scrivi una ricetta per la pasta"
    is_ood, reason = is_out_of_domain(query)
    assert is_ood is True
    assert reason == "off_topic"


def test_is_out_of_domain_valid_visa_query():
    """Test that valid visa queries are not flagged as out-of-domain"""
    query = "Quale visto mi serve per lavorare a Bali?"
    is_ood, reason = is_out_of_domain(query)
    assert is_ood is False
    assert reason is None


def test_is_out_of_domain_valid_business_query():
    """Test that valid business queries are not flagged as out-of-domain"""
    query = "Come apro una PT PMA a Bali?"
    is_ood, reason = is_out_of_domain(query)
    assert is_ood is False
    assert reason is None


# ============================================================================
# POST-PROCESS RESPONSE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_post_process_response_cleans_internal_reasoning(orchestrator):
    """Test that _post_process_response removes internal reasoning"""
    response_with_thought = (
        "THOUGHT: I need to think.\nObservation: None.\nFinal Answer: The answer is KITAS."
    )
    cleaned = orchestrator._post_process_response(response_with_thought, "test query")
    assert "THOUGHT:" not in cleaned
    assert "Observation:" not in cleaned
    assert "KITAS" in cleaned


@pytest.mark.asyncio
async def test_post_process_response_formats_procedural_questions(orchestrator):
    """Test that _post_process_response formats procedural questions as numbered lists"""
    query = "Come faccio a richiedere il KITAS?"
    response = "Prepara i documenti. Trova uno sponsor. Applica online."
    processed = orchestrator._post_process_response(response, query)
    # Should contain numbered list
    assert "1." in processed or "2." in processed


@pytest.mark.asyncio
async def test_post_process_response_adds_emotional_acknowledgment(orchestrator):
    """Test that _post_process_response adds emotional acknowledgment when needed"""
    query = "Sono disperato, il mio visto è stato rifiutato!"
    response = "Puoi fare ricorso."
    processed = orchestrator._post_process_response(response, query)
    # Should contain emotional acknowledgment keywords
    assert any(
        keyword in processed.lower()
        for keyword in ["capisco", "tranquillo", "aiuto", "soluzione", "possibilità"]
    )
