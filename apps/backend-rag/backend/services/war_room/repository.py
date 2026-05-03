"""WarRoomRepository — asyncpg CRUD for war_room_* tables.

Inherits BaseRepository (backend/db/base_repository.py) for consistent
pool injection, transactions, and structured error logging.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.db.base_repository import BaseRepository
from backend.services.war_room.models import (
    ConversionStage,
    CostType,
    DraftStatus,
    MetricSource,
    MissedRunReason,
    Platform,
    RegisterTone,
    RejectedBy,
    RejectionReason,
    WarRoomDraft,
    WarRoomDraftCreate,
    WarRoomMetric,
    WarRoomMissedRun,
    WarRoomPost,
    WarRoomPostCreate,
    WarRoomRejection,
)


def _row_to_draft(row: Any) -> WarRoomDraft:
    return WarRoomDraft(
        id=row["id"],
        topic=row["topic"],
        tone_register=RegisterTone(row["register"]) if row["register"] else None,
        status=DraftStatus(row["status"]),
        brief_json=row["brief_json"],
        research_json=row["research_json"],
        council_debate_json=row["council_debate_json"],
        slides_json=row["slides_json"],
        drafts_json=row["drafts_json"],
        rejection_reason=row["rejection_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
    )


def _row_to_post(row: Any) -> WarRoomPost:
    return WarRoomPost(
        id=row["id"],
        draft_id=row["draft_id"],
        platform=Platform(row["platform"]),
        post_external_id=row["post_external_id"],
        post_url=row["post_url"],
        tone_register=RegisterTone(row["register"]) if row["register"] else None,
        published_at=row["published_at"],
        final_text=row["final_text"],
    )


class WarRoomRepository(BaseRepository):
    """CRUD for war_room_* tables (migration 112)."""

    # ── Drafts ──────────────────────────────────────────────────────────
    async def create_draft(self, draft: WarRoomDraftCreate) -> WarRoomDraft:
        row = await self.fetchrow_safe(
            """
            INSERT INTO war_room_drafts (topic, register, status, brief_json)
            VALUES ($1, $2, $3, $4)
            RETURNING *;
            """,
            draft.topic,
            draft.tone_register.value if draft.tone_register else None,
            draft.status.value,
            draft.brief_json,
        )
        assert row is not None
        return _row_to_draft(row)

    async def get_draft(self, draft_id: UUID) -> WarRoomDraft | None:
        row = await self.fetchrow_safe(
            "SELECT * FROM war_room_drafts WHERE id = $1;",
            draft_id,
        )
        return _row_to_draft(row) if row else None

    async def update_status(
        self,
        draft_id: UUID,
        status: DraftStatus,
        *,
        rejection_reason: str | None = None,
        approved_by: str | None = None,
    ) -> WarRoomDraft | None:
        row = await self.fetchrow_safe(
            """
            UPDATE war_room_drafts
               SET status = $2,
                   rejection_reason = COALESCE($3, rejection_reason),
                   approved_by = COALESCE($4, approved_by),
                   approved_at = CASE WHEN $2 = 'approved' THEN NOW() ELSE approved_at END
             WHERE id = $1
            RETURNING *;
            """,
            draft_id,
            status.value,
            rejection_reason,
            approved_by,
        )
        return _row_to_draft(row) if row else None

    async def patch_json(
        self,
        draft_id: UUID,
        *,
        research_json: dict[str, Any] | None = None,
        council_debate_json: dict[str, Any] | None = None,
        slides_json: dict[str, Any] | None = None,
        drafts_json: dict[str, Any] | None = None,
    ) -> WarRoomDraft | None:
        row = await self.fetchrow_safe(
            """
            UPDATE war_room_drafts
               SET research_json = COALESCE($2::jsonb, research_json),
                   council_debate_json = COALESCE($3::jsonb, council_debate_json),
                   slides_json = COALESCE($4::jsonb, slides_json),
                   drafts_json = COALESCE($5::jsonb, drafts_json)
             WHERE id = $1
            RETURNING *;
            """,
            draft_id,
            research_json,
            council_debate_json,
            slides_json,
            drafts_json,
        )
        return _row_to_draft(row) if row else None

    async def count_registers_last_14d(self) -> dict[str, int]:
        rows = await self.fetch_safe(
            """
            SELECT register, COUNT(*) AS n
              FROM war_room_posts
             WHERE published_at > NOW() - INTERVAL '14 days'
               AND register IS NOT NULL
             GROUP BY register;
            """,
        )
        return {row["register"]: row["n"] for row in rows}

    # ── Posts ───────────────────────────────────────────────────────────
    async def create_post(self, post: WarRoomPostCreate) -> WarRoomPost:
        row = await self.fetchrow_safe(
            """
            INSERT INTO war_room_posts
                (draft_id, platform, post_external_id, post_url, register, final_text)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *;
            """,
            post.draft_id,
            post.platform.value,
            post.post_external_id,
            post.post_url,
            post.tone_register.value if post.tone_register else None,
            post.final_text,
        )
        assert row is not None
        return _row_to_post(row)

    async def get_posts_for_draft(self, draft_id: UUID) -> list[WarRoomPost]:
        rows = await self.fetch_safe(
            "SELECT * FROM war_room_posts WHERE draft_id = $1 ORDER BY published_at;",
            draft_id,
        )
        return [_row_to_post(row) for row in rows]

    async def count_posts_published_today(
        self,
        platform: Platform,
    ) -> int:
        """Volume-governor utility (Sprint 19: blog 3-5 hard-capped at 8/day)."""
        row = await self.fetchrow_safe(
            """
            SELECT COUNT(*)::int AS n
              FROM war_room_posts
             WHERE platform = $1
               AND DATE(published_at AT TIME ZONE 'UTC')
                   = DATE(NOW() AT TIME ZONE 'UTC');
            """,
            platform.value,
        )
        return int(row["n"]) if row else 0

    # ── Metrics ─────────────────────────────────────────────────────────
    async def record_metric(
        self,
        post_id: UUID,
        metric_name: str,
        value: float,
        source: MetricSource,
    ) -> None:
        await self.execute_safe(
            """
            INSERT INTO war_room_metrics (post_id, metric_name, value, source)
            VALUES ($1, $2, $3, $4);
            """,
            post_id,
            metric_name,
            float(value),
            source.value,
        )

    async def metrics_for_post(self, post_id: UUID) -> list[WarRoomMetric]:
        rows = await self.fetch_safe(
            """
            SELECT * FROM war_room_metrics
             WHERE post_id = $1
             ORDER BY collected_at DESC;
            """,
            post_id,
        )
        return [
            WarRoomMetric(
                id=row["id"],
                post_id=row["post_id"],
                metric_name=row["metric_name"],
                value=row["value"],
                collected_at=row["collected_at"],
                source=MetricSource(row["source"]),
            )
            for row in rows
        ]

    # ── Leads ───────────────────────────────────────────────────────────
    async def attribute_lead(
        self,
        post_id: UUID,
        *,
        contact_id: UUID | None = None,
        utm_campaign: str | None = None,
        utm_medium: str | None = None,
        utm_source: str | None = None,
        conversion_stage: ConversionStage | None = None,
        revenue_idr: Decimal | None = None,
    ) -> None:
        await self.execute_safe(
            """
            INSERT INTO war_room_leads
                (post_id, contact_id, utm_campaign, utm_medium, utm_source,
                 conversion_stage, revenue_idr)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
            """,
            post_id,
            contact_id,
            utm_campaign,
            utm_medium,
            utm_source,
            conversion_stage.value if conversion_stage else None,
            revenue_idr,
        )

    # ── Rejections ──────────────────────────────────────────────────────
    async def record_rejection(
        self,
        draft_id: UUID,
        reason: RejectionReason,
        rejected_by: RejectedBy,
        *,
        reason_detail: str | None = None,
    ) -> WarRoomRejection:
        row = await self.fetchrow_safe(
            """
            INSERT INTO war_room_rejections
                (draft_id, reason, reason_detail, rejected_by)
            VALUES ($1, $2, $3, $4)
            RETURNING *;
            """,
            draft_id,
            reason.value,
            reason_detail,
            rejected_by.value,
        )
        assert row is not None
        return WarRoomRejection(
            id=row["id"],
            draft_id=row["draft_id"],
            reason=RejectionReason(row["reason"]),
            reason_detail=row["reason_detail"],
            rejected_by=RejectedBy(row["rejected_by"]),
            rejected_at=row["rejected_at"],
        )

    async def recent_rejections(self, days: int = 14) -> list[WarRoomRejection]:
        rows = await self.fetch_safe(
            """
            SELECT * FROM war_room_rejections
             WHERE rejected_at > NOW() - make_interval(days => $1)
             ORDER BY rejected_at DESC;
            """,
            days,
        )
        return [
            WarRoomRejection(
                id=row["id"],
                draft_id=row["draft_id"],
                reason=RejectionReason(row["reason"]),
                reason_detail=row["reason_detail"],
                rejected_by=RejectedBy(row["rejected_by"]),
                rejected_at=row["rejected_at"],
            )
            for row in rows
        ]

    # ── Missed runs ─────────────────────────────────────────────────────
    async def record_missed_run(
        self,
        scheduled_at: datetime,
        reason: MissedRunReason,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self.execute_safe(
            """
            INSERT INTO war_room_missed_runs
                (scheduled_at, skipped_reason, details_json)
            VALUES ($1, $2, $3);
            """,
            scheduled_at,
            reason.value,
            details,
        )

    async def pending_missed_runs(
        self, days: int = 2,
    ) -> list[WarRoomMissedRun]:
        """Unnotified missed runs within the lookback window."""
        rows = await self.fetch_safe(
            """
            SELECT id, scheduled_at, skipped_reason, details_json,
                   notified_zero, created_at
              FROM war_room_missed_runs
             WHERE created_at > NOW() - make_interval(days => $1)
               AND notified_zero = FALSE
             ORDER BY scheduled_at DESC;
            """,
            days,
        )
        return [
            WarRoomMissedRun(
                id=row["id"],
                scheduled_at=row["scheduled_at"],
                skipped_reason=MissedRunReason(row["skipped_reason"]),
                details_json=row["details_json"],
                notified_zero=row["notified_zero"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def mark_missed_runs_notified(
        self, ids: list[UUID],
    ) -> None:
        if not ids:
            return
        await self.execute_safe(
            """
            UPDATE war_room_missed_runs
               SET notified_zero = TRUE
             WHERE id = ANY($1::uuid[]);
            """,
            ids,
        )

    # ── Costs ───────────────────────────────────────────────────────────
    async def record_cost(
        self,
        draft_id: UUID | None,
        cost_type: CostType,
        cost_usd: Decimal,
        meta: dict[str, Any] | None = None,
    ) -> None:
        await self.execute_safe(
            """
            INSERT INTO war_room_costs
                (draft_id, cost_type, cost_usd, meta_json)
            VALUES ($1, $2, $3, $4);
            """,
            draft_id,
            cost_type.value,
            cost_usd,
            meta,
        )

    async def total_cost_for_draft(self, draft_id: UUID) -> Decimal:
        row = await self.fetchrow_safe(
            """
            SELECT COALESCE(SUM(cost_usd), 0) AS total
              FROM war_room_costs
             WHERE draft_id = $1;
            """,
            draft_id,
        )
        return Decimal(row["total"]) if row else Decimal("0")
