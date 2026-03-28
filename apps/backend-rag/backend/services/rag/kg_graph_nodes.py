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
import time
from typing import Any

import asyncpg
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
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


@traceable(run_type="chain", name="KG: Understand Query", tags=["nuzantara", "kg"])
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
    - Domain: visa, tax, property, kbli, company, general (for routing)

    Args:
        state: Current KGAgentState
        llm: LangChain LLM for structured extraction

    Returns:
        Updated state with intent and extracted_entities populated
    """
    logger.info(f"🔍 [Understand Query] Processing: {state['query'][:100]}...")

    query_lower = state["query"].lower()

    # Pre-check for domain-specific queries (fast-path before LLM call)
    # This prevents visa/tax/property queries from being misclassified
    domain_hints = _detect_domain_from_query(query_lower)

    # Build extraction prompt with enhanced domain guidance
    system_prompt = """You are an expert in Indonesian business and immigration law.
Extract the following from the user's query:

1. **Intent** (choose ONE):
   - company_setup: Setting up PT PMA, PT Perorangan, CV, Firma
   - visa: KITAS, KITAP, VITAS, work permits, immigration queries
   - hire: Hiring employees (TKA or local)
   - property: Real estate, Hak Pakai, HGB, villa rental, land ownership
   - tax: PPh, PPN, tax compliance, NPWP, VAT
   - general: General questions about regulations

2. **Domain Classification** (critical for routing):
   - visa: Query is about KITAS, KITAP, visas, work permits, or immigration
   - tax: Query is about taxes, NPWP, PPh, PPN, or fiscal matters
   - property: Query is about real estate, Hak Pakai, HGB, or land
   - kbli: Query is specifically about KBLI business codes
   - company: Query is about company setup or business formation
   - general: General information queries

   IMPORTANT: If query asks "What is KITAS?" or "Apa itu KITAS?" → domain MUST be "visa"
   If query asks "What is NPWP?" or "Apa itu NPWP?" → domain MUST be "tax"
   If query asks "What is Hak Pakai?" → domain MUST be "property"

3. **Entities** (list all mentioned):
   - KBLI codes (e.g., "56101", "ristorante" → extract "56101")
   - Visa types (e.g., "KITAS", "KITAP", "E28A", "investor visa")
   - Tax concepts (e.g., "NPWP", "PPh 21", "PPN")
   - Property types (e.g., "Hak Pakai", "HGB")
   - Document names (e.g., "NIB", "NPWP", "RPTKA")
   - Company types (e.g., "PT PMA", "CV")
   - Legal references (e.g., "UU 6/2023", "PP 28/2025")

4. **Citizenship** (infer from context):
   - foreign: Query mentions "straniero", "expat", "foreign investor"
   - domestic: Query about local Indonesian processes

