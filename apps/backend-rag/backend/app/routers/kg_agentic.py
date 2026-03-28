"""
KG-Agentic RAG API Router

Exposes the KGAgenticOrchestrator which combines:
- Knowledge Graph traversal
- Golden route matching
- Vector search with intelligent collection routing
- LLM synthesis with reasoning trace

Endpoints:
- POST /kg-query: Process query with full KG-enhanced reasoning
- GET /kg-routes: List available golden routes
- GET /kg-stats: Get KG statistics

Author: Nuzantara Team
Date: 2026-01-28
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import (
    get_current_user,
    get_optional_database_pool,
    get_search_service,
)
from backend.app.utils.tracing import set_span_attribute, trace_span
from backend.services.rag.agentic.kg_orchestrator import (
    AgenticResponse,
    KGAgenticOrchestrator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kg", tags=["Knowledge Graph RAG"])

# Singleton orchestrator instances
_kg_orchestrator: KGAgenticOrchestrator | None = None
_kg_langgraph_orchestrator: Any = None  # KGLangGraphOrchestrator, lazy import


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class KGQueryRequest(BaseModel):
    """Request model for KG-enhanced query."""

    query: str = Field(..., min_length=3, max_length=2000, description="User query")
    session_id: str | None = Field(None, description="Session identifier for context")
    include_sources: bool = Field(True, description="Include source documents in response")
    include_reasoning: bool = Field(True, description="Include reasoning trace")


class KGQueryResponse(BaseModel):
    """Response model for KG-enhanced query."""

    answer: str
    confidence: float
    reasoning_trace: list[str] | None = None
    sources: list[dict[str, Any]] | None = None
    estimated_timeline: str | None = None
    estimated_cost: str | None = None

    # Metadata
    intent_category: str | None = None
    golden_route_matched: str | None = None
    kg_entities_found: int = 0
    collections_searched: list[str] = []
    total_time_ms: float = 0.0
    model_used: str | None = None


class GoldenRouteInfo(BaseModel):
    """Info about a golden route."""

    route_id: str
    name: str
    description: str
    path: list[str]
    key_conditions: list[str]
    estimated_timeline_months: float | None = None
    estimated_cost_range_usd: list[int] | None = None


class KGStatsResponse(BaseModel):
    """KG statistics response."""

    total_nodes: int
    total_edges: int
    node_types: dict[str, int]
    edge_types: dict[str, int]
    golden_routes_available: int


# =============================================================================
# DEPENDENCIES
# =============================================================================


async def get_kg_orchestrator(
    db_pool=Depends(get_optional_database_pool),
    retriever=Depends(get_search_service),
) -> KGAgenticOrchestrator:
    """
    Get or create KGAgenticOrchestrator singleton.

    Uses dependency injection for db_pool and retriever.
    """
    global _kg_orchestrator

    if _kg_orchestrator is None:
        if db_pool is None:
            raise HTTPException(
                status_code=503,
                detail="Database not available. KG orchestrator requires PostgreSQL.",
            )

        _kg_orchestrator = KGAgenticOrchestrator(
            db_pool=db_pool,
            retriever=retriever,
        )
        logger.info("✅ KGAgenticOrchestrator initialized")

    return _kg_orchestrator


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post(
    "/query",
    response_model=KGQueryResponse,
    summary="Process query with KG-enhanced reasoning",
    description="""
    Process a user query using the KG-Agentic orchestrator.

    This endpoint:
    1. Classifies query intent
    2. Extracts entities and traverses the Knowledge Graph
    3. Matches golden routes for known scenarios
    4. Executes vector search on relevant collections
    5. Synthesizes answer with LLM
    6. Returns reasoning trace for explainability

    **Example queries:**
    - "How to open a restaurant in Bali as a foreigner?"
    - "What's the process to convert KITAS to KITAP?"
    - "Digital nomad visa requirements"
    """,
)
async def kg_query(
    request: KGQueryRequest,
    orchestrator: KGAgenticOrchestrator = Depends(get_kg_orchestrator),
    current_user: dict = Depends(get_current_user),
) -> KGQueryResponse:
    """
    Process query with full KG-enhanced agentic reasoning.
    """
    with trace_span("kg_agentic_query", {"query_length": len(request.query)}):
        start_time = time.time()

        try:
            # Generate session_id if not provided
            session_id = request.session_id or f"kg_{int(time.time())}"

            logger.info(
                f"🧠 KG Query: {request.query[:100]}... "
                f"(session={session_id}, user={current_user.get('sub', 'anonymous')})"
            )

            # Process with orchestrator
            result: AgenticResponse = await orchestrator.process(
                query=request.query,
                session_id=session_id,
                user_id=current_user.get("sub"),
            )

            # Build response
            response = KGQueryResponse(
                answer=result.answer,
                confidence=result.confidence,
                reasoning_trace=result.reasoning_trace if request.include_reasoning else None,
                sources=result.sources if request.include_sources else None,
                estimated_timeline=result.estimated_timeline,
                estimated_cost=result.estimated_cost,
                intent_category=result.intent_category,
                golden_route_matched=result.golden_route_matched,
                kg_entities_found=result.kg_entities_found,
                collections_searched=result.collections_searched,
                total_time_ms=result.total_time_ms,
                model_used=result.model_used,
            )

            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"✅ KG Query complete: confidence={result.confidence:.2f}, "
                f"golden_route={result.golden_route_matched}, "
                f"time={total_time:.0f}ms"
            )

            set_span_attribute("confidence", result.confidence)
            set_span_attribute("golden_route", result.golden_route_matched or "none")

            return response

        except Exception as e:
            logger.error(f"❌ KG Query failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"KG query processing failed: {str(e)}",
            ) from e


@router.get(
    "/routes",
    response_model=list[GoldenRouteInfo],
    summary="List available golden routes",
    description="Get all pre-defined golden routes with their paths and conditions.",
)
async def list_golden_routes(
    orchestrator: KGAgenticOrchestrator = Depends(get_kg_orchestrator),
) -> list[GoldenRouteInfo]:
    """
    List all available golden routes.
    """
    try:
        routes = orchestrator.kg_retrieval._load_golden_routes()

        return [
            GoldenRouteInfo(
                route_id=route.route_id,
                name=route.name,
                description=route.description,
                path=route.path,
                key_conditions=route.key_conditions,
                estimated_timeline_months=route.estimated_timeline_months,
                estimated_cost_range_usd=route.estimated_cost_range_usd,
            )
            for route in routes.values()
        ]

    except Exception as e:
        logger.error(f"❌ Failed to list golden routes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list golden routes: {str(e)}",
        ) from e


@router.get(
    "/stats",
    response_model=KGStatsResponse,
    summary="Get KG statistics",
    description="Get statistics about the Knowledge Graph (nodes, edges, types).",
)
async def kg_stats(
    orchestrator: KGAgenticOrchestrator = Depends(get_kg_orchestrator),
) -> KGStatsResponse:
    """
    Get Knowledge Graph statistics. Cached for 2 minutes.
    """
    try:
        # Check cache first (stats change rarely)
        from backend.services.rag.kg_cache import get_kg_cache

        cache = get_kg_cache()
        cached = await cache.get_stats()
        if cached is not None:
            return KGStatsResponse(**cached)

        async with orchestrator.db_pool.acquire() as conn:
            # Single query: node + edge counts in one round-trip
            counts = await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM kg_nodes) as total_nodes,
                    (SELECT COUNT(*) FROM kg_edges) as total_edges
                """
            )

            # Get node types
            node_types_rows = await conn.fetch(
                """
                SELECT entity_type, COUNT(*) as count
                FROM kg_nodes
                GROUP BY entity_type
                ORDER BY count DESC
                """
            )
            node_types = {r["entity_type"]: r["count"] for r in node_types_rows}

            # Get edge types
            edge_types_rows = await conn.fetch(
                """
                SELECT relationship_type, COUNT(*) as count
                FROM kg_edges
                GROUP BY relationship_type
                ORDER BY count DESC
                """
            )
            edge_types = {r["relationship_type"]: r["count"] for r in edge_types_rows}

            # Count golden routes
            routes = orchestrator.kg_retrieval._load_golden_routes()

        stats_data = {
            "total_nodes": counts["total_nodes"] or 0,
            "total_edges": counts["total_edges"] or 0,
            "node_types": node_types,
            "edge_types": edge_types,
            "golden_routes_available": len(routes),
        }
        await cache.set_stats(stats_data)

        return KGStatsResponse(**stats_data)

    except Exception as e:
        logger.error(f"❌ Failed to get KG stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get KG stats: {str(e)}",
        ) from e


