"""
LAM Episodic Memory Tools
Exposes save_episode, recall_similar, list_recent_episodes, delete_episode
to the MCP agent layer via the /api/memory/lam/* backend endpoints.
"""

import logging
from typing import Any, Callable, Optional

from nuzantara_mcp.auth import require_role

logger = logging.getLogger("nuzantara-mcp.memory")


def register(mcp, _call: Callable, _call_safe: Callable) -> None:

    @mcp.tool()
    @require_role("visa_specialist", "tax_consultant", "company_setup", "admin")
    async def save_episode(
        content: str,
        agent: str = "main",
        tags: Optional[list[str]] = None,
        outcome: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        """
        Save a memory episode for the LAM agent after completing a task.

        Use this to remember:
        - What you did and what happened (outcome)
        - Key decisions taken and why
        - Errors encountered and how they were fixed
        - Client patterns and preferences

        Args:
            content: Description of the episode (what happened, what was done)
            agent: Agent identifier, default "main"
            tags: Semantic labels e.g. ["client_onboarding", "error_recovery"]
            outcome: Result — "success", "partial", "failed", or free text
            metadata: Extra structured context (client_id, tool_used, etc.)

        Returns:
            {"id": "uuid", "status": "saved"}
        """
        return await _call_safe(
            "/api/memory/lam/episodes",
            method="POST",
            json={
                "content": content,
                "agent": agent,
                "tags": tags if tags is not None else [],
                "outcome": outcome,
                "metadata": metadata if metadata is not None else {},
            },
        )

    @mcp.tool()
    @require_role("visa_specialist", "tax_consultant", "company_setup")
    async def recall_similar(
        query: str,
        limit: int = 5,
        agent: Optional[str] = None,
    ) -> dict:
        """
        Recall past episodes semantically similar to a query.

        Use this BEFORE attempting a task to check if you've solved
        something similar before and what the outcome was.

        Args:
            query: Natural language description of the current task or question
            limit: Max episodes to return (default 5)
            agent: Filter by agent name (optional)

        Returns:
            {"results": [...episodes sorted by similarity...], "query": "...", "execution_time_ms": ...}
        """
        return await _call_safe(
            "/api/memory/lam/recall",
            method="POST",
            json={"query": query, "limit": limit, "agent": agent},
        )

    @mcp.tool()
    async def list_recent_episodes(
        limit: int = 10,
        agent: Optional[str] = None,
    ) -> dict:
        """
        List the most recent LAM memory episodes.

        Use this to review recent history or audit what has been remembered.

        Args:
            limit: Max episodes to return (default 10)
            agent: Filter by agent name (optional)

        Returns:
            {"episodes": [...], "total": N}
        """
        params: dict[str, Any] = {"limit": limit}
        if agent:
            params["agent"] = agent
        return await _call_safe("/api/memory/lam/episodes", params=params)

    @mcp.tool()
    @require_role("admin")
    async def delete_episode(episode_id: str) -> dict:
        """
        Delete a specific LAM memory episode by ID.

        Use this to remove outdated, incorrect, or irrelevant memories.

        Args:
            episode_id: UUID of the episode to delete

        Returns:
            {"status": "deleted", "id": "..."}
        """
        return await _call_safe(f"/api/memory/lam/episodes/{episode_id}", method="DELETE")
