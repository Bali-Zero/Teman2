"""
Workflow Chain Executor.

Dispatches workflow jobs to their registered executors.
Each chain_id maps to a coroutine that receives (payload, thread_id, checkpointer).

Chain implementations call the backend API internally via httpx (not the MCP server)
to avoid cross-process coupling. The checkpointer handles LangGraph state persistence.
"""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("zantara.workflow.executor")

# Registry: chain_id -> async callable(payload, thread_id, app_state)
_CHAIN_REGISTRY: dict[str, Any] = {}


def register_chain(chain_id: str) -> Callable:
    """Decorator to register a chain executor."""

    def decorator(fn: Callable) -> Callable:
        _CHAIN_REGISTRY[chain_id] = fn
        logger.debug(f"Registered chain executor: {chain_id}")
        return fn

    return decorator


async def execute_chain(
    chain_id: str,
    thread_id: str,
    payload: dict[str, Any],
    app_state: Any,
) -> dict[str, Any]:
    """
    Execute a workflow chain by chain_id.
    Raises KeyError if chain not registered.
    """
    executor = _CHAIN_REGISTRY.get(chain_id)
    if executor is None:
        raise KeyError(
            f"No executor registered for chain_id='{chain_id}'. "
            f"Available: {list(_CHAIN_REGISTRY.keys())}"
        )

    logger.info(f"Dispatching chain_id={chain_id} thread_id={thread_id}")
    result = await executor(payload=payload, thread_id=thread_id, app_state=app_state)
    return result or {}


def get_registered_chains() -> list[str]:
    return list(_CHAIN_REGISTRY.keys())
