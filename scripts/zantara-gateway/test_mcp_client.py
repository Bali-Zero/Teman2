# scripts/zantara-gateway/test_mcp_client.py
"""Tests for MCP tool client."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_client import MCPToolClient


@pytest.fixture
def mock_mcp_session():
    session = AsyncMock()

    # MagicMock(name=...) sets the mock's internal name, not a .name attribute.
    # Build tool mocks explicitly to avoid that trap.
    tool1 = MagicMock()
    tool1.name = "list_clients"
    tool1.description = "List CRM clients"
    tool1.inputSchema = {"type": "object", "properties": {"limit": {"type": "integer"}}}

    tool2 = MagicMock()
    tool2.name = "get_client"
    tool2.description = "Get client details"
    tool2.inputSchema = {
        "type": "object",
        "properties": {"client_id": {"type": "string"}},
        "required": ["client_id"],
    }

    session.list_tools.return_value = MagicMock(tools=[tool1, tool2])
    session.call_tool.return_value = MagicMock(
        content=[MagicMock(text='[{"id": "c1", "name": "Test Client"}]')]
    )
    return session


def test_tool_definitions_to_ollama_format(mock_mcp_session):
    """Tool definitions should convert to Ollama/OpenAI function calling format."""
    client = MCPToolClient.__new__(MCPToolClient)
    client._session = mock_mcp_session
    client._tools_cache = None

    tools = asyncio.get_event_loop().run_until_complete(client.get_tool_definitions())

    assert len(tools) == 2
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "list_clients"
    assert "parameters" in tools[0]["function"]


def test_execute_tool_call(mock_mcp_session):
    """Execute a tool call via MCP session."""
    client = MCPToolClient.__new__(MCPToolClient)
    client._session = mock_mcp_session
    client._tools_cache = None

    result = asyncio.get_event_loop().run_until_complete(
        client.execute_tool("list_clients", {"limit": 10})
    )

    mock_mcp_session.call_tool.assert_called_once_with("list_clients", arguments={"limit": 10})
    assert "Test Client" in result
