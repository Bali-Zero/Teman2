"""
Company Setup Subgraph for LangGraph KG

Handles PT PMA, Perorangan, and CV company setup workflows.
Specialized subgraph for company formation queries with domain-specific logic.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md (Phase 3)
"""

import json
import logging
from typing import Any, TypedDict

import asyncpg
from langgraph.graph import END, StateGraph

from backend.services.kbli_pma_disclosure import disclose_pma

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
    # Two DIFFERENT figures, and conflating them is client-facing misinformation:
    # `capital_amount` is the INVESTMENT PLAN threshold (nilai investasi), while
    # `paid_up_amount` is placed/paid-up company capital (modal
    # ditempatkan/disetor). For PT PMA the general rule is >10bn per five-digit
    # KBLI per project location, with statutory sector/activity exceptions, plus
    # at least 2.5bn placed/paid up per PT under Permeninvesthil/Kepala BKPM
    # 5/2025 Article 26.
    # Telling a founder to "prepare minimum capital: Rp 10,000,000,000" reads as
    # the second and is wrong by a factor of four.
    capital_amount: int | None  # in IDR — investment plan value, NOT paid-up
    paid_up_amount: int | None  # in IDR — modal ditempatkan/disetor
    investment_threshold_strict: bool  # True means amount is an exclusive lower bound
    kbli_codes: list[str]  # Business classification codes
    licensing_requirements: list[dict]  # NIB, OSS, sector licenses
    shareholders: list[dict]  # For PT PMA
    legal_structure_recommendations: list[dict]


# ============================================================================
# PMA eligibility vocabulary
# ============================================================================
#
# Censused on the live KG 2026-08-03 (`kg_nodes`, ids matching `kbli:NNNNN`):
#   TERBUKA 1464 · TERTUTUP 61 · TERBATAS 29 · "Verify at OSS" 4
# Not ONE row speaks the English vocabulary this module used to test itself
# against ("allowed" / "open" / "restricted"), so the old
# `pma_status in ["allowed", "open"]` evaluated False for EVERY code in the
# store — including all 1464 fully open ones. The English keys are kept below
# because this module's own docstrings promise them and an older loader may
# still write them; they are not what production speaks.
#
# `eligible` is deliberately TRI-STATE. TERBATAS means "open to foreign
# ownership up to a CAP": answering False there is the L2.11 defect (denying a
# lawful 49% stake), answering True hides the cap. This store carries no cap at
# all — `pma_max_asing` / `pma_official_basis` / `pma_cap_verified` are absent
# from all 13,633 kbli nodes (verified 2026-08-03) — so the cap has to come
# from the canonical dataset via `backend/services/kbli_eye.py`. Undetermined
# is the honest answer here, and it is also the fallback for any status this
# table does not name: an unrecognised status NEVER yields a silent False.
# The verdict is carried by a STRING state, and the tri-state bool is derived
# from it in exactly one place. Two renderings of one fact, one writer.
#
# The bool exists because `eligible` is the field this node has always emitted
# — but a bool cannot express "undetermined" safely: a consumer writing the
# natural `if not detail["eligible"]` treats None exactly like False, which is
# the L2.11 defect back again (denying a lawful capped stake) arriving through
# a downstream truthiness test instead of through this table. Consumers should
# branch on `eligibility_state`; the bool is for `is True` / `is False` /
# `is None` only. This hazard was named by the adversarial review of this diff.
PMA_STATE_OPEN = "open"
PMA_STATE_CLOSED = "closed"
PMA_STATE_UNDETERMINED = "undetermined"

_ELIGIBLE_BY_STATE: dict[str, bool | None] = {
    PMA_STATE_OPEN: True,
    PMA_STATE_CLOSED: False,
    PMA_STATE_UNDETERMINED: None,
}

_PMA_ELIGIBILITY: dict[str, tuple[str, str]] = {
    "TERBUKA": (PMA_STATE_OPEN, "pma_status=TERBUKA — open to foreign ownership"),
    "TERTUTUP": (PMA_STATE_CLOSED, "pma_status=TERTUTUP — closed to foreign ownership"),
    "TERBATAS": (
        PMA_STATE_UNDETERMINED,
        "pma_status=TERBATAS — open to foreign ownership up to a cap; the KG "
        "carries no cap field, read it from the canonical dataset "
        "(backend/services/kbli_eye.py) before answering a client",
    ),
    "VERIFY AT OSS": (
        PMA_STATE_UNDETERMINED,
        "pma_status='Verify at OSS' — undetermined, check OSS",
    ),
    # Legacy English tokens named by this module's docstrings. Absent from the
    # live store as of the census above.
    "OPEN": (PMA_STATE_OPEN, "pma_status=open — open to foreign ownership"),
    "ALLOWED": (PMA_STATE_OPEN, "pma_status=allowed — open to foreign ownership"),
    "CLOSED": (PMA_STATE_CLOSED, "pma_status=closed — closed to foreign ownership"),
    "RESTRICTED": (
        PMA_STATE_UNDETERMINED,
        "pma_status=restricted — capped, not closed; read the cap from the "
        "canonical dataset (backend/services/kbli_eye.py)",
    ),
}


