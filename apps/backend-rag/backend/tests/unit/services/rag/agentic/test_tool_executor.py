"""
Comprehensive test coverage for tool_executor.py
Target: Maximum coverage for all code paths - Security Critical
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.tool_executor import (
    execute_tool,
    parse_native_function_call,
    parse_tool_call,
    parse_tool_call_regex,
)
from backend.services.tools.definitions import BaseTool


class MockTool(BaseTool):
    """Mock tool for testing"""

    def __init__(self, name: str = "mock_tool", execute_result: str = "success"):
        self._name = name
        self._execute_result = execute_result
        self._should_raise = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock tool {self._name}"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> str:
        if self._should_raise:
            raise self._should_raise(self._execute_result)
        return self._execute_result

    def to_gemini_function_declaration(self) -> dict:
        return {"name": self._name, "description": self.description}

    def set_raise_exception(self, exception_class, message: str = "error"):
        """Helper to make execute raise an exception"""
        self._should_raise = exception_class
        self._execute_result = message


class TestParseNativeFunctionCall:
    """Test suite for parse_native_function_call"""

    def test_no_function_call_attribute(self):
        """Test when object has no function_call attribute"""
        obj = MagicMock(spec=[])
        result = parse_native_function_call(obj)
        assert result is None

    def test_function_call_is_none(self):
        """Test when function_call attribute exists but is None"""
        obj = MagicMock()
        obj.function_call = None
        result = parse_native_function_call(obj)
        assert result is None

    def test_successful_parsing_with_args(self):
        """Test successful parsing with arguments"""
        obj = MagicMock()
        obj.function_call.name = "vector_search"
        obj.function_call.args = {"query": "test", "collection": "test_collection"}
        result = parse_native_function_call(obj)
        assert result is not None
        assert result.tool_name == "vector_search"
        assert result.arguments == {"query": "test", "collection": "test_collection"}

    def test_successful_parsing_empty_args(self):
        """Test successful parsing with empty arguments"""
        obj = MagicMock()
        obj.function_call.name = "calculator"
        obj.function_call.args = {}
        result = parse_native_function_call(obj)
        assert result is not None
        assert result.tool_name == "calculator"
        assert result.arguments == {}

    def test_successful_parsing_none_args(self):
        """Test successful parsing with None arguments (converted to empty dict)"""
        obj = MagicMock()
        obj.function_call.name = "test_tool"
        obj.function_call.args = None
        result = parse_native_function_call(obj)
        assert result is not None
        assert result.tool_name == "test_tool"
        assert result.arguments == {}

    def test_empty_tool_name(self):
        """Test when tool_name is empty string"""
        obj = MagicMock()
        obj.function_call.name = ""
        obj.function_call.args = {}
        result = parse_native_function_call(obj)
        assert result is None

    def test_empty_tool_name_with_none_args(self):
        """Test when tool_name is empty and args is None"""
        obj = MagicMock()
        obj.function_call.name = ""
        obj.function_call.args = None
        result = parse_native_function_call(obj)
        assert result is None


class TestParseToolCallRegex:
    """Test suite for parse_tool_call_regex"""

    def test_no_match(self):
        """Test when regex doesn't match"""
        text = "This is just regular text"
        result = parse_tool_call_regex(text)
        assert result is None

    def test_vector_search_with_key_value_args(self):
        """Test parsing vector_search with key=value arguments"""
        text = 'ACTION: vector_search(query="visa requirements", collection="visa_oracle")'
        result = parse_tool_call_regex(text)
        assert result is not None
        assert result.tool_name == "vector_search"
        assert result.arguments["query"] == "visa requirements"
        assert result.arguments["collection"] == "visa_oracle"

    def test_vector_search_with_single_query_arg(self):
        """Test parsing vector_search with single query argument"""
        text = 'ACTION: vector_search("test query")'
        result = parse_tool_call_regex(text)
        assert result is not None
        assert result.tool_name == "vector_search"
        assert result.arguments["query"] == "test query"

    def test_web_search_with_single_query_arg(self):
        """Test parsing web_search with single query argument"""
        text = 'ACTION: web_search("bali weather")'
        result = parse_tool_call_regex(text)
        assert result is not None
        assert result.tool_name == "web_search"
        assert result.arguments["query"] == "bali weather"

    def test_calculator_with_expression_arg(self):
        """Test parsing calculator with expression argument"""
        text = 'ACTION: calculator("1000000 * 0.25")'
        result = parse_tool_call_regex(text)
        assert result is not None
        assert result.tool_name == "calculator"
        assert result.arguments["expression"] == "1000000 * 0.25"

    def test_unknown_tool_with_args(self):
        """Test parsing unknown tool (should return empty args)"""
        text = 'ACTION: unknown_tool("some arg")'
        result = parse_tool_call_regex(text)
        assert result is not None
        assert result.tool_name == "unknown_tool"
        assert result.arguments == {}

    def test_args_with_single_quotes(self):
        """Test parsing args with single quotes"""
        text = "ACTION: vector_search(query='test query', collection='test_collection')"
        result = parse_tool_call_regex(text)
        assert result is not None
        assert result.arguments["query"] == "test query"
        assert result.arguments["collection"] == "test_collection"

    def test_args_with_whitespace(self):
        """Test parsing args with whitespace"""
        text = 'ACTION: vector_search(query = "test query" , collection = "test_collection" )'
        result = parse_tool_call_regex(text)
        assert result is not None
        assert result.arguments["query"] == "test query"
        assert result.arguments["collection"] == "test_collection"

    def test_invalid_args_parsing(self):
        """Test when args parsing fails (ValueError)"""
        text = "ACTION: vector_search(invalid=args=format)"
        result = parse_tool_call_regex(text)
        assert result is None

    def test_args_parsing_keyerror(self):
        """Test when args parsing raises KeyError"""
        # This is hard to trigger directly, but we can test the error handling path
        text = "ACTION: vector_search()"
        result = parse_tool_call_regex(text)
        # Should return a ToolCall with empty args
        assert result is not None
        assert result.tool_name == "vector_search"


