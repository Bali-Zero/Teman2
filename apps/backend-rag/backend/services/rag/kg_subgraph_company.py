"""
Company Setup Subgraph for LangGraph KG

Handles PT PMA, Perorangan, and CV company setup workflows.
Specialized subgraph for company formation queries with domain-specific logic.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md (Phase 3)
"""

import logging
from typing import Any, TypedDict

import asyncpg
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


# ============================================================================
# Company-Specific State
# ============================================================================


class CompanyState(TypedDict, total=False):
    """
    State for Company Setup Subgraph.

    Extends KGAgentState with company-specific fields.
    """

    # Inherited from parent (KGAgentState)
    query: str
    user_context: dict
    current_entities: list[str]
    visited_entities: set[str]
    relationship_chains: list[list[dict]]
    workflow: dict | None

    # Company-specific fields
    company_type: str | None  # "pt_pma", "perorangan", "cv", "pt_lokal"
    is_foreign_investor: bool
    capital_amount: int | None  # in IDR
    kbli_codes: list[str]  # Business classification codes
    licensing_requirements: list[dict]  # NIB, OSS, sector licenses
    shareholders: list[dict]  # For PT PMA
    legal_structure_recommendations: list[dict]


# ============================================================================
# Node 1: Identify Company Type
# ============================================================================


async def identify_company_type_node(
    state: CompanyState, llm, db_pool: asyncpg.Pool | None = None,
) -> CompanyState:
    """
    Identify company type from query and user context.

    Determines: PT PMA, Perorangan, CV, or PT Lokal based on:
    - Citizenship (foreign → likely PT PMA)
    - Capital amount (>10B IDR → PT, <1B → Perorangan/CV)
    - Business activity (from KBLI codes) - KG lookup if db_pool available
    - KG relationships (KBLI -> REQUIRES -> company:pt_pma)

    Args:
        state: Current CompanyState
        llm: LangChain LLM for reasoning
        db_pool: Optional PostgreSQL connection pool for KG lookup

    Returns:
        Updated state with company_type identified
    """
    import re

    logger.info("🏢 [Company Subgraph] Identifying company type...")

    query = state["query"]
    user_context = state.get("user_context", {})
    citizenship = user_context.get("citizenship", "unknown")

    # Simple heuristic (can be enhanced with LLM)
    is_foreign = citizenship == "foreign"

    # Check for PT PMA indicators in query
    query_lower = query.lower()
    if "pt pma" in query_lower or (is_foreign and "company" in query_lower):
        company_type = "pt_pma"
    elif "cv" in query_lower or "commanditaire" in query_lower:
        company_type = "cv"
    elif "perorangan" in query_lower or "sole proprietor" in query_lower:
        company_type = "perorangan"
    elif "pt" in query_lower:
        company_type = "pt_lokal"
    else:
        # Default based on citizenship
        company_type = "pt_pma" if is_foreign else "perorangan"

    # NEW: Check KG for KBLI requirements (overrides heuristics)
    if db_pool:
        kbli_codes = state.get("kbli_codes", [])
        if not kbli_codes:
            # Extract from query
            kbli_match = re.search(r"KBLI\s*(\d{5})", query, re.IGNORECASE)
            if kbli_match:
                kbli_codes = [f"kbli:{kbli_match.group(1)}"]
            else:
                kbli_codes = [e for e in state.get("current_entities", []) if e.startswith("kbli:")]

        if kbli_codes:
            try:
                async with db_pool.acquire() as conn:
                    # Check if KBLI requires PT PMA
                    requires_ptpma = await conn.fetchval(
                        """
                        SELECT COUNT(*) > 0
                        FROM kg_edges
                        WHERE source_entity_id = ANY($1::text[])
                        AND target_entity_id = 'company:pt_pma'
                        AND relationship_type = 'REQUIRES'
                        """,
                        kbli_codes,
                    )

                    if requires_ptpma:
                        company_type = "pt_pma"
                        is_foreign = True  # PT PMA implies foreign investor
                        logger.info(
                            f"✅ [Company Subgraph] KBLI {kbli_codes} requires PT PMA (from KG)",
                        )
            except Exception as e:
                logger.warning(f"⚠️ [Company Subgraph] KG lookup failed: {e}")

    state["company_type"] = company_type
    state["is_foreign_investor"] = is_foreign

    logger.info(f"✅ [Company Subgraph] Identified type: {company_type}, foreign: {is_foreign}")

    return state