def resolve_pma_eligibility(payload: dict[str, Any]) -> tuple[str, bool | None, str]:
    """
    Map one complete KG PMA evidence tuple to ``(state, eligible, basis)``.

    ``state`` is the authoritative verdict (``open`` / ``closed`` /
    ``undetermined``); ``eligible`` is derived from it here and nowhere else.

    Anything the table above does not name — including a missing status —
    resolves to ``undetermined``. Never ``closed`` by default: "we do not
    know" and "closed to foreigners" are different answers, and this store is
    only entitled to the first one when it is silent.
    """
    disclosed = disclose_pma(payload)
    if disclosed["pma_verification_status"] != "located":
        return (
            PMA_STATE_UNDETERMINED,
            None,
            "official per-code PMA evidence tuple not located — status and cap NOT_VERIFIED",
        )

    raw_status = disclosed["pma_status"]
    key = str(raw_status or "").strip().upper()
    if not key:
        state, basis = PMA_STATE_UNDETERMINED, "no pma_status on the KG node — undetermined"
    else:
        verdict = _PMA_ELIGIBILITY.get(key)
        if verdict is None:
            state, basis = (
                PMA_STATE_UNDETERMINED,
                f"pma_status={raw_status!r} not recognised — undetermined",
            )
        else:
            state, basis = verdict
    return (state, _ELIGIBLE_BY_STATE[state], basis)


# ============================================================================
# Node 1: Identify Company Type
# ============================================================================


async def identify_company_type_node(
    state: CompanyState,
    llm,
    db_pool: asyncpg.Pool | None = None,
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
                            "✅ [Company Subgraph] KBLI %s requires PT PMA (from KG)",
                            kbli_codes,
                        )
            except Exception as e:
                logger.warning("⚠️ [Company Subgraph] KG lookup failed: %s", e)

    state["company_type"] = company_type
    state["is_foreign_investor"] = is_foreign

    logger.info("✅ [Company Subgraph] Identified type: %s, foreign: %s", company_type, is_foreign)

    return state


# ============================================================================
# Node 2: Check PMA Eligibility
# ============================================================================


