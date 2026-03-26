"""Cost Guard reflex — 1ms latency budget.
Pure arithmetic. Blocks actions that would push daily spend past 90% of limit."""
from enum import Enum


class BudgetDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"


def check_budget(current_daily_spend: float, estimated_action_cost: float, daily_limit: float) -> BudgetDecision:
    """Check if an action is affordable."""
    threshold = daily_limit * 0.9
    if (current_daily_spend + estimated_action_cost) > threshold:
        return BudgetDecision.DENY
    return BudgetDecision.ALLOW
