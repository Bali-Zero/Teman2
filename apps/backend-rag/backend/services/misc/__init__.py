"""Miscellaneous services module.

Uses lazy imports to avoid circular dependencies with llm module.
"""

from typing import TYPE_CHECKING

from ..autonomous_agents.knowledge_graph_builder import (
    Entity,
    EntityType,
    KnowledgeGraphBuilder,
    Relationship,
    RelationType,
)
from . import autonomous_scheduler
from .autonomous_research_service import AutonomousResearchService
from .autonomous_scheduler import AutonomousScheduler
from .clarification_service import ClarificationService
from .conversation_service import ConversationService
from .cultural_insights_service import CulturalInsightsService
from .cultural_rag_service import CulturalRAGService
from .emotional_attunement import EmotionalAttunementService, ToneStyle
from .graph_service import GraphService
from .mcp_client_service import MCPClientService
from .migration_runner import MigrationRunner
from .performance_optimizer import PerformanceMonitor, async_timed, timed
from .proactive_compliance_monitor import ProactiveComplianceMonitor
from .result_formatter import format_search_results
from .session_service import SessionService
from .tool_executor import ToolExecutor
from .work_session_service import WorkSessionService

# Lazy imports - these import from llm module and would cause circular imports
# They are loaded on first access via __getattr__

_LAZY_IMPORTS = {
    "ClientJourneyOrchestrator": ".client_journey_orchestrator",
    "FollowupService": ".followup_service",
    "GoldenAnswerService": ".golden_answer_service",
    "ImageGenerationService": ".image_generation_service",
    # "PersonalityService": removed (audit 2026-04-03)
    "ZantaraTools": ".zantara_tools",
    "get_zantara_tools": ".zantara_tools",
}

_loaded_lazy = {}


def __getattr__(name: str):
    """Lazy import handler for modules that depend on llm."""
    if name in _LAZY_IMPORTS:
        if name not in _loaded_lazy:
            import importlib

            module = importlib.import_module(_LAZY_IMPORTS[name], package=__name__)
            _loaded_lazy[name] = getattr(module, name)
        return _loaded_lazy[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Eager
    "AutonomousResearchService",
    "AutonomousScheduler",
    "ClarificationService",
    "ConversationService",
    "CulturalInsightsService",
    "CulturalRAGService",
    "EmotionalAttunementService",
    "ToneStyle",
    "GraphService",
    "KnowledgeGraphBuilder",
    "Entity",
    "EntityType",
    "Relationship",
    "RelationType",
    "MCPClientService",
    "MigrationRunner",
    "PerformanceMonitor",
    "async_timed",
    "timed",
    "ProactiveComplianceMonitor",
    "format_search_results",
    "SessionService",
    "ToolExecutor",
    "WorkSessionService",
    # Lazy
    "ClientJourneyOrchestrator",
    "FollowupService",
    "GoldenAnswerService",
    "ImageGenerationService",
    "ZantaraTools",
    "get_zantara_tools",
]
