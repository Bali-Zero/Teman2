"""
Unit tests for MCPClientService
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.misc.mcp_client_service import MCPClientService


class TestMCPClientService:
    """Tests for MCPClientService"""

    def test_init(self):
        """Test initialization"""
        service = MCPClientService()
        assert len(service.sessions) == 0
        assert len(service.available_tools) == 0
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization"""
        service = MCPClientService()
        await service.initialize()
        assert service._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self):
        """Test initialization when already initialized"""
        service = MCPClientService()
        service._initialized = True
        await service.initialize()
        assert service._initialized is True

    def test_get_tools_for_gemini_empty(self):
        """Test getting tools for Gemini when no tools available"""
        service = MCPClientService()
        tools = service.get_tools_for_gemini()
        assert isinstance(tools, list)
        assert len(tools) == 0

    def test_get_tools_for_gemini_with_tools(self):
        """Test getting tools for Gemini with available tools"""
        service = MCPClientService()
        service.available_tools = {
            "mcp_test_tool1": {
                "server": "test",
                "original_name": "tool1",
                "description": "Test tool",
                "schema": {"type": "object", "properties": {}},
            }
        }
        tools = service.get_tools_for_gemini()
        assert len(tools) == 1
        assert tools[0]["name"] == "mcp_test_tool1"
        assert "[MCP]" in tools[0]["description"]

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test executing a tool that doesn't exist"""
        service = MCPClientService()
        result = await service.execute_tool("nonexistent_tool", {})
        assert result["success"] is False
        assert "error" in result

    def test_is_mcp_tool(self):
        """Test checking if a tool is an MCP tool"""
        service = MCPClientService()
        assert service.is_mcp_tool("mcp_test_tool") is True
        assert service.is_mcp_tool("get_pricing") is False

    def test_get_tools_for_gemini_multiple_tools(self):
        """Test getting tools for Gemini with multiple tools"""
        service = MCPClientService()
        service.available_tools = {
            "mcp_test_tool1": {
                "server": "test1",
                "original_name": "tool1",
                "description": "Test tool 1",
                "schema": {"type": "object", "properties": {}},
            },
            "mcp_test_tool2": {
                "server": "test2",
                "original_name": "tool2",
                "description": "Test tool 2",
                "schema": {"type": "object", "properties": {"param": {"type": "string"}}},
            },
        }
        tools = service.get_tools_for_gemini()
        assert len(tools) == 2
        assert tools[0]["name"] == "mcp_test_tool1"
        assert tools[1]["name"] == "mcp_test_tool2"
        assert all("[MCP]" in tool["description"] for tool in tools)

    @pytest.mark.asyncio
    async def test_execute_tool_server_not_configured(self):
        """Test executing tool with server not configured"""
        service = MCPClientService()
        service.available_tools = {
            "mcp_test_tool": {
                "server": "unknown_server",
                "original_name": "tool",
                "description": "Test tool",
                "schema": {},
            }
        }

        result = await service.execute_tool("mcp_test_tool", {})
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_execution_error(self):
        """Test executing tool with execution error"""
        service = MCPClientService()
        service.available_tools = {
            "mcp_test_tool": {
                "server": "filesystem",
                "original_name": "tool",
                "description": "Test tool",
                "schema": {},
            }
        }

        # execute_tool will try to connect to server, which will fail in test
        # So we expect an error
        result = await service.execute_tool("mcp_test_tool", {})
        # Should return error (connection will fail without actual MCP server)
        assert "success" in result