@router.get(
    "/path",
    summary="Find path between entities",
    description="Find paths in the KG between two entity IDs.",
)
async def find_kg_path(
    source: str = Query(..., description="Source entity ID (e.g., kbli:56101)"),
    target: str = Query(..., description="Target entity ID (e.g., permit:kitas)"),
    max_depth: int = Query(3, ge=1, le=6, description="Maximum path depth"),
    orchestrator: KGAgenticOrchestrator = Depends(get_kg_orchestrator),
) -> dict[str, Any]:
    """
    Find paths between two entities in the Knowledge Graph.
    """
    try:
        async with orchestrator.db_pool.acquire() as conn:
            paths = await conn.fetch(
                """
                WITH RECURSIVE path_finder AS (
                    SELECT
                        e.source_entity_id,
                        e.target_entity_id,
                        e.relationship_type,
                        ARRAY[e.source_entity_id, e.target_entity_id] as path,
                        ARRAY[e.relationship_type] as rels,
                        1 as depth
                    FROM kg_edges e
                    WHERE e.source_entity_id = $1

                    UNION ALL

                    SELECT
                        e.source_entity_id,
                        e.target_entity_id,
                        e.relationship_type,
                        pf.path || e.target_entity_id,
                        pf.rels || e.relationship_type,
                        pf.depth + 1
                    FROM path_finder pf
                    JOIN kg_edges e ON e.source_entity_id = pf.target_entity_id
                    WHERE NOT e.target_entity_id = ANY(pf.path)
                      AND pf.depth < $3
                )
                SELECT path, rels, depth
                FROM path_finder
                WHERE target_entity_id = $2
                ORDER BY depth
                LIMIT 5
                """,
                source,
                target,
                max_depth,
            )

        if not paths:
            return {
                "source": source,
                "target": target,
                "paths_found": 0,
                "paths": [],
            }

        formatted_paths = []
        for p in paths:
            steps = []
            for i, node in enumerate(p["path"]):
                step = {"entity": node}
                if i < len(p["rels"]):
                    step["relation"] = p["rels"][i]
                steps.append(step)

            formatted_paths.append(
                {
                    "depth": p["depth"],
                    "steps": steps,
                }
            )

        return {
            "source": source,
            "target": target,
            "paths_found": len(formatted_paths),
            "paths": formatted_paths,
        }

    except Exception as e:
        logger.error(f"❌ Failed to find KG path: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to find path: {str(e)}",
        ) from e