# ============================================================================
# Node 2: Check PMA Eligibility
# ============================================================================


async def check_pma_eligibility_node(state: CompanyState, db_pool: asyncpg.Pool) -> CompanyState:
    """
    Check if business activity is eligible for foreign investment (PMA).

    Queries KG for:
    - KBLI codes with pma_status = "allowed" or "restricted"
    - DNI (Daftar Negatif Investasi) restrictions

    Args:
        state: Current CompanyState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with PMA eligibility info
    """
    logger.info("🔍 [Company Subgraph] Checking PMA eligibility...")

    if not state.get("is_foreign_investor"):
        logger.info("⏭️ [Company Subgraph] Not foreign investor, skipping PMA check")
        return state

    kbli_codes = state.get("kbli_codes", [])
    if not kbli_codes:
        # Try to extract from current_entities
        kbli_codes = [e for e in state.get("current_entities", []) if e.startswith("kbli:")]

    if not kbli_codes:
        logger.warning("⚠️ [Company Subgraph] No KBLI codes found for PMA check")
        return state

    async with db_pool.acquire() as conn:
        # Query KBLI nodes for PMA status
        results = await conn.fetch(
            """
            SELECT entity_id, name, properties
            FROM kg_nodes
            WHERE entity_id = ANY($1::text[])
              AND entity_type = 'kbli'
            """,
            kbli_codes,
        )

        pma_info = []
        for row in results:
            props = row.get("properties", {})
            pma_status = props.get("pma_status", "unknown")

            pma_info.append(
                {
                    "kbli_code": row["entity_id"],
                    "business_name": row["name"],
                    "pma_status": pma_status,
                    "eligible": pma_status in ["allowed", "open"],
                },
            )

        state["kbli_codes"] = kbli_codes
        state.setdefault("licensing_requirements", []).extend(
            [
                {
                    "requirement_type": "pma_eligibility",
                    "details": pma_info,
                },
            ],
        )

        logger.info(f"✅ [Company Subgraph] PMA eligibility checked for {len(pma_info)} KBLI codes")

    return state


# ============================================================================
# Node 3: Get Capital Requirements
# ============================================================================


async def get_capital_requirements_node(state: CompanyState, db_pool: asyncpg.Pool) -> CompanyState:
    """
    Get capital requirements for the company type.

    Queries KG for:
    - Minimum capital for PT PMA (usually 10B IDR)
    - Paid-up capital requirements
    - Capital structure requirements

    Args:
        state: Current CompanyState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with capital requirements
    """
    logger.info("💰 [Company Subgraph] Getting capital requirements...")

    company_type = state.get("company_type")

    # Hardcoded knowledge (can be queried from KG)
    capital_reqs = {
        "pt_pma": {
            "min_capital": 10_000_000_000,  # 10B IDR
            "paid_up_min": 2_500_000_000,  # 2.5B IDR
            "currency": "IDR",
            "notes": "Foreign investment minimum as per BKPM regulations",
        },
        "pt_lokal": {
            "min_capital": 50_000_000,  # 50M IDR
            "paid_up_min": 12_500_000,  # 12.5M IDR (25%)
            "currency": "IDR",
            "notes": "Standard PT minimum capital",
        },
        "cv": {
            "min_capital": None,
            "paid_up_min": None,
            "currency": "IDR",
            "notes": "No minimum capital required",
        },
        "perorangan": {
            "min_capital": None,
            "paid_up_min": None,
            "currency": "IDR",
            "notes": "No minimum capital required for sole proprietorship",
        },
    }

    requirements = capital_reqs.get(company_type, {})

    state.setdefault("licensing_requirements", []).append(
        {
            "requirement_type": "capital",
            "details": requirements,
        },
    )

    state["capital_amount"] = requirements.get("min_capital")

    logger.info(
        f"✅ [Company Subgraph] Capital requirements: {requirements.get('min_capital', 'N/A')} IDR",
    )

    return state


# ============================================================================
# Node 4: Synthesize Company Workflow
# ============================================================================


