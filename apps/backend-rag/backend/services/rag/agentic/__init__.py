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
from typing import Any

from services.misc.clarification_service import ClarificationService
from services.misc.graph_service import GraphService
from services.rag.agent.diagnostics_tool import DiagnosticsTool
from services.rag.agent.mcp_tool import MCPSuperTool
from services.rag.agentic.graph_tool import GraphTraversalTool
from services.search.semantic_cache import SemanticCache

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
    VectorSearchTool,
    VisionTool,
    WebSearchTool,
)

logger = logging.getLogger(__name__)

# Export all public classes
__all__ = [
    "AgenticRAGOrchestrator",
    "create_agentic_rag",
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
]


def create_agentic_rag(
    retriever,
    db_pool,
    web_search_client=None,
    semantic_cache: SemanticCache = None,
    clarification_service: ClarificationService = None,
) -> AgenticRAGOrchestrator:
    """
    Factory function to create a fully configured AgenticRAGOrchestrator.

    This function assembles all required tools and initializes the orchestrator
    with proper configuration. It maintains backward compatibility with the
    original agentic.py interface.

    Args:
        retriever: Knowledge base retriever (SearchService/KnowledgeService)
        db_pool: PostgreSQL connection pool for database queries
        web_search_client: Optional web search client (disabled by default)
        semantic_cache: Optional semantic cache for query results
        clarification_service: Optional service for resolving ambiguous queries

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
    from services.autonomous_agents.knowledge_graph_builder import KnowledgeGraphBuilder
    from services.tools.knowledge_graph_tool import KnowledgeGraphTool
    
    # We pass the ai_client later if needed, but for now we use the factory's db_pool
    kg_builder = KnowledgeGraphBuilder(search_service=retriever, db_pool=db_pool)

    # IMPORTANT: vector_search comes first to be the default tool
    # ZANTARA LEAN STRATEGY (Dec 2025): Reduced to essential tools only.
    tools = [
        VectorSearchTool(retriever),  # FIRST: Primary tool for knowledge base search
        PricingTool(),               # SECOND: Official Pricing
        TeamKnowledgeTool(db_pool),  # THIRD: Team member queries
        KnowledgeGraphTool(kg_builder), # FOURTH: Structured Knowledge Graph (NEW)
        CalculatorTool(),            # FIFTH: Math safety
        VisionTool(),                # SIXTH: Document analysis
        ImageGenerationTool(),       # SEVENTH: Image generation (Imagen)
        WebSearchTool(),             # EIGHTH: Web search for out-of-KB queries (Brave)
    ]
    logger.debug("create_agentic_rag: Tools list created")

    logger.debug("create_agentic_rag: Instantiating AgenticRAGOrchestrator...")
    orchestrator = AgenticRAGOrchestrator(
        tools=tools,
        db_pool=db_pool,
        semantic_cache=semantic_cache,
        retriever=retriever,
        clarification_service=clarification_service,
    )
    logger.debug("create_agentic_rag: Orchestrator instantiated")
    return orchestrator
