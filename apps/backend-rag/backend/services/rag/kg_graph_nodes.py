"""
Knowledge Graph LangGraph Node Implementations

Implements the 5 core nodes for the KG exploration workflow:
1. understand_query_node - Extract intent and entities from user query
2. resolve_entities_node - Map query entities to KG entity_ids
3. traverse_graph_node - BFS traversal to find relationship chains
4. reason_over_graph_node - LLM analyzes chains to answer query
5. synthesize_workflow_node - Convert chains to executable workflow

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md
"""

import logging
import re
import time
from typing import Any

import asyncpg
from langchain_core.messages import HumanMessage, SystemMessage
from prometheus_client import Counter, Histogram

from backend.services.rag.kg_graph_state import KGAgentState

logger = logging.getLogger(__name__)


# ============================================================================
# Prometheus Metrics
# ============================================================================

kg_langgraph_queries_total = Counter(
    "kg_langgraph_queries_total",
    "Total KG LangGraph queries processed",
    ["status", "intent"],
)

kg_graph_traversal_depth = Histogram(
    "kg_graph_traversal_depth",
    "Graph traversal depth reached",
    buckets=[1, 2, 3, 4, 5],
)

kg_relationship_chains_found = Histogram(
    "kg_relationship_chains_found",
    "Number of relationship chains discovered",
    buckets=[0, 1, 5, 10, 20, 50],
)

kg_llm_reasoning_duration_seconds = Histogram(
    "kg_llm_reasoning_duration_seconds",
    "LLM reasoning duration",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0],
)

kg_checkpoint_operations_total = Counter(
    "kg_checkpoint_operations_total",
    "PostgreSQL checkpoint operations",
    ["operation"],  # save, load, resume
)


# ============================================================================
# Node 1: Query Understanding
# ============================================================================


async def understand_query_node(
    state: KGAgentState,
    llm: Any,  # LangChain LLM instance
) -> KGAgentState:
    """
    Extract intent, entities, and citizenship context from user query.

    Uses LLM to parse the query and identify:
    - Intent: company_setup, visa, hire, property, tax, general
    - Entities: KBLI codes, visa types, document names, etc.
    - Citizenship: foreign vs domestic (impacts workflow requirements)

    Args:
        state: Current KGAgentState
        llm: LangChain LLM for structured extraction

    Returns:
        Updated state with intent and extracted_entities populated
    """
    logger.info(f"🔍 [Understand Query] Processing: {state['query'][:100]}...")

    # Build extraction prompt
    system_prompt = """You are an expert in Indonesian business and immigration law.
Extract the following from the user's query:

1. **Intent** (choose ONE):
   - company_setup: Setting up PT PMA, PT Perorangan, CV, Firma
   - visa: KITAS, KITAP, VITAS, work permits
   - hire: Hiring employees (TKA or local)
   - property: Real estate, Hak Pakai, villa rental
   - tax: PPh, PPN, tax compliance, NPWP
   - general: General questions about regulations

2. **Entities** (list all mentioned):
   - KBLI codes (e.g., "56101", "ristorante" → extract "56101")
   - Visa types (e.g., "KITAS E28A", "investor visa")
   - Document names (e.g., "NIB", "NPWP", "RPTKA")
   - Company types (e.g., "PT PMA", "CV")
   - Legal references (e.g., "UU 6/2023", "PP 28/2025")

3. **Citizenship** (infer from context):
   - foreign: Query mentions "straniero", "expat", "foreign investor"
   - domestic: Query about local Indonesian processes

Return ONLY a JSON object:
{
  "intent": "company_setup",
  "entities": ["kbli:56101", "pt_pma"],
  "citizenship": "foreign"
}
"""

    user_prompt = f"Query: {state['query']}"

    # Call LLM
    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )

    # Parse response (assume LLM returns JSON)
    try:
        import json

        parsed = json.loads(response.content)
        state["intent"] = parsed.get("intent")
        state["extracted_entities"] = parsed.get("entities", [])

        # Update user_context with citizenship
        if "citizenship" in parsed:
            state["user_context"]["citizenship"] = parsed["citizenship"]

        logger.info(
            f"✅ [Understand Query] Intent: {state['intent']}, "
            f"Entities: {len(state['extracted_entities'])}, "
            f"Citizenship: {state['user_context'].get('citizenship')}"
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"❌ [Understand Query] Failed to parse LLM response: {e}")
        state["intent"] = "general"
        state["extracted_entities"] = []

    return state


