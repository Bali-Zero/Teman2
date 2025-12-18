"""
Comprehensive tests for services/tool_executor.py
Target: 99%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestToolExecutorComprehensive:
    """Comprehensive test suite for ToolExecutor"""

    @pytest.fixture
    def mock_zantara_tools(self):
        """Mock ZantaraTools instance"""
        tools = MagicMock()
        tools.execute_tool = AsyncMock(return_value={"success": True, "data": {"result": "test"}})
        tools.get_tool_definitions = MagicMock(
            return_value=[
                {
                    "name": "get_pricing",
                    "description": "Get pricing",
                    "input_schema": {"type": "object"},
                }
            ]
        )
        return tools

    @pytest.fixture
    def executor(self, mock_zantara_tools):
        """Create ToolExecutor instance"""
        from services.tool_executor import ToolExecutor

        return ToolExecutor(zantara_tools=mock_zantara_tools)

    @pytest.fixture
    def executor_no_tools(self):
        """Create ToolExecutor without tools"""
        from services.tool_executor import ToolExecutor

        return ToolExecutor()

    def test_init(self):
        """Test ToolExecutor initialization"""
        from services.tool_executor import ToolExecutor

        executor = ToolExecutor()
        assert executor.zantara_tools is None
        assert len(executor.zantara_tool_names) > 0

    def test_init_with_tools(self, mock_zantara_tools):
        """Test ToolExecutor initialization with tools"""
        from services.tool_executor import ToolExecutor

        executor = ToolExecutor(zantara_tools=mock_zantara_tools)
        assert executor.zantara_tools == mock_zantara_tools

    def test_zantara_tool_names(self, executor):
        """Test zantara_tool_names contains expected tools"""
        assert "get_team_logins_today" in executor.zantara_tool_names
        assert "get_team_active_sessions" in executor.zantara_tool_names
        assert "get_pricing" in executor.zantara_tool_names
        assert "search_team_member" in executor.zantara_tool_names

    @pytest.mark.asyncio
    async def test_execute_tool_calls_empty(self, executor):
        """Test execute_tool_calls with empty list"""
        result = await executor.execute_tool_calls([])
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_tool_calls_dict_format(self, executor):
        """Test execute_tool_calls with dict format"""
        tool_calls = [
            {
                "id": "tool_123",
                "name": "get_pricing",
                "input": {"service": "test"},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        assert result[0]["tool_use_id"] == "tool_123"
        assert "content" in result[0]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_pydantic_object(self, executor):
        """Test execute_tool_calls with Pydantic object"""
        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool_456"
        mock_tool_use.name = "get_pricing"
        mock_tool_use.input = {"service": "test"}

        result = await executor.execute_tool_calls([mock_tool_use])
        assert len(result) == 1
        assert result[0]["tool_use_id"] == "tool_456"

    @pytest.mark.asyncio
    async def test_execute_tool_calls_tool_not_found(self, executor_no_tools):
        """Test execute_tool_calls with unknown tool"""
        tool_calls = [
            {
                "id": "tool_123",
                "name": "unknown_tool",
                "input": {},
            }
        ]
        result = await executor_no_tools.execute_tool_calls(tool_calls)
        assert len(result) == 1
        assert result[0].get("is_error") is True

    @pytest.mark.asyncio
    async def test_execute_tool_calls_tool_error(self, executor):
        """Test execute_tool_calls with tool error"""
        executor.zantara_tools.execute_tool = AsyncMock(
            return_value={"success": False, "error": "Tool error"}
        )
        tool_calls = [
            {
                "id": "tool_123",
                "name": "get_pricing",
                "input": {},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        assert result[0].get("is_error") is True

    @pytest.mark.asyncio
    async def test_execute_tool_calls_exception(self, executor):
        """Test execute_tool_calls with exception"""
        executor.zantara_tools.execute_tool = AsyncMock(side_effect=Exception("Error"))
        tool_calls = [
            {
                "id": "tool_123",
                "name": "get_pricing",
                "input": {},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        assert result[0].get("is_error") is True

    @pytest.mark.asyncio
    async def test_execute_tool_calls_multiple_tools(self, executor):
        """Test execute_tool_calls with multiple tools"""
        tool_calls = [
            {"id": "tool_1", "name": "get_pricing", "input": {}},
            {"id": "tool_2", "name": "get_team_overview", "input": {}},
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_execute_tool_calls_dict_result(self, executor):
        """Test execute_tool_calls with dict result"""
        executor.zantara_tools.execute_tool = AsyncMock(
            return_value={"success": True, "data": {"key": "value"}}
        )
        tool_calls = [
            {
                "id": "tool_123",
                "name": "get_pricing",
                "input": {},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1
        assert "content" in result[0]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_list_result(self, executor):
        """Test execute_tool_calls with list result"""
        executor.zantara_tools.execute_tool = AsyncMock(
            return_value={"success": True, "data": [1, 2, 3]}
        )
        tool_calls = [
            {
                "id": "tool_123",
                "name": "get_pricing",
                "input": {},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_tool_calls_string_result(self, executor):
        """Test execute_tool_calls with string result"""
        executor.zantara_tools.execute_tool = AsyncMock(
            return_value={"success": True, "data": "string result"}
        )
        tool_calls = [
            {
                "id": "tool_123",
                "name": "get_pricing",
                "input": {},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, executor):
        """Test execute_tool success"""
        result = await executor.execute_tool("get_pricing", {"service": "test"}, "user123")
        assert result["success"] is True
        assert "result" in result

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, executor_no_tools):
        """Test execute_tool with unknown tool"""
        result = await executor_no_tools.execute_tool("unknown_tool", {}, "user123")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_error(self, executor):
        """Test execute_tool with tool error"""
        executor.zantara_tools.execute_tool = AsyncMock(
            return_value={"success": False, "error": "Tool error"}
        )
        result = await executor.execute_tool("get_pricing", {}, "user123")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_exception(self, executor):
        """Test execute_tool with exception"""
        executor.zantara_tools.execute_tool = AsyncMock(side_effect=Exception("Error"))
        result = await executor.execute_tool("get_pricing", {}, "user123")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_available_tools_with_tools(self, executor):
        """Test get_available_tools with tools"""
        tools = await executor.get_available_tools()
        assert len(tools) > 0
        assert all("name" in tool for tool in tools)

    @pytest.mark.asyncio
    async def test_get_available_tools_no_tools(self, executor_no_tools):
        """Test get_available_tools without tools"""
        tools = await executor_no_tools.get_available_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_get_available_tools_error(self, executor):
        """Test get_available_tools with error"""
        executor.zantara_tools.get_tool_definitions = MagicMock(side_effect=Exception("Error"))
        tools = await executor.get_available_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_execute_tool_calls_missing_id(self, executor):
        """Test execute_tool_calls with missing id"""
        tool_calls = [
            {
                "name": "get_pricing",
                "input": {},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_tool_calls_missing_name(self, executor):
        """Test execute_tool_calls with missing name"""
        tool_calls = [
            {
                "id": "tool_123",
                "input": {},
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_tool_calls_missing_input(self, executor):
        """Test execute_tool_calls with missing input"""
        tool_calls = [
            {
                "id": "tool_123",
                "name": "get_pricing",
            }
        ]
        result = await executor.execute_tool_calls(tool_calls)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_tool_calls_none_input(self, executor):
        """Test execute_tool_calls with None input"""
        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool_456"
        mock_tool_use.name = "get_pricing"
        mock_tool_use.input = None

        result = await executor.execute_tool_calls([mock_tool_use])
        assert len(result) == 1
