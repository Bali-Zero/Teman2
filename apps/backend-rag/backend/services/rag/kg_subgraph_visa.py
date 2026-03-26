"""
Visa Subgraph for LangGraph KG

Handles KITAS, KITAP, and VITAS visa processing workflows.
Specialized subgraph for visa/immigration queries with domain-specific logic.

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
# Visa-Specific State
# ============================================================================


class VisaState(TypedDict, total=False):
    """
    State for Visa Subgraph.

    Extends KGAgentState with visa-specific fields.
    """

    # Inherited from parent (KGAgentState)
    query: str
    user_context: dict
    current_entities: list[str]
    visited_entities: set[str]
    relationship_chains: list[list[dict]]
    workflow: dict | None

    # Visa-specific fields
    visa_type: str | None  # "kitas", "kitap", "vitas", "visa_on_arrival"
    purpose: str | None  # "work", "investment", "retirement", "family"
    employment_type: str | None  # "director", "employee", "shareholder"
    requires_rptka: bool  # Work permit
    sponsor_company: str | None  # PT PMA name
    duration_months: int | None
    visa_requirements: list[dict]


# ============================================================================
# Node 1: Identify Visa Type
# ============================================================================


async def identify_visa_type_node(state: VisaState, llm) -> VisaState:
    """
    Identify visa type from query and user context.

    Determines: KITAS, KITAP, VITAS, or Visa on Arrival based on:
    - Purpose (work → KITAS, retirement → KITAP, tourist → VOA)
    - Duration (<60 days → VOA, <1 year → limited stay, >=1 year → KITAS)
    - Employment status (director vs employee)

    Args:
        state: Current VisaState
        llm: LangChain LLM for reasoning

    Returns:
        Updated state with visa_type identified
    """
    logger.info("🛂 [Visa Subgraph] Identifying visa type...")

    query = state["query"]
    state.get("user_context", {})

    query_lower = query.lower()

    # Identify visa type from query keywords
    if "kitas" in query_lower:
        visa_type = "kitas"
        purpose = "work"
    elif "kitap" in query_lower:
        visa_type = "kitap"
        purpose = "retirement" if "retire" in query_lower else "permanent_stay"
    elif "vitas" in query_lower or "social visit" in query_lower:
        visa_type = "vitas"
        purpose = "social_visit"
    elif "tourist" in query_lower or "visit" in query_lower:
        visa_type = "visa_on_arrival"
        purpose = "tourism"
    else:
        # Default based on work indicators
        if any(word in query_lower for word in ["work", "employ", "job", "chef", "manager"]):
            visa_type = "kitas"
            purpose = "work"
        else:
            visa_type = "vitas"
            purpose = "social_visit"

    # Identify employment type
    employment_type = None
    if "director" in query_lower or "commissaris" in query_lower:
        employment_type = "director"
    elif "employee" in query_lower or "staff" in query_lower or "chef" in query_lower:
        employment_type = "employee"
    elif "shareholder" in query_lower or "investor" in query_lower:
        employment_type = "shareholder"

    state["visa_type"] = visa_type
    state["purpose"] = purpose
    state["employment_type"] = employment_type

    # RPTKA required for work visas
    state["requires_rptka"] = visa_type == "kitas" and purpose == "work"

    logger.info(
        f"✅ [Visa Subgraph] Identified: {visa_type}, purpose: {purpose}, "
        f"employment: {employment_type}, RPTKA: {state['requires_rptka']}"
    )

    return state


# ============================================================================
# Node 2: Check RPTKA Requirements
# ============================================================================


async def check_rptka_requirements_node(state: VisaState, db_pool: asyncpg.Pool) -> VisaState:
    """
    Check RPTKA (Rencana Penggunaan Tenaga Kerja Asing) requirements.

    For work visas, RPTKA is required before KITAS application.
    Queries KG for RPTKA requirements and process.

    Args:
        state: Current VisaState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with RPTKA requirements
    """
    logger.info("📋 [Visa Subgraph] Checking RPTKA requirements...")

    if not state.get("requires_rptka"):
        logger.info("⏭️ [Visa Subgraph] RPTKA not required, skipping")
        return state

    # Query KG for RPTKA requirements
    rptka_steps: list[str] = []
    rptka_duration: str = "Typically 2-4 weeks"
    rptka_validity: str = "Matches employment contract (max 5 years)"
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT e.properties->>'description' AS req,
                       e.properties->>'duration' AS dur,
                       e.properties->>'validity' AS val
                FROM kg_edges e
                JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                WHERE n.entity_type ILIKE 'rptka'
                  AND e.relationship_type = 'REQUIRES'
                LIMIT 20
                """,
            )
            for row in rows:
                if row["req"]:
                    rptka_steps.append(row["req"])
                if row["dur"]:
                    rptka_duration = row["dur"]
                if row["val"]:
                    rptka_validity = row["val"]
    except Exception as e:
        logger.warning(f"KG RPTKA query failed, using fallback: {e}")

    # Fallback if KG has no RPTKA data
    if not rptka_steps:
        rptka_steps = [
            "Submit TKA allocation quota application to Kementerian Ketenagakerjaan",
            "Apply for IMTA (Izin Mempekerjakan Tenaga Kerja Asing) online via SPKP system",
            "Provide job description and justification",
            "Provide local training plan (mentorship program)",
            "Pay IMTA fee per worker",
        ]

    rptka_req = {
        "requirement_type": "rptka",
        "description": "Work Permit for Foreign Workers",
        "steps": rptka_steps,
        "duration": rptka_duration,
        "validity": rptka_validity,
        "renewal": "Can be extended before expiry",
    }

    state.setdefault("visa_requirements", []).append(rptka_req)

    logger.info("✅ [Visa Subgraph] RPTKA requirements added")

    return state


