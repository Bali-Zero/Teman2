"""
Knowledge Graph LangGraph Orchestrator

Orchestrates the KG exploration workflow using LangGraph StateGraph.
Composes the 5 core nodes with conditional routing for intelligent
multi-hop reasoning and workflow synthesis.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md
"""

import logging
import os
from typing import Any

import asyncpg
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph

from backend.services.rag.kg_graph_nodes import (
    kg_checkpoint_operations_total,
    kg_langgraph_queries_total,
    reason_over_graph_node,
    resolve_entities_node,
    synthesize_workflow_node,
    traverse_graph_node,
    understand_query_node,
)
from backend.services.rag.kg_graph_state import KGAgentState

logger = logging.getLogger(__name__)


# ============================================================================
# LLM Configuration
# ============================================================================


def get_llm_for_reasoning() -> Any:
    """
    Get LLM instance for reasoning tasks.

    Uses Claude Sonnet 4.5 for complex reasoning,
    falls back to OpenAI GPT-4 if Anthropic unavailable.

    Returns:
        LangChain LLM instance
    """
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if anthropic_key:
        logger.info("🤖 [LLM] Using Claude Sonnet 4.5 for reasoning")
        return ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.2,  # Low temp for deterministic reasoning
            api_key=anthropic_key,
        )
    elif openai_key:
        logger.info("🤖 [LLM] Using OpenAI GPT-4 for reasoning (Anthropic unavailable)")
        return ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.2,
            api_key=openai_key,
        )
    else:
        raise ValueError("No LLM API key configured (ANTHROPIC_API_KEY or OPENAI_API_KEY required)")


# ============================================================================
# Node Wrappers (Inject Dependencies)
# ============================================================================


async def understand_query_wrapper(state: KGAgentState) -> KGAgentState:
    """Wrapper to inject LLM dependency into understand_query_node."""
    llm = get_llm_for_reasoning()
    return await understand_query_node(state, llm)