Return ONLY a JSON object:
{
  "intent": "visa",
  "domain": "visa",
  "entities": ["KITAS"],
  "citizenship": "foreign"
}
"""

    user_prompt = f"Query: {state['query']}"

    # Call LLM
    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
    )

    # Parse response (assume LLM returns JSON)
    try:
        import json

        parsed = json.loads(response.content)
        state["intent"] = parsed.get("intent")
        state["extracted_entities"] = parsed.get("entities", [])

        # Store domain for routing decisions
        domain = parsed.get("domain", domain_hints.get("domain", "general"))
        state["domain"] = domain

        # Update user_context with citizenship and domain
        if "citizenship" in parsed:
            state["user_context"]["citizenship"] = parsed["citizenship"]
        state["user_context"]["domain"] = domain

        logger.info(
            f"✅ [Understand Query] Intent: {state['intent']}, "
            f"Domain: {domain}, "
            f"Entities: {len(state['extracted_entities'])}, "
            f"Citizenship: {state['user_context'].get('citizenship')}",
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"❌ [Understand Query] Failed to parse LLM response: {e}")
        # Use pre-detected domain as fallback
        state["intent"] = domain_hints.get("intent", "general")
        state["domain"] = domain_hints.get("domain", "general")
        state["extracted_entities"] = domain_hints.get("entities", [])
        logger.info(f"⚠️ [Understand Query] Using fallback classification: {state['domain']}")

    return state


def _detect_domain_from_query(query_lower: str) -> dict:
    """
    Fast domain detection without LLM call.

    Used for fallback when LLM parsing fails, and to validate
    LLM classification against explicit domain keywords.

    Returns dict with domain, intent, and entities.
    """
    result = {"domain": "general", "intent": "general", "entities": []}

    # Visa domain detection
    visa_keywords = [
        "kitas",
        "kitap",
        "vitas",
        "visa",
        "work permit",
        "izin kerja",
        "rptka",
        "imta",
        "immigration",
        "imigrasi",
        "stay permit",
        "izin tinggal",
        "foreign worker",
        "tenaga kerja asing",
        "tka",
        "e28",
        "e31",
        "e33",
        "e-visa",
        "evisa",
    ]
    if any(kw in query_lower for kw in visa_keywords):
        result["domain"] = "visa"
        result["intent"] = "visa"
        # Extract specific visa type
        if "kitas" in query_lower:
            result["entities"].append("KITAS")
        elif "kitap" in query_lower:
            result["entities"].append("KITAP")
        elif "vitas" in query_lower:
            result["entities"].append("VITAS")
        return result

    # Tax domain detection
    tax_keywords = [
        "npwp",
        "pph",
        "ppn",
        "pbb",
        "tax",
        "pajak",
        "tasse",
        "fiscal",
        "vat",
        "income tax",
        "spt",
    ]
    if any(kw in query_lower for kw in tax_keywords):
        result["domain"] = "tax"
        result["intent"] = "tax"
        if "npwp" in query_lower:
            result["entities"].append("NPWP")
        elif "pph" in query_lower:
            result["entities"].append("PPh")
        elif "ppn" in query_lower:
            result["entities"].append("PPN")
        return result

    # Property domain detection
    property_keywords = [
        "hak pakai",
        "hgb",
        "hak milik",
        "hak guna bangunan",
        "property",
        "villa",
        "real estate",
        "tanah",
        "land",
        "hak sewa",
        "sertifikat",
    ]
    if any(kw in query_lower for kw in property_keywords):
        result["domain"] = "property"
        result["intent"] = "property"
        if "hak pakai" in query_lower:
            result["entities"].append("Hak Pakai")
        elif "hgb" in query_lower:
            result["entities"].append("HGB")
        return result

    return result


# ============================================================================
# Node 2: Entity Resolution
# ============================================================================

# Domain-specific entity prefixes for proper routing
DOMAIN_ENTITY_PREFIXES = {
    "visa": ["visa_", "kitas", "kitap", "vitas", "imta", "rptka", "e31", "e28", "e33"],
    "tax": ["tax_", "npwp", "pph_", "ppn", "pbb_", "spt"],
    "property": ["property_", "hak_", "hgb", "shm", "ajb"],
    "kbli": ["kbli_"],
    "company": ["company_", "pt_", "nib_"],
}

# Entity types that should NOT be resolved against KBLI codes
NON_KBLI_ENTITY_TYPES = {"visa_type", "tax_concept", "tax_code", "property_type"}


def _is_non_kbli_entity(entity_str: str, entity_type: str | None = None) -> bool:
    """
    Check if an entity should NOT be matched against KBLI codes.

    Args:
        entity_str: The entity string from extraction
        entity_type: Optional entity type hint

    Returns:
        True if entity is visa/tax/property (non-KBLI)
    """
    entity_lower = entity_str.lower()

    # Check explicit entity type
    if entity_type and entity_type in NON_KBLI_ENTITY_TYPES:
        return True

    # Check for visa-related entities
    visa_patterns = [
        "kitas",
        "kitap",
        "vitas",
        "visa",
        "e28",
        "e31",
        "e33",
        "imta",
        "rptka",
        "work_permit",
        "stay_permit",
    ]
    if any(pattern in entity_lower for pattern in visa_patterns):
        return True

    # Check for tax-related entities
    tax_patterns = ["npwp", "pph", "ppn", "pbb", "spt", "tax_"]
    if any(pattern in entity_lower for pattern in tax_patterns):
        return True

    # Check for property-related entities
    property_patterns = ["hak_pakai", "hgb", "hak_milik", "property_", "shm_"]
    return bool(any(pattern in entity_lower for pattern in property_patterns))


def _get_entity_type_filter(entity_str: str) -> list[str] | None:
    """
    Get the expected entity types for a given entity string.

    Returns list of entity types to filter by, or None for no filter.
    """
    entity_lower = entity_str.lower()

    # Visa entities
    if any(
        pattern in entity_lower
        for pattern in ["kitas", "kitap", "vitas", "e28", "e31", "e33", "imta", "rptka"]
    ):
        return ["visa", "permit", "immigration"]

    # Tax entities
    if any(pattern in entity_lower for pattern in ["npwp", "pph", "ppn", "pbb"]):
        return ["tax", "permit"]

    # Property entities
    if any(pattern in entity_lower for pattern in ["hak_pakai", "hgb", "hak_milik", "shm"]):
        return ["property", "permit"]

    # KBLI entities
    if entity_str.isdigit() and len(entity_str) == 5:
        return ["kbli", "business_code"]

    return None


@traceable(run_type="retriever", name="KG: Resolve Entities", tags=["nuzantara", "kg"])
async def resolve_entities_node(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
) -> KGAgentState:
    """
    Map extracted entities to KG entity_ids via fuzzy matching.

    Uses PostgreSQL similarity search (backed by GIN trigram index) to find
    KG entities that match the extracted entity strings from the query.
    Results are cached in Redis to avoid repeated DB lookups.

    Batched: all resolvable entities are processed in a single DB connection
    acquisition, with cache checked first for each entity.

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

    from backend.services.rag.kg_cache import get_kg_cache

    cache = get_kg_cache()

    entity_ids: list[str] = []
    confidence_scores: dict[str, float] = {}
    entities_to_resolve: list[str] = []

    # Phase 1: Filter non-KBLI entities, check cache for the rest
    for entity_str in state["extracted_entities"]:
        if _is_non_kbli_entity(entity_str):
            logger.info(f"🛂 [Resolve] Non-KBLI entity detected, skipping KG lookup: {entity_str}")
            continue

        # Check cache first
        cached = await cache.get_resolved_entity(entity_str)
        if cached is not None:
            entity_ids.append(cached["entity_id"])
            confidence_scores[cached["entity_id"]] = cached["confidence"]
            logger.info(f"⚡ [Resolve] Cache hit: {entity_str} → {cached['entity_id']}")
            continue

        entities_to_resolve.append(entity_str)

    # Phase 2: Batch resolve remaining entities in a single connection
    if entities_to_resolve:
        async with db_pool.acquire() as conn:
            for entity_str in entities_to_resolve:
                entity_types = _get_entity_type_filter(entity_str)

                # Try exact match first (uses idx_kg_nodes_name_lower index)
                exact_match = await conn.fetchrow(
                    """
                    SELECT entity_id, name, confidence, entity_type
                    FROM kg_nodes
                    WHERE entity_id = $1 OR LOWER(name) = LOWER($2)
                    LIMIT 1
                    """,
                    entity_str,
                    entity_str,
                )

                if exact_match:
                    eid = exact_match["entity_id"]
                    conf = exact_match["confidence"]
                    entity_ids.append(eid)
                    confidence_scores[eid] = conf
                    await cache.set_resolved_entity(
                        entity_str, {"entity_id": eid, "confidence": conf},
                    )
                    logger.info(f"✅ [Resolve] Exact match: {entity_str} → {eid}")
                    continue

                # Fallback: fuzzy match (uses idx_kg_nodes_name_trgm GIN index)
                if entity_types:
                    fuzzy_matches = await conn.fetch(
                        """
                        SELECT entity_id, name, confidence, entity_type,
                               similarity(name, $1) as sim_score
                        FROM kg_nodes
                        WHERE similarity(name, $1) > 0.7
                          AND entity_type = ANY($2)
                        ORDER BY sim_score DESC
                        LIMIT 3
                        """,
                        entity_str,
                        entity_types,
                    )
                else:
                    fuzzy_matches = await conn.fetch(
                        """
                        SELECT entity_id, name, confidence, entity_type,
                               similarity(name, $1) as sim_score
                        FROM kg_nodes
                        WHERE similarity(name, $1) > 0.7
                        ORDER BY sim_score DESC
                        LIMIT 3
                        """,
                        entity_str,
                    )

                if fuzzy_matches:
                    best = fuzzy_matches[0]
                    eid = best["entity_id"]
                    conf = best["confidence"] * best["sim_score"]
                    entity_ids.append(eid)
                    confidence_scores[eid] = conf
                    await cache.set_resolved_entity(
                        entity_str, {"entity_id": eid, "confidence": conf},
                    )
                    logger.info(
                        f"🔍 [Resolve] Fuzzy match: {entity_str} → {eid} "
                        f"(sim: {best['sim_score']:.2f}, type: {best['entity_type']})",
                    )
                else:
                    # Cache the miss too (avoids repeated DB lookups for unknown entities)
                    await cache.set_resolved_entity(entity_str, {"entity_id": "", "confidence": 0})
                    logger.warning(f"⚠️ [Resolve] No match found for: {entity_str}")

    state["current_entities"] = entity_ids
    state["confidence_scores"] = confidence_scores

    logger.info(
        f"✅ [Resolve Entities] Resolved {len(entity_ids)}/{len(state['extracted_entities'])} entities",
    )

    return state


