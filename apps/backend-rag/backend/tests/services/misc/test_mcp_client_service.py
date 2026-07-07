from __future__ import annotations

import pytest

from backend.services.misc import mcp_client_service as module
from backend.services.misc.mcp_client_service import (
    MCPClientService,
    get_mcp_client,
    initialize_mcp_client,
)


def test_get_mcp_client_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_mcp_client", None)

    first = get_mcp_client()
    second = get_mcp_client()

    assert isinstance(first, MCPClientService)
    assert first is second


@pytest.mark.asyncio
async def test_initialize_mcp_client_marks_empty_registry_initialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_mcp_client", None)

    client = await initialize_mcp_client()

    assert client._initialized is True
    assert client.available_tools == {}


def test_get_tools_for_gemini_formats_registered_mcp_tools() -> None:
    client = MCPClientService()
    client.available_tools["mcp_filesystem_read_file"] = {
        "server": "filesystem",
        "original_name": "read_file",
        "description": "Read a file",
        "schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    }

    tools = client.get_tools_for_gemini()

    assert tools == [
        {
            "name": "mcp_filesystem_read_file",
            "description": "[MCP] Read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
        },
    ]


@pytest.mark.asyncio
async def test_execute_tool_returns_error_for_unknown_tool() -> None:
    client = MCPClientService()

    assert await client.execute_tool("mcp_missing", {}) == {
        "success": False,
        "error": "Tool 'mcp_missing' not found",
    }


@pytest.mark.asyncio
async def test_execute_tool_returns_error_for_registered_but_unconfigured_server() -> None:
    client = MCPClientService()
    client.available_tools["mcp_custom_run"] = {
        "server": "custom",
        "original_name": "run",
        "description": "Run custom",
        "schema": {},
    }

    assert await client.execute_tool("mcp_custom_run", {"x": 1}) == {
        "success": False,
        "error": "Server 'custom' not configured",
    }


def test_is_mcp_tool_checks_prefix_only() -> None:
    client = MCPClientService()

    assert client.is_mcp_tool("mcp_filesystem_read_file") is True
    assert client.is_mcp_tool("search_web") is False
