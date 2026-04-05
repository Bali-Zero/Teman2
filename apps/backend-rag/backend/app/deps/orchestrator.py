"""
AgenticRAGOrchestrator dependency.

Lazy singleton — created on first request using services from app.state.
Exposed as module-level variable for health.py backward compatibility.
"""

import logging
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)

__all__ = [
    "get_orchestrator",
    "_agentic_rag_orchestrator",
]

# Global orchestrator instance (lazy-loaded on first request)
_agentic_rag_orchestrator = None


def get_orchestrator(request: Request) -> Any:
    """
    Dependency injection for AgenticRAGOrchestrator.

    Lazy initialization: created on first call using services from app.state.
    Subsequent calls return the same singleton.

    Returns:
        AgenticRAGOrchestrator: Singleton orchestrator instance
    """
    global _agentic_rag_orchestrator

    if _agentic_rag_orchestrator is None:
        from backend.services.rag.agentic import create_agentic_rag

        db_pool = getattr(request.app.state, "db_pool", None)
        search_service = getattr(request.app.state, "search_service", None)
        nlm_enrichment_service = getattr(request.app.state, "nlm_enrichment_service", None)
        _agentic_rag_orchestrator = create_agentic_rag(
            retriever=search_service,
            db_pool=db_pool,
            nlm_enrichment_service=nlm_enrichment_service,
        )

    return _agentic_rag_orchestrator
