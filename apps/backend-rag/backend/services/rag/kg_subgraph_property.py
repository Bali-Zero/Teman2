"""
Property Subgraph for LangGraph KG

Handles property acquisition workflows (Hak Pakai, HGB, villa rental).
Specialized subgraph for real estate queries with domain-specific logic.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md (Phase 3)
"""

import logging
from typing import Any, TypedDict

import asyncpg
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class PropertyState(TypedDict, total=False):
    """State for Property Subgraph."""

    query: str
    user_context: dict
    current_entities: list[str]
    workflow: dict | None

    # Property-specific
    property_type: str | None  # "hak_pakai", "hgb", "hak_milik", "rental"
    is_foreign_buyer: bool
    property_value: int | None
    location: str | None
    property_requirements: list[dict]


async def identify_property_type_node(state: PropertyState, llm) -> PropertyState:
    """Identify property ownership type."""
    logger.info("🏠 [Property Subgraph] Identifying property type...")

    query_lower = state["query"].lower()
    is_foreign = state.get("user_context", {}).get("citizenship") == "foreign"

    if "hak pakai" in query_lower:
        prop_type = "hak_pakai"
    elif "hgb" in query_lower or "hak guna bangunan" in query_lower:
        prop_type = "hgb"
    elif "hak milik" in query_lower:
        prop_type = "hak_milik"
    elif "rent" in query_lower or "lease" in query_lower:
        prop_type = "rental"
    else:
        prop_type = "hak_pakai" if is_foreign else "hak_milik"

    state["property_type"] = prop_type
    state["is_foreign_buyer"] = is_foreign

    logger.info(f"✅ [Property Subgraph] Type: {prop_type}, foreign: {is_foreign}")
    return state


async def get_property_requirements_node(
    state: PropertyState, db_pool: asyncpg.Pool
) -> PropertyState:
    """Get ownership requirements."""
    logger.info("📋 [Property Subgraph] Getting property requirements...")

    prop_type = state.get("property_type", "unknown")

    requirements_db = {
        "hak_pakai": {
            "allowed_for_foreigners": True,
            "max_duration": "30 years (renewable 20+30 years)",
            "requirements": [
                "KITAS/KITAP holder",
                "Notary deed",
                "Land certificate check (BPN)",
                "Pay BPHTB (5% tax)",
            ],
            "notes": "Most common for foreign property ownership",
        },
        "hgb": {
            "allowed_for_foreigners": False,
            "max_duration": "30 years (renewable)",
            "requirements": [
                "Indonesian citizen or Indonesian legal entity only",
            ],
            "notes": "Foreigners can acquire via PT PMA",
        },
        "hak_milik": {
            "allowed_for_foreigners": False,
            "max_duration": "Permanent",
            "requirements": [
                "Indonesian citizen only",
            ],
            "notes": "Full ownership, not available to foreigners",
        },
        "rental": {
            "allowed_for_foreigners": True,
            "max_duration": "Varies (typically 1-5 years)",
            "requirements": [
                "Rental agreement",
                "Passport copy",
                "Deposit (usually 2-3 months rent)",
            ],
            "notes": "Simplest option for short-term stay",
        },
    }

    reqs = requirements_db.get(prop_type, {})
    state.setdefault("property_requirements", []).append(
        {
            "requirement_type": "ownership",
            "details": reqs,
        }
    )

    logger.info(f"✅ [Property Subgraph] Requirements added for {prop_type}")
    return state


async def synthesize_property_workflow_node(state: PropertyState) -> PropertyState:
    """Synthesize property acquisition workflow."""
    logger.info("📋 [Property Subgraph] Synthesizing property workflow...")

    prop_type = state.get("property_type", "unknown")

    steps = [
        {
            "step": 1,
            "action": f"Identify property with {prop_type.upper()} title",
            "entity_id": prop_type,
        },
        {
            "step": 2,
            "action": "Conduct due diligence (BPN certificate check)",
            "entity_id": "bpn_check",
        },
        {"step": 3, "action": "Negotiate price and terms", "entity_id": "negotiation"},
        {"step": 4, "action": "Sign Jual Beli (Sale & Purchase Agreement)", "entity_id": "ppjb"},
        {"step": 5, "action": "Notary deed execution", "entity_id": "notary"},
        {"step": 6, "action": "Pay BPHTB tax (5% of transaction value)", "entity_id": "bphtb"},
        {"step": 7, "action": "Register at Land Office (BPN)", "entity_id": "bpn_registration"},
    ]

    from dataclasses import asdict

    from backend.services.rag.confidence import calculate_subgraph_confidence

    breakdown = calculate_subgraph_confidence(
        workflow_source="property_subgraph",
        steps_count=len(steps),
        has_db_validation=False,
        unique_sources=1,
    )

    workflow = {
        "id": f"property:{prop_type}",
        "type": "property_acquisition",
        "name": f"{prop_type.upper()} Property Acquisition",
        "steps": steps,
        "source": "property_subgraph",
        "confidence": breakdown.overall,
        "confidence_breakdown": asdict(breakdown),
    }

    state["workflow"] = workflow
    logger.info(f"✅ [Property Subgraph] Workflow with {len(steps)} steps")
    return state


def build_property_subgraph(db_pool: asyncpg.Pool, llm: Any) -> StateGraph:
    """Build Property Subgraph."""
    logger.info("🏗️ [Property Subgraph] Building property subgraph...")

    subgraph = StateGraph(PropertyState)

    # Async closures (lambdas can't be async, causing coroutine-instead-of-dict errors)
    async def _identify(s) -> Any:
        return await identify_property_type_node(s, llm)

    async def _get_reqs(s) -> Any:
        return await get_property_requirements_node(s, db_pool)

    async def _synthesize(s) -> Any:
        return await synthesize_property_workflow_node(s)

    subgraph.add_node("identify_property_type", _identify)
    subgraph.add_node("get_property_requirements", _get_reqs)
    subgraph.add_node("synthesize_property_workflow", _synthesize)

    subgraph.set_entry_point("identify_property_type")
    subgraph.add_edge("identify_property_type", "get_property_requirements")
    subgraph.add_edge("get_property_requirements", "synthesize_property_workflow")
    subgraph.add_edge("synthesize_property_workflow", END)

    logger.info("✅ [Property Subgraph] Built with 3 nodes")
    return subgraph
