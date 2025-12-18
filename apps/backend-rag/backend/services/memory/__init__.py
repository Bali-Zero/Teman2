"""
Memory Module - Centralized Memory Orchestration for ZANTARA

This module provides a unified interface for all memory operations:
- Fact extraction from conversations
- Persistent storage in PostgreSQL
- Semantic search in Qdrant (future)
- Cross-session memory retrieval

Architecture:
    MemoryOrchestrator (facade)
        ├── MemoryFactExtractor (extraction)
        ├── MemoryServicePostgres (PostgreSQL storage)
        └── MemoryVectorService (Qdrant search - future)

Usage:
    from services.memory import MemoryOrchestrator

    orchestrator = MemoryOrchestrator(db_pool)
    await orchestrator.initialize()

    # Get user context before query
    context = await orchestrator.get_user_context(user_email)

    # Save facts after query
    await orchestrator.process_conversation(
        user_email=user_email,
        user_message=query,
        ai_response=response,
    )
"""

from services.memory.models import (
    FactType,
    MemoryContext,
    MemoryFact,
    MemoryProcessResult,
    MemoryStats,
)
from services.memory.orchestrator import MemoryOrchestrator

__all__ = [
    "MemoryOrchestrator",
    "MemoryContext",
    "MemoryFact",
    "MemoryStats",
    "MemoryProcessResult",
    "FactType",
]
