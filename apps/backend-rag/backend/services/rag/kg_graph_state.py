"""
Knowledge Graph LangGraph State Definitions

Defines TypedDict states for the LangGraph-powered Knowledge Graph workflow.
Enables multi-hop reasoning, graph traversal, and stateful knowledge exploration.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class KGAgentState(TypedDict):
    """
    State for Knowledge Graph exploration workflow.

    Used by LangGraph to track multi-hop reasoning, graph traversal,
    and workflow synthesis across node transitions.

    Attributes:
        query: Original user query (e.g., "Aprire ristorante e assumere chef straniero")
        user_context: User metadata (citizenship, intent, session history)

        # Graph Exploration State
        current_entities: Entity IDs being explored in current traversal step
        visited_entities: Set of entity IDs already visited (prevents cycles)
        relationship_chains: List of multi-hop paths found during traversal
                            Format: [[{source, target, rel_type, metadata}, ...], ...]

        # Reasoning State
        reasoning_steps: LLM reasoning log (chain-of-thought)
        confidence_scores: Per-entity confidence (key: entity_id, value: 0.0-1.0)
        intent: Extracted intent from query (company_setup|visa|hire|property|tax)
        extracted_entities: Entities extracted from query text (before KG resolution)

        # Result State
        workflow: Final workflow dict (if deterministic path found)
        answer_evidence: Supporting graph facts for LLM answer
        golden_route_match: Golden route ID if exact match found (e.g., "pt_pma_setup")

        # LangGraph Control
        messages: Conversation messages (for LLM context)
        next_step: Router decision (which node to execute next)
    """

    # Input
    query: str
    user_context: dict  # {citizenship: str, intent: str, session_history: list}

    # Graph Exploration State
    current_entities: list[str]  # Entity IDs (e.g., ["kbli:56101", "visa:e28a"])
    visited_entities: set[str]  # Prevents infinite loops in graph traversal
    relationship_chains: list[list[dict]]  # Multi-hop paths: [[{source, target, rel_type}, ...]]

    # Reasoning State
    reasoning_steps: list[str]  # LLM chain-of-thought log
    confidence_scores: dict[str, float]  # {entity_id: confidence}
    intent: str | None  # company_setup, visa, hire, property, tax, etc.
    extracted_entities: list[str]  # Raw entities from query (before KG match)
    domain: str | None  # visa, tax, property, kbli, company, general (for routing)

    # Result State
    workflow: dict | None  # Final workflow if found
    answer_evidence: list[dict]  # Supporting facts: [{entity_id, name, relationship, context}]
    golden_route_match: str | None  # Golden route ID if exact match

    # LangGraph Control
    messages: Annotated[list[BaseMessage], add_messages]  # Conversation history
    next_step: str  # Router decision: resolve_entities|traverse_graph|reason|use_golden_route|END


class CompanySetupState(TypedDict):
    """
    Subgraph state for Company Setup domain.

    Handles PT PMA, PT Perorangan, CV workflows.
    Shared state keys with parent KGAgentState for handoff.
    """

    # Shared with parent
    query: str
    user_context: dict
    messages: Annotated[list[BaseMessage], add_messages]

    # Domain-specific
    company_type: str | None  # pt_pma, pt_perorangan, cv, firma
    capital_amount_idr: int | None  # Modal dasar (for PT PMA validation)
    shareholder_count: int | None  # Number of shareholders
    business_activities: list[str]  # KBLI codes
    timeline: dict | None  # {estimated_duration_days: int, critical_path: [steps]}

    # Result
    company_workflow: dict | None  # Workflow specific to company setup


class VisaState(TypedDict):
    """
    Subgraph state for Visa/Immigration domain.

    Handles KITAS, KITAP, VITAS, work permits.
    """

    # Shared with parent
    query: str
    user_context: dict
    messages: Annotated[list[BaseMessage], add_messages]

    # Domain-specific
    visa_type: str | None  # kitas, kitap, vitas, social_visa
    stay_duration_months: int | None  # Intended stay duration
    employment_type: str | None  # director, employee, investor, digital_nomad
    sponsor_entity_type: str | None  # pt_pma, pt_perorangan, individual
    requires_work_permit: bool  # True if RPTKA needed

    # Result
    visa_workflow: dict | None  # Workflow specific to visa processing


class PropertyState(TypedDict):
    """
    Subgraph state for Property/Real Estate domain.

    Handles Hak Pakai, HGB, villa rental, property purchase.
    """

    # Shared with parent
    query: str
    user_context: dict
    messages: Annotated[list[BaseMessage], add_messages]

    # Domain-specific
    property_type: str | None  # villa, apartment, land, commercial
    ownership_type: str | None  # hak_pakai, hgb, rental
    location: str | None  # Bali province/regency
    budget_idr: int | None  # Purchase/rental budget
    foreigner_eligible: bool  # True if foreigner can own (Hak Pakai)

    # Result
    property_workflow: dict | None  # Workflow specific to property acquisition


class TaxState(TypedDict):
    """
    Subgraph state for Tax Compliance domain.

    Handles PPh, PPN, tax obligations, tax reporting.
    """

    # Shared with parent
    query: str
    user_context: dict
    messages: Annotated[list[BaseMessage], add_messages]

    # Domain-specific
    entity_type: str | None  # pt_pma, pt_perorangan, individual, freelancer
    income_type: str | None  # salary, business_income, investment, rental
    tax_year: int | None  # Tax year for compliance
    has_npwp: bool  # True if NPWP already obtained

    # Result
    tax_workflow: dict | None  # Workflow specific to tax compliance


# Utility type for workflow output
class WorkflowOutput(TypedDict):
    """
    Standardized workflow output format.

    Returned by all subgraphs and main graph.
    """

    workflow_id: str  # Unique workflow ID (e.g., "pt_pma_setup", "dynamic:company_visa_20260209")
    workflow_type: str  # company_setup, visa, property, tax, multi_domain
    steps: list[dict]  # [{step_id, title, description, documents_required, estimated_duration}]
    total_estimated_duration_days: int | None
    total_estimated_cost_idr: tuple[int, int] | None  # (min, max)
    confidence: float  # 0.0-1.0 (how confident we are in this workflow)
    source: str  # golden_route, graph_traversal, hybrid
    evidence: list[dict]  # Supporting KG facts used to build workflow
