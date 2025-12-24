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

from services.graph_service import GraphService
from services.rag.agent.diagnostics_tool import DiagnosticsTool
from services.rag.agent.mcp_tool import MCPSuperTool
from services.rag.agentic.graph_tool import GraphTraversalTool
from services.semantic_cache import SemanticCache

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
    DatabaseQueryTool,
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
    "WebSearchTool",
    "DatabaseQueryTool",
    "CalculatorTool",
    "VisionTool",
    "PricingTool",
    "TeamKnowledgeTool",
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
    retriever, db_pool, web_search_client=None, semantic_cache: SemanticCache = None
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

    Returns:
        Configured AgenticRAGOrchestrator instance

    Tool Priority:
        1. VectorSearchTool (primary knowledge base search)
        2. GraphTraversalTool (knowledge graph exploration)
        3. DatabaseQueryTool (deep dive into full documents)
        4. CalculatorTool (numerical computations)
        5. VisionTool (visual document analysis)
        6. PricingTool (official Bali Zero pricing)
        7. DiagnosticsTool (system health checks)
        8. MCPSuperTool (admin operations)
        9. WebSearchTool (fallback, added last if available)
    """
    logger.debug("create_agentic_rag: Initializing tools...")

    # Initialize GraphService
    graph_service = GraphService(db_pool)

    # IMPORTANT: vector_search comes first to be the default tool
    tools = [
        VectorSearchTool(retriever),  # FIRST: Primary tool for knowledge base search
        TeamKnowledgeTool(db_pool),  # SECOND: Team member queries (CEO, founder, staff)
        GraphTraversalTool(graph_service),  # THIRD: Graph exploration
        DatabaseQueryTool(db_pool),
        CalculatorTool(),
        VisionTool(),
        PricingTool(),
        DiagnosticsTool(),  # System health checks (self-healing)
        MCPSuperTool(),  # MCP superpowers (admin only: zero@balizero.com)
    ]
    logger.debug("create_agentic_rag: Tools list created")

    # web_search is only added if configured AND functional
    # It's added at the end to not interfere with vector_search
    if web_search_client:
        tools.append(WebSearchTool(web_search_client))

    logger.debug("create_agentic_rag: Instantiating AgenticRAGOrchestrator...")
    orchestrator = AgenticRAGOrchestrator(
        tools=tools, db_pool=db_pool, semantic_cache=semantic_cache, retriever=retriever
    )
    logger.debug("create_agentic_rag: Orchestrator instantiated")
    return orchestrator
