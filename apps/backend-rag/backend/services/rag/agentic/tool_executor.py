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
- Prometheus metrics for tool call tracking
"""

import logging
import re
import time
from typing import Any

from backend.app.metrics import metrics_collector
from backend.services.agents.confirmation_service import (
    ConfirmationRedisDown,
    ConfirmationService,
    ConfirmationTimeout,
)
from backend.services.agents.tool_authorizer import ToolAuthorizer
from backend.services.tools.definitions import BaseTool, ToolCall

logger = logging.getLogger(__name__)

# Module-level singletons — set by service_initializer.py at app startup.
# Before Phase 3 wiring, the authorizer was a bare ToolAuthorizer() with no
# dependencies. Now it may have a ConfirmationService. Both are replaced once
# by `configure_tool_executor()` during initialization.
_authorizer = ToolAuthorizer()
_confirmation_service: ConfirmationService | None = None


def configure_tool_executor(
    authorizer: ToolAuthorizer,
    confirmation_service: ConfirmationService | None = None,
) -> None:
    """
    Called once by service_initializer.py to inject app-scoped singletons.

    This replaces the module-level defaults with properly wired instances.
    The function exists so that tool_executor doesn't import from
    service_initializer (which would create a circular import).
    """
    global _authorizer, _confirmation_service  # noqa: PLW0603
    _authorizer = authorizer
    _confirmation_service = confirmation_service


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
        # fc can be None even if the attribute exists
        if fc is None:
            return None
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
    agent_role: Any | None = None,
    confirmation_emitter: Any | None = None,
) -> tuple[str, float]:
    """
    Execute tool with rate limiting and RBAC authorization.

    Args:
        tool_map: Dictionary mapping tool names to tool instances
        tool_name: Name of tool to execute
        arguments: Tool arguments (LLM-supplied — must NOT contain server fields)
        user_id: Optional user ID for admin tools
        tool_execution_counter: Mutable dict with 'count' key for rate limiting
        agent_role: VASSAL Phase 2. The caller's AgentRole (from
            team_agent_config) for server-side RBAC enforcement. When None
            (legacy /stream path, blog/marketing flows), the authorizer
            passes through as ALLOWED. Read by reasoning.py via
            getattr(state, "agent_role", None) at each call site.
        confirmation_emitter: VASSAL Phase 3. Optional async callback
            ``Callable[[dict], Awaitable[None]]`` that pushes SSE events
            upstream to the streaming generator. Set by reasoning.py at
            the streaming call site; None for non-streaming paths.
            Deviation from briefing §3.2 ("no new params on execute_tool"):
            the alternative — pre-computing confirmation needs in
            reasoning.py — would duplicate authorizer logic and pollute
            args. This single optional kwarg keeps the authorizer as the
            single source of truth for confirmation decisions.

    Returns:
        Tuple of (tool execution result as string, execution duration in seconds)

    Raises:
        RuntimeError: If rate limit exceeded (10 per query)
    """
    start_time = time.time()

    # Security: Rate limiting - max 10 tool executions per query
    if tool_execution_counter is not None:
        tool_execution_counter["count"] += 1
        if tool_execution_counter["count"] > 10:
            logger.warning(
                f"⚠️ Tool execution limit exceeded ({tool_execution_counter['count']} > 10)",
            )
            metrics_collector.record_tool_call(tool_name, "rate_limited")
            raise RuntimeError("Maximum tool executions exceeded (10 per query)")

    # Unknown-tool short-circuit MUST run BEFORE authorization. There is no
    # point asking the authorizer about a tool that doesn't exist in the
    # registry — and the test contract (test_unknown_tool_short_circuits_before_authz)
    # encodes this ordering explicitly.
    if tool_name not in tool_map:
        metrics_collector.record_tool_call(tool_name, "unknown")
        return f"Error: Unknown tool '{tool_name}'", time.time() - start_time

    tool = tool_map[tool_name]

    # ── VASSAL Phase 2: RBAC chokepoint ─────────────────────────────────
    # The authorizer is invoked BEFORE we mutate `arguments` with server
    # fields (`_user_id`). This matters because:
    #   1. The authorizer must see only LLM-supplied args (server fields
    #      would confuse future client_scope checks).
    #   2. The authorizer can mutate args (Phase 3+ may inject scope
    #      filters); whatever it returns becomes the new authoritative
    #      args dict.
    # When `agent_role=None` (legacy /stream path), the authorizer's own
    # backward-compat branch returns ALLOWED — see ToolAuthorizer.authorize().
    auth_result = await _authorizer.authorize(
        user_email=user_id,
        agent_role=agent_role,
        tool_name=tool_name,
        args=arguments,
    )
    if auth_result.is_denied:
        metrics_collector.record_tool_call(tool_name, "denied")
        return (
            f"Tool execution denied: {auth_result.reason}",
            time.time() - start_time,
        )
    if auth_result.needs_confirmation:
        # ── VASSAL Phase 3: interactive confirmation gate ────────────────
        # The authorizer has determined that this tool requires user
        # confirmation before execution. If a ConfirmationService is
        # wired, we request confirmation, emit an SSE event for the
        # frontend modal (Phase 3B), and block until the user resolves.
        # If the service is not wired (e.g., in tests or light mode),
        # fail-closed: treat as DENIED.
        if _confirmation_service is None:
            logger.warning(
                "tool_authz: NEEDS_CONFIRMATION for %s but "
                "ConfirmationService is not wired — treating as DENIED",
                tool_name,
            )
            metrics_collector.record_tool_call(tool_name, "denied")
            return (
                f"Tool execution denied: confirmation service unavailable "
                f"for '{tool_name}'",
                time.time() - start_time,
            )
        try:
            approved = await _confirmation_service.request_and_wait(
                tool_name=tool_name,
                args=arguments,
                user_email=user_id or "anonymous",
                preview=auth_result.reason,
                emitter=confirmation_emitter,
            )
        except ConfirmationRedisDown as exc:
            metrics_collector.record_tool_call(tool_name, "denied")
            logger.warning(
                "tool_authz: confirmation Redis down for %s: %s",
                tool_name,
                exc,
            )
            return (
                f"Tool execution denied: confirmation system unavailable "
                f"(Redis down) for '{tool_name}'",
                time.time() - start_time,
            )
        except ConfirmationTimeout:
            metrics_collector.record_tool_call(tool_name, "timeout")
            logger.info(
                "tool_authz: confirmation timed out for %s",
                tool_name,
            )
            return (
                f"Tool execution denied: user did not confirm "
                f"'{tool_name}' within the allowed time",
                time.time() - start_time,
            )
        if not approved:
            metrics_collector.record_tool_call(tool_name, "rejected")
            logger.info(
                "tool_authz: user rejected confirmation for %s",
                tool_name,
            )
            return (
                f"Tool execution denied: user rejected '{tool_name}'",
                time.time() - start_time,
            )
        metrics_collector.record_tool_call(tool_name, "confirmed")
        logger.info("tool_authz: user confirmed %s — proceeding", tool_name)
    # Authoritative args after the authorizer (possibly mutated in
    # Phase 3+; Phase 2 returns args unchanged).
    arguments = auth_result.args

    try:
        # Pass user_id to tools that need it (e.g., MCPSuperTool for admin
        # check). Injected AFTER the authorizer call so the authorizer never
        # sees server-controlled fields mixed in with LLM-supplied args.
        if user_id:
            arguments["_user_id"] = user_id
        result = await tool.execute(**arguments)
        duration = time.time() - start_time

        # Record successful tool call
        metrics_collector.record_tool_call(tool_name, "success")
        logger.debug(f"🔧 [Tool] {tool_name} completed in {duration:.3f}s")

        return result, duration
    except (ValueError, RuntimeError, KeyError, TypeError, AttributeError) as e:
        duration = time.time() - start_time
        metrics_collector.record_tool_call(tool_name, "error")
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return f"Error executing {tool_name}: {str(e)}", duration