# ============================================================================
# Node 3: Multi-Hop Graph Traversal (BFS)
# ============================================================================


@traceable(run_type="retriever", name="KG: Graph Traversal", tags=["nuzantara", "kg"])
async def traverse_graph_node(
    state: KGAgentState,
    db_pool: asyncpg.Pool,
    max_depth: int = 3,
) -> KGAgentState:
    """
    BFS traversal to find multi-hop relationship chains.

    Explores the Knowledge Graph starting from current_entities,
    following REQUIRES, ENABLES, PART_OF relationships up to max_depth hops.
    Results are cached in Redis keyed by (sorted entity_ids, max_depth).

    Args:
        state: Current KGAgentState
        db_pool: PostgreSQL connection pool
        max_depth: Maximum traversal depth (default: 3 hops)

    Returns:
        Updated state with relationship_chains and visited_entities populated
    """
    logger.info(
        f"🌐 [Traverse Graph] Starting BFS from {len(state['current_entities'])} entities, "
        f"max_depth={max_depth}",
    )

    if not state["current_entities"]:
        logger.warning("⚠️ [Traverse] No starting entities, skipping traversal")
        state["relationship_chains"] = []
        return state

    # Check traversal cache
    from backend.services.rag.kg_cache import get_kg_cache

    cache = get_kg_cache()

    cached_chains = await cache.get_traversal(state["current_entities"], max_depth)
    if cached_chains is not None:
        state["relationship_chains"] = cached_chains
        # Rebuild visited set from cached chains
        visited = set(state.get("visited_entities", set()))
        for chain in cached_chains:
            for el in chain:
                visited.add(el["source_entity_id"])
                visited.add(el["target_entity_id"])
        state["visited_entities"] = visited
        kg_relationship_chains_found.observe(len(cached_chains))
        logger.info(f"⚡ [Traverse Graph] Cache hit: {len(cached_chains)} chains")
        return state

    frontier = state["current_entities"]
    visited = state.get("visited_entities", set())
    chains: list[list[dict]] = []
    actual_depth = 0

    async with db_pool.acquire() as conn:
        for depth in range(max_depth):
            actual_depth = depth
            logger.info(
                f"🔍 [Traverse] Depth {depth + 1}/{max_depth}, frontier size: {len(frontier)}",
            )

            if not frontier:
                break

            # Filter out already-visited entities before querying
            unvisited = [eid for eid in frontier if eid not in visited]
            if not unvisited:
                break

            visited.update(unvisited)

            # Batch query: fetch all edges for the entire frontier in one round-trip
            # Uses idx_kg_edges_source_reltype composite index
            edges = await conn.fetch(
                """
                SELECT e.source_entity_id,
                       e.relationship_type, e.target_entity_id,
                       s.name as source_name, s.entity_type as source_type,
                       t.name as target_name, t.entity_type as target_type,
                       t.confidence as target_confidence,
                       e.confidence as edge_confidence,
                       e.source_collection as edge_source_collection,
                       t.source_collection as target_source_collection,
                       t.created_at as target_created_at,
                       e.created_at as edge_created_at
                FROM kg_edges e
                JOIN kg_nodes s ON e.source_entity_id = s.entity_id
                JOIN kg_nodes t ON e.target_entity_id = t.entity_id
                WHERE e.source_entity_id = ANY($1::text[])
                  AND e.relationship_type IN ('REQUIRES', 'ENABLES', 'PART_OF', 'ISSUED_BY', 'HAS_FEE', 'HAS_DURATION', 'APPLIES_TO', 'TAX_OBLIGATION', 'CLASSIFIED_AS')
                  AND t.confidence > 0.7
                ORDER BY t.confidence DESC
                """,
                unvisited,
            )

            next_frontier = []

            for edge in edges:
                chain_element = {
                    "source_entity_id": edge["source_entity_id"],
                    "source_name": edge["source_name"],
                    "source_type": edge["source_type"],
                    "relationship_type": edge["relationship_type"],
                    "target_entity_id": edge["target_entity_id"],
                    "target_name": edge["target_name"],
                    "target_type": edge["target_type"],
                    "depth": depth + 1,
                    "edge_confidence": edge.get("edge_confidence"),
                    "edge_source_collection": edge.get("edge_source_collection"),
                    "target_source_collection": edge.get("target_source_collection"),
                    "target_created_at": edge.get("target_created_at"),
                    "edge_created_at": edge.get("edge_created_at"),
                }

                chains.append([chain_element])

                if edge["target_entity_id"] not in visited:
                    next_frontier.append(edge["target_entity_id"])

            frontier = next_frontier

        state["relationship_chains"] = chains
        state["visited_entities"] = visited

        # Cache the traversal result
        await cache.set_traversal(state["current_entities"], max_depth, chains)

        # Track metrics
        kg_graph_traversal_depth.observe(actual_depth + 1)
        kg_relationship_chains_found.observe(len(chains))

        logger.info(
            f"✅ [Traverse Graph] Found {len(chains)} relationship chains, "
            f"visited {len(visited)} entities",
        )

    return state


