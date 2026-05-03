"""
Mata Garuda — Case Status Tools.

Every agent MUST terminate with one of these two tools:
- case_resolved: task completed successfully
- case_not_resolved: task failed, with reason and takeaway

These provide the fitness signal for the Lamarckian pattern:
  resolved → reinforce GENOME (no mutation)
  not_resolved → log to feedback.md → trigger mutation review
"""
from __future__ import annotations

from mata_garuda.registry import register_tool


@register_tool(name="case_resolved")
def case_resolved(result: str, context_variables: dict | None = None) -> str:
    """Use this tool when the task IS resolved. Provide the final answer.

    Args:
        result: The solution or final answer
    """
    return f"Case resolved. The result is: {result}"


@register_tool(name="case_not_resolved")
def case_not_resolved(
    failure_reason: str,
    take_away_message: str,
    context_variables: dict | None = None,
) -> str:
    """Use this when the task could NOT be resolved after best effort.

    Args:
        failure_reason: Why the task failed
        take_away_message: What was learned from the failure (insight for GENOME mutation)
    """
    return (
        f"Case not resolved. Reason: {failure_reason}. "
        f"Insight: {take_away_message}"
    )