async def resolve_entities_wrapper(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """Wrapper to inject db_pool dependency into resolve_entities_node."""
    return await resolve_entities_node(state, db_pool)


async def traverse_graph_wrapper(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """Wrapper to inject db_pool dependency into traverse_graph_node."""
    return await traverse_graph_node(state, db_pool, max_depth=3)


async def reason_wrapper(state: KGAgentState) -> KGAgentState:
    """Wrapper to inject LLM dependency into reason_over_graph_node."""
    llm = get_llm_for_reasoning()
    return await reason_over_graph_node(state, llm)


async def synthesize_workflow_wrapper(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """Wrapper to inject db_pool dependency into synthesize_workflow_node."""
    return await synthesize_workflow_node(state, db_pool)


# ============================================================================
# Conditional Routing Functions
# ============================================================================


def route_after_query_understanding(state: KGAgentState) -> str:
    """
    Decide next step after query understanding.

    Routing logic:
    - If intent matches golden route → use_golden_route
    - If complex query (multiple entities) → resolve_entities
    - If simple query → fallback_to_vector (END)

    Args:
        state: Current KGAgentState

    Returns:
        Next node name: "use_golden_route" | "resolve_entities" | "END"
    """
    intent = state.get("intent")
    entities_count = len(state.get("extracted_entities", []))

    logger.info(
        f"🔀 [Router] After understand_query: intent={intent}, entities={entities_count}"
    )

    # Check if golden route exists for this intent
    golden_route_intents = ["pt_pma_setup", "kitas_work", "nib_oss", "npwp_registration"]
    if intent in golden_route_intents:
        logger.info(f"✅ [Router] Routing to golden route for intent: {intent}")
        return "use_golden_route"

    # Complex query with multiple entities → graph traversal
    if entities_count >= 2 or "AND" in state["query"].upper():
        logger.info(f"✅ [Router] Complex query detected, routing to graph traversal")
        return "resolve_entities"

    # Simple query → skip graph, use vector search (terminate workflow)
    logger.info(f"✅ [Router] Simple query, terminating (fallback to vector search)")
    return END


def route_after_traversal(state: KGAgentState) -> str:
    """
    Decide next step after graph traversal.

    Routing logic:
    - If many chains found (>5) → reason_over_graph
    - If few chains (<5) → expand_search (re-traverse with relaxed filters)
    - If no chains → END (fallback to vector)

    Args:
        state: Current KGAgentState

    Returns:
        Next node name: "reason" | "expand_search" | "END"
    """
    chains_count = len(state.get("relationship_chains", []))

    logger.info(f"🔀 [Router] After traverse_graph: chains_found={chains_count}")

    if chains_count >= 5:
        logger.info(f"✅ [Router] Sufficient evidence found, routing to reasoning")
        return "reason"
    elif chains_count > 0:
        # Could implement expand_search logic here (try synonyms, related entities)
        # For now, proceed with limited evidence
        logger.info(f"⚠️ [Router] Limited evidence ({chains_count} chains), proceeding to reasoning")
        return "reason"
    else:
        logger.info(f"❌ [Router] No graph evidence found, terminating")
        return END


# ============================================================================
# Golden Route Node (Placeholder)
# ============================================================================


async def use_golden_route_node(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Use pre-computed golden route for exact intent match.

    Fetches golden route from kg_enhanced_retrieval.py golden routes.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with workflow from golden route
    """
    from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

    logger.info(f"🌟 [Golden Route] Fetching golden route for intent: {state['intent']}")

    kg_service = KGEnhancedRetrieval(db_pool)
    golden_routes = await kg_service.get_golden_routes()

    # Find matching golden route
    for route in golden_routes:
        if route.route_id == state["intent"]:
            state["workflow"] = {
                "id": route.route_id,
                "type": "golden_route",
                "name": route.name,
                "description": route.description,
                "steps": [{"entity_id": entity_id} for entity_id in route.path],
                "source": "golden_route",
                "confidence": 1.0,  # Golden routes are 100% confident
            }
            state["golden_route_match"] = route.route_id
            logger.info(f"✅ [Golden Route] Found: {route.name}")
            return state

    logger.warning(f"⚠️ [Golden Route] No match for intent: {state['intent']}, falling back")
    return state


# ============================================================================
# StateGraph Construction
# ============================================================================


def build_kg_langgraph_workflow(db_pool: asyncpg.Pool) -> StateGraph:
    """
    Build the complete LangGraph workflow for KG exploration.

    Constructs StateGraph with:
    - 5 core nodes (understand, resolve, traverse, reason, synthesize)
    - 1 golden route node
    - Conditional routing edges
    - PostgreSQL checkpointing

    Args:
        db_pool: PostgreSQL connection pool (for nodes and checkpointer)

    Returns:
        Compiled LangGraph workflow (Pregel app)
    """
    logger.info("🏗️ [Build Workflow] Constructing KG LangGraph StateGraph...")

    # Initialize StateGraph
    workflow = StateGraph(KGAgentState)

    # Add nodes
    workflow.add_node("understand_query", understand_query_wrapper)
    workflow.add_node(
        "resolve_entities",
        lambda state: resolve_entities_wrapper(state, db_pool),
    )
    workflow.add_node(
        "traverse_graph",
        lambda state: traverse_graph_wrapper(state, db_pool),
    )
    workflow.add_node("reason", reason_wrapper)
    workflow.add_node(
        "synthesize_workflow",
        lambda state: synthesize_workflow_wrapper(state, db_pool),
    )
    workflow.add_node(
        "use_golden_route",
        lambda state: use_golden_route_node(state, db_pool),
    )

    # Set entry point
    workflow.set_entry_point("understand_query")

    # Add conditional edges
    workflow.add_conditional_edges(
        "understand_query",
        route_after_query_understanding,
        {
            "use_golden_route": "use_golden_route",
            "resolve_entities": "resolve_entities",
            END: END,
        },
    )

    # Linear edges (resolve → traverse)
    workflow.add_edge("resolve_entities", "traverse_graph")

    # Conditional routing after traversal
    workflow.add_conditional_edges(
        "traverse_graph",
        route_after_traversal,
        {
            "reason": "reason",
            END: END,
        },
    )

    # Linear edges (reason → synthesize → END)
    workflow.add_edge("reason", "synthesize_workflow")
    workflow.add_edge("synthesize_workflow", END)

    # Golden route → END
    workflow.add_edge("use_golden_route", END)

    logger.info("✅ [Build Workflow] StateGraph constructed with 6 nodes and routing logic")

    return workflow


async def compile_kg_workflow(db_pool: asyncpg.Pool) -> Any:
    """
    Compile the KG workflow with PostgreSQL checkpointing.

    Enables state persistence and resumption via PostgresSaver.

    Args:
        db_pool: PostgreSQL connection pool

    Returns:
        Compiled Pregel app (runnable workflow)
    """
    logger.info("⚙️ [Compile] Compiling KG workflow with PostgreSQL checkpointing...")

    workflow = build_kg_langgraph_workflow(db_pool)

    # Configure PostgreSQL checkpointer
    checkpointer = PostgresSaver(db_pool)

    # Compile workflow
    app = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ [Compile] KG workflow compiled successfully")

    return app


# ============================================================================
# Public API
# ============================================================================


class KGLangGraphOrchestrator:
    """
    High-level orchestrator for KG exploration via LangGraph.

    Usage:
        orchestrator = KGLangGraphOrchestrator(db_pool)
        result = await orchestrator.query(
            "Aprire ristorante e assumere chef straniero",
            user_context={"citizenship": "foreign"}
        )
        # result["workflow"] contains the synthesized workflow
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize orchestrator with database pool.

        Args:
            db_pool: PostgreSQL connection pool
        """
        self.db_pool = db_pool
        self.app = None

    async def initialize(self):
        """Compile the LangGraph workflow (call once at startup)."""
        if self.app is None:
            self.app = await compile_kg_workflow(self.db_pool)
            logger.info("✅ [Orchestrator] KG LangGraph workflow initialized")

    async def query(
        self,
        query: str,
        user_context: dict | None = None,
        thread_id: str | None = None,
    ) -> dict:
        """
        Execute KG exploration query.

        Args:
            query: User query (e.g., "Aprire PT PMA a Bali")
            user_context: User metadata (citizenship, session history, etc.)
            thread_id: Optional thread ID for resumable sessions

        Returns:
            Final state dict with workflow, evidence, reasoning
        """
        if self.app is None:
            await self.initialize()

        # Build initial state
        initial_state: KGAgentState = {
            "query": query,
            "user_context": user_context or {},
            "current_entities": [],
            "visited_entities": set(),
            "relationship_chains": [],
            "reasoning_steps": [],
            "confidence_scores": {},
            "intent": None,
            "extracted_entities": [],
            "workflow": None,
            "answer_evidence": [],
            "golden_route_match": None,
            "messages": [],
            "next_step": "",
        }

        # Execute workflow
        config = {"configurable": {"thread_id": thread_id or f"kg_query_{hash(query)}"}}

        logger.info(f"🚀 [Query] Starting KG exploration: {query[:100]}...")

        try:
            final_state = await self.app.ainvoke(initial_state, config=config)

            # Track success metrics
            intent = final_state.get("intent", "unknown")
            kg_langgraph_queries_total.labels(status="success", intent=intent).inc()

            logger.info(f"✅ [Query] KG exploration complete, intent={intent}")

            return final_state
        except Exception as e:
            # Track error metrics
            intent = initial_state.get("intent", "unknown")
            kg_langgraph_queries_total.labels(status="error", intent=intent).inc()
            logger.error(f"❌ [Query] KG exploration failed: {e}", exc_info=True)
            raise
