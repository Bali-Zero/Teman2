"""
Comprehensive tests for Tool Executor Service
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, Mock

import pytest


class TestToolExecutorInit:
    """Test ToolExecutor initialization"""

    def test_init_without_zantara_tools(self):
        """Test initialization without ZantaraTools"""
        from backend.services.tool_executor import ToolExecutor

        executor = ToolExecutor()

        assert executor.zantara_tools is None
        assert len(executor.zantara_tool_names) > 0

    def test_init_with_zantara_tools(self):
        """Test initialization with ZantaraTools"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = Mock()
        executor = ToolExecutor(zantara_tools=mock_tools)

        assert executor.zantara_tools == mock_tools

    def test_zantara_tool_names_set(self):
        """Test that zantara_tool_names contains expected tools"""
        from backend.services.tool_executor import ToolExecutor

        executor = ToolExecutor()

        expected_tools = {
            "get_team_logins_today",
            "get_team_active_sessions",
            "get_team_member_stats",
            "get_team_overview",
            "get_team_members_list",
            "search_team_member",
            "get_session_details",
            "end_user_session",
            "retrieve_user_memory",
            "search_memory",
            "get_pricing",
        }

        assert executor.zantara_tool_names == expected_tools


class TestToolExecutorExecuteToolCalls:
    """Test execute_tool_calls method"""

    @pytest.mark.asyncio
    async def test_execute_tool_calls_empty(self):
        """Test execute with empty tool list"""
        from backend.services.tool_executor import ToolExecutor

        executor = ToolExecutor()
        result = await executor.execute_tool_calls([])

        assert result == []

    @pytest.mark.asyncio
    async def test_execute_tool_calls_dict_format(self):
        """Test execute with dict format tool use"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            "data": {"price": 100},
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [
            {
                "type": "tool_use",
                "id": "tool_123",
                "name": "get_pricing",
                "input": {"service": "kitas"},
            }
        ]

        result = await executor.execute_tool_calls(tool_uses)

        assert len(result) == 1
        assert result[0]["type"] == "tool_result"
        assert result[0]["tool_use_id"] == "tool_123"
        assert '"price": 100' in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_object_format(self):
        """Test execute with object format tool use (Pydantic)"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            "data": ["member1", "member2"],
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        # Simulate Pydantic ToolUseBlock object
        tool_use = Mock()
        tool_use.id = "tool_456"
        tool_use.name = "get_team_members_list"
        tool_use.input = {}

        result = await executor.execute_tool_calls([tool_use])

        assert len(result) == 1
        assert result[0]["tool_use_id"] == "tool_456"
        assert "member1" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_tool_error(self):
        """Test execute when tool returns error"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": False,
            "error": "Tool execution failed",
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [{"id": "tool_789", "name": "get_pricing", "input": {}}]

        result = await executor.execute_tool_calls(tool_uses)

        assert len(result) == 1
        assert result[0]["is_error"] is True
        assert "Tool execution failed" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_unknown_tool(self):
        """Test execute with unknown tool name"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [{"id": "tool_unknown", "name": "unknown_tool", "input": {}}]

        result = await executor.execute_tool_calls(tool_uses)

        assert len(result) == 1
        assert result[0]["is_error"] is True
        assert "not available" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_no_zantara_tools(self):
        """Test execute when ZantaraTools not provided"""
        from backend.services.tool_executor import ToolExecutor

        executor = ToolExecutor()  # No zantara_tools

        tool_uses = [{"id": "tool_no_tools", "name": "get_pricing", "input": {}}]

        result = await executor.execute_tool_calls(tool_uses)

        assert len(result) == 1
        assert result[0]["is_error"] is True
        assert "not available" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_exception(self):
        """Test execute handles exceptions"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.side_effect = Exception("Unexpected error")

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [{"id": "tool_exc", "name": "get_pricing", "input": {}}]

        result = await executor.execute_tool_calls(tool_uses)

        assert len(result) == 1
        assert result[0]["is_error"] is True
        assert "Unexpected error" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_string_result(self):
        """Test execute with string result (non-dict/list)"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            "data": "Simple string result",
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [{"id": "tool_str", "name": "get_pricing", "input": {}}]

        result = await executor.execute_tool_calls(tool_uses)

        assert result[0]["content"] == "Simple string result"

    @pytest.mark.asyncio
    async def test_execute_tool_calls_multiple(self):
        """Test execute multiple tool calls"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.side_effect = [
            {"success": True, "data": "result1"},
            {"success": True, "data": "result2"},
        ]

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [
            {"id": "tool_1", "name": "get_pricing", "input": {}},
            {"id": "tool_2", "name": "get_team_overview", "input": {}},
        ]

        result = await executor.execute_tool_calls(tool_uses)

        assert len(result) == 2
        assert result[0]["tool_use_id"] == "tool_1"
        assert result[1]["tool_use_id"] == "tool_2"


class TestToolExecutorExecuteTool:
    """Test execute_tool method (for prefetch)"""

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test single tool execution success"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            "data": {"key": "value"},
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        result = await executor.execute_tool(
            tool_name="get_pricing",
            tool_input={"service": "visa"},
            user_id="user_123",
        )

        assert result["success"] is True
        assert result["result"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_execute_tool_failure(self):
        """Test single tool execution failure"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": False,
            "error": "Service unavailable",
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        result = await executor.execute_tool(
            tool_name="get_pricing",
            tool_input={},
            user_id="user_123",
        )

        assert result["success"] is False
        assert result["error"] == "Service unavailable"

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self):
        """Test single tool execution with unknown tool"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        executor = ToolExecutor(zantara_tools=mock_tools)

        result = await executor.execute_tool(
            tool_name="nonexistent_tool",
            tool_input={},
            user_id="user_123",
        )

        assert result["success"] is False
        assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_no_zantara_tools(self):
        """Test single tool execution without ZantaraTools"""
        from backend.services.tool_executor import ToolExecutor

        executor = ToolExecutor()

        result = await executor.execute_tool(
            tool_name="get_pricing",
            tool_input={},
            user_id="user_123",
        )

        assert result["success"] is False
        assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_exception(self):
        """Test single tool execution handles exception"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.side_effect = Exception("Crash!")

        executor = ToolExecutor(zantara_tools=mock_tools)

        result = await executor.execute_tool(
            tool_name="get_pricing",
            tool_input={},
            user_id="user_123",
        )

        assert result["success"] is False
        assert "Crash!" in result["error"]


