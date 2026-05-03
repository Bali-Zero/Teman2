"""
Precision/recall/F1 per compliance category from alert_outcomes (m115).

Conventions:
  precision = acted / (acted + dismissed)    → how often team found alerts useful
  recall    = acted / (acted + expired)      → how often a needed alert fired
  f1        = 2 * p * r / (p + r)  (0 when p+r == 0)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import asyncpg


@dataclass
class CategoryMetrics:
    category: str
    window_days: int
    sample_size: int
    acted: int
    dismissed: int
    expired: int
    precision: float
    recall: float
    f1: float
    threshold_current: int | None = None


async def compute_metrics(
    conn: asyncpg.Connection,
    *,
    window_days: int,
    category: str,
) -> CategoryMetrics:
    """Compute precision/recall/F1 for one category over the given window.

    Args:
        conn: asyncpg connection (or transaction-scoped connection in tests).
        window_days: How many days back to look for outcomes.
        category: Compliance alert category (e.g. "visa_expiry").

    Returns:
        CategoryMetrics dataclass with computed stats.
    """
    row = await conn.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE o.outcome = 'acted')     AS acted,
          COUNT(*) FILTER (WHERE o.outcome = 'dismissed') AS dismissed,
          COUNT(*) FILTER (WHERE o.outcome = 'expired')   AS expired
        FROM alert_outcomes o
        JOIN compliance_alerts a ON a.alert_id = o.alert_id
        WHERE a.category = $1
          AND o.actioned_at > NOW() - INTERVAL '1 day' * $2
        """,
        category,
        window_days,
    )
    acted: int = row["acted"] or 0
    dismissed: int = row["dismissed"] or 0
    expired: int = row["expired"] or 0

    denom_p = acted + dismissed
    precision: float = (acted / denom_p) if denom_p > 0 else 0.0
    denom_r = acted + expired
    recall: float = (acted / denom_r) if denom_r > 0 else 0.0
    f1: float = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )

    threshold_val = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = $1",
        f"compliance_alert_threshold_urgent_{category}",
    )
    threshold_current: int | None = int(threshold_val) if threshold_val is not None else None

    return CategoryMetrics(
        category=category,
        window_days=window_days,
        sample_size=acted + dismissed + expired,
        acted=acted,
        dismissed=dismissed,
        expired=expired,
        precision=precision,
        recall=recall,
        f1=f1,
        threshold_current=threshold_current,
    )


async def compute_metrics_all(
    conn: asyncpg.Connection,
    *,
    window_days: int,
) -> dict[str, CategoryMetrics]:
    """Compute metrics for all categories that have outcomes in the window.

    Args:
        conn: asyncpg connection.
        window_days: How many days back to look for outcomes.

    Returns:
        Dict mapping category name → CategoryMetrics.
    """
    categories = await conn.fetch(
        """
        SELECT DISTINCT a.category
        FROM alert_outcomes o
        JOIN compliance_alerts a ON a.alert_id = o.alert_id
        WHERE o.actioned_at > NOW() - INTERVAL '1 day' * $1
        """,
        window_days,
    )
    out: dict[str, CategoryMetrics] = {}
    for r in categories:
        cat: str = r["category"]
        out[cat] = await compute_metrics(conn, window_days=window_days, category=cat)
    return out


__all__ = ["CategoryMetrics", "compute_metrics", "compute_metrics_all"]
