"""Naga search agents — pluggable web/domain/academic search backends."""

from backend.services.naga.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

__all__ = [
    "AgentResponse",
    "BaseSearchAgent",
    "SearchResult",
]