async def check_pma_eligibility_node(state: CompanyState, db_pool: asyncpg.Pool) -> CompanyState:
    """
    Check if business activity is eligible for foreign investment (PMA).

    Queries KG for:
    - KBLI codes with pma_status (TERBUKA / TERTUTUP / TERBATAS / Verify at OSS)
    - DNI (Daftar Negatif Investasi) restrictions

    Every emitted detail carries a TRI-STATE ``eligible`` (True / False /
    None) plus the ``eligibility_basis`` that produced it — see
    ``resolve_pma_eligibility``. None means undetermined, never "closed".

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
        # Query KBLI nodes for PMA status.
        #
        # Keyed on entity_id ALONE, deliberately. The caller already supplies
        # exact ids (`kbli:NNNNN`) and that id IS the entity; the old
        # `entity_type = 'kbli'` filter added no protection and silently
        # dropped rows. Measured 2026-08-03: the `kbli:` id namespace holds
        # 1,568 codes across TWO types — 1,558 as `kbli` and 10 filed as
        # `kbli_code`, with zero overlap. Those 10 are 47721 / 55111 / 56101 /
        # 62011 / 62021 / 68110 / 70201 / 73110 / 74100 / 79110 — i.e. the
        # restaurant, hotel and travel-agency codes this product is asked
        # about most, every one of them invisible to the old filter.
        results = await conn.fetch(
            """
            SELECT entity_id, entity_type, name, properties
            FROM kg_nodes
            WHERE entity_id = ANY($1::text[])
            """,
            kbli_codes,
        )

        pma_info = []
        answered: set[str] = set()
        for row in results:
            props = row["properties"]
            if isinstance(props, str):  # pool without a jsonb codec
                try:
                    props = json.loads(props)
                except (TypeError, ValueError):
                    props = {}
            if not isinstance(props, dict):
                props = {}

            disclosed = disclose_pma(props)
            pma_status = disclosed["pma_status"]
            state_str, eligible, basis = resolve_pma_eligibility(props)
            answered.add(row["entity_id"])

            pma_info.append(
                {
                    "kbli_code": row["entity_id"],
                    "business_name": row["name"],
                    "pma_status": pma_status if pma_status else "unknown",
                    # Branch on this. "open" / "closed" / "undetermined".
                    "eligibility_state": state_str,
                    # Tri-state: True open · False closed · None undetermined.
                    # Compare with `is`, never with truthiness — None is not False.
                    "eligible": eligible,
                    "eligibility_basis": basis,
                    "pma_max_asing": disclosed["pma_max_asing"],
                    "pma_verification_status": disclosed["pma_verification_status"],
                    "pma_official_basis": disclosed["pma_official_basis"],
                    "pma_source_vintage": disclosed["pma_source_vintage"],
                    "source_entity_type": row["entity_type"],
                },
            )

        # A code the KG has never heard of must say so. Reporting nothing at
        # all reads downstream as "no restrictions found", which is the same
        # wrong answer as False with fewer places to catch it.
        for missing in [c for c in kbli_codes if c not in answered]:
            pma_info.append(
                {
                    "kbli_code": missing,
                    "business_name": None,
                    "pma_status": "unknown",
                    "eligibility_state": PMA_STATE_UNDETERMINED,
                    "eligible": None,
                    "eligibility_basis": "no node in the KG for this code — undetermined",
                    "source_entity_type": None,
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
            # NOT stale, and NOT the same number: >10bn is the investment PLAN
            # value under the general rule, while 2.5bn is separate company
            # capital that must be placed/paid up. Permeninvesthil/Kepala BKPM
            # 5/2025 Article 26 preserves the >10bn threshold, introduces
            # calculation exceptions, and sets placed/paid-up capital at 2.5bn.
            "min_capital": 10_000_000_000,  # exclusive investment-plan threshold
            "investment_threshold_strict": True,
            "paid_up_min": 2_500_000_000,  # modal ditempatkan/disetor
            "currency": "IDR",
            "notes": (
                "Permeninvesthil/Kepala BKPM 5/2025 Article 26(2): the general "
                "PT PMA rule is total investment greater than IDR 10bn, excluding "
                "land and buildings, per five-digit KBLI per project location. "
                "Articles 26(3)-(8) provide sector/activity, asset, location, and "
                "special-economic-zone exceptions. Separately, Article 26(10) "
                "requires placed/paid-up capital of at least IDR 2.5bn per PT, "
                "unless another regulation provides otherwise."
            ),
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
    state["paid_up_amount"] = requirements.get("paid_up_min")
    state["investment_threshold_strict"] = requirements.get("investment_threshold_strict", False)

    logger.info(
        "✅ [Company Subgraph] Capital requirements: investment plan "
        f"{requirements.get('min_capital', 'N/A')} IDR, paid-up "
        f"{requirements.get('paid_up_min', 'N/A')} IDR",
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
    paid_up = state.get("paid_up_amount")
    investment_threshold_strict = state.get("investment_threshold_strict", company_type == "pt_pma")

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

    # Step 2: Capital preparation.
    #
    # This string is read by clients: the whatsapp/web answer quotes the workflow
    # verbatim. "Prepare minimum capital: Rp 10,000,000,000" names the INVESTMENT
    # PLAN value but reads as cash to deposit, which is 2.5bn (BKPM 5/2025) — a
    # 4x overstatement on the single number a founder budgets against. Both
    # figures are in `capital_reqs` two functions up; only one was ever surfaced.
    if capital:
        comparison = "greater than" if investment_threshold_strict else "at least"
        action = f"Plan a total investment value {comparison} Rp {capital:,}"
        if paid_up:
            action += (
                f". Separately, place and pay up at least Rp {paid_up:,} as company capital "
                "(modal ditempatkan/disetor, meaning placed and paid up)"
            )
        if company_type == "pt_pma":
            action += (
                ". Different sector-specific capital rules and the Article 26 "
                "investment-basis exceptions may apply."
            )
        steps.append(
            {
                "step": 2,
                "action": action,
                "entity_id": "capital_requirement",
                "details": {
                    "investment_plan_amount": capital,
                    "investment_threshold_strict": investment_threshold_strict,
                    "paid_up_amount": paid_up,
                    "currency": "IDR",
                    # Kept unchanged as a non-breaking precaution, NOT because a
                    # reader was found: grepping the backend turns up no consumer
                    # of this key, and the renderer at orchestrator_core.py:906
                    # reads only `action` plus requirement/location/processing_time.
                    # Whatever it meant, it was always the investment plan value.
                    "amount": capital,
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
