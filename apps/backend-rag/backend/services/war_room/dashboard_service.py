"""Dashboard aggregate queries for /war-room/metrics (Sprint 11).

Reads-only service that hits war_room_drafts / war_room_posts /
war_room_metrics / war_room_rejections / war_room_leads / war_room_costs
to produce the 6 widgets defined in docs/war-room-2.0-design.md §7.3.

All queries return JSON-serializable dicts so the router can pass-through.
Percentages / averages computed in SQL when possible (cheaper than Python).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


# Alert threshold from design §7.3 — warn if any register claims > 40% of the
# distribution in the last 30d (indicates tonal drift).
PIE_DOMINANCE_ALERT_PCT = 40.0


@dataclass
class TimelineBucket:
    day: date
    register: str
    post_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "register": self.register,
            "post_count": self.post_count,
        }


@dataclass
class HeatmapCell:
    register: str
    metric_name: str
    avg_value: float
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "register": self.register,
            "metric_name": self.metric_name,
            "avg_value": round(self.avg_value, 3),
            "sample_count": self.sample_count,
        }


@dataclass
class PieSlice:
    register: str
    post_count: int
    pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "register": self.register,
            "post_count": self.post_count,
            "pct": round(self.pct, 2),
        }


@dataclass
class FunnelStage:
    stage: str  # drafts | approved | published | leads
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "count": self.count}


@dataclass
class RejectionBucket:
    reason: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "count": self.count}


@dataclass
class CostRow:
    draft_id: UUID
    topic: str
    total_usd: float
    by_type: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": str(self.draft_id),
            "topic": self.topic,
            "total_usd": round(self.total_usd, 4),
            "by_type": {k: round(v, 4) for k, v in self.by_type.items()},
        }


@dataclass
class DistributionResult:
    total_posts: int
    slices: list[PieSlice]
    dominant_register: str | None
    alert: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_posts": self.total_posts,
            "slices": [s.to_dict() for s in self.slices],
            "dominant_register": self.dominant_register,
            "alert": self.alert,
        }


class DashboardService:
    """Read-only aggregates for the War Room metrics dashboard."""

    def __init__(self, repo: WarRoomRepository) -> None:
        self.repo = repo
        self.logger = logger

    # ── 1. Timeline — posts per day per register ────────────────

    async def timeline(self, *, days: int = 14) -> list[TimelineBucket]:
        if days not in (14, 30, 90):
            days = 14
        rows = await self.repo.fetch_safe(
            """
            SELECT DATE(published_at AT TIME ZONE 'UTC') AS day,
                   COALESCE(register, 'unknown')           AS register,
                   COUNT(*)                                AS post_count
              FROM war_room_posts
             WHERE published_at > NOW() - make_interval(days => $1)
             GROUP BY 1, 2
             ORDER BY 1 ASC, 2 ASC;
            """,
            days,
        )
        return [
            TimelineBucket(
                day=row["day"],
                register=row["register"],
                post_count=int(row["post_count"]),
            )
            for row in rows
        ]

    # ── 2. Heatmap — register × metric_name avg ────────────────

    async def register_performance_heatmap(
        self, *, days: int = 30,
    ) -> list[HeatmapCell]:
        rows = await self.repo.fetch_safe(
            """
            SELECT COALESCE(p.register, 'unknown') AS register,
                   m.metric_name,
                   AVG(m.value)::float             AS avg_value,
                   COUNT(*)                         AS sample_count
              FROM war_room_metrics m
              JOIN war_room_posts p ON p.id = m.post_id
             WHERE m.collected_at > NOW() - make_interval(days => $1)
             GROUP BY 1, 2
             ORDER BY 1 ASC, 2 ASC;
            """,
            days,
        )
        return [
            HeatmapCell(
                register=row["register"],
                metric_name=row["metric_name"],
                avg_value=float(row["avg_value"] or 0),
                sample_count=int(row["sample_count"]),
            )
            for row in rows
        ]

    # ── 3. Distribution pie — alert if any >40% ────────────────

    async def register_distribution(
        self, *, days: int = 30,
    ) -> DistributionResult:
        rows = await self.repo.fetch_safe(
            """
            SELECT COALESCE(register, 'unknown') AS register,
                   COUNT(*)                       AS post_count
              FROM war_room_posts
             WHERE published_at > NOW() - make_interval(days => $1)
             GROUP BY 1
             ORDER BY 2 DESC;
            """,
            days,
        )
        total = sum(int(row["post_count"]) for row in rows)
        slices: list[PieSlice] = []
        dominant: str | None = None
        alert = False
        for row in rows:
            count = int(row["post_count"])
            pct = (count / total * 100) if total > 0 else 0.0
            slices.append(
                PieSlice(register=row["register"], post_count=count, pct=pct),
            )
            if dominant is None:
                dominant = row["register"]
            if pct > PIE_DOMINANCE_ALERT_PCT:
                alert = True
        return DistributionResult(
            total_posts=total,
            slices=slices,
            dominant_register=dominant,
            alert=alert,
        )

    # ── 4. Funnel: drafts → approved → published → leads ──────

    async def funnel(self, *, days: int = 30) -> list[FunnelStage]:
        drafts_row = await self.repo.fetchrow_safe(
            """
            SELECT COUNT(*) AS n
              FROM war_room_drafts
             WHERE created_at > NOW() - make_interval(days => $1);
            """,
            days,
        )
        approved_row = await self.repo.fetchrow_safe(
            """
            SELECT COUNT(*) AS n
              FROM war_room_drafts
             WHERE approved_at IS NOT NULL
               AND approved_at > NOW() - make_interval(days => $1);
            """,
            days,
        )
        published_row = await self.repo.fetchrow_safe(
            """
            SELECT COUNT(DISTINCT draft_id) AS n
              FROM war_room_posts
             WHERE published_at > NOW() - make_interval(days => $1);
            """,
            days,
        )
        leads_row = await self.repo.fetchrow_safe(
            """
            SELECT COUNT(*) AS n
              FROM war_room_leads
             WHERE attributed_at > NOW() - make_interval(days => $1);
            """,
            days,
        )
        return [
            FunnelStage("drafts", int(drafts_row["n"]) if drafts_row else 0),
            FunnelStage("approved", int(approved_row["n"]) if approved_row else 0),
            FunnelStage("published", int(published_row["n"]) if published_row else 0),
            FunnelStage("leads", int(leads_row["n"]) if leads_row else 0),
        ]

    # ── 5. Rejections by reason ────────────────────────────────

    async def rejection_reasons(
        self, *, days: int = 30,
    ) -> list[RejectionBucket]:
        rows = await self.repo.fetch_safe(
            """
            SELECT reason, COUNT(*) AS n
              FROM war_room_rejections
             WHERE rejected_at > NOW() - make_interval(days => $1)
             GROUP BY reason
             ORDER BY n DESC;
            """,
            days,
        )
        return [
            RejectionBucket(reason=row["reason"], count=int(row["n"]))
            for row in rows
        ]

    # ── 6. Cost per draft ──────────────────────────────────────

    async def cost_per_draft(
        self,
        *,
        days: int = 30,
        limit: int = 50,
    ) -> list[CostRow]:
        rows = await self.repo.fetch_safe(
            """
            WITH totals AS (
                SELECT c.draft_id,
                       SUM(c.cost_usd) AS total_usd
                  FROM war_room_costs c
                 WHERE c.occurred_at > NOW() - make_interval(days => $1)
                   AND c.draft_id IS NOT NULL
                 GROUP BY c.draft_id
                 ORDER BY total_usd DESC
                 LIMIT $2
            ),
            by_type AS (
                SELECT c.draft_id, c.cost_type, SUM(c.cost_usd) AS t
                  FROM war_room_costs c
                 WHERE c.draft_id IN (SELECT draft_id FROM totals)
                 GROUP BY 1, 2
            )
            SELECT t.draft_id,
                   d.topic,
                   t.total_usd,
                   JSONB_OBJECT_AGG(b.cost_type, b.t) FILTER (WHERE b.cost_type IS NOT NULL)
                     AS by_type
              FROM totals t
              LEFT JOIN war_room_drafts d ON d.id = t.draft_id
              LEFT JOIN by_type b         ON b.draft_id = t.draft_id
             GROUP BY t.draft_id, d.topic, t.total_usd
             ORDER BY t.total_usd DESC;
            """,
            days,
            limit,
        )
        out: list[CostRow] = []
        for row in rows:
            by_type_raw = row.get("by_type") if hasattr(row, "get") else row["by_type"]
            by_type = _normalize_by_type(by_type_raw)
            out.append(
                CostRow(
                    draft_id=row["draft_id"],
                    topic=row.get("topic") if hasattr(row, "get") else row["topic"] or "",
                    total_usd=float(row["total_usd"] or 0),
                    by_type=by_type,
                )
            )
        return out


def _normalize_by_type(value: Any) -> dict[str, float]:
    if value is None:
        return {}
    if isinstance(value, str):
        import json
        try:
            parsed = json.loads(value)
        except Exception:  # noqa: BLE001
            return {}
        value = parsed
    if not isinstance(value, dict):
        return {}
    return {
        str(k): float(v) if v is not None else 0.0
        for k, v in value.items()
    }
