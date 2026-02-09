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
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    PostgresSaver = None  # type: ignore[assignment,misc]
    logger.warning("langgraph-checkpoint-postgres not installed, checkpointing disabled")

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None  # type: ignore[assignment,misc]
    logger.warning("langchain-anthropic not installed, Claude reasoning unavailable")

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    logger.warning("langchain-openai not installed, OpenAI reasoning unavailable")

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

# Import subgraphs (Phase 3)
from backend.services.rag.kg_subgraph_company import build_company_subgraph
from backend.services.rag.kg_subgraph_property import build_property_subgraph
from backend.services.rag.kg_subgraph_tax import build_tax_subgraph
from backend.services.rag.kg_subgraph_visa import build_visa_subgraph


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

    if anthropic_key and ChatAnthropic is not None:
        logger.info("🤖 [LLM] Using Claude Sonnet 4.5 for reasoning")
        return ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.2,  # Low temp for deterministic reasoning
            api_key=anthropic_key,
        )
    elif openai_key and ChatOpenAI is not None:
        logger.info("🤖 [LLM] Using OpenAI GPT-4 for reasoning (Anthropic unavailable)")
        return ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.2,
            api_key=openai_key,
        )
    else:
        raise ValueError(
            "No LLM available for KG reasoning. "
            f"ANTHROPIC_API_KEY={'set' if anthropic_key else 'missing'} (lib={'ok' if ChatAnthropic else 'missing'}), "
            f"OPENAI_API_KEY={'set' if openai_key else 'missing'} (lib={'ok' if ChatOpenAI else 'missing'})"
        )


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
    1. Check if domain-specific subgraph (company, visa, property, tax) → route to subgraph
    2. Check if intent matches golden route → use_golden_route
    3. If complex query (multiple entities) → resolve_entities
    4. If simple query → fallback_to_vector (END)

    Args:
        state: Current KGAgentState

    Returns:
        Next node name: "company_subgraph" | "visa_subgraph" | "property_subgraph" |
                        "tax_subgraph" | "use_golden_route" | "resolve_entities" | "END"
    """
    intent = state.get("intent")
    entities_count = len(state.get("extracted_entities", []))
    query_lower = state.get("query", "").lower()

    logger.info(
        f"🔀 [Router] After understand_query: intent={intent}, entities={entities_count}"
    )

    # Phase 3: Domain-Specific Subgraph Routing
    # Company setup queries
    company_keywords = ["pt pma", "pt lokal", "perorangan", "cv", "company", "azienda", "società"]
    if intent in ["company_setup", "pt_pma_setup", "business_formation"] or \
       any(kw in query_lower for kw in company_keywords):
        logger.info(f"🏢 [Router] Company-related query, routing to CompanySubgraph")
        return "company_subgraph"

    # Visa/immigration queries
    visa_keywords = ["kitas", "kitap", "vitas", "visa", "work permit", "rptka", "immigration"]
    if intent in ["visa_application", "kitas_work", "immigration"] or \
       any(kw in query_lower for kw in visa_keywords):
        logger.info(f"🛂 [Router] Visa-related query, routing to VisaSubgraph")
        return "visa_subgraph"

    # Property queries
    property_keywords = ["property", "villa", "hak pakai", "hgb", "hak milik", "rental", "real estate"]
    if intent in ["property_acquisition", "property_purchase"] or \
       any(kw in query_lower for kw in property_keywords):
        logger.info(f"🏠 [Router] Property-related query, routing to PropertySubgraph")
        return "property_subgraph"

    # Tax queries
    tax_keywords = ["tax", "pph", "ppn", "npwp", "pajak", "tasse", "fiscal", "vat"]
    if intent in ["tax_compliance", "npwp_registration"] or \
       any(kw in query_lower for kw in tax_keywords):
        logger.info(f"🧾 [Router] Tax-related query, routing to TaxSubgraph")
        return "tax_subgraph"

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
# Subgraph Invocation Nodes (Phase 3)
# ============================================================================


async def invoke_company_subgraph(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Invoke Company Setup Subgraph.

    Handles PT PMA, Perorangan, CV company formation workflows.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with workflow from CompanySubgraph
    """
    logger.info("🏢 [CompanySubgraph] Invoking Company Setup Subgraph...")

    llm = get_llm_for_reasoning()
    subgraph = build_company_subgraph(db_pool, llm)
    compiled_subgraph = subgraph.compile()

    # Pass current state to subgraph
    subgraph_result = await compiled_subgraph.ainvoke(state)

    # Merge workflow back to parent state
    state["workflow"] = subgraph_result.get("workflow")
    logger.info(f"✅ [CompanySubgraph] Workflow synthesized: {state['workflow']['name']}")

    return state