@router.get(
    "/visualize",
    summary="Get KG visual graph",
    description="Get Mermaid diagram of the KG exploration graph.",
)
async def kg_visualize(
    subgraph: str | None = Query(None, description="Optional subgraph name"),
    db_pool=Depends(get_optional_database_pool),
) -> dict[str, str]:
    """
    Get Mermaid diagram of the graph. Reuses singleton LangGraph orchestrator.
    """
    try:
        global _kg_langgraph_orchestrator
        if _kg_langgraph_orchestrator is None:
            from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

            _kg_langgraph_orchestrator = KGLangGraphOrchestrator(db_pool)

        mermaid = await _kg_langgraph_orchestrator.get_visual_graph(subgraph)

        return {"mermaid": mermaid}

    except Exception as e:
        logger.error(f"❌ Failed to visualize KG: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to visualize KG: {str(e)}",
        ) from e


@router.post(
    "/cache/invalidate",
    summary="Invalidate KG cache",
    description="Clear all cached KG query results. Use after graph ingestion or updates.",
)
async def invalidate_kg_cache(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Invalidate all KG cache entries (requires auth)."""
    from backend.services.rag.kg_cache import get_kg_cache

    cache = get_kg_cache()
    count = await cache.invalidate_all()
    return {"invalidated": count, "status": "ok"}
