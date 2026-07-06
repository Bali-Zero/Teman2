import pytest

from backend.services.tools.definitions import (
    AgentState,
    BaseTool,
    Tool,
    ToolCall,
    ToolType,
)


class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo a piece of text"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer"},
                "options": {
                    "type": "object",
                    "properties": {"loud": {"type": "boolean"}},
                },
            },
            "required": ["text"],
        }

    async def execute(self, **kwargs) -> str:
        return str(kwargs["text"])


def test_base_tool_exports_gemini_function_declaration() -> None:
    declaration = EchoTool().to_gemini_function_declaration()

    assert declaration["name"] == "echo"
    assert declaration["description"] == "Echo a piece of text"
    assert declaration["parameters"]["type"] == "OBJECT"
    assert declaration["parameters"]["properties"]["text"]["type"] == "STRING"
    assert declaration["parameters"]["properties"]["count"]["type"] == "INTEGER"
    assert declaration["parameters"]["properties"]["options"]["type"] == "OBJECT"
    assert declaration["parameters"]["properties"]["options"]["properties"]["loud"]["type"] == "BOOLEAN"
    assert declaration["parameters"]["required"] == ["text"]


def test_to_gemini_tool_is_legacy_alias_for_function_declaration() -> None:
    tool = EchoTool()

    assert tool.to_gemini_tool() == tool.to_gemini_function_declaration()


@pytest.mark.asyncio
async def test_concrete_tool_execute_returns_string_result() -> None:
    assert await EchoTool().execute(text="hello") == "hello"


def test_tool_and_tool_call_dataclasses_keep_execution_metadata() -> None:
    tool = Tool(
        name="pricing",
        description="Get a price",
        tool_type=ToolType.PRICING,
        parameters={"type": "object"},
        function=lambda: "ok",
        requires_confirmation=True,
    )
    call = ToolCall(tool_name=tool.name, arguments={"visa": "E33G"})

    assert tool.requires_confirmation is True
    assert call.success is True
    assert call.result is None
    assert call.execution_time == 0.0


def test_agent_state_defaults_are_request_scoped() -> None:
    state = AgentState(query="How much is an investor KITAS?")

    assert state.max_steps == 3
    assert state.current_step == 0
    assert state.steps == []
    assert state.context_gathered == []
    assert state.final_answer is None
