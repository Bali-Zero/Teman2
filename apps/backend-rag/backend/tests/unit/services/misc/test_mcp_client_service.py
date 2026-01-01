"""
Unit tests for MCPClientService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.mcp_client_service import MCPClientService


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
                "schema": {"type": "object", "properties": {}}
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

