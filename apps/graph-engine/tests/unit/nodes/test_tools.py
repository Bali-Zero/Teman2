"""Tests for the tools node."""

import pytest

from nuzantara_graph.nodes.tools import make_tools_node, register_tool, TOOL_REGISTRY
from nuzantara_schemas.state import GraphState
from nuzantara_schemas.tools import ToolCallRecord, ToolStatus
from helpers.mocks import make_mock_services


class TestToolsNode:
    def setup_method(self):
        """Clear tool registry before each test."""
        TOOL_REGISTRY.clear()

    @pytest.mark.asyncio
    async def test_executes_registered_tool(self):
        async def mock_kbli_lookup(code: str) -> dict:
            return {"kode_kbli": code, "judul": "Restoran"}

        register_tool("kbli_lookup", mock_kbli_lookup)

        svc = make_mock_services()
        node = make_tools_node(svc)
        state = GraphState(
            query="Look up KBLI 56101",
            tool_calls=[
                ToolCallRecord(
                    tool_name="kbli_lookup",
                    arguments={"code": "56101"},
                ),
            ],
        )

        result = await node(state)

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0].status == ToolStatus.SUCCESS
        assert result["tool_calls"][0].result["kode_kbli"] == "56101"
        assert result["tool_calls"][0].duration_ms is not None

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        svc = make_mock_services()
        node = make_tools_node(svc)
        state = GraphState(
            query="Test",
            tool_calls=[
                ToolCallRecord(
                    tool_name="nonexistent_tool",
                    arguments={},
                ),
            ],
        )

        result = await node(state)

        assert result["tool_calls"][0].status == ToolStatus.ERROR
        assert "Unknown tool" in result["tool_calls"][0].error_message

    @pytest.mark.asyncio
    async def test_tool_exception_handled(self):
        async def failing_tool(**kwargs) -> dict:
            raise ValueError("Tool crashed")

        register_tool("failing_tool", failing_tool)

        svc = make_mock_services()
        node = make_tools_node(svc)
        state = GraphState(
            query="Test",
            tool_calls=[
                ToolCallRecord(tool_name="failing_tool", arguments={}),
            ],
        )

        result = await node(state)

        assert result["tool_calls"][0].status == ToolStatus.ERROR
        assert "Tool crashed" in result["tool_calls"][0].error_message

    @pytest.mark.asyncio
    async def test_skips_already_executed_tools(self):
        svc = make_mock_services()
        node = make_tools_node(svc)
        state = GraphState(
            query="Test",
            tool_calls=[
                ToolCallRecord(
                    tool_name="some_tool",
                    arguments={},
                    status=ToolStatus.SUCCESS,
                    result={"done": True},
                ),
            ],
        )

        result = await node(state)

        assert result["tool_calls"][0].status == ToolStatus.SUCCESS
        assert result["tool_calls"][0].result == {"done": True}

    @pytest.mark.asyncio
    async def test_empty_tool_calls(self):
        svc = make_mock_services()
        node = make_tools_node(svc)
        state = GraphState(query="Test", tool_calls=[])

        result = await node(state)

        assert result["tool_calls"] == []
