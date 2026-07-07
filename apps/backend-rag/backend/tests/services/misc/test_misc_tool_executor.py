from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from backend.services.misc.tool_executor import ToolExecutor


class FakeZantaraTools:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def execute_tool(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        self.calls.append({"tool_name": tool_name, "tool_input": tool_input, "user_id": user_id})
        if self.fail:
            return {"success": False, "error": "failed"}
        return {"success": True, "data": {"tool": tool_name, "input": tool_input}}

    def get_tool_definitions(self, include_admin_tools: bool = False) -> list[dict[str, str]]:
        assert include_admin_tools is False
        return [{"name": "get_pricing"}]


class FakeMCPClient:
    available_tools = {"mcp_search": {}}

    def is_mcp_tool(self, tool_name: str) -> bool:
        return tool_name == "mcp_search"

    async def execute_tool(self, *, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "data": {"tool": tool_name, "params": params}}

    def get_tools_for_gemini(self) -> list[dict[str, str]]:
        return [{"name": "mcp_search"}]


async def test_execute_tool_calls_dispatches_zantara_mcp_and_unknown_tools() -> None:
    executor = ToolExecutor(
        zantara_tools=FakeZantaraTools(),
        mcp_client=FakeMCPClient(),
    )

    results = await executor.execute_tool_calls(
        [
            {"id": "z1", "name": "get_pricing", "input": {"service_type": "visa"}},
            {"id": "m1", "name": "mcp_search", "input": {"query": "visa"}},
            {"id": "x1", "name": "missing", "input": {}},
        ]
    )

    assert results[0] == {
        "type": "tool_result",
        "tool_use_id": "z1",
        "content": '{"tool": "get_pricing", "input": {"service_type": "visa"}}',
    }
    assert results[1] == {
        "type": "tool_result",
        "tool_use_id": "m1",
        "content": '{"tool": "mcp_search", "params": {"query": "visa"}}',
    }
    assert results[2]["is_error"] is True
    assert "Tool 'missing' not available" in results[2]["content"]


async def test_execute_tool_calls_supports_object_tool_use_blocks() -> None:
    executor = ToolExecutor(zantara_tools=FakeZantaraTools())
    tool_use = SimpleNamespace(id="tool-1", name="get_pricing", input={"service_type": "all"})

    result = await executor.execute_tool_calls([tool_use])

    assert result[0]["tool_use_id"] == "tool-1"
    assert "get_pricing" in result[0]["content"]


async def test_execute_tool_returns_prefetch_result_and_error() -> None:
    executor = ToolExecutor(zantara_tools=FakeZantaraTools())

    success = await executor.execute_tool("get_pricing", {"service_type": "visa"}, user_id="u1")
    missing = await executor.execute_tool("missing", {})

    assert success == {
        "success": True,
        "result": {"tool": "get_pricing", "input": {"service_type": "visa"}},
    }
    assert missing["success"] is False
    assert "Tool 'missing' not available" in missing["error"]


async def test_execute_tool_returns_zantara_failure() -> None:
    result = await ToolExecutor(zantara_tools=FakeZantaraTools(fail=True)).execute_tool(
        "get_pricing",
        {},
    )

    assert result == {"success": False, "error": "failed"}


def test_get_all_tools_for_ai_returns_mcp_gemini_tools() -> None:
    assert ToolExecutor(mcp_client=FakeMCPClient()).get_all_tools_for_ai() == [
        {"name": "mcp_search"}
    ]


async def test_get_available_tools_includes_zantara_definitions() -> None:
    assert await ToolExecutor(zantara_tools=FakeZantaraTools()).get_available_tools() == [
        {"name": "get_pricing"}
    ]
