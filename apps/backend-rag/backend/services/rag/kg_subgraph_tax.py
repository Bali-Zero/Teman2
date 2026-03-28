"""
Tax Compliance Subgraph for LangGraph KG

Handles PPh (income tax), PPN (VAT), and tax obligations for businesses.
Specialized subgraph for tax compliance queries with domain-specific logic.

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
# Tax-Specific State
# ============================================================================


class TaxState(TypedDict, total=False):
    """
    State for Tax Compliance Subgraph.

    Extends KGAgentState with tax-specific fields.
    """

    # Inherited from parent (KGAgentState)
    query: str
    user_context: dict
    current_entities: list[str]
    visited_entities: set[str]
    relationship_chains: list[list[dict]]
    workflow: dict | None

    # Tax-specific fields
    business_entity_type: str | None  # "pt_pma", "perorangan", "cv"
    revenue_amount: int | None  # Annual revenue in IDR
    employee_count: int | None
    tax_obligations: list[dict]  # PPh, PPN, etc.
    tax_rates: dict[str, float]  # PPh rates by bracket
    vat_applicable: bool
    npwp_required: bool


# ============================================================================
# Node 1: Identify Tax Type
# ============================================================================


async def identify_tax_type_node(state: TaxState, llm) -> TaxState:
    """
    Identify applicable tax types based on business entity and activity.

    Determines: PPh (income tax), PPN (VAT), withholding taxes based on:
    - Business entity type (PT → corporate tax, Perorangan → personal)
    - Revenue amount (VAT threshold at 4.8B IDR)
    - Business activity (services vs goods)

    Args:
        state: Current TaxState
        llm: LangChain LLM for reasoning

    Returns:
        Updated state with tax types identified
    """
    logger.info("🧾 [Tax Subgraph] Identifying tax types...")

    query = state["query"]
    user_context = state.get("user_context", {})

    query_lower = query.lower()

    # Identify business entity from context or query
    entity_type = user_context.get("business_entity_type")
    if not entity_type:
        if "pt pma" in query_lower or "pt" in query_lower:
            entity_type = "pt_pma"
        elif "cv" in query_lower:
            entity_type = "cv"
        elif "perorangan" in query_lower:
            entity_type = "perorangan"
        else:
            entity_type = "pt_pma"  # Default for foreign investors

    state["business_entity_type"] = entity_type

    # NPWP (Tax ID) required for all business entities
    state["npwp_required"] = True

    # VAT threshold: 4.8B IDR annual revenue
    revenue = state.get("revenue_amount")
    state["vat_applicable"] = revenue is not None and revenue >= 4_800_000_000

    logger.info(
        f"✅ [Tax Subgraph] Entity: {entity_type}, "
        f"NPWP required: {state['npwp_required']}, "
        f"VAT applicable: {state['vat_applicable']}",
    )

    return state


# ============================================================================
# Node 2: Get Tax Obligations
# ============================================================================


async def get_tax_obligations_node(state: TaxState, db_pool: asyncpg.Pool) -> TaxState:
    """
    Get tax obligations based on entity type.

    Queries KG for:
    - PPh (income tax) rates and brackets
    - PPN (VAT) rates
    - Withholding taxes (PPh 21, 23, 26)
    - Filing deadlines

    Args:
        state: Current TaxState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with tax obligations
    """
    logger.info("📋 [Tax Subgraph] Getting tax obligations...")

    entity_type = state.get("business_entity_type", "unknown")

    # Hardcoded knowledge (can be queried from KG)
    tax_obligations_db = {
        "pt_pma": {
            "pph_corporate": {
                "rate": 0.22,  # 22% corporate tax
                "description": "Corporate Income Tax (PPh Badan)",
                "filing_deadline": "4 months after fiscal year end",
                "monthly_installment": "PPh 25 (estimated tax)",
            },
            "pph_21": {
                "description": "Withholding tax on employee salaries",
                "progressive_rates": [
                    {"bracket": "0-60M", "rate": 0.05},
                    {"bracket": "60-250M", "rate": 0.15},
                    {"bracket": "250-500M", "rate": 0.25},
                    {"bracket": "500M+", "rate": 0.30},
                ],
                "filing_deadline": "20th of following month",
            },
            "pph_23": {
                "rate": 0.02,  # 2% for services
                "description": "Withholding tax on services/rent",
                "filing_deadline": "20th of following month",
            },
            "pph_26": {
                "rate": 0.20,  # 20% for foreign payments
                "description": "Withholding tax on payments to non-residents",
                "filing_deadline": "20th of following month",
                "note": "May be reduced by tax treaty",
            },
            "ppn": {
                # VERIFIED 2026-02-09: 11% confirmed by Direktorat Jenderal Pajak
                # 12% applies ONLY to luxury goods (PPnBM), 11% remains standard rate
                # Source: https://stats.pajak.go.id/index.php/en/node/118104
                "rate": 0.11,  # 11% VAT (standard rate, verified for 2026)
                "description": "Value Added Tax",
                "filing_deadline": "End of following month",
                "threshold": 4_800_000_000,  # 4.8B IDR
            },
        },
        "cv": {
            "pph_corporate": {
                "rate": 0.22,
                "description": "Corporate Income Tax (CV is taxed as corporate entity)",
                "filing_deadline": "4 months after fiscal year end",
            },
            "ppn": {
                "rate": 0.11,
                "description": "Value Added Tax",
                "filing_deadline": "End of following month",
                "threshold": 4_800_000_000,
            },
        },
        "perorangan": {
            "pph_personal": {
                "description": "Personal Income Tax",
                "progressive_rates": [
                    {"bracket": "0-60M", "rate": 0.05},
                    {"bracket": "60-250M", "rate": 0.15},
                    {"bracket": "250-500M", "rate": 0.25},
                    {"bracket": "500M+", "rate": 0.30},
                ],
                "filing_deadline": "March 31 of following year",
            },
            "ppn": {
                "rate": 0.11,
                "description": "Value Added Tax (if revenue > 4.8B IDR)",
                "filing_deadline": "End of following month",
                "threshold": 4_800_000_000,
            },
        },
    }

    obligations = tax_obligations_db.get(entity_type, {})

    # Filter VAT if not applicable
    if not state.get("vat_applicable", False):
        obligations.pop("ppn", None)

    state.setdefault("tax_obligations", []).append(
        {
            "obligation_type": "tax_overview",
            "entity_type": entity_type,
            "details": obligations,
        },
    )

    logger.info(f"✅ [Tax Subgraph] Added {len(obligations)} tax obligations for {entity_type}")

    return state


# ============================================================================
# Node 3: Calculate Tax Requirements
# ============================================================================


async def calculate_tax_requirements_node(state: TaxState) -> TaxState:
    """
    Calculate estimated tax amounts and compliance requirements.

    Based on revenue and entity type, estimates:
    - Annual tax liability
    - Monthly installments
    - Filing frequency

    Args:
        state: Current TaxState

    Returns:
        Updated state with calculated tax requirements
    """
    logger.info("💰 [Tax Subgraph] Calculating tax requirements...")

    entity_type = state.get("business_entity_type")
    revenue = state.get("revenue_amount")

    if not revenue:
        logger.info("⏭️ [Tax Subgraph] No revenue provided, skipping calculation")
        return state

    # Simple tax calculation
    if entity_type in ["pt_pma", "cv"]:
        # Corporate tax: 22% on net profit (assume 20% profit margin)
        net_profit = revenue * 0.20
        corporate_tax = net_profit * 0.22
        tax_summary = {
            "corporate_tax_pph": corporate_tax,
            "monthly_installment_pph25": corporate_tax / 12,
        }

        if state.get("vat_applicable"):
            # VERIFIED: 11% standard PPN rate confirmed for 2026
            # VAT: 11% on revenue (simplified)
            vat_payable = revenue * 0.11
            tax_summary["vat_ppn"] = vat_payable

    elif entity_type == "perorangan":
        # Progressive personal tax
        if revenue <= 60_000_000:
            tax = revenue * 0.05
        elif revenue <= 250_000_000:
            tax = 3_000_000 + (revenue - 60_000_000) * 0.15
        elif revenue <= 500_000_000:
            tax = 31_500_000 + (revenue - 250_000_000) * 0.25
        else:
            tax = 94_000_000 + (revenue - 500_000_000) * 0.30

        tax_summary = {
            "personal_tax_pph": tax,
        }

        if state.get("vat_applicable"):
            tax_summary["vat_ppn"] = revenue * 0.11

    else:
        tax_summary = {}

    state.setdefault("tax_obligations", []).append(
        {
            "obligation_type": "estimated_tax",
            "revenue": revenue,
            "currency": "IDR",
            "calculations": tax_summary,
        },
    )

    logger.info(f"✅ [Tax Subgraph] Tax calculations: {len(tax_summary)} items")

    return state


# ============================================================================
# Node 4: Synthesize Tax Workflow
# ============================================================================


async def synthesize_tax_workflow_node(state: TaxState) -> TaxState:
    """
    Synthesize tax compliance workflow from collected information.

    Builds step-by-step workflow:
    1. Obtain NPWP (Tax ID)
    2. Register for VAT (if applicable)
    3. Set up bookkeeping system
    4. Monthly tax filing (PPh 21, 23, 25, PPN)
    5. Annual tax return

    Args:
        state: Current TaxState

    Returns:
        Updated state with workflow synthesized
    """
    logger.info("📋 [Tax Subgraph] Synthesizing tax workflow...")

    entity_type = state.get("business_entity_type", "unknown")
    vat_applicable = state.get("vat_applicable", False)

    steps = []

    # Step 1: NPWP registration
    steps.append(
        {
            "step": 1,
            "action": "Obtain NPWP (Tax ID)",
            "entity_id": "npwp",
            "details": {
                "requirement": "Mandatory for all businesses",
                "registration": "Online via DJP (Direktorat Jenderal Pajak)",
                "processing_time": "1-3 days",
            },
        },
    )

    # Step 2: VAT registration (if applicable)
    if vat_applicable:
        steps.append(
            {
                "step": 2,
                "action": "Register as VAT Taxable Entrepreneur (PKP)",
                "entity_id": "pkp_registration",
                "details": {
                    "requirement": "Revenue > 4.8B IDR annually",
                    "registration": "Online via DJP",
                    "processing_time": "7-14 days",
                },
            },
        )

    # Step 3: Bookkeeping
    steps.append(
        {
            "step": len(steps) + 1,
            "action": "Set up bookkeeping and accounting system",
            "entity_id": "bookkeeping",
            "details": {
                "requirement": "Required for all business entities",
                "software": "E.g., Jurnal, Accurate, or custom",
            },
        },
    )

    # Step 4: Monthly filings
    monthly_filings = []
    if entity_type in ["pt_pma", "cv"]:
        monthly_filings = ["PPh 21 (employee tax)", "PPh 23 (service tax)", "PPh 25 (installment)"]
    if vat_applicable:
        monthly_filings.append("PPN (VAT return)")

    if monthly_filings:
        steps.append(
            {
                "step": len(steps) + 1,
                "action": "Monthly tax filing",
                "entity_id": "monthly_filing",
                "details": {
                    "filings": monthly_filings,
                    "deadline": "20th of following month (withholding), end of month (VAT)",
                },
            },
        )

    # Step 5: Annual return
    steps.append(
        {
            "step": len(steps) + 1,
            "action": "Annual tax return (SPT Tahunan)",
            "entity_id": "annual_return",
            "details": {
                "deadline": "4 months after fiscal year end (corporate), March 31 (personal)",
                "requirement": "Audited financial statements for revenue > 50B IDR",
            },
        },
    )

    from dataclasses import asdict

    from backend.services.rag.confidence import calculate_subgraph_confidence

    breakdown = calculate_subgraph_confidence(
        workflow_source="tax_subgraph",
        steps_count=len(steps),
        has_db_validation=False,
        unique_sources=1,
    )

    workflow = {
        "id": f"tax_compliance:{entity_type}",
        "type": "tax_compliance",
        "name": f"{entity_type.upper()} Tax Compliance",
        "steps": steps,
        "source": "tax_subgraph",
        "confidence": breakdown.overall,
        "confidence_breakdown": asdict(breakdown),
    }

    state["workflow"] = workflow

    logger.info(f"✅ [Tax Subgraph] Workflow synthesized with {len(steps)} steps")

    return state


# ============================================================================
# Subgraph Construction
# ============================================================================


def build_tax_subgraph(db_pool: asyncpg.Pool, llm: Any) -> StateGraph:
    """
    Build Tax Compliance Subgraph.

    Flow:
    1. identify_tax_type
    2. get_tax_obligations
    3. calculate_tax_requirements
    4. synthesize_tax_workflow → END

    Args:
        db_pool: PostgreSQL connection pool
        llm: LangChain LLM for reasoning

    Returns:
        Compiled StateGraph for tax compliance
    """
    logger.info("🏗️ [Tax Subgraph] Building tax compliance subgraph...")

    subgraph = StateGraph(TaxState)

    # Async closures (lambdas can't be async, causing coroutine-instead-of-dict errors)
    async def _identify(state) -> Any:
        return await identify_tax_type_node(state, llm)

    async def _get_obligations(state) -> Any:
        return await get_tax_obligations_node(state, db_pool)

    async def _calculate(state) -> Any:
        return await calculate_tax_requirements_node(state)

    async def _synthesize(state) -> Any:
        return await synthesize_tax_workflow_node(state)

    # Add nodes
    subgraph.add_node("identify_tax_type", _identify)
    subgraph.add_node("get_tax_obligations", _get_obligations)
    subgraph.add_node("calculate_tax_requirements", _calculate)
    subgraph.add_node("synthesize_tax_workflow", _synthesize)

    # Set entry point
    subgraph.set_entry_point("identify_tax_type")

    # Add edges
    subgraph.add_edge("identify_tax_type", "get_tax_obligations")
    subgraph.add_edge("get_tax_obligations", "calculate_tax_requirements")
    subgraph.add_edge("calculate_tax_requirements", "synthesize_tax_workflow")
    subgraph.add_edge("synthesize_tax_workflow", END)

    logger.info("✅ [Tax Subgraph] Subgraph built with 4 nodes")

    return subgraph
