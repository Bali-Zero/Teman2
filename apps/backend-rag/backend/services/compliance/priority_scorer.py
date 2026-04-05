"""
Priority Scorer — Composite score for compliance forecasts.

score = urgency_weight × value_weight × complexity

urgency_weight: how many days until the recommended_action_by date
value_weight:   normalized revenue value (0-1 scale, max 55M IDR = KITAP)
complexity:     from RenewalRule.complexity (1.0 = simple, 3.0 = KITAP upgrade)

Score range: approximately 0-30 (higher = more urgent to act on).
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Urgency levels ─────────────────────────────────────────────────────────────

URGENCY_LEVELS: tuple[tuple[int, str, float], ...] = (
    # (max_days_until_action, level_name, weight)
    (0, "overdue", 10.0),
    (7, "critical", 8.0),
    (30, "urgent", 5.0),
    (60, "warning", 3.0),
    (90, "planning", 2.0),
    (365, "informational", 1.0),
)

# Maximum revenue used to normalise value_weight (Investor KITAP = 55M IDR)
_MAX_REVENUE_IDR: int = 55_000_000


@dataclass(frozen=True)
class PriorityResult:
    score: float
    urgency_level: str
    urgency_weight: float
    value_weight: float
    complexity: float


def calculate_priority(
    days_until_action: int,
    estimated_revenue_idr: int | None,
    complexity: float,
) -> PriorityResult:
    """
    Calculate composite priority score for a compliance forecast.

    Args:
        days_until_action:    Days from today until recommended_action_by.
                              Negative = already overdue.
        estimated_revenue_idr: Revenue estimate in IDR, or None.
        complexity:           Rule complexity factor (1.0-3.0).

    Returns:
        PriorityResult with score and breakdown.
    """
    # Urgency weight
    urgency_level = "informational"
    urgency_weight = 1.0
    for max_days, level, weight in URGENCY_LEVELS:
        if days_until_action <= max_days:
            urgency_level = level
            urgency_weight = weight
            break

    # Value weight: normalize revenue to 0.5-1.5 range
    # No revenue → 0.5 (still worth tracking, just no direct BZ revenue)
    # Max revenue → 1.5
    if estimated_revenue_idr is None or estimated_revenue_idr <= 0:
        value_weight = 0.5
    else:
        normalized = min(estimated_revenue_idr / _MAX_REVENUE_IDR, 1.0)
        value_weight = 0.5 + normalized  # range: [0.5, 1.5]

    score = round(urgency_weight * value_weight * complexity, 2)

    return PriorityResult(
        score=score,
        urgency_level=urgency_level,
        urgency_weight=urgency_weight,
        value_weight=round(value_weight, 3),
        complexity=complexity,
    )


def sort_forecasts(forecasts: list, *, key: str = "priority_score") -> list:
    """Sort forecast dicts or dataclasses descending by priority_score."""
    return sorted(
        forecasts,
        key=lambda f: getattr(f, key) if hasattr(f, key) else f.get(key, 0),
        reverse=True,
    )
