from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.llm_clients.pricing import TokenUsage
from services.rag.agentic.orchestrator import AgenticRAGOrchestrator
from services.rag.agentic.schema import CoreResult
from services.tools.definitions import BaseTool


# Define a concrete MockTool since BaseTool is abstract/pydantic
class MockTool(BaseTool):
    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {"arg1": {"type": "string"}}}

    async def execute(self, **kwargs) -> str:
        return "Mock result"


@pytest.fixture
def mock_llm_gateway():
    gateway = AsyncMock()
    # Mock create_chat_with_history to return a dummy chat object
    gateway.create_chat_with_history.return_value = MagicMock()

    # Configure set_gemini_tools as a synchronous MagicMock
    gateway.set_gemini_tools = MagicMock()

    # Setup default return for send_message to avoid errors if side_effect runs out
    gateway.send_message.return_value = (
        "Default response",
        "mock-model",
        MagicMock(candidates=[]),
        TokenUsage(),
    )
    return gateway


@pytest.fixture
def mock_services():
    with (
        patch("services.rag.agentic.orchestrator.IntentClassifier") as cls_mock,
        patch("services.rag.agentic.orchestrator.EmotionalAttunementService") as emo_mock,
        patch("services.rag.agentic.orchestrator.ContextWindowManager") as cwm_mock,
        patch("services.rag.agentic.orchestrator.EntityExtractionService") as ent_mock,
    ):
        # Intent Classifier setup
        intent_instance = cls_mock.return_value
        intent_instance.classify_intent = AsyncMock(
            return_value={"suggested_ai": "FLASH", "category": "simple"}
        )

        # Entity Extractor setup
        ent_instance = ent_mock.return_value
        ent_instance.extract_entities = AsyncMock(return_value={})

        yield {
            "intent": intent_instance,
            "emotional": emo_mock.return_value,
            "cwm": cwm_mock.return_value,
            "entity": ent_instance,
        }


@pytest.fixture
def mock_db_pool():
    return AsyncMock()


@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_llm_gateway, mock_services, mock_db_pool):
    tools = [MockTool()]
    orchestrator = AgenticRAGOrchestrator(
        tools=tools, llm_gateway=mock_llm_gateway, db_pool=mock_db_pool
    )
    assert orchestrator.llm_gateway == mock_llm_gateway
    assert "mock_tool" in orchestrator.tools


@pytest.mark.asyncio
async def test_process_query_abstains_on_no_context(mock_llm_gateway, mock_services, mock_db_pool):
    """Test that process_query abstains when no context is gathered (safety mechanism)."""
    tools = [MockTool()]
    orchestrator = AgenticRAGOrchestrator(
        tools=tools,
        llm_gateway=mock_llm_gateway,
        db_pool=mock_db_pool,
        entity_extractor=mock_services["entity"],
    )

    # Configure LLM to return a simple answer
    mock_llm_gateway.send_message.return_value = (
        "Direct answer from LLM.",
        "gemini-flash",
        MagicMock(candidates=[]),
        TokenUsage(prompt_tokens=10, completion_tokens=5, cost_usd=0.0002),
    )

    # Need to mock get_user_context since it's called in process_query
    with patch(
        "services.rag.agentic.orchestrator.get_user_context", new_callable=AsyncMock
    ) as mock_ctx:
        mock_ctx.return_value = {"profile": None, "history": [], "facts": []}

        # Execute
        result = await orchestrator.process_query(query="What is RAG?", user_id="user1")

    # Verify: Orchestrator should override the direct answer because evidence is 0
    assert isinstance(result, CoreResult)
    assert "non ho trovato informazioni" in result.answer
    assert result.evidence_score < 0.3
    assert result.model_used == "gemini-flash"


@pytest.mark.asyncio
async def test_process_query_with_tool_execution(mock_llm_gateway, mock_services, mock_db_pool):
    """Test a query that triggers a tool call."""
    tools = [MockTool()]
    orchestrator = AgenticRAGOrchestrator(
        tools=tools,
        llm_gateway=mock_llm_gateway,
        db_pool=mock_db_pool,
        entity_extractor=mock_services["entity"],
    )

    # 1. Mock the Tool Call Response
    tool_call_part = MagicMock()
    # Create a proper function call object structure
    tool_call_part.function_call.name = "mock_tool"
    tool_call_part.function_call.args = {"arg1": "val1"}

    # Gemini returns parts in candidate.content.parts
    candidate = MagicMock()
    candidate.content.parts = [tool_call_part]
    response_obj_tool = MagicMock(candidates=[candidate])

    # 2. Mock the Final Response
    response_obj_final = MagicMock(candidates=[])

    # Sequence of LLM responses
    mock_llm_gateway.send_message.side_effect = [
        # Step 1: LLM decides to call tool
        (
            "I will use the tool.",
            "gemini-pro",
            response_obj_tool,
            TokenUsage(prompt_tokens=5, completion_tokens=5),
        ),
        # Step 2: LLM receives observation and gives final answer
        (
            "Final Answer: Tool executed successfully.",
            "gemini-pro",
            response_obj_final,
            TokenUsage(prompt_tokens=5, completion_tokens=5),
        ),
    ]

    # Patch execute_tool in reasoning.py to return our mock result
    with patch("services.rag.agentic.reasoning.execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ("Tool Result Data", 0.5)  # (result, duration)

        with patch(
            "services.rag.agentic.orchestrator.get_user_context", new_callable=AsyncMock
        ) as mock_ctx:
            mock_ctx.return_value = {}

            result = await orchestrator.process_query(query="Run tool", user_id="user1")

    assert "Tool executed successfully" in result.answer
    assert mock_exec.called
    assert mock_exec.call_args[0][1] == "mock_tool"  # 2nd arg is tool_name


@pytest.mark.asyncio
async def test_process_query_low_evidence_warning(mock_llm_gateway, mock_services, mock_db_pool):
    """Test that low evidence results trigger a warning or abstention."""
    tools = [MockTool()]
    orchestrator = AgenticRAGOrchestrator(
        tools=tools,
        llm_gateway=mock_llm_gateway,
        db_pool=mock_db_pool,
        entity_extractor=mock_services["entity"],
    )

    # We simulate a ReAct loop where context gathered is minimal/irrelevant
    # so evidence score calculation in reasoning.py will be low.

    # Mock LLM to return a thought but NO tool call, then final answer
    # If no tool called, context_gathered is empty, evidence = 0.

    mock_llm_gateway.send_message.side_effect = None  # Reset side effect
    mock_llm_gateway.send_message.return_value = (
        "I am not sure. Final Answer: I don't know.",
        "gemini-flash",
        MagicMock(candidates=[]),
        TokenUsage(prompt_tokens=5, completion_tokens=5),
    )

    with patch(
        "services.rag.agentic.orchestrator.get_user_context", new_callable=AsyncMock
    ) as mock_ctx:
        mock_ctx.return_value = {}

        result = await orchestrator.process_query(query="Unknown question", user_id="user1")

    # Since evidence score is 0 and no trusted tools used, it should trigger ABSTAIN or warning
    # reasoning.py logic: if not state.final_answer and state.context_gathered ...
    # OR if state.final_answer and evidence < 0.3 -> override

    # Expectation: The answer should be the canned "Mi dispiace..." message
    assert "Mi dispiace" in result.answer or "non ho trovato informazioni" in result.answer
    assert result.evidence_score < 0.3
