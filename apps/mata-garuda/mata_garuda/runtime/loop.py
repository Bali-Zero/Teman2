"""
Mata Garuda — MetaChain Loop.

Minimal agent execution loop:
1. Resolve agent instructions (str or callable)
2. Build prompt with tool descriptions
3. Send to CLI runtime
4. Parse tool calls from output
5. Execute tools, collect results
6. Repeat until no more tool calls or case_resolved/case_not_resolved

Sprint 2: synchronous, no Lamarckian (Sprint 3).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from mata_garuda.runtime.cli_runtime import CLIRuntime, parse_tool_calls
from mata_garuda.types import Agent, Response, Result

logger = logging.getLogger("mata_garuda.runtime")

MAX_TURNS = 10  # Safety limit to prevent infinite loops


def _resolve_instructions(agent: Agent, context_variables: dict) -> str:
    """Resolve agent instructions — can be str or callable(context_variables)."""
    if callable(agent.instructions):
        return agent.instructions(context_variables)
    return agent.instructions


def _build_tool_descriptions(agent: Agent) -> str:
    """Build a text description of available tools for the LLM."""
    if not agent.functions:
        return ""

    lines = ["\n\nAvailable tools (call via <tool_call> JSON):"]
    for fn in agent.functions:
        import inspect

        sig = inspect.signature(fn)
        params = []
        for name, param in sig.parameters.items():
            if name == "context_variables":
                continue
            annotation = (
                param.annotation.__name__
                if hasattr(param.annotation, "__name__")
                else str(param.annotation)
            )
            params.append(f"{name}: {annotation}")

        doc = inspect.getdoc(fn) or "No description"
        first_line = doc.strip().split("\n")[0]
        lines.append(f"- {fn.__name__}({', '.join(params)}): {first_line}")

    lines.append(
        '\nTo call a tool, output: <tool_call>{"tool_name": "name", '
        '"arguments": {"key": "value"}}</tool_call>'
    )
    lines.append(
        "After the tool runs, you will receive its result and can continue."
    )
    return "\n".join(lines)


def _execute_tool(
    agent: Agent, tool_name: str, arguments: dict, context_variables: dict
) -> str:
    """Find and execute a tool by name, return its result as string."""
    for fn in agent.functions:
        if fn.__name__ == tool_name:
            # Inject context_variables if the function accepts it
            import inspect

            sig = inspect.signature(fn)
            if "context_variables" in sig.parameters:
                arguments["context_variables"] = context_variables

            try:
                result = fn(**arguments)
            except Exception as e:
                return f"[ERROR] Tool {tool_name} failed: {e}"

            # Handle Result type (can trigger agent handoff)
            if isinstance(result, Result):
                if result.context_variables:
                    context_variables.update(result.context_variables)
                return result.value

            if isinstance(result, Agent):
                return f"[HANDOFF] Switching to agent: {result.name}"

            return str(result)

    return f"[ERROR] Unknown tool: {tool_name}"


def run_agent_loop(
    agent: Agent,
    query: str,
    context_variables: Optional[dict] = None,
    max_turns: int = MAX_TURNS,
) -> Response:
    """
    Run the MetaChain loop for an agent.

    Args:
        agent: Agent instance to run
        query: User query / task
        context_variables: Shared state across the conversation
        max_turns: Safety limit for loop iterations

    Returns:
        Response with all messages from the conversation
    """
    if context_variables is None:
        context_variables = {}

    runtime = CLIRuntime(model=agent.model)
    system_prompt = _resolve_instructions(agent, context_variables)
    tool_descriptions = _build_tool_descriptions(agent)
    full_system = system_prompt + tool_descriptions

    messages: list[dict] = []
    current_prompt = query

    for turn in range(max_turns):
        logger.info(f"[MetaChain] Turn {turn + 1}/{max_turns} for {agent.name}")

        result = runtime.invoke(prompt=current_prompt, system_prompt=full_system)

        if not result.success:
            messages.append({
                "role": "assistant",
                "content": f"[ERROR] CLI failed: {result.stderr}",
            })
            break

        output = result.output
        messages.append({"role": "assistant", "content": output})

        # Parse tool calls FIRST — they take priority over text-based case resolution.
        # Without this, "case_resolved" inside a <tool_call> tag triggers
        # early exit before the tool is actually executed.
        tool_calls = parse_tool_calls(output)

        if not tool_calls:
            # No tool calls — check for case resolution in plain text
            if "Case resolved" in output or "case_resolved" in output.lower():
                logger.info(f"[MetaChain] {agent.name} resolved the case")
                break

            if "Case not resolved" in output or "case_not_resolved" in output.lower():
                logger.info(f"[MetaChain] {agent.name} could not resolve the case")
                break

            # No tool calls and no case resolution — done
            logger.info(f"[MetaChain] {agent.name} finished (no tool calls)")
            break

        # Execute each tool call and collect results
        tool_results = []
        for tc in tool_calls:
            tool_name = tc.get("tool_name", "")
            arguments = tc.get("arguments", {})
            logger.info(f"[MetaChain] Executing tool: {tool_name}")

            tool_result = _execute_tool(
                agent, tool_name, arguments, context_variables
            )
            tool_results.append(f"[{tool_name}] {tool_result}")
            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": tool_result,
            })

        # Feed tool results back as next prompt
        current_prompt = (
            "Tool results:\n"
            + "\n".join(tool_results)
            + "\n\nContinue with your task. "
            "Call another tool or output case_resolved/case_not_resolved."
        )

    return Response(
        messages=messages,
        agent=agent,
        context_variables=context_variables,
    )
