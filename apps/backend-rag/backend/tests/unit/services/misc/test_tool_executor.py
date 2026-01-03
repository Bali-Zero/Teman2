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

    @pytest.mark.asyncio
    async def test_execute_tool_calls_zantara_tool_error(self, tool_executor, mock_zantara_tools):
        """Test executing ZantaraTools with error"""
        mock_zantara_tools.execute_tool = AsyncMock(return_value={"success": False, "error": "Test error"})
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_123",
            "name": "get_pricing",
            "input": {}
        }]
        results = await tool_executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        assert results[0].get("is_error") is True

    @pytest.mark.asyncio
    async def test_execute_tool_calls_mcp_tool_error(self, tool_executor, mock_mcp_client):
        """Test executing MCP tool with error"""
        mock_mcp_client.execute_tool = AsyncMock(return_value={"success": False, "error": "MCP error"})
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_456",
            "name": "mcp_test_tool",
            "input": {}
        }]
        results = await tool_executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        assert results[0].get("is_error") is True

    @pytest.mark.asyncio
    async def test_execute_tool_calls_exception(self, tool_executor, mock_zantara_tools):
        """Test handling exceptions during tool execution"""
        mock_zantara_tools.execute_tool = AsyncMock(side_effect=Exception("Test exception"))
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_123",
            "name": "get_pricing",
            "input": {}
        }]
        results = await tool_executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        assert results[0].get("is_error") is True

    @pytest.mark.asyncio
    async def test_execute_tool_calls_pydantic_object(self, tool_executor, mock_zantara_tools):
        """Test executing tool with Pydantic ToolUseBlock object"""
        mock_tool_use = MagicMock()
        mock_tool_use.id = "toolu_123"
        mock_tool_use.name = "get_pricing"
        mock_tool_use.input = {"service_type": "visa"}

        results = await tool_executor.execute_tool_calls([mock_tool_use])
        assert len(results) == 1
        mock_zantara_tools.execute_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, tool_executor, mock_zantara_tools):
        """Test execute_tool method (single tool)"""
        result = await tool_executor.execute_tool("get_pricing", {"service_type": "visa"})
        assert result["success"] is True
        assert "result" in result

    @pytest.mark.asyncio
    async def test_execute_tool_error(self, tool_executor, mock_zantara_tools):
        """Test execute_tool with error"""
        mock_zantara_tools.execute_tool = AsyncMock(return_value={"success": False, "error": "Error"})
        result = await tool_executor.execute_tool("get_pricing", {})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, tool_executor, mock_mcp_client):
        """Test execute_tool with unknown tool"""
        mock_mcp_client.is_mcp_tool.return_value = False
        result = await tool_executor.execute_tool("unknown_tool", {})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_mcp(self, tool_executor, mock_mcp_client):
        """Test execute_tool with MCP tool"""
        result = await tool_executor.execute_tool("mcp_test_tool", {"param": "value"})
        assert result["success"] is True
        mock_mcp_client.execute_tool.assert_called_once()

    def test_get_all_tools_for_ai(self, tool_executor, mock_mcp_client):
        """Test get_all_tools_for_ai"""
        mock_mcp_client.get_tools_for_gemini = MagicMock(return_value=[{"name": "test_tool"}])
        tools = tool_executor.get_all_tools_for_ai()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_get_available_tools(self, tool_executor, mock_zantara_tools):
        """Test get_available_tools"""
        mock_zantara_tools.get_tool_definitions = MagicMock(return_value=[{"name": "test_tool"}])
        tools = await tool_executor.get_available_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_get_available_tools_error(self, tool_executor, mock_zantara_tools):
        """Test get_available_tools with error"""
        mock_zantara_tools.get_tool_definitions = MagicMock(side_effect=Exception("Error"))
        tools = await tool_executor.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_execute_tool_calls_without_zantara_tools(self, mock_mcp_client):
        """Test executing tool calls without ZantaraTools"""
        mock_mcp_client.is_mcp_tool.return_value = False
        executor = ToolExecutor(mcp_client=mock_mcp_client)
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_123",
            "name": "get_pricing",
            "input": {}
        }]
        results = await executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        # Should return error because tool is not available
        assert results[0].get("is_error") is True or "not available" in str(results[0].get("content", ""))

    @pytest.mark.asyncio
    async def test_execute_tool_calls_without_mcp_client(self, mock_zantara_tools):
        """Test executing tool calls without MCP client"""
        executor = ToolExecutor(zantara_tools=mock_zantara_tools)
        tool_uses = [{
            "type": "tool_use",
            "id": "toolu_456",
            "name": "mcp_test_tool",
            "input": {}
        }]
        results = await executor.execute_tool_calls(tool_uses)
        assert len(results) == 1
        assert results[0].get("is_error") is True

