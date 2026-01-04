"""
Memory Module - Centralized Memory Orchestration for ZANTARA

Uses lazy imports for MemoryOrchestrator to avoid circular dependency
with agents module.
"""

# Eager imports - no circular dependencies
from .collective_memory_emitter import CollectiveMemoryEmitter
from .collective_memory_service import CollectiveMemory, CollectiveMemoryService
from .collective_memory_workflow import (
    CollectiveMemoryState,
    MemoryCategory,
    create_collective_memory_workflow,
)
from .episodic_memory_service import Emotion, EpisodicMemoryService, EventType
from .memory_fact_extractor import MemoryFactExtractor
from .memory_fallback import InMemoryConversationCache, get_memory_cache
from .memory_service_postgres import MemoryServicePostgres, UserMemory
from .models import (
    FactType,
    MemoryContext,
    MemoryFact,
    MemoryProcessResult,
    MemoryStats,
)

# Lazy imports - orchestrator imports agents which causes circular imports
_LAZY_IMPORTS = {
    "MemoryOrchestrator": ".orchestrator",
}

_loaded_lazy = {}


def __getattr__(name: str):
    """Lazy import handler for MemoryOrchestrator."""
    if name in _LAZY_IMPORTS:
        if name not in _loaded_lazy:
            import importlib

            module = importlib.import_module(_LAZY_IMPORTS[name], package=__name__)
            _loaded_lazy[name] = getattr(module, name)
        return _loaded_lazy[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MemoryOrchestrator",  # lazy
    "MemoryContext",
    "MemoryFact",
    "MemoryStats",
    "MemoryProcessResult",
    "FactType",
    "MemoryFactExtractor",
    "InMemoryConversationCache",
    "get_memory_cache",
    "MemoryServicePostgres",
    "UserMemory",
    "EpisodicMemoryService",
    "EventType",
    "Emotion",
    "CollectiveMemoryService",
    "CollectiveMemory",
    "CollectiveMemoryEmitter",
    "MemoryCategory",
    "CollectiveMemoryState",
    "create_collective_memory_workflow",
]