# ============================================================================
# Node 4: LLM Reasoning Over Graph
# ============================================================================


@traceable(run_type="llm", name="KG: LLM Reasoning", tags=["nuzantara", "kg"])
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

    system_prompt = f"""You are analyzing a Knowledge Graph to answer: "{state["query"]}"

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
        ],
    )

    state["reasoning_steps"].append(response.content)

    # Extract evidence (entities mentioned in reasoning)
    evidence = extract_evidence_from_chains(state["relationship_chains"])
    state["answer_evidence"] = evidence

    # Track metrics
    duration = time.time() - start_time
    kg_llm_reasoning_duration_seconds.observe(duration)

    logger.info(
        f"✅ [Reason] Reasoning complete, {len(evidence)} evidence pieces extracted ({duration:.2f}s)",
    )

    return state


# ============================================================================
# Node 5: Workflow Synthesis
# ============================================================================


@traceable(run_type="chain", name="KG: Synthesize Workflow", tags=["nuzantara", "kg"])
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

    # Build workflow output with dynamic confidence scoring (Phase 2)
    from dataclasses import asdict

    from backend.services.rag.confidence import calculate_dynamic_confidence

    breakdown = calculate_dynamic_confidence(state)

    workflow = {
        "id": f"dynamic:{state['intent']}_{len(steps)}steps",
        "type": state["intent"] or "general",
        "steps": steps,
        "source": "graph_traversal",
        "confidence": breakdown.overall,
        "confidence_breakdown": asdict(breakdown),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
                },
            )

    return evidence


def calculate_workflow_confidence(state: KGAgentState) -> float:
    """
    Calculate confidence score for synthesized workflow.

    .. deprecated::
        Use ``confidence.calculate_dynamic_confidence(state)`` instead.
        Kept for backward compatibility with existing tests.

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
    if chains_count < 3:
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
