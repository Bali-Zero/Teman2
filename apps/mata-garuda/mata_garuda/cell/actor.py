"""MetaChainActor — wraps MG's run_with_lamarckian_feedback as cell-core Actor.

The existing MetaChain loop is synchronous. This adapter runs it via
asyncio.to_thread() to keep PulseLoop's event loop clean.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from cell_core.types import Proposal

# Import side-effect: populate @register_agent decorators so get_agent() works
# when this module is imported before mata_garuda.agents.
import mata_garuda.agents  # noqa: F401

from mata_garuda.registry import get_agent
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.runtime.lamarckian import run_with_lamarckian_feedback
from mata_garuda.types import Response

logger = logging.getLogger("mata_garuda.cell")

# Map PulseLoop action names to MG agent names
_ACTION_TO_AGENT = {
    "run_regulation_watcher": "Regulation Watcher",
    "run_meta_agent": "Meta Agent",
}


class MetaChainActor:
    """Wraps MG's Lamarckian loop as a cell-core Actor protocol."""

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        self._kb = kb
        self.last_run_success: Optional[bool] = None
        self.last_response: Optional[Response] = None

    def can_execute(self, action_name: str) -> bool:
        return action_name in _ACTION_TO_AGENT

    async def act(self, proposal: Proposal) -> str:
        agent_name = _ACTION_TO_AGENT.get(proposal.action)
        if not agent_name:
            return f"[ERROR] Unknown action: {proposal.action}"

        try:
            response = await asyncio.to_thread(
                self._run_sync, agent_name, proposal.reason,
            )
            self.last_response = response

            # Determine success from messages
            last_msg = response.messages[-1]["content"] if response.messages else ""
            if "case resolved" in last_msg.lower() or "case_resolved" in last_msg.lower():
                self.last_run_success = True
                return f"resolved: {last_msg[:200]}"
            elif "case not resolved" in last_msg.lower() or "case_not_resolved" in last_msg.lower():
                self.last_run_success = False
                return f"not_resolved: {last_msg[:200]}"
            else:
                self.last_run_success = None
                return f"completed: {last_msg[:200]}"
        except Exception as e:
            self.last_run_success = False
            logger.error(f"[actor] MetaChain failed: {e}")
            return f"[ERROR] {e}"

    def _run_sync(self, agent_name: str, query: str) -> Response:
        """Run MG agent synchronously — called via asyncio.to_thread."""
        agent = get_agent(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not registered")
        return run_with_lamarckian_feedback(
            agent=agent, query=query, kb=self._kb,
        )