async def synthesize_company_workflow_node(state: CompanyState) -> CompanyState:
    """
    Synthesize company setup workflow from collected information.

    Builds step-by-step workflow:
    1. Choose legal structure
    2. Prepare capital
    3. Register company (NIB, OSS)
    4. Obtain licenses (sector-specific)
    5. Open bank account

    Args:
        state: Current CompanyState

    Returns:
        Updated state with workflow synthesized
    """
    logger.info("📋 [Company Subgraph] Synthesizing company workflow...")

    company_type = state.get("company_type", "unknown")
    is_foreign = state.get("is_foreign_investor", False)
    capital = state.get("capital_amount")

    steps = []

    # Step 1: Legal structure decision
    steps.append(
        {
            "step": 1,
            "action": f"Choose legal structure: {company_type.upper()}",
            "entity_id": f"company_type:{company_type}",
            "details": {
                "company_type": company_type,
                "is_foreign_investor": is_foreign,
            },
        },
    )

    # Step 2: Capital preparation
    if capital:
        steps.append(
            {
                "step": 2,
                "action": f"Prepare minimum capital: Rp {capital:,}",
                "entity_id": "capital_requirement",
                "details": {
                    "amount": capital,
                    "currency": "IDR",
                },
            },
        )

    # Step 3: Company registration
    steps.append(
        {
            "step": len(steps) + 1,
            "action": "Register company via OSS (Online Single Submission)",
            "entity_id": "oss_registration",
            "details": {
                "system": "OSS",
                "outputs": ["NIB", "TDP", "API (if applicable)"],
            },
        },
    )

    # Step 4: Licensing
    if state.get("kbli_codes"):
        steps.append(
            {
                "step": len(steps) + 1,
                "action": "Obtain sector licenses for KBLI codes",
                "entity_id": "sector_licensing",
                "details": {
                    "kbli_codes": state["kbli_codes"],
                },
            },
        )

    # Step 5: Bank account
    steps.append(
        {
            "step": len(steps) + 1,
            "action": "Open corporate bank account",
            "entity_id": "bank_account",
            "details": {
                "requirement": "After NIB issuance",
            },
        },
    )

    from dataclasses import asdict

    from backend.services.rag.confidence import calculate_subgraph_confidence

    has_db = state.get("is_foreign_investor", False)  # PMA eligibility checked DB
    breakdown = calculate_subgraph_confidence(
        workflow_source="company_subgraph",
        steps_count=len(steps),
        has_db_validation=has_db,
        unique_sources=1,
    )

    workflow = {
        "id": f"company_setup:{company_type}",
        "type": "company_setup",
        "name": f"{company_type.upper()} Company Setup",
        "steps": steps,
        "source": "company_subgraph",
        "confidence": breakdown.overall,
        "confidence_breakdown": asdict(breakdown),
    }

    state["workflow"] = workflow

    logger.info(f"✅ [Company Subgraph] Workflow synthesized with {len(steps)} steps")

    return state


# ============================================================================
# Subgraph Construction
# ============================================================================


def build_company_subgraph(db_pool: asyncpg.Pool, llm: Any) -> StateGraph:
    """
    Build Company Setup Subgraph.

    Flow:
    1. identify_company_type
    2. check_pma_eligibility (if foreign)
    3. get_capital_requirements
    4. synthesize_company_workflow → END

    Args:
        db_pool: PostgreSQL connection pool
        llm: LangChain LLM for reasoning

    Returns:
        Compiled StateGraph for company setup
    """
    logger.info("🏗️ [Company Subgraph] Building company setup subgraph...")

    subgraph = StateGraph(CompanyState)

    # Async closures (lambdas can't be async, causing coroutine-instead-of-dict errors)
    async def _identify(state) -> Any:
        return await identify_company_type_node(state, llm, db_pool)

    async def _check_pma(state) -> Any:
        return await check_pma_eligibility_node(state, db_pool)

    async def _get_capital(state) -> Any:
        return await get_capital_requirements_node(state, db_pool)

    async def _synthesize(state) -> Any:
        return await synthesize_company_workflow_node(state)

    # Add nodes
    subgraph.add_node("identify_company_type", _identify)
    subgraph.add_node("check_pma_eligibility", _check_pma)
    subgraph.add_node("get_capital_requirements", _get_capital)
    subgraph.add_node("synthesize_company_workflow", _synthesize)

    # Set entry point
    subgraph.set_entry_point("identify_company_type")

    # Add edges
    subgraph.add_edge("identify_company_type", "check_pma_eligibility")
    subgraph.add_edge("check_pma_eligibility", "get_capital_requirements")
    subgraph.add_edge("get_capital_requirements", "synthesize_company_workflow")
    subgraph.add_edge("synthesize_company_workflow", END)

    logger.info("✅ [Company Subgraph] Subgraph built with 4 nodes")

    return subgraph
