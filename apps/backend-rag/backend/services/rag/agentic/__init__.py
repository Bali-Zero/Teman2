"""
Agentic RAG with Tool Use - Refactored Architecture

This module has been refactored from a 2,200+ line monolithic file into
a well-structured package with clear separation of concerns:

Structure:
- tools.py: Tool class definitions (VectorSearch, WebSearch, Database, Calculator, Vision, Pricing)
- orchestrator.py: Main orchestrator with query processing and streaming (910 lines)
- llm_gateway.py: Unified LLM interface with model fallback cascade (493 lines)
- reasoning.py: ReAct reasoning loop (Thought→Action→Observation) (294 lines)
- prompt_builder.py: System prompt construction with caching
- response_processor.py: Response cleaning and formatting
- context_manager.py: User context and memory management
- tool_executor.py: Tool parsing and execution with rate limiting
- pipeline.py: Response processing pipeline with verification, cleaning, and citation stages

Key Features:
- Quality routing (Fast/Pro/DeepThink)
- ReAct pattern (Reason-Act-Observe)
- Multi-tier fallback (Gemini Pro -> Flash -> Flash-Lite -> OpenRouter)
- Native function calling with regex fallback
- Memory persistence and semantic caching
- Streaming and non-streaming modes
- Response verification and self-correction

Backward Compatibility:
All original exports are maintained for seamless integration with existing code.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.core.semantic_cache import SemanticCache
    from backend.services.misc.clarification_service import ClarificationService

# Lazy import to prevent circular dependencies
_GraphTraversalTool = None


def _get_graph_traversal_tool():
    """Lazy load GraphTraversalTool to prevent circular imports."""
    global _GraphTraversalTool
    if _GraphTraversalTool is None:
        from backend.services.rag.agentic.graph_tool import GraphTraversalTool

        _GraphTraversalTool = GraphTraversalTool
    return _GraphTraversalTool


# Core orchestrators
# Submodules (for direct access)
from . import context_manager, llm_gateway, memory_handler, prompt_builder, reasoning
from .kg_orchestrator import AgenticResponse, KGAgenticOrchestrator
from .orchestrator import AgenticRAGOrchestrator
from .pipeline import (
    CitationStage,
    FormatStage,
    PostProcessingStage,
    ResponsePipeline,
    VerificationStage,
    create_default_pipeline,
)
from .tools import (
    CalculatorTool,
    ImageGenerationTool,
    PricingTool,
    TeamKnowledgeTool,
    TimeSheetTool,
    VectorSearchTool,
    VisionTool,
    WebSearchTool,
)

logger = logging.getLogger(__name__)

# Export all public classes
__all__ = [
    "AgenticRAGOrchestrator",
    "KGAgenticOrchestrator",
    "AgenticResponse",
    "create_agentic_rag",
    "create_kg_agentic_rag",
    # Tools
    "TimeSheetTool",
    "VectorSearchTool",
    "CalculatorTool",
    "VisionTool",
    "PricingTool",
    "TeamKnowledgeTool",
    "ImageGenerationTool",
    "WebSearchTool",
    "GraphTraversalTool",
    # Pipeline components
    "ResponsePipeline",
    "VerificationStage",
    "PostProcessingStage",
    "CitationStage",
    "FormatStage",
    "create_default_pipeline",
    # Submodules (for direct access)
    "context_manager",
    "llm_gateway",
    "memory_handler",
    "prompt_builder",
    "reasoning",
]


def create_agentic_rag(
    retriever,
    db_pool,
    _web_search_client=None,
    semantic_cache: "SemanticCache" = None,
    clarification_service: "ClarificationService" = None,
    nlm_enrichment_service: Any = None,
    graph_service: Any = None,
    cultural_insights_service: Any = None,
) -> AgenticRAGOrchestrator:
    """
    Factory function to create a fully configured AgenticRAGOrchestrator.

    This function assembles all required tools and initializes the orchestrator
    with proper configuration. It maintains backward compatibility with the
    original agentic.py interface.

    Args:
        retriever: Knowledge base retriever (SearchService/KnowledgeService)
        db_pool: PostgreSQL connection pool for database queries
        _web_search_client: Optional web search client (disabled by default)
        semantic_cache: Optional semantic cache for query results
        clarification_service: Optional service for resolving ambiguous queries
        nlm_enrichment_service: Optional NLM enrichment service for CAUTIOUS-zone queries

    Returns:
        Configured AgenticRAGOrchestrator instance

    Tool Priority:
        1. VectorSearchTool (primary knowledge base search)
        2. PricingTool (official Bali Zero pricing)
        3. TeamKnowledgeTool (team member queries)
        4. KnowledgeGraphTool (structured knowledge graph)
        5. CalculatorTool (numerical computations)
        6. VisionTool (visual document analysis)
        7. ImageGenerationTool (AI image generation)
        8. WebSearchTool (web search for out-of-KB queries via Brave)
    """
    logger.debug("create_agentic_rag: Initializing tools...")

    # Initialize New Knowledge Graph Builder (Dec 2025)
    # Uses PostgreSQL persistence and LLM semantic extraction
    from backend.services.autonomous_agents.knowledge_graph_builder import KnowledgeGraphBuilder
    from backend.services.tools.knowledge_graph_tool import KnowledgeGraphTool

    # We pass the ai_client later if needed, but for now we use the factory's db_pool
    kg_builder = KnowledgeGraphBuilder(search_service=retriever, db_pool=db_pool)

    # IMPORTANT: vector_search comes first to be the default tool
    # ZANTARA LEAN STRATEGY (Dec 2025): Reduced to essential tools only.
    tools = [
        VectorSearchTool(retriever, user_level=3),  # FIRST: Primary tool for knowledge base search
        PricingTool(),  # SECOND: Official Pricing
        TeamKnowledgeTool(db_pool),  # THIRD: Team member queries
        KnowledgeGraphTool(kg_builder),  # FOURTH: Structured Knowledge Graph (NEW)
        CalculatorTool(),  # FIFTH: Math safety
        VisionTool(),  # SIXTH: Document analysis
        ImageGenerationTool(),  # SEVENTH: Image generation (Imagen)
        WebSearchTool(),  # EIGHTH: Web search for out-of-KB queries (Brave)
        TimeSheetTool(),  # NINTH: Timesheet Management
    ]

    # TENTH: Graph Traversal Tool (PostgreSQL KG traversal — optional)
    if graph_service is not None:
        GraphTraversalTool = _get_graph_traversal_tool()
        tools.append(GraphTraversalTool(graph_service))
        logger.info("✅ GraphTraversalTool added to tools list")
    logger.debug("create_agentic_rag: Tools list created")

    logger.debug("create_agentic_rag: Instantiating AgenticRAGOrchestrator...")
    orchestrator = AgenticRAGOrchestrator(
        tools=tools,
        db_pool=db_pool,
        semantic_cache=semantic_cache,
        retriever=retriever,
        clarification_service=clarification_service,
        nlm_enrichment_service=nlm_enrichment_service,
        cultural_insights_service=cultural_insights_service,
    )
    logger.debug("create_agentic_rag: Orchestrator instantiated")
    return orchestrator


def create_kg_agentic_rag(
    retriever,
    db_pool,
) -> KGAgenticOrchestrator:
    """
    Factory function to create a KG-enhanced Agentic RAG Orchestrator.

    This orchestrator combines Knowledge Graph traversal with vector search
    and LLM reasoning for explainable, high-quality answers.

    Args:
        retriever: Knowledge base retriever (SearchService)
        db_pool: PostgreSQL connection pool for KG database access

    Returns:
        Configured KGAgenticOrchestrator instance
    """
    logger.debug("create_kg_agentic_rag: Initializing KG orchestrator...")

    orchestrator = KGAgenticOrchestrator(
        db_pool=db_pool,
        retriever=retriever,
    )

    logger.info("✅ KGAgenticOrchestrator created")
    return orchestrator
