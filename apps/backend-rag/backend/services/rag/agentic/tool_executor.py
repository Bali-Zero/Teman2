"""
Tool Execution and Parsing for Agentic RAG

This module handles:
- Parsing tool calls from AI responses (native function calling or ReAct format)
- Executing tools with rate limiting
- Tool result handling
- Security validation

Key Features:
- Native Gemini function calling (primary)
- Regex ReAct parser fallback for OpenRouter/non-Gemini models
- Rate limiting (max 10 executions per query)
- User ID injection for admin tools
- Error handling and logging
"""

import logging
import re
from typing import Any

from services.tools.definitions import BaseTool, ToolCall

logger = logging.getLogger(__name__)


def parse_native_function_call(function_call_part: Any) -> ToolCall | None:
    """
    Parse native Gemini function call from response part.

    This is the primary method for tool calling when using Gemini models.
    Extracts function name and arguments from Gemini's native function_call object.

    Args:
        function_call_part: Gemini response part with function_call attribute

    Returns:
        ToolCall object if function call detected, None otherwise

    Example:
        >>> # Gemini returns: part.function_call.name = "vector_search"
        >>> # part.function_call.args = {"query": "visa requirements", "collection": "visa_oracle"}
        >>> tool_call = parse_native_function_call(part)
        >>> print(tool_call.tool_name)  # "vector_search"
    """
    if not hasattr(function_call_part, "function_call"):
        return None

    try:
        fc = function_call_part.function_call
        tool_name = fc.name
        arguments = dict(fc.args) if fc.args else {}
        
        if not tool_name:
            logger.warning("🔧 [Native Function Call] Empty tool name detected (ignoring)")
            return None

        logger.info(f"🔧 [Native Function Call] Detected: {tool_name} with args: {arguments}")
        return ToolCall(tool_name=tool_name, arguments=arguments)

    except (AttributeError, TypeError, ValueError) as e:
        logger.warning(f"Failed to parse native function call: {e}", exc_info=True)
        return None


def parse_tool_call_regex(text: str) -> ToolCall | None:
    """
    FALLBACK: Parse ReAct-style tool calls from text using regex.

    This is a legacy parser used only for OpenRouter and non-Gemini models.
    For Gemini models, use parse_native_function_call() instead.

    Args:
        text: AI response text to parse

    Returns:
        ToolCall object if found, None otherwise

    Example:
        ACTION: vector_search(query="visa requirements", collection="visa_oracle")
        ACTION: calculator(expression="1000000 * 0.25")

    Note:
        This parser is fragile and deprecated. Prefer native function calling.
    """
    logger.debug(f"[FALLBACK Regex Parser] Parsing text (first 500 chars): {text[:500]}...")

    match = re.search(r"ACTION:\s*(\w+)\((.*)\)", text)
    if match:
        tool_name = match.group(1)
        args_str = match.group(2)
        try:
            # Try to parse args as JSON-like key=value or just string
            # This is very basic
            if "=" in args_str:
                args = dict(item.split("=") for item in args_str.split(","))
                # Clean quotes
                args = {k.strip(): v.strip().strip('"').strip("'") for k, v in args.items()}
            else:
                # Assume single arg 'query' or 'expression' based on tool
                if tool_name in ["vector_search", "web_search"]:
                    args = {"query": args_str.strip().strip('"')}
                elif tool_name == "calculator":
                    args = {"expression": args_str.strip().strip('"')}
                else:
                    args = {}

            logger.info(f"🔧 [Regex Fallback] Parsed: {tool_name} with args: {args}")
            return ToolCall(tool_name=tool_name, arguments=args)
        except (ValueError, KeyError, AttributeError):
            return None
    return None


def parse_tool_call(text_or_part: Any, use_native: bool = True) -> ToolCall | None:
    """
    Universal tool call parser with automatic mode detection.

    Attempts native function calling first, then falls back to regex parsing.
    This ensures compatibility with both Gemini (native) and OpenRouter (text).

    Args:
        text_or_part: Either a Gemini response part (with function_call) or text string
        use_native: Whether to attempt native parsing first (default: True)

    Returns:
        ToolCall object if found, None otherwise

    Example:
        # Native mode (Gemini)
        >>> tool_call = parse_tool_call(response_part, use_native=True)

        # Fallback mode (OpenRouter)
        >>> tool_call = parse_tool_call(response_text, use_native=False)
    """
    if use_native:
        # Try native function calling first
        native_call = parse_native_function_call(text_or_part)
        if native_call:
            return native_call

    # Fallback to regex parsing (for text responses)
    if isinstance(text_or_part, str):
        return parse_tool_call_regex(text_or_part)

    return None


async def execute_tool(
    tool_map: dict[str, BaseTool],
    tool_name: str,
    arguments: dict,
    user_id: str | None = None,
    tool_execution_counter: dict[str, int] | None = None,
) -> str:
    """
    Execute tool with rate limiting to prevent abuse.

    Args:
        tool_map: Dictionary mapping tool names to tool instances
        tool_name: Name of tool to execute
        arguments: Tool arguments
        user_id: Optional user ID for admin tools
        tool_execution_counter: Mutable dict with 'count' key for rate limiting

    Returns:
        Tool execution result as string

    Raises:
        RuntimeError: If rate limit exceeded (10 per query)
    """
    # Security: Rate limiting - max 10 tool executions per query
    if tool_execution_counter is not None:
        tool_execution_counter["count"] += 1
        if tool_execution_counter["count"] > 10:
            logger.warning(
                f"⚠️ Tool execution limit exceeded ({tool_execution_counter['count']} > 10)"
            )
            raise RuntimeError("Maximum tool executions exceeded (10 per query)")

    if tool_name not in tool_map:
        return f"Error: Unknown tool '{tool_name}'"

    tool = tool_map[tool_name]

    try:
        # Pass user_id to tools that need it (e.g., MCPSuperTool for admin check)
        if user_id:
            arguments["_user_id"] = user_id
        result = await tool.execute(**arguments)
        return result
    except (ValueError, RuntimeError, KeyError, TypeError, AttributeError) as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return f"Error executing {tool_name}: {str(e)}"