async def invoke_visa_subgraph(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Invoke Visa/Immigration Subgraph.

    Handles KITAS, KITAP, VITAS visa processing workflows.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with workflow from VisaSubgraph
    """
    logger.info("🛂 [VisaSubgraph] Invoking Visa/Immigration Subgraph...")

    llm = get_llm_for_reasoning()
    subgraph = build_visa_subgraph(db_pool, llm)
    compiled_subgraph = subgraph.compile()

    subgraph_result = await compiled_subgraph.ainvoke(state)
    state["workflow"] = subgraph_result.get("workflow")
    logger.info(f"✅ [VisaSubgraph] Workflow synthesized: {state['workflow']['name']}")

    return state


async def invoke_property_subgraph(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Invoke Property Acquisition Subgraph.

    Handles Hak Pakai, HGB, rental property workflows.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with workflow from PropertySubgraph
    """
    logger.info("🏠 [PropertySubgraph] Invoking Property Acquisition Subgraph...")

    llm = get_llm_for_reasoning()
    subgraph = build_property_subgraph(db_pool, llm)
    compiled_subgraph = subgraph.compile()

    subgraph_result = await compiled_subgraph.ainvoke(state)
    state["workflow"] = subgraph_result.get("workflow")
    logger.info(f"✅ [PropertySubgraph] Workflow synthesized: {state['workflow']['name']}")

    return state


async def invoke_tax_subgraph(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Invoke Tax Compliance Subgraph.

    Handles PPh, PPN, NPWP tax workflows.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with workflow from TaxSubgraph
    """
    logger.info("🧾 [TaxSubgraph] Invoking Tax Compliance Subgraph...")

    llm = get_llm_for_reasoning()
    subgraph = build_tax_subgraph(db_pool, llm)
    compiled_subgraph = subgraph.compile()

    subgraph_result = await compiled_subgraph.ainvoke(state)
    state["workflow"] = subgraph_result.get("workflow")
    logger.info(f"✅ [TaxSubgraph] Workflow synthesized: {state['workflow']['name']}")

    return state


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

    # Create async closures that capture db_pool
    # (lambdas can't be async, so we need proper async functions)
    async def _resolve(state: KGAgentState) -> KGAgentState:
        return await resolve_entities_wrapper(state, db_pool)

    async def _traverse(state: KGAgentState) -> KGAgentState:
        return await traverse_graph_wrapper(state, db_pool)

    async def _synthesize(state: KGAgentState) -> KGAgentState:
        return await synthesize_workflow_wrapper(state, db_pool)

    async def _golden_route(state: KGAgentState) -> KGAgentState:
        return await use_golden_route_node(state, db_pool)

    async def _company_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_company_subgraph(state, db_pool)

    async def _visa_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_visa_subgraph(state, db_pool)

    async def _property_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_property_subgraph(state, db_pool)

    async def _tax_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_tax_subgraph(state, db_pool)

    # Add core nodes
    workflow.add_node("understand_query", understand_query_wrapper)
    workflow.add_node("resolve_entities", _resolve)
    workflow.add_node("traverse_graph", _traverse)
    workflow.add_node("reason", reason_wrapper)
    workflow.add_node("synthesize_workflow", _synthesize)
    workflow.add_node("use_golden_route", _golden_route)

    # Add subgraph nodes (Phase 3)
    workflow.add_node("company_subgraph", _company_subgraph)
    workflow.add_node("visa_subgraph", _visa_subgraph)
    workflow.add_node("property_subgraph", _property_subgraph)
    workflow.add_node("tax_subgraph", _tax_subgraph)

    # Set entry point
    workflow.set_entry_point("understand_query")

    # Add conditional edges from understand_query
    workflow.add_conditional_edges(
        "understand_query",
        route_after_query_understanding,
        {
            # Subgraph routes (Phase 3)
            "company_subgraph": "company_subgraph",
            "visa_subgraph": "visa_subgraph",
            "property_subgraph": "property_subgraph",
            "tax_subgraph": "tax_subgraph",
            # Core routes
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

    # Subgraph routes → END (Phase 3)
    workflow.add_edge("company_subgraph", END)
    workflow.add_edge("visa_subgraph", END)
    workflow.add_edge("property_subgraph", END)
    workflow.add_edge("tax_subgraph", END)

    logger.info("✅ [Build Workflow] StateGraph constructed with 10 nodes (6 core + 4 subgraphs) and routing logic")

    return workflow


async def compile_kg_workflow(db_pool: asyncpg.Pool) -> Any:
    """
    Compile the KG workflow with optional PostgreSQL checkpointing.

    Attempts to enable state persistence via PostgresSaver.
    Falls back to in-memory (no checkpointer) if PostgresSaver setup fails
    (e.g., missing checkpoint tables, incompatible pool type).

    Args:
        db_pool: PostgreSQL connection pool

    Returns:
        Compiled Pregel app (runnable workflow)
    """
    logger.info("⚙️ [Compile] Compiling KG workflow...")

    workflow = build_kg_langgraph_workflow(db_pool)

    # Try PostgreSQL checkpointing, fall back to no checkpointer
    checkpointer = None
    if PostgresSaver is None:
        logger.warning("⚠️ [Compile] PostgresSaver not available, compiling without checkpointer")
    else:
        try:
            checkpointer = PostgresSaver(db_pool)
            await checkpointer.setup()
            logger.info("✅ [Compile] PostgreSQL checkpointer initialized")
            kg_checkpoint_operations_total.labels(operation="setup").inc()
        except Exception as e:
            logger.warning(
                f"⚠️ [Compile] PostgresSaver setup failed ({type(e).__name__}: {e}), "
                f"compiling without checkpointer (no state persistence)"
            )
            checkpointer = None

    # Compile workflow (with or without checkpointer)
    app = workflow.compile(checkpointer=checkpointer)

    logger.info(
        f"✅ [Compile] KG workflow compiled successfully "
        f"(checkpointer={'postgres' if checkpointer else 'none'})"
    )

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
            # Track error metrics and return empty result (don't crash the caller)
            intent = initial_state.get("intent", "unknown")
            kg_langgraph_queries_total.labels(status="error", intent=intent).inc()
            logger.error(f"❌ [Query] KG exploration failed: {e}", exc_info=True)
            return {"workflow": None, "error": str(e)}
