"""Constants for graph node and edge names — single source of truth."""

from enum import StrEnum


class NodeName(StrEnum):
    UNDERSTAND = "understand"
    RETRIEVE = "retrieve"
    REASON = "reason"
    SYNTHESIZE = "synthesize"
    TOOLS = "tools"

    # Graders
    GRADE_RETRIEVAL = "grade_retrieval"
    GRADE_REASONING = "grade_reasoning"
    GRADE_ANSWER = "grade_answer"
    GRADE_HALLUCINATION = "grade_hallucination"
    GRADE_PRICING = "grade_pricing"

    # Subgraphs
    SUBGRAPH_COMPANY = "subgraph_company"
    SUBGRAPH_VISA = "subgraph_visa"
    SUBGRAPH_PROPERTY = "subgraph_property"
    SUBGRAPH_TAX = "subgraph_tax"

    # Terminal
    SYNTHESIZE_DIRECT = "synthesize_direct"
    SYNTHESIZE_FAIL_FAST = "synthesize_fail_fast"


class RouteDecision(StrEnum):
    """Deterministic routing decisions from the route node."""

    RETRIEVE = "retrieve"
    SUBGRAPH_COMPANY = "subgraph_company"
    SUBGRAPH_VISA = "subgraph_visa"
    SUBGRAPH_PROPERTY = "subgraph_property"
    SUBGRAPH_TAX = "subgraph_tax"
    TOOLS = "tools"
    DIRECT = "direct"  # greeting, cache hit
