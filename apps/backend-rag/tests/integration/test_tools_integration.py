"""
Comprehensive Integration Tests for Tools System
Tests ToolExecutor, ZantaraTools, and tool execution

Covers:
- ToolExecutor functionality
- ZantaraTools execution
- Tool call processing
- Error handling
- Tool result formatting
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestToolExecutorIntegration:
    """Integration tests for ToolExecutor"""

    @pytest.mark.asyncio
    async def test_tool_executor_initialization(self):
        """Test ToolExecutor initialization"""
        with patch("services.tool_executor.ZantaraTools") as mock_zantara_tools:
            from services.tool_executor import ToolExecutor

            executor = ToolExecutor(zantara_tools=mock_zantara_tools.return_value)

            assert executor is not None
            assert executor.zantara_tools is not None

    @pytest.mark.asyncio
    async def test_execute_zantara_tool(self):
        """Test executing Zantara tool"""
        with patch("services.tool_executor.ZantaraTools") as mock_zantara_tools:
            mock_tools_instance = MagicMock()
            mock_tools_instance.execute_tool = AsyncMock(
                return_value={"success": True, "result": "Tool result"}
            )
            mock_zantara_tools.return_value = mock_tools_instance

            from services.tool_executor import ToolExecutor

            executor = ToolExecutor(zantara_tools=mock_tools_instance)

            tool_uses = [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "get_pricing",
                    "input": {"service": "KITAS"},
                }
            ]

            results = await executor.execute_tool_calls(tool_uses)

            assert len(results) == 1
            assert results[0]["type"] == "tool_result"
            assert results[0]["tool_use_id"] == "toolu_123"

    @pytest.mark.asyncio
    async def test_execute_multiple_tools(self):
        """Test executing multiple tools"""
        with patch("services.tool_executor.ZantaraTools") as mock_zantara_tools:
            mock_tools_instance = MagicMock()
            mock_tools_instance.execute_tool = AsyncMock(
                return_value={"success": True, "result": "Tool result"}
            )
            mock_zantara_tools.return_value = mock_tools_instance

            from services.tool_executor import ToolExecutor

            executor = ToolExecutor(zantara_tools=mock_tools_instance)

            tool_uses = [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_pricing",
                    "input": {"service": "KITAS"},
                },
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "search_team_member",
                    "input": {"query": "tax"},
                },
            ]

            results = await executor.execute_tool_calls(tool_uses)

            assert len(results) == 2
            assert all(r["type"] == "tool_result" for r in results)

    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self):
        """Test tool execution error handling"""
        with patch("services.tool_executor.ZantaraTools") as mock_zantara_tools:
            mock_tools_instance = MagicMock()
            mock_tools_instance.execute_tool = AsyncMock(
                side_effect=Exception("Tool execution error")
            )
            mock_zantara_tools.return_value = mock_tools_instance

            from services.tool_executor import ToolExecutor

            executor = ToolExecutor(zantara_tools=mock_tools_instance)

            tool_uses = [
                {
                    "type": "tool_use",
                    "id": "toolu_error",
                    "name": "get_pricing",
                    "input": {},
                }
            ]

            results = await executor.execute_tool_calls(tool_uses)

            assert len(results) == 1
            assert "error" in results[0]["content"][0]["text"].lower()


@pytest.mark.integration
class TestZantaraToolsIntegration:
    """Integration tests for ZantaraTools"""

    @pytest.mark.asyncio
    async def test_zantara_tools_initialization(self):
        """Test ZantaraTools initialization"""
        with (
            patch("services.zantara_tools.get_pricing_service") as mock_pricing,
            patch("services.zantara_tools.CollaboratorService") as mock_collaborator,
        ):
            from services.zantara_tools import ZantaraTools

            tools = ZantaraTools()

            assert tools is not None
            assert tools.pricing_service is not None
            assert tools.collaborator_service is not None

    @pytest.mark.asyncio
    async def test_get_pricing_tool(self):
        """Test get_pricing tool execution"""
        with (
            patch("services.zantara_tools.get_pricing_service") as mock_pricing,
            patch("services.zantara_tools.CollaboratorService") as mock_collaborator,
        ):
            mock_pricing_instance = MagicMock()
            mock_pricing_instance.get_pricing = AsyncMock(
                return_value={"service": "KITAS", "price": 1000}
            )
            mock_pricing.return_value = mock_pricing_instance

            from services.zantara_tools import ZantaraTools

            tools = ZantaraTools()

            result = await tools.execute_tool("get_pricing", {"service": "KITAS"}, "test_user")

            assert result["success"] is True
            assert "price" in result or "result" in result

    @pytest.mark.asyncio
    async def test_search_team_member_tool(self):
        """Test search_team_member tool execution"""
        with (
            patch("services.zantara_tools.get_pricing_service") as mock_pricing,
            patch("services.zantara_tools.CollaboratorService") as mock_collaborator,
        ):
            mock_collaborator_instance = MagicMock()
            mock_collaborator_instance.search_team_member = AsyncMock(
                return_value=[{"name": "Test Member", "role": "Tax Lead"}]
            )
            mock_collaborator.return_value = mock_collaborator_instance

            from services.zantara_tools import ZantaraTools

            tools = ZantaraTools()

            result = await tools.execute_tool("search_team_member", {"query": "tax"}, "test_user")

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_team_members_list_tool(self):
        """Test get_team_members_list tool execution"""
        with (
            patch("services.zantara_tools.get_pricing_service") as mock_pricing,
            patch("services.zantara_tools.CollaboratorService") as mock_collaborator,
        ):
            mock_collaborator_instance = MagicMock()
            mock_collaborator_instance.get_team_members = AsyncMock(
                return_value=[
                    {"name": "Member 1", "role": "Tax"},
                    {"name": "Member 2", "role": "Legal"},
                ]
            )
            mock_collaborator.return_value = mock_collaborator_instance

            from services.zantara_tools import ZantaraTools

            tools = ZantaraTools()

            result = await tools.execute_tool("get_team_members_list", {}, "test_user")

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """Test error handling for unknown tool"""
        with (
            patch("services.zantara_tools.get_pricing_service") as mock_pricing,
            patch("services.zantara_tools.CollaboratorService") as mock_collaborator,
        ):
            from services.zantara_tools import ZantaraTools

            tools = ZantaraTools()

            result = await tools.execute_tool("unknown_tool", {}, "test_user")

            assert result["success"] is False
            assert "error" in result
            assert "Unknown tool" in result["error"]