# ============================================================================
# Node 3: Get Visa Requirements
# ============================================================================


async def get_visa_requirements_node(state: VisaState, db_pool: asyncpg.Pool) -> VisaState:
    """
    Get specific visa requirements based on visa type.

    Queries KG for documents, fees, and processing time.

    Args:
        state: Current VisaState
        db_pool: PostgreSQL connection pool

    Returns:
        Updated state with visa requirements
    """
    logger.info("📄 [Visa Subgraph] Getting visa requirements...")

    visa_type = state.get("visa_type", "unknown")

    # Hardcoded requirements (can be queried from KG)
    requirements_db = {
        "kitas": {
            "documents": [
                "Passport (valid >18 months)",
                "E-Visa approval",
                "Sponsorship letter from PT PMA",
                "IMTA (work permit approval)",
                "Employment contract",
                "Health insurance",
                "CV and certificates",
            ],
            "fees": {
                "PNBP": 3_500_000,  # IDR
                "KITAS card": 1_055_000,  # IDR
                "currency": "IDR",
            },
            "processing_time": "14-30 days after VITAS approval",
            "validity": "1-2 years (renewable)",
        },
        "kitap": {
            "documents": [
                "Passport",
                "KITAS history (min 3 consecutive years)",
                "Proof of pension/income",
                "Sponsorship letter",
                "Health insurance",
            ],
            "fees": {
                "PNBP": 8_000_000,  # IDR
                "currency": "IDR",
            },
            "processing_time": "30-60 days",
            "validity": "5 years (renewable)",
        },
        "vitas": {
            "documents": [
                "Passport",
                "Sponsorship letter",
                "Proof of purpose",
            ],
            "fees": {
                "PNBP": 1_500_000,  # IDR (varies by category)
                "currency": "IDR",
            },
            "processing_time": "7-14 days",
            "validity": "60 days (must convert to KITAS within 60 days)",
        },
        "visa_on_arrival": {
            "documents": [
                "Passport (valid >6 months)",
                "Return ticket",
            ],
            "fees": {
                "PNBP": 500_000,  # IDR
                "currency": "IDR",
            },
            "processing_time": "On arrival",
            "validity": "30 days (extendable once to 60 days total)",
        },
    }

    requirements = requirements_db.get(visa_type, {})

    state.setdefault("visa_requirements", []).append(
        {
            "requirement_type": "visa_documents_and_fees",
            "visa_type": visa_type,
            "details": requirements,
        }
    )

    state["duration_months"] = {
        "kitas": 12,
        "kitap": 60,
        "vitas": 2,
        "visa_on_arrival": 1,
    }.get(visa_type, 12)

    logger.info(f"✅ [Visa Subgraph] Requirements added for {visa_type}")

    return state


# ============================================================================
# Node 4: Synthesize Visa Workflow
# ============================================================================


