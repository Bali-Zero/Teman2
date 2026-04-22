"""M13 Feedback Loop — closes post → measure → retrain cycle.

Responsibilities (see research/sota-social-2026-v1/10_m13_measurer_config.md):

1. collect_post_metrics   — insert into post_metrics_history
2. compute_delta_vs_baseline — compare recent engagement to 00_baseline.json
3. should_trigger_retrain — ±10% delta threshold
4. is_pillar_threshold_breach — -20% auto-toggle publisher off
5. _smooth_weight          — apply 20%/week change cap
6. log_retrain             — append to m13_retrain_log
"""

from __future__ import annotations

import enum
import json
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class M13CollectionHorizon(enum.Enum):
    T_24H = 24
    T_72H = 72
    T_168H = 168


class M13FeedbackLoop:
    """Closes the WR2 post publication feedback loop."""

    RETRAIN_DELTA_THRESHOLD = 0.10
    PILLAR_BREACH_THRESHOLD = -0.20
    WEIGHT_SMOOTHING_CAP = 0.20

    def __init__(self, db_pool: Any) -> None:
        self.db_pool = db_pool

    async def collect_post_metrics(
        self,
        post_id: UUID,
        horizon: M13CollectionHorizon,
        metrics: dict[str, float],
        source: str,
    ) -> None:
        """Insert one row per metric into post_metrics_history."""
        sql = """
            INSERT INTO post_metrics_history
                (post_id, horizon_hours, metric_name, metric_value, source)
            VALUES ($1, $2, $3, $4, $5)
        """
        async with self.db_pool.acquire() as conn:
            for name, value in metrics.items():
                await conn.execute(
                    sql, post_id, horizon.value, name, float(value), source
                )
        logger.debug(
            "collected %d metrics for post %s @ %s",
            len(metrics),
            post_id,
            horizon.name,
        )

    async def compute_delta_vs_baseline(self, channel: str, pillar: str) -> float:
        """Return (recent_avg - baseline_avg) / baseline_avg over last 7 days."""
        metric_map = {
            "audience": "saves",
            "authority": "reach",
            "lead": "click_through",
        }
        metric = metric_map.get(pillar, "likes")
        async with self.db_pool.acquire() as conn:
            recent = await conn.fetchval(
                """
                SELECT AVG(metric_value)
                  FROM post_metrics_history pmh
                  JOIN war_room_posts wrp ON wrp.id = pmh.post_id
                 WHERE wrp.platform = $1
                   AND pmh.metric_name = $2
                   AND pmh.collected_at > NOW() - INTERVAL '7 days'
                """,
                channel,
                metric,
            )
            baseline = await conn.fetchval(
                """
                SELECT AVG(metric_value)
                  FROM post_metrics_history pmh
                  JOIN war_room_posts wrp ON wrp.id = pmh.post_id
                 WHERE wrp.platform = $1
                   AND pmh.metric_name = $2
                   AND pmh.collected_at BETWEEN NOW() - INTERVAL '30 days'
                                             AND NOW() - INTERVAL '7 days'
                """,
                channel,
                metric,
            )
        if not baseline or baseline == 0:
            return 0.0
        return (float(recent or 0) - float(baseline)) / float(baseline)

    def should_trigger_retrain(self, *, delta: float) -> bool:
        return abs(delta) >= self.RETRAIN_DELTA_THRESHOLD

    def is_pillar_threshold_breach(self, *, delta: float) -> bool:
        return delta <= self.PILLAR_BREACH_THRESHOLD

    def _smooth_weight(
        self, *, old: float, desired: float, cap: float | None = None
    ) -> float:
        if cap is None:
            cap = self.WEIGHT_SMOOTHING_CAP
        return old + (desired - old) * cap

    async def log_retrain(
        self,
        *,
        trigger_type: str,
        delta_pct: float,
        weights_before: dict,
        weights_after: dict,
        reason: str,
    ) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO m13_retrain_log
                    (trigger_type, delta_pct, weights_before_json, weights_after_json, reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                trigger_type,
                delta_pct,
                json.dumps(weights_before),
                json.dumps(weights_after),
                reason,
            )
