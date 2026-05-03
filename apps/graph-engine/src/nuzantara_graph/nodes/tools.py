"""Tools node — executes tool calls requested by the reason node."""

from __future__ import annotations

import time
from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState
from nuzantara_schemas.tools import ToolCallRecord, ToolStatus

logger = structlog.get_logger()

# Registry of available tools — extended in later batches
TOOL_REGISTRY: dict[str, Any] = {}


def register_tool(name: str, func: Any) -> None:
    """Register a tool function by name."""
    TOOL_REGISTRY[name] = func


def make_tools_node(services: Services):
    """Factory that creates a tools node with injected services."""

    async def tools_node(state: GraphState) -> dict[str, Any]:
        """Execute pending tool calls from the reason node."""
        logger.info("tools_start", pending_calls=len(state.tool_calls))

        executed: list[ToolCallRecord] = []

        for call in state.tool_calls:
            if call.status != ToolStatus.PENDING:
                executed.append(call)
                continue

            start = time.monotonic()
            tool_func = TOOL_REGISTRY.get(call.tool_name)

            if tool_func is None:
                executed.append(
                    call.model_copy(update={
                        "status": ToolStatus.ERROR,
                        "error_message": f"Unknown tool: {call.tool_name}",
                        "duration_ms": (time.monotonic() - start) * 1000,
                    })
                )
                continue

            try:
                result = await tool_func(**call.arguments)
                executed.append(
                    call.model_copy(update={
                        "status": ToolStatus.SUCCESS,
                        "result": result,
                        "duration_ms": (time.monotonic() - start) * 1000,
                    })
                )
            except Exception as e:
                executed.append(
                    call.model_copy(update={
                        "status": ToolStatus.ERROR,
                        "error_message": str(e),
                        "duration_ms": (time.monotonic() - start) * 1000,
                    })
                )

        logger.info(
            "tools_complete",
            total=len(executed),
            success=sum(1 for c in executed if c.status == ToolStatus.SUCCESS),
        )

        return {
            "tool_calls": executed,
            "current_node": "tools",
        }

    return tools_node