class TestToolExecutorGetAvailableTools:
    """Test get_available_tools method"""

    @pytest.mark.asyncio
    async def test_get_available_tools_with_zantara(self):
        """Test getting available tools with ZantaraTools"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = Mock()
        mock_tools.get_tool_definitions.return_value = [
            {"name": "get_pricing", "description": "Get pricing"},
            {"name": "get_team_members_list", "description": "List team"},
        ]

        executor = ToolExecutor(zantara_tools=mock_tools)

        result = await executor.get_available_tools()

        assert len(result) == 2
        assert result[0]["name"] == "get_pricing"
        mock_tools.get_tool_definitions.assert_called_once_with(include_admin_tools=False)

    @pytest.mark.asyncio
    async def test_get_available_tools_without_zantara(self):
        """Test getting available tools without ZantaraTools"""
        from backend.services.tool_executor import ToolExecutor

        executor = ToolExecutor()

        result = await executor.get_available_tools()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_available_tools_exception(self):
        """Test getting available tools handles exception"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = Mock()
        mock_tools.get_tool_definitions.side_effect = Exception("Load failed")

        executor = ToolExecutor(zantara_tools=mock_tools)

        result = await executor.get_available_tools()

        # Should return empty list on error
        assert result == []


class TestToolExecutorEdgeCases:
    """Test edge cases"""

    @pytest.mark.asyncio
    async def test_execute_tool_calls_none_input(self):
        """Test execute with None input"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            "data": "ok",
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        # Object with None input
        tool_use = Mock()
        tool_use.id = "tool_none"
        tool_use.name = "get_pricing"
        tool_use.input = None  # None input

        result = await executor.execute_tool_calls([tool_use])

        # Should handle None input as empty dict
        mock_tools.execute_tool.assert_called_once()
        call_args = mock_tools.execute_tool.call_args
        assert call_args[1]["tool_input"] == {}

    @pytest.mark.asyncio
    async def test_execute_tool_calls_result_without_data(self):
        """Test execute when result has no data key"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            # No "data" key - should use full result
            "other_key": "value",
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [{"id": "tool_no_data", "name": "get_pricing", "input": {}}]

        result = await executor.execute_tool_calls(tool_uses)

        # Should use full result dict when no "data" key
        assert "other_key" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_list_result(self):
        """Test execute with list result"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            "data": [1, 2, 3],
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [{"id": "tool_list", "name": "get_pricing", "input": {}}]

        result = await executor.execute_tool_calls(tool_uses)

        # Should JSON encode list
        assert "[1, 2, 3]" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_dict_format_missing_input(self):
        """Test execute with dict missing input key"""
        from backend.services.tool_executor import ToolExecutor

        mock_tools = AsyncMock()
        mock_tools.execute_tool.return_value = {
            "success": True,
            "data": "ok",
        }

        executor = ToolExecutor(zantara_tools=mock_tools)

        tool_uses = [
            {"id": "tool_no_input", "name": "get_pricing"}  # No "input" key
        ]

        result = await executor.execute_tool_calls(tool_uses)

        # Should use empty dict for input
        call_args = mock_tools.execute_tool.call_args
        assert call_args[1]["tool_input"] == {}
