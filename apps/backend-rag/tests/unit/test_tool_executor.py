"""
Unit tests for ToolExecutor service
Tests tool execution functionality
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestToolExecutor:
    """Unit tests for ToolExecutor"""

    def test_tool_executor_init(self):
        """Test ToolExecutor initialization"""
        from services.tool_executor import ToolExecutor

        executor = ToolExecutor()
        assert executor is not None
        assert executor.zantara_tools is None

    def test_tool_executor_init_with_tools(self):
        """Test ToolExecutor initialization with ZantaraTools"""
        from unittest.mock import MagicMock

        from services.tool_executor import ToolExecutor

        mock_tools = MagicMock()
        executor = ToolExecutor(zantara_tools=mock_tools)
        assert executor is not None
        assert executor.zantara_tools == mock_tools

    def test_zantara_tool_names(self):
        """Test that zantara_tool_names contains expected tools"""
        from services.tool_executor import ToolExecutor

        executor = ToolExecutor()
        assert "get_team_logins_today" in executor.zantara_tool_names
        assert "get_team_active_sessions" in executor.zantara_tool_names
        assert "get_pricing" in executor.zantara_tool_names
        assert "search_team_member" in executor.zantara_tool_names

    @pytest.mark.asyncio
    async def test_execute_tool_calls_empty_list(self):
        """Test executing empty tool calls list"""
        from services.tool_executor import ToolExecutor

        executor = ToolExecutor()
        result = await executor.execute_tool_calls([])
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_tool_calls_zantara_tool(self):
        """Test executing ZantaraTools function"""
        from unittest.mock import MagicMock

        from services.tool_executor import ToolExecutor

        mock_tools = MagicMock()
        mock_tools.get_pricing = MagicMock(return_value={"price": 100})
        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_calls = [{"id": "tool_123", "name": "get_pricing", "input": {"service": "test"}}]

        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        assert result[0]["tool_use_id"] == "tool_123"
        assert "content" in result[0]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_unknown_tool(self):
        """Test executing unknown tool"""
        from services.tool_executor import ToolExecutor

        executor = ToolExecutor()
        tool_calls = [{"id": "tool_123", "name": "unknown_tool", "input": {}}]

        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        # Result format: {"type": "tool_result", "tool_use_id": ..., "is_error": True, "content": "..."}
        assert result[0].get("is_error") is True or "error" in str(result[0]).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_calls_with_pydantic_object(self):
        """Test executing tool calls with Pydantic ToolUseBlock object"""
        from unittest.mock import MagicMock

        from services.tool_executor import ToolExecutor

        mock_tools = MagicMock()
        mock_tools.get_team_overview = MagicMock(return_value={"members": 5})
        executor = ToolExecutor(zantara_tools=mock_tools)

        # Simulate Pydantic object
        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool_456"
        mock_tool_use.name = "get_team_overview"
        mock_tool_use.input = {}

        result = await executor.execute_tool_calls([mock_tool_use])
        assert len(result) == 1
        assert result[0]["tool_use_id"] == "tool_456"

    @pytest.mark.asyncio
    async def test_execute_tool_calls_tool_exception(self):
        """Test handling tool execution exception"""
        from unittest.mock import AsyncMock, MagicMock

        from services.tool_executor import ToolExecutor

        mock_tools = MagicMock()
        mock_tools.execute_tool = AsyncMock(return_value={"success": False, "error": "Tool error"})
        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_calls = [{"id": "tool_123", "name": "get_pricing", "input": {}}]

        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        # Result format may vary, check that error is handled
        assert "error" in str(result[0]).lower() or result[0].get("is_error") is True

    @pytest.mark.asyncio
    async def test_execute_tool_calls_multiple_tools(self):
        """Test executing multiple tool calls"""
        from unittest.mock import MagicMock

        from services.tool_executor import ToolExecutor

        mock_tools = MagicMock()
        mock_tools.get_pricing = MagicMock(return_value={"price": 100})
        mock_tools.get_team_overview = MagicMock(return_value={"members": 5})
        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_calls = [
            {"id": "tool_1", "name": "get_pricing", "input": {}},
            {"id": "tool_2", "name": "get_team_overview", "input": {}},
        ]

        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 2
        assert result[0]["tool_use_id"] == "tool_1"
        assert result[1]["tool_use_id"] == "tool_2"

    @pytest.mark.asyncio
    async def test_execute_tool_calls_missing_tool_name(self):
        """Test executing tool call without name"""
        from services.tool_executor import ToolExecutor

        executor = ToolExecutor()
        tool_calls = [
            {
                "id": "tool_123",
                "name": None,  # Missing name
                "input": {},
            }
        ]

        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        # Tool name None should be handled gracefully
        assert result[0].get("tool_use_id") == "tool_123"