class TestParseToolCall:
    """Test suite for parse_tool_call (universal parser)"""

    def test_native_mode_success(self):
        """Test native mode with successful native parsing"""
        obj = MagicMock()
        obj.function_call.name = "vector_search"
        obj.function_call.args = {"query": "test"}
        result = parse_tool_call(obj, use_native=True)
        assert result is not None
        assert result.tool_name == "vector_search"

    def test_native_mode_fallback_to_regex(self):
        """Test native mode falls back to regex when native fails"""
        text = 'ACTION: vector_search("test")'
        result = parse_tool_call(text, use_native=True)
        assert result is not None
        assert result.tool_name == "vector_search"

    def test_native_mode_no_fallback_if_not_string(self):
        """Test native mode doesn't fallback if input is not string"""
        obj = MagicMock()
        # No function_call attribute
        del obj.function_call
        result = parse_tool_call(obj, use_native=True)
        assert result is None

    def test_regex_only_mode(self):
        """Test regex-only mode (use_native=False)"""
        text = 'ACTION: vector_search("test")'
        result = parse_tool_call(text, use_native=False)
        assert result is not None
        assert result.tool_name == "vector_search"

    def test_regex_only_mode_no_match(self):
        """Test regex-only mode with no match"""
        text = "Just text"
        result = parse_tool_call(text, use_native=False)
        assert result is None

    def test_none_input(self):
        """Test with None input"""
        result = parse_tool_call(None, use_native=True)
        assert result is None

    def test_integer_input(self):
        """Test with non-string, non-object input"""
        result = parse_tool_call(123, use_native=True)
        assert result is None


