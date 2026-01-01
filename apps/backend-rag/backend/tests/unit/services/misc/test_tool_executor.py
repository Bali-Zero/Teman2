"""
Unit tests for ToolExecutor
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.tool_executor import ToolExecutor


@pytest.fixture
def mock_zantara_tools():
    """Mock ZantaraTools"""
    tools = MagicMock()
    tools.execute_tool = AsyncMock(return_value={"success": True, "data": "test"})
    return tools


@pytest.fixture
def mock_mcp_client():
    """Mock MCPClientService"""
    client = MagicMock()
    client.execute_tool = AsyncMock(return_value={"success": True, "data": "test"})
    client.is_mcp_tool = MagicMock(return_value=True)
    client.available_tools = {"mcp_test_tool": {}}
    return client


@pytest.fixture
def tool_executor(mock_zantara_tools, mock_mcp_client):
    """Create ToolExecutor instance"""
    return ToolExecutor(zantara_tools=mock_zantara_tools, mcp_client=mock_mcp_client)


class TestToolExecutor:
    """Tests for ToolExecutor"""

    def test_init(self, mock_zantara_tools, mock_mcp_client):
        """Test initialization"""
        executor = ToolExecutor(zantara_tools=mock_zantara_tools, mcp_client=mock_mcp_client)
        assert executor.zantara_tools == mock_zantara_tools
        assert executor.mcp_client == mock_mcp_client

    def test_init_without_services(self):
        """Test initialization without services"""
        executor = ToolExecutor()
        assert executor.zantara_tools is None
        assert executor.mcp_client is None

    @pytest.mark.asyncio
    async def test_execute_tool_calls_zantara_tool(self, tool_executor, mock_zantara_tools):
        """Test executing ZantaraTools"""
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_123",
            "name": "get_pricing",
            "input": {"service_type": "visa"}
        }]
        results = await tool_executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        assert results[0]["tool_use_id"] == "toolu_123"
        mock_zantara_tools.execute_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_calls_mcp_tool(self, tool_executor, mock_mcp_client):
        """Test executing MCP tool"""
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_456",
            "name": "mcp_test_tool",
            "input": {"param": "value"}
        }]
        results = await tool_executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        mock_mcp_client.execute_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_calls_unknown_tool(self, tool_executor, mock_mcp_client):
        """Test executing unknown tool"""
        mock_mcp_client.is_mcp_tool.return_value = False
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_789",
            "name": "unknown_tool",
            "input": {}
        }]
        results = await tool_executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        # Check for error indication in result
        result = results[0]
        assert result.get("is_error") is True or "not available" in str(result.get("content", "")).lower() or "error" in str(result.get("content", "")).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_calls_empty_list(self, tool_executor):
        """Test executing empty tool calls list"""
        results = await tool_executor.execute_tool_calls([])
        assert len(results) == 0