async def synthesize_visa_workflow_node(state: VisaState) -> VisaState:
    """
    Synthesize visa application workflow from collected information.

    Builds step-by-step workflow:
    1. RPTKA application (if work visa)
    2. VITAS application (if applicable)
    3. Enter Indonesia with VITAS
    4. Convert to KITAS within 60 days
    5. MERP (Multiple Exit/Re-entry Permit)

    Args:
        state: Current VisaState

    Returns:
        Updated state with workflow synthesized
    """
    logger.info("📋 [Visa Subgraph] Synthesizing visa workflow...")

    visa_type = state.get("visa_type", "unknown")
    requires_rptka = state.get("requires_rptka", False)
    state.get("purpose", "unknown")

    steps = []

    # Step 1: IMTA/TKA Allocation (if work visa)
    if requires_rptka:
        steps.append(
            {
                "step": 1,
                "action": "Apply for TKA allocation quota and IMTA via SPKP system (Kementerian Ketenagakerjaan)",
                "entity_id": "imta_tka",
                "details": {
                    "requirement": "Work permit for foreign employee (IMTA)",
                    "processing_time": "2-4 weeks",
                },
            }
        )

    # Step 2: VITAS application (for KITAS/KITAP)
    if visa_type in ["kitas", "kitap"]:
        steps.append(
            {
                "step": len(steps) + 1,
                "action": "Apply for E-Visa online via imigrasi.go.id",
                "entity_id": f"evisa_{visa_type}",
                "details": {
                    "system": "Online application via immigration portal",
                    "processing_time": "7-14 days",
                },
            }
        )

    # Step 3: Entry to Indonesia
    steps.append(
        {
            "step": len(steps) + 1,
            "action": f"Enter Indonesia with {visa_type.upper()}",
            "entity_id": f"{visa_type}_entry",
            "details": {
                "validity": f"{state.get('duration_months', 1)} months",
            },
        }
    )

    # Step 4: KITAS conversion (if VITAS)
    if visa_type == "kitas":
        steps.append(
            {
                "step": len(steps) + 1,
                "action": "Convert VITAS to KITAS within 60 days",
                "entity_id": "kitas_conversion",
                "details": {
                    "location": "Immigration office in Indonesia",
                    "documents": "Passport, VITAS, sponsorship docs",
                },
            }
        )

    # Step 5: MERP (for KITAS/KITAP)
    if visa_type in ["kitas", "kitap"]:
        steps.append(
            {
                "step": len(steps) + 1,
                "action": "Apply for MERP (Multiple Exit/Re-entry Permit)",
                "entity_id": "merp",
                "details": {
                    "purpose": "Allow multiple exits from Indonesia",
                    "validity": "Matches KITAS/KITAP validity",
                },
            }
        )

    from dataclasses import asdict

    from backend.services.rag.confidence import calculate_subgraph_confidence

    breakdown = calculate_subgraph_confidence(
        workflow_source="visa_subgraph",
        steps_count=len(steps),
        has_db_validation=state.get("requires_rptka", False),
        unique_sources=1,
    )

    workflow = {
        "id": f"visa_processing:{visa_type}",
        "type": "visa_processing",
        "name": f"{visa_type.upper()} Visa Processing",
        "steps": steps,
        "source": "visa_subgraph",
        "confidence": breakdown.overall,
        "confidence_breakdown": asdict(breakdown),
    }

    state["workflow"] = workflow

    logger.info(f"✅ [Visa Subgraph] Workflow synthesized with {len(steps)} steps")

    return state


# ============================================================================
# Subgraph Construction
# ============================================================================


def build_visa_subgraph(db_pool: asyncpg.Pool, llm: Any) -> StateGraph:
    """
    Build Visa Subgraph.

    Flow:
    1. identify_visa_type
    2. check_rptka_requirements (if work visa)
    3. get_visa_requirements
    4. synthesize_visa_workflow → END

    Args:
        db_pool: PostgreSQL connection pool
        llm: LangChain LLM for reasoning

    Returns:
        Compiled StateGraph for visa processing
    """
    logger.info("🏗️ [Visa Subgraph] Building visa subgraph...")

    subgraph = StateGraph(VisaState)

    # Async closures (lambdas can't be async, causing coroutine-instead-of-dict errors)
    async def _identify(state) -> Any:
        return await identify_visa_type_node(state, llm)

    async def _check_rptka(state) -> Any:
        return await check_rptka_requirements_node(state, db_pool)

    async def _get_requirements(state) -> Any:
        return await get_visa_requirements_node(state, db_pool)

    async def _synthesize(state) -> Any:
        return await synthesize_visa_workflow_node(state)

    # Add nodes
    subgraph.add_node("identify_visa_type", _identify)
    subgraph.add_node("check_rptka_requirements", _check_rptka)
    subgraph.add_node("get_visa_requirements", _get_requirements)
    subgraph.add_node("synthesize_visa_workflow", _synthesize)

    # Set entry point
    subgraph.set_entry_point("identify_visa_type")

    # Add edges
    subgraph.add_edge("identify_visa_type", "check_rptka_requirements")
    subgraph.add_edge("check_rptka_requirements", "get_visa_requirements")
    subgraph.add_edge("get_visa_requirements", "synthesize_visa_workflow")
    subgraph.add_edge("synthesize_visa_workflow", END)

    logger.info("✅ [Visa Subgraph] Subgraph built with 4 nodes")

    return subgraph