# ============================================================================
# Node 2: Entity Resolution
# ============================================================================


async def resolve_entities_node(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Map extracted entities to KG entity_ids via fuzzy matching.

    Uses PostgreSQL similarity search to find KG entities that match
    the extracted entity strings from the query.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with current_entities populated
    """
    logger.info(f"🔗 [Resolve Entities] Resolving {len(state['extracted_entities'])} entities...")

    if not state["extracted_entities"]:
        logger.warning("⚠️ [Resolve Entities] No entities to resolve, skipping")
        state["current_entities"] = []
        return state

    async with db_pool.acquire() as conn:
        # Build query for fuzzy entity matching
        entity_ids = []
        confidence_scores = {}

        for entity_str in state["extracted_entities"]:
            # Try exact match first
            exact_match = await conn.fetchrow(
                """
                SELECT entity_id, name, confidence
                FROM kg_nodes
                WHERE entity_id = $1 OR LOWER(name) = LOWER($2)
                LIMIT 1
                """,
                entity_str,
                entity_str,
            )

            if exact_match:
                entity_id = exact_match["entity_id"]
                entity_ids.append(entity_id)
                confidence_scores[entity_id] = exact_match["confidence"]
                logger.info(f"✅ [Resolve] Exact match: {entity_str} → {entity_id}")
                continue

            # Fallback: fuzzy match (similarity > 0.7)
            fuzzy_matches = await conn.fetch(
                """
                SELECT entity_id, name, confidence,
                       similarity(name, $1) as sim_score
                FROM kg_nodes
                WHERE similarity(name, $1) > 0.7
                ORDER BY sim_score DESC
                LIMIT 3
                """,
                entity_str,
            )

            if fuzzy_matches:
                # Take best match
                best_match = fuzzy_matches[0]
                entity_id = best_match["entity_id"]
                entity_ids.append(entity_id)
                confidence_scores[entity_id] = best_match["confidence"] * best_match["sim_score"]
                logger.info(
                    f"🔍 [Resolve] Fuzzy match: {entity_str} → {entity_id} "
                    f"(sim: {best_match['sim_score']:.2f})"
                )
            else:
                logger.warning(f"⚠️ [Resolve] No match found for: {entity_str}")

        state["current_entities"] = entity_ids
        state["confidence_scores"] = confidence_scores

        logger.info(
            f"✅ [Resolve Entities] Resolved {len(entity_ids)}/{len(state['extracted_entities'])} entities"
        )

    return state


# ============================================================================
# Node 3: Multi-Hop Graph Traversal (BFS)
# ============================================================================


async def traverse_graph_node(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
    max_depth: int = 3,
) -> KGAgentState:
    """
    BFS traversal to find multi-hop relationship chains.

    Explores the Knowledge Graph starting from current_entities,
    following REQUIRES, ENABLES, PART_OF relationships up to max_depth hops.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool
        max_depth: Maximum traversal depth (default: 3 hops)

    Returns:
        Updated state with relationship_chains and visited_entities populated
    """
    logger.info(
        f"🌐 [Traverse Graph] Starting BFS from {len(state['current_entities'])} entities, "
        f"max_depth={max_depth}"
    )

    if not state["current_entities"]:
        logger.warning("⚠️ [Traverse] No starting entities, skipping traversal")
        state["relationship_chains"] = []
        return state

    frontier = state["current_entities"]
    visited = state.get("visited_entities", set())
    chains = []

    async with db_pool.acquire() as conn:
        for depth in range(max_depth):
            logger.info(f"🔍 [Traverse] Depth {depth + 1}/{max_depth}, frontier size: {len(frontier)}")

            if not frontier:
                break

            next_frontier = []

            for source_entity_id in frontier:
                if source_entity_id in visited:
                    continue
                visited.add(source_entity_id)

                # Get outgoing edges (REQUIRES, ENABLES, PART_OF only)
                edges = await conn.fetch(
                    """
                    SELECT e.relationship_type, e.target_entity_id,
                           s.name as source_name, s.entity_type as source_type,
                           t.name as target_name, t.entity_type as target_type,
                           t.confidence as target_confidence
                    FROM kg_edges e
                    JOIN kg_nodes s ON e.source_entity_id = s.entity_id
                    JOIN kg_nodes t ON e.target_entity_id = t.entity_id
                    WHERE e.source_entity_id = $1
                      AND e.relationship_type IN ('REQUIRES', 'ENABLES', 'PART_OF')
                      AND t.confidence > 0.7
                    ORDER BY t.confidence DESC
                    LIMIT 20
                    """,
                    source_entity_id,
                )

                for edge in edges:
                    # Build chain element
                    chain_element = {
                        "source_entity_id": source_entity_id,
                        "source_name": edge["source_name"],
                        "source_type": edge["source_type"],
                        "relationship_type": edge["relationship_type"],
                        "target_entity_id": edge["target_entity_id"],
                        "target_name": edge["target_name"],
                        "target_type": edge["target_type"],
                        "depth": depth + 1,
                    }

                    # Add to chains (group by path)
                    chains.append([chain_element])

                    # Add target to next frontier (if not visited)
                    if edge["target_entity_id"] not in visited:
                        next_frontier.append(edge["target_entity_id"])

            frontier = next_frontier

        state["relationship_chains"] = chains
        state["visited_entities"] = visited

        # Track metrics
        kg_graph_traversal_depth.observe(depth + 1)
        kg_relationship_chains_found.observe(len(chains))

        logger.info(
            f"✅ [Traverse Graph] Found {len(chains)} relationship chains, "
            f"visited {len(visited)} entities"
        )

    return state


# ============================================================================
# Node 4: LLM Reasoning Over Graph
# ============================================================================


async def reason_over_graph_node(
    state: KGAgentState,
    llm: Any,
) -> KGAgentState:
    """
    LLM analyzes graph chains to answer the user's query.

    Formats the relationship chains as structured context and asks
    the LLM to reason over them to provide an answer.

    Args:
        state: Current KGAgentState
        llm: LangChain LLM for reasoning

    Returns:
        Updated state with reasoning_steps and answer_evidence populated
    """
    logger.info(f"🧠 [Reason] Analyzing {len(state['relationship_chains'])} graph chains...")

    start_time = time.time()

    if not state["relationship_chains"]:
        logger.warning("⚠️ [Reason] No graph chains to analyze")
        state["reasoning_steps"].append("No graph evidence found, using general knowledge")
        return state

    # Format chains for LLM context
    graph_context = format_chains_for_llm(state["relationship_chains"])

    system_prompt = f"""You are analyzing a Knowledge Graph to answer: "{state['query']}"

The graph contains Indonesian business and immigration regulations.
Use the relationship chains below to construct a logical answer.

Focus on:
- Requirements (what REQUIRES what)
- Enabling relationships (what ENABLES what)
- Hierarchical structure (what is PART_OF what)

Graph Evidence:
{graph_context}

Provide:
1. A step-by-step reasoning based on the graph chains
2. Key entities and their relationships
3. Final answer to the query
"""

    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Analyze the graph and answer the query."),
        ]
    )

    state["reasoning_steps"].append(response.content)

    # Extract evidence (entities mentioned in reasoning)
    evidence = extract_evidence_from_chains(state["relationship_chains"])
    state["answer_evidence"] = evidence

    # Track metrics
    duration = time.time() - start_time
    kg_llm_reasoning_duration_seconds.observe(duration)

    logger.info(f"✅ [Reason] Reasoning complete, {len(evidence)} evidence pieces extracted ({duration:.2f}s)")

    return state


# ============================================================================
# Node 5: Workflow Synthesis
# ============================================================================


async def synthesize_workflow_node(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Convert graph chains into an executable workflow.

    Takes the relationship chains and constructs a deterministic
    workflow with steps, documents, timeline, and costs.

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with workflow populated
    """
    logger.info("🔨 [Synthesize] Building workflow from graph chains...")

    if not state["relationship_chains"]:
        logger.warning("⚠️ [Synthesize] No chains to synthesize, workflow=None")
        state["workflow"] = None
        return state

    # Extract workflow steps from chains
    steps = []
    seen_entities = set()

    for chain in state["relationship_chains"]:
        for element in chain:
            target_id = element["target_entity_id"]

            # Avoid duplicates
            if target_id in seen_entities:
                continue
            seen_entities.add(target_id)

            # Build step
            step = {
                "step_id": target_id,
                "title": element["target_name"],
                "entity_type": element["target_type"],
                "relationship": element["relationship_type"],
                "depth": element["depth"],
            }
            steps.append(step)

    # Sort by depth (ensures logical order)
    steps.sort(key=lambda x: x["depth"])

    # Build workflow output
    workflow = {
        "id": f"dynamic:{state['intent']}_{len(steps)}steps",
        "type": state["intent"] or "general",
        "steps": steps,
        "source": "graph_traversal",
        "confidence": calculate_workflow_confidence(state),
        "generated_at": "2026-02-09",  # TODO: Use actual timestamp
    }

    state["workflow"] = workflow

    logger.info(f"✅ [Synthesize] Workflow created: {workflow['id']} with {len(steps)} steps")

    return state


# ============================================================================
# Helper Functions
# ============================================================================


def format_chains_for_llm(chains: list[list[dict]]) -> str:
    """
    Format relationship chains as readable text for LLM context.

    Example output:
        Chain 1:
        - KBLI 56101 (Restauran) REQUIRES PT PMA
        - PT PMA ENABLES KITAS E28G
        - KITAS E28G REQUIRES RPTKA

    Args:
        chains: List of relationship chain lists

    Returns:
        Formatted string for LLM prompt
    """
    if not chains:
        return "(No graph chains found)"

    formatted = []
    for i, chain in enumerate(chains[:10], 1):  # Limit to 10 chains to avoid token overflow
        chain_lines = [f"Chain {i}:"]
        for element in chain:
            line = (
                f"  - {element['source_name']} ({element['source_type']}) "
                f"{element['relationship_type']} "
                f"{element['target_name']} ({element['target_type']})"
            )
            chain_lines.append(line)
        formatted.append("\n".join(chain_lines))

    return "\n\n".join(formatted)


def extract_evidence_from_chains(chains: list[list[dict]]) -> list[dict]:
    """
    Extract evidence pieces from relationship chains.

    Args:
        chains: List of relationship chain lists

    Returns:
        List of evidence dicts: [{entity_id, name, relationship, context}]
    """
    evidence = []
    seen = set()

    for chain in chains:
        for element in chain:
            entity_id = element["target_entity_id"]
            if entity_id in seen:
                continue
            seen.add(entity_id)

            evidence.append(
                {
                    "entity_id": entity_id,
                    "name": element["target_name"],
                    "entity_type": element["target_type"],
                    "relationship": element["relationship_type"],
                    "context": f"Found via {element['relationship_type']} from {element['source_name']}",
                }
            )

    return evidence


def calculate_workflow_confidence(state: KGAgentState) -> float:
    """
    Calculate confidence score for synthesized workflow.

    Based on:
    - Number of chains found (more = higher confidence)
    - Average entity confidence scores
    - Intent clarity

    Args:
        state: Current KGAgentState

    Returns:
        Confidence score (0.0-1.0)
    """
    # Base confidence from number of chains
    chains_count = len(state["relationship_chains"])
    if chains_count == 0:
        return 0.0
    elif chains_count < 3:
        base = 0.5
    elif chains_count < 10:
        base = 0.7
    else:
        base = 0.9

    # Adjust by entity confidence scores
    if state["confidence_scores"]:
        avg_confidence = sum(state["confidence_scores"].values()) / len(state["confidence_scores"])
        base = base * 0.7 + avg_confidence * 0.3

    # Boost if intent is clear
    if state.get("intent") and state["intent"] != "general":
        base = min(1.0, base + 0.1)

    return round(base, 2)
