"""Conditional edge functions — deterministic routing based on state.

Supports three outcomes after grading:
  "continue"  → proceed to next node (PASS or exhausted retries on FAIL)
  "retry"     → loop back to previous node (RETRY + corrections available)
  "fail_fast" → skip downstream nodes, go straight to synthesize with
                a polite "rephrase" message (FAIL + score < fail_fast_threshold)
"""

from __future__ import annotations

from nuzantara_graph.graph.constants import RouteDecision
from nuzantara_schemas.grading import GradeDecision
from nuzantara_schemas.state import GraphState, IntentType


def route_after_understand(state: GraphState) -> RouteDecision:
    """Route after understand node based on classified intent."""
    if state.intent == IntentType.GREETING:
        return RouteDecision.DIRECT

    if state.intent == IntentType.BUSINESS_SETUP:
        return RouteDecision.SUBGRAPH_COMPANY

    if state.intent == IntentType.VISA:
        return RouteDecision.SUBGRAPH_VISA

    if state.intent == IntentType.PROPERTY:
        return RouteDecision.SUBGRAPH_PROPERTY

    if state.intent == IntentType.TAX:
        return RouteDecision.SUBGRAPH_TAX

    # Default: general retrieval path
    return RouteDecision.RETRIEVE


def route_after_visa_subgraph(state: GraphState) -> str:
    """Route after SUBGRAPH_VISA.

    The visa multi-step planner produces a fully-cited answer of its own.
    When that answer is present, skip REASON/SYNTHESIZE entirely and go
    straight to the hallucination grader as a final safety check. If the
    planner failed (empty answer), fall back to the normal REASON path.

    Returns:
        "direct"  — planner produced an answer, go to grade_hallucination
        "reason"  — planner produced nothing, run the normal REASON pipeline
    """
    if state.answer and state.answer.strip():
        return "direct"
    return "reason"


def route_after_grade(state: GraphState, retry_node: str, continue_node: str) -> str:
    """Route after a grader node with fail-fast support.

    Returns:
        "retry"     — loop back: RETRY decision + corrections available
        "fail_fast" — skip ahead: FAIL decision (score critically low)
        "continue"  — proceed: PASS, or exhausted retries
    """
    last_grade = state.last_grade
    if last_grade is None:
        return "continue"

    if last_grade.decision == GradeDecision.FAIL:
        # Fail-fast: score critically low, no point retrying garbage
        return "fail_fast"

    if (
        last_grade.decision == GradeDecision.RETRY
        and state.correction_count < state.max_corrections
    ):
        return "retry"

    # PASS, or RETRY with exhausted corrections
    return "continue"