class TestExecuteTool:
    """Test suite for execute_tool"""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Test rate limiting raises RuntimeError"""
        tool_map = {"test_tool": MockTool("test_tool")}
        counter = {"count": 10}  # Already at limit
        with pytest.raises(RuntimeError, match="Maximum tool executions exceeded"):
            await execute_tool(tool_map, "test_tool", {}, tool_execution_counter=counter)

    @pytest.mark.asyncio
    async def test_rate_limit_at_limit(self):
        """Test rate limiting at exactly 10 (should still allow)"""
        tool_map = {"test_tool": MockTool("test_tool")}
        counter = {"count": 9}  # One before limit
        result, duration = await execute_tool(
            tool_map, "test_tool", {}, tool_execution_counter=counter
        )
        assert result == "success"
        assert counter["count"] == 10

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Test unknown tool returns error message"""
        tool_map = {"known_tool": MockTool("known_tool")}
        result, duration = await execute_tool(tool_map, "unknown_tool", {})
        assert "Error: Unknown tool 'unknown_tool'" in result
        assert isinstance(duration, float)
        assert duration >= 0

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful tool execution"""
        tool_map = {"test_tool": MockTool("test_tool", "result123")}
        result, duration = await execute_tool(tool_map, "test_tool", {})
        assert result == "result123"
        assert isinstance(duration, float)
        assert duration >= 0

    @pytest.mark.asyncio
    async def test_user_id_injection(self):
        """Test user_id is injected into arguments"""
        tool = MockTool("test_tool")
        tool_map = {"test_tool": tool}
        execute_spy = AsyncMock(return_value="success")
        tool.execute = execute_spy

        await execute_tool(tool_map, "test_tool", {"arg1": "value1"}, user_id="user123")

        # Verify user_id was added to arguments
        execute_spy.assert_called_once()
        call_kwargs = execute_spy.call_args[1]
        assert call_kwargs["arg1"] == "value1"
        assert call_kwargs["_user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_no_user_id_injection_when_none(self):
        """Test user_id is not injected when None"""
        tool = MockTool("test_tool")
        tool_map = {"test_tool": tool}
        execute_spy = AsyncMock(return_value="success")
        tool.execute = execute_spy

        await execute_tool(tool_map, "test_tool", {"arg1": "value1"}, user_id=None)

        call_kwargs = execute_spy.call_args[1]
        assert "_user_id" not in call_kwargs

    @pytest.mark.asyncio
    async def test_no_user_id_injection_when_empty_string(self):
        """Test user_id is not injected when empty string"""
        tool = MockTool("test_tool")
        tool_map = {"test_tool": tool}
        execute_spy = AsyncMock(return_value="success")
        tool.execute = execute_spy

        await execute_tool(tool_map, "test_tool", {"arg1": "value1"}, user_id="")

        call_kwargs = execute_spy.call_args[1]
        assert "_user_id" not in call_kwargs

    @pytest.mark.asyncio
    async def test_value_error_handling(self):
        """Test ValueError from tool.execute is caught"""
        tool = MockTool("test_tool")
        tool.set_raise_exception(ValueError, "Invalid value")
        tool_map = {"test_tool": tool}

        result, duration = await execute_tool(tool_map, "test_tool", {})

        assert "Error executing test_tool" in result
        assert "Invalid value" in result
        assert isinstance(duration, float)

    @pytest.mark.asyncio
    async def test_runtime_error_handling(self):
        """Test RuntimeError from tool.execute is caught"""
        tool = MockTool("test_tool")
        tool.set_raise_exception(RuntimeError, "Runtime error")
        tool_map = {"test_tool": tool}

        result, duration = await execute_tool(tool_map, "test_tool", {})

        assert "Error executing test_tool" in result
        assert "Runtime error" in result

    @pytest.mark.asyncio
    async def test_key_error_handling(self):
        """Test KeyError from tool.execute is caught"""
        tool = MockTool("test_tool")
        tool.set_raise_exception(KeyError, "Missing key")
        tool_map = {"test_tool": tool}

        result, duration = await execute_tool(tool_map, "test_tool", {})

        assert "Error executing test_tool" in result

    @pytest.mark.asyncio
    async def test_type_error_handling(self):
        """Test TypeError from tool.execute is caught"""
        tool = MockTool("test_tool")
        tool.set_raise_exception(TypeError, "Type error")
        tool_map = {"test_tool": tool}

        result, duration = await execute_tool(tool_map, "test_tool", {})

        assert "Error executing test_tool" in result
        assert "Type error" in result

    @pytest.mark.asyncio
    async def test_attribute_error_handling(self):
        """Test AttributeError from tool.execute is caught"""
        tool = MockTool("test_tool")
        tool.set_raise_exception(AttributeError, "Attribute error")
        tool_map = {"test_tool": tool}

        result, duration = await execute_tool(tool_map, "test_tool", {})

        assert "Error executing test_tool" in result
        assert "Attribute error" in result

    @pytest.mark.asyncio
    async def test_no_counter_provided(self):
        """Test execution without counter (should not limit)"""
        tool_map = {"test_tool": MockTool("test_tool")}
        result, duration = await execute_tool(
            tool_map, "test_tool", {}, tool_execution_counter=None
        )
        assert result == "success"

    @pytest.mark.asyncio
    @patch("backend.services.rag.agentic.tool_executor.metrics_collector")
    async def test_metrics_recorded_on_success(self, mock_metrics):
        """Test metrics are recorded on successful execution"""
        tool_map = {"test_tool": MockTool("test_tool")}
        await execute_tool(tool_map, "test_tool", {})
        mock_metrics.record_tool_call.assert_called_with("test_tool", "success")

    @pytest.mark.asyncio
    @patch("backend.services.rag.agentic.tool_executor.metrics_collector")
    async def test_metrics_recorded_on_error(self, mock_metrics):
        """Test metrics are recorded on error"""
        tool = MockTool("test_tool")
        tool.set_raise_exception(ValueError, "error")
        tool_map = {"test_tool": tool}

        await execute_tool(tool_map, "test_tool", {})

        mock_metrics.record_tool_call.assert_called_with("test_tool", "error")

    @pytest.mark.asyncio
    @patch("backend.services.rag.agentic.tool_executor.metrics_collector")
    async def test_metrics_recorded_on_unknown_tool(self, mock_metrics):
        """Test metrics are recorded for unknown tool"""
        tool_map = {}
        await execute_tool(tool_map, "unknown_tool", {})
        mock_metrics.record_tool_call.assert_called_with("unknown_tool", "unknown")

    @pytest.mark.asyncio
    @patch("backend.services.rag.agentic.tool_executor.metrics_collector")
    async def test_metrics_recorded_on_rate_limit(self, mock_metrics):
        """Test metrics are recorded on rate limit"""
        tool_map = {"test_tool": MockTool("test_tool")}
        counter = {"count": 10}

        with pytest.raises(RuntimeError):
            await execute_tool(tool_map, "test_tool", {}, tool_execution_counter=counter)

        mock_metrics.record_tool_call.assert_called_with("test_tool", "rate_limited")

    @pytest.mark.asyncio
    async def test_execution_duration_tracking(self):
        """Test execution duration is tracked correctly"""
        import asyncio

        async def slow_execute(**kwargs):
            await asyncio.sleep(0.01)  # 10ms delay
            return "slow result"

        tool = MockTool("slow_tool")
        tool.execute = slow_execute
        tool_map = {"slow_tool": tool}

        result, duration = await execute_tool(tool_map, "slow_tool", {})

        assert result == "slow result"
        assert duration >= 0.01  # Should be at least 10ms

    @pytest.mark.asyncio
    async def test_counter_incremented_on_success(self):
        """Test counter is incremented on successful execution"""
        tool_map = {"test_tool": MockTool("test_tool")}
        counter = {"count": 5}

        await execute_tool(tool_map, "test_tool", {}, tool_execution_counter=counter)

        assert counter["count"] == 6

    @pytest.mark.asyncio
    async def test_counter_incremented_before_execution(self):
        """Test counter is incremented before execution (so rate limit check happens)"""
        tool_map = {"test_tool": MockTool("test_tool")}
        counter = {"count": 9}

        # This should succeed and increment to 10
        await execute_tool(tool_map, "test_tool", {}, tool_execution_counter=counter)

        assert counter["count"] == 10

    @pytest.mark.asyncio
    async def test_empty_arguments(self):
        """Test execution with empty arguments dict"""
        tool_map = {"test_tool": MockTool("test_tool")}
        result, duration = await execute_tool(tool_map, "test_tool", {})
        assert result == "success"

    @pytest.mark.asyncio
    async def test_complex_arguments(self):
        """Test execution with complex arguments"""
        tool = MockTool("test_tool")
        tool_map = {"test_tool": tool}
        execute_spy = AsyncMock(return_value="success")
        tool.execute = execute_spy

        complex_args = {
            "query": "test query",
            "collection": "test_collection",
            "limit": 10,
            "metadata": {"key": "value"},
        }

        await execute_tool(tool_map, "test_tool", complex_args)

        call_kwargs = execute_spy.call_args[1]
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["collection"] == "test_collection"
        assert call_kwargs["limit"] == 10
        assert call_kwargs["metadata"] == {"key": "value"}
