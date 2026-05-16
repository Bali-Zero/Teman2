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
from prometheus_client import Counter, Histogram

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
from backend.services.rag.kg_subgraph_company import build_company_subgraph
from backend.services.rag.kg_subgraph_property import build_property_subgraph
from backend.services.rag.kg_subgraph_tax import build_tax_subgraph
from backend.services.rag.kg_subgraph_visa import build_visa_subgraph

logger = logging.getLogger(__name__)

kg_subgraph_duration_seconds = Histogram(
    "kg_subgraph_duration_seconds",
    "Domain subgraph execution duration",
    ["domain"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

kg_subgraph_requests_total = Counter(
    "kg_subgraph_requests_total",
    "Domain subgraph invocations",
    ["domain", "status"],  # status: success, cache_hit, error
)

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    PostgresSaver = None  # type: ignore[assignment,misc]
    logger.warning("langgraph-checkpoint-postgres not installed, checkpointing disabled")

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    logger.warning("langchain-openai not installed, OpenAI reasoning unavailable")

# We no longer use ``langchain_anthropic``. Claude reasoning now goes
# through ``backend.llm.claude_oauth_langchain.build_claude_oauth_chat_model``,
# which shells out to ``claude -p`` with Max OAuth tokens. Imported lazily
# inside :func:`get_llm_for_reasoning` so LangChain Core is only loaded
# when needed.

# ============================================================================
# LLM Configuration
# ============================================================================


_cached_reasoning_llm: Any | None = None


def get_llm_for_reasoning() -> Any:
    """Return the cached LangChain chat model used by KG reasoning nodes.

    Preference order:

    1. **Claude via Max OAuth** (``claude -p`` subprocess) — the project's
       primary reasoning path per ``feedback_claude_oauth_only.md``. This
       is preferred whenever the ``claude`` CLI is available. Opt-out with
       ``KG_REASONING_PROVIDER=openai``.
    2. **OpenAI GPT-4o-mini** — fallback for environments without the CLI
       (e.g. Fly.io workers until we ship the CLI into the image). Used if
       ``OPENAI_API_KEY`` is set.

    ``ANTHROPIC_API_KEY`` is **never** consulted — it would mean billing
    against the pay-as-you-go key while the Max plan is already paid.
    """
    global _cached_reasoning_llm
    if _cached_reasoning_llm is not None:
        return _cached_reasoning_llm

    provider = (os.getenv("KG_REASONING_PROVIDER") or "").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY")

    if provider != "openai":
        try:
            from backend.llm.claude_oauth_langchain import (  # noqa: PLC0415
                build_claude_oauth_chat_model,
            )

            _cached_reasoning_llm = build_claude_oauth_chat_model(model="claude-sonnet-4-6")
            logger.info("🤖 [LLM] KG reasoning: Claude via Max OAuth (sonnet-4-6, singleton)")
            return _cached_reasoning_llm
        except Exception as exc:  # ImportError, missing langchain-core, etc.
            logger.warning(
                "Claude OAuth LLM unavailable (%s); falling back to OpenAI.",
                exc,
            )

    if openai_key and ChatOpenAI is not None:
        logger.info(
            "🤖 [LLM] KG reasoning: OpenAI GPT-4o-mini (singleton, OAuth-Claude unavailable)",
        )
        _cached_reasoning_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            api_key=openai_key,
        )
        return _cached_reasoning_llm

    raise ValueError(
        "No LLM available for KG reasoning. "
        "Install langchain-core (for Claude OAuth) or set OPENAI_API_KEY. "
        "Never set ANTHROPIC_API_KEY — project policy forbids it "
        "(memory/feedback_claude_oauth_only.md).",
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

    Routing logic (Pydantic validated):
    1. Check domain field (visa, tax, property, company, kbli) → route to appropriate subgraph.
    2. Check intent for golden routes.
    3. If complex query (multiple entities) → resolve_entities.
    4. If simple general query → fallback_to_vector (END).

    Args:
        state: Current KGAgentState

    Returns:
        Next node name: "company_subgraph" | "visa_subgraph" | "property_subgraph" |
                        "tax_subgraph" | "use_golden_route" | "resolve_entities" | "END"
    """
    intent = state.get("intent", "general")
    domain = state.get("domain", "general")
    entities_count = len(state.get("extracted_entities", []))

    logger.info(
        f"🔀 [Router] After understand_query: intent={intent}, domain={domain}, entities={entities_count}",
    )

    # PHASE 1: Domain-based routing (highest priority, strictly validated via Pydantic schema)
    domain_to_subgraph = {
        "visa": "visa_subgraph",
        "tax": "tax_subgraph",
        "property": "property_subgraph",
        "company": "company_subgraph",
        "kbli": "company_subgraph",
    }

    if domain in domain_to_subgraph:
        target = domain_to_subgraph[domain]
        logger.info(f"📍 [Router] Domain='{domain}', routing strictly to {target}")
        return target

    # PHASE 2: Golden route matching for specific intents
    golden_route_intents = {"pt_pma_setup", "kitas_work", "nib_oss", "npwp_registration"}
    if intent in golden_route_intents:
        logger.info(f"✅ [Router] Routing to golden route for intent: {intent}")
        return "use_golden_route"

    # PHASE 3: Complex query routing
    if entities_count >= 2 or "AND" in state.get("query", "").upper():
        logger.info("✅ [Router] Complex query detected, routing to graph traversal")
        return "resolve_entities"

    # PHASE 4: Simple query fallback
    logger.info("✅ [Router] Simple general query, terminating (fallback to vector search)")
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
        logger.info("✅ [Router] Sufficient evidence found, routing to reasoning")
        return "reason"
    if chains_count > 0:
        # Could implement expand_search logic here (try synonyms, related entities)
        # For now, proceed with limited evidence
        logger.info(f"⚠️ [Router] Limited evidence ({chains_count} chains), proceeding to reasoning")
        return "reason"
    logger.info("❌ [Router] No graph evidence found, terminating")
    return END


# ============================================================================
# Subgraph Invocation Nodes (Phase 3)
# ============================================================================


async def invoke_subgraph(
    state: KGAgentState,
    compiled_subgraph: Any,
    domain_name: str,
    domain_emoji: str,
) -> KGAgentState:
    """
    Invoke a pre-compiled domain subgraph with result caching.

    Domain subgraphs return mostly hardcoded data, so identical queries
    to the same domain produce identical results. Cached for 5 minutes.

    Args:
        state: Current KGAgentState
        compiled_subgraph: Pre-compiled LangGraph subgraph (or None to build on-the-fly)
        domain_name: Domain name for logging (e.g. "Company", "Visa")
        domain_emoji: Emoji for logging

    Returns:
        Updated state with workflow from subgraph
    """
    from backend.services.rag.kg_cache import get_kg_cache

    cache = get_kg_cache()
    domain_lower = domain_name.lower()
    query = state.get("query", "")

    # Check cache
    cached_workflow = await cache.get_subgraph_result(domain_lower, query)
    if cached_workflow is not None:
        state["workflow"] = cached_workflow
        workflow_name = cached_workflow.get("name", "cached")
        kg_subgraph_requests_total.labels(domain=domain_lower, status="cache_hit").inc()
        logger.info(f"⚡ [{domain_name}Subgraph] Cache hit: {workflow_name}")
        return state

    logger.info(f"{domain_emoji} [{domain_name}Subgraph] Invoking {domain_name} Subgraph...")
    import time as _time
    _subgraph_start = _time.time()

    try:
        subgraph_result = await compiled_subgraph.ainvoke(state)
        state["workflow"] = subgraph_result.get("workflow")
        kg_subgraph_requests_total.labels(domain=domain_lower, status="success").inc()
    except Exception:
        kg_subgraph_requests_total.labels(domain=domain_lower, status="error").inc()
        raise
    finally:
        kg_subgraph_duration_seconds.labels(domain=domain_lower).observe(_time.time() - _subgraph_start)

    workflow_name = state["workflow"]["name"] if state.get("workflow") else "None"
    logger.info(f"✅ [{domain_name}Subgraph] Workflow synthesized: {workflow_name}")

    # Cache the result
    if state.get("workflow"):
        await cache.set_subgraph_result(domain_lower, query, state["workflow"])

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


def build_kg_langgraph_workflow(
    db_pool: asyncpg.Pool,
    compiled_subgraphs: dict[str, Any] | None = None,
) -> StateGraph:
    """
    Build the complete LangGraph workflow for KG exploration.

    Constructs StateGraph with:
    - 5 core nodes (understand, resolve, traverse, reason, synthesize)
    - 1 golden route node
    - 4 domain subgraph nodes (using pre-compiled subgraphs if provided)
    - Conditional routing edges

    Args:
        db_pool: PostgreSQL connection pool (for nodes and checkpointer)
        compiled_subgraphs: Optional pre-compiled subgraphs dict. If None, builds on-the-fly.

    Returns:
        Compiled LangGraph workflow (Pregel app)
    """
    logger.info("🏗️ [Build Workflow] Constructing KG LangGraph StateGraph...")

    # Initialize StateGraph
    workflow = StateGraph(KGAgentState)

    # Build subgraphs on-the-fly only if not pre-compiled
    if compiled_subgraphs is None:
        llm = get_llm_for_reasoning()
        compiled_subgraphs = {
            "company": build_company_subgraph(db_pool, llm).compile(),
            "visa": build_visa_subgraph(db_pool, llm).compile(),
            "property": build_property_subgraph(db_pool, llm).compile(),
            "tax": build_tax_subgraph(db_pool, llm).compile(),
        }

    # Create async closures that capture db_pool and compiled subgraphs
    async def _resolve(state: KGAgentState) -> KGAgentState:
        return await resolve_entities_wrapper(state, db_pool)

    async def _traverse(state: KGAgentState) -> KGAgentState:
        return await traverse_graph_wrapper(state, db_pool)

    async def _synthesize(state: KGAgentState) -> KGAgentState:
        return await synthesize_workflow_wrapper(state, db_pool)

    async def _golden_route(state: KGAgentState) -> KGAgentState:
        return await use_golden_route_node(state, db_pool)

    async def _company_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_subgraph(state, compiled_subgraphs["company"], "Company", "🏢")

    async def _visa_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_subgraph(state, compiled_subgraphs["visa"], "Visa", "🛂")

    async def _property_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_subgraph(state, compiled_subgraphs["property"], "Property", "🏠")

    async def _tax_subgraph(state: KGAgentState) -> KGAgentState:
        return await invoke_subgraph(state, compiled_subgraphs["tax"], "Tax", "🧾")

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

    logger.info(
        "✅ [Build Workflow] StateGraph constructed with 10 nodes (6 core + 4 subgraphs) and routing logic",
    )

    return workflow


async def compile_kg_workflow(
    db_pool: asyncpg.Pool,
    compiled_subgraphs: dict[str, Any] | None = None,
) -> Any:
    """
    Compile the KG workflow with optional PostgreSQL checkpointing.

    Attempts to enable state persistence via PostgresSaver.
    Falls back to in-memory (no checkpointer) if PostgresSaver setup fails
    (e.g., missing checkpoint tables, incompatible pool type).

    Args:
        db_pool: PostgreSQL connection pool
        compiled_subgraphs: Optional pre-compiled subgraphs dict

    Returns:
        Compiled Pregel app (runnable workflow)
    """
    logger.info("⚙️ [Compile] Compiling KG workflow...")

    workflow = build_kg_langgraph_workflow(db_pool, compiled_subgraphs)

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
                f"compiling without checkpointer (no state persistence)",
            )
            checkpointer = None

    # Compile workflow (with or without checkpointer)
    app = workflow.compile(checkpointer=checkpointer)

    logger.info(
        f"✅ [Compile] KG workflow compiled successfully "
        f"(checkpointer={'postgres' if checkpointer else 'none'})",
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

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        """
        Initialize orchestrator with database pool.

        Args:
            db_pool: PostgreSQL connection pool
        """
        self.db_pool = db_pool
        self.app = None
        # Pre-compiled subgraphs (built once in initialize)
        self._compiled_subgraphs: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Compile the LangGraph workflow and subgraphs (call once at startup)."""
        if self.app is None:
            # Pre-compile all 4 domain subgraphs once
            llm = get_llm_for_reasoning()
            self._compiled_subgraphs = {
                "company": build_company_subgraph(self.db_pool, llm).compile(),
                "visa": build_visa_subgraph(self.db_pool, llm).compile(),
                "property": build_property_subgraph(self.db_pool, llm).compile(),
                "tax": build_tax_subgraph(self.db_pool, llm).compile(),
            }

            # Pass pre-compiled subgraphs to avoid rebuilding them
            self.app = await compile_kg_workflow(self.db_pool, self._compiled_subgraphs)

            logger.info(
                "✅ [Orchestrator] KG LangGraph workflow initialized (4 subgraphs pre-compiled)",
            )

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
            raw_intent = final_state.get("intent", "unknown")
            valid_intents = {"company_setup", "visa", "hire", "property", "tax", "general", "unknown"}
            intent_label = raw_intent if raw_intent in valid_intents else "unknown"
            kg_langgraph_queries_total.labels(status="success", intent=intent_label).inc()

            logger.info(f"✅ [Query] KG exploration complete, intent={intent_label}")

            return final_state
        except Exception as e:
            # Track error metrics and return empty result (don't crash the caller)
            raw_intent = initial_state.get("intent", "unknown")
            valid_intents = {"company_setup", "visa", "hire", "property", "tax", "general", "unknown"}
            intent_label = raw_intent if raw_intent in valid_intents else "unknown"
            kg_langgraph_queries_total.labels(status="error", intent=intent_label).inc()
            logger.error(f"❌ [Query] KG exploration failed: {e}", exc_info=True)
            return {"workflow": None, "error": str(e)}

    async def get_visual_graph(self, subgraph: str | None = None) -> str:
        """
        Get Mermaid diagram of the graph.

        Args:
            subgraph: Optional subgraph name (visa, company, tax, property)

        Returns:
            Mermaid string
        """
        if self.app is None:
            await self.initialize()

        target_app = self.app

        if subgraph and subgraph in self._compiled_subgraphs:
            target_app = self._compiled_subgraphs[subgraph]

        return target_app.get_graph().draw_mermaid()
