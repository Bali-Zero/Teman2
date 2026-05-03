"""TrendAnalyzer — EMA, classification, and weekly delta for metabolic metrics.

# Organo: cell-core (L0) metabolic module
# Produce: trend classification (improving/stable/degrading)
# Consuma: MetabolicStore (historical snapshots)
"""
from __future__ import annotations

import logging

from cell_core.metabolic.definitions import (
    DIRECTION_LOWER_BETTER,
    EMA_ALPHA,
    METRIC_DIRECTIONS,
    MIN_SNAPSHOTS_FOR_TREND,
    TREND_THRESHOLD_PCT,
)
from cell_core.metabolic.storage import MetabolicStore

logger = logging.getLogger("cell_core.metabolic.trend")

TREND_IMPROVING = "improving"
TREND_STABLE = "stable"
TREND_DEGRADING = "degrading"
TREND_INSUFFICIENT = "insufficient_data"


class TrendAnalyzer:
    """Computes trends from historical snapshots in MetabolicStore."""

    def __init__(
        self,
        store: MetabolicStore,
        ema_alpha: float = EMA_ALPHA,
        threshold_pct: float = TREND_THRESHOLD_PCT,
        min_snapshots: int = MIN_SNAPSHOTS_FOR_TREND,
    ) -> None:
        self._store = store
        self._alpha = ema_alpha
        self._threshold = threshold_pct
        self._min_snapshots = min_snapshots

    def ema(self, metric_type: str, window: int = 30) -> float | None:
        """Compute EMA over the last `window` snapshots for a metric.

        Returns None if fewer than 2 non-null values exist.
        Series is processed oldest-first so the EMA reflects the most recent data.
        """
        series = self._store.metric_series(metric_type, n=window)
        # series is newest-first; reverse for EMA computation
        values = [v for _, v in reversed(series) if v is not None]
        if len(values) < 2:
            return None
        ema_val = values[0]
        for v in values[1:]:
            ema_val = self._alpha * v + (1.0 - self._alpha) * ema_val
        return ema_val

    def classify(self, metric_type: str, window: int = 30) -> str:
        """Classify trend as improving/stable/degrading/insufficient_data.

        Compares current EMA against the EMA computed excluding the most recent
        `min_snapshots` entries (approximation of "7 days ago").
        """
        series = self._store.metric_series(metric_type, n=window)
        values = [v for _, v in reversed(series) if v is not None]

        if len(values) < self._min_snapshots:
            return TREND_INSUFFICIENT

        # Current EMA (all values)
        current = self._compute_ema(values)

        # Past EMA (exclude the most recent min_snapshots entries)
        past_values = values[:-self._min_snapshots]
        if len(past_values) < 2:
            return TREND_INSUFFICIENT
        past = self._compute_ema(past_values)

        if past == 0:
            return TREND_STABLE

        pct_change = ((current - past) / abs(past)) * 100.0
        direction = METRIC_DIRECTIONS.get(metric_type, DIRECTION_LOWER_BETTER)

        if direction == DIRECTION_LOWER_BETTER:
            # Decreasing is good
            if pct_change < -self._threshold:
                return TREND_IMPROVING
            elif pct_change > self._threshold:
                return TREND_DEGRADING
        else:
            # Increasing is good
            if pct_change > self._threshold:
                return TREND_IMPROVING
            elif pct_change < -self._threshold:
                return TREND_DEGRADING

        return TREND_STABLE

    def weekly_delta(self, metric_type: str) -> float | None:
        """Compute this-week mean vs last-week mean delta.

        Returns the percentage change, or None if insufficient data.
        Positive = metric went up; interpretation depends on direction.
        """
        series = self._store.metric_series(metric_type, n=14)
        values = [v for _, v in reversed(series) if v is not None]

        if len(values) < 2:
            return None

        # Split: last 7 = this week, earlier = last week
        mid = min(7, len(values) // 2)
        this_week = values[-mid:]
        last_week = values[:-mid]

        if not last_week or not this_week:
            return None

        mean_this = sum(this_week) / len(this_week)
        mean_last = sum(last_week) / len(last_week)

        if mean_last == 0:
            return None

        return ((mean_this - mean_last) / abs(mean_last)) * 100.0

    def classify_all(self, window: int = 30) -> dict[str, str]:
        """Classify all 4 metrics at once. Returns {metric_type: trend_str}."""
        from cell_core.metabolic.definitions import ALL_METRICS
        return {m: self.classify(m, window) for m in ALL_METRICS}

    def _compute_ema(self, values: list[float]) -> float:
        """Compute EMA over a list of values (oldest first)."""
        ema_val = values[0]
        for v in values[1:]:
            ema_val = self._alpha * v + (1.0 - self._alpha) * ema_val
        return ema_val
