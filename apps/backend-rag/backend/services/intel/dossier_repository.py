"""IntelRepository — asyncpg CRUD for trend_signals + research_dossiers + dossier_reuses.

Reference: docs/war-room-2.0-design.md §15, §16, §21.
Migration: 113.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from backend.db.base_repository import BaseRepository
from backend.services.intel.dossier_models import (
    ConsumerType,
    DossierCitation,
    DossierEntity,
    DossierFact,
    DossierNumber,
    DossierPrecedent,
    RefreshReason,
    ResearchDossier,
    ResearchDossierCreate,
    TopicCategory,
    TrendSignal,
    TrendSignalCreate,
    TrendSource,
)


def _row_to_trend(row: asyncpg.Record) -> TrendSignal:
    entities = row["entities_linked"]
    if isinstance(entities, str):
        entities = json.loads(entities)
    return TrendSignal(
        id=row["id"],
        source=TrendSource(row["source"]),
        source_url=row["source_url"],
        topic=row["topic"],
        raw_title=row["raw_title"],
        raw_snippet=row["raw_snippet"],
        language=row["language"],
        urgency_score=float(row["urgency_score"]),
        bali_zero_relevance=(
            float(row["bali_zero_relevance"])
            if row["bali_zero_relevance"] is not None
            else None
        ),
        decay_half_life_hours=row["decay_half_life_hours"],
        entities_linked=entities,
        detected_at=row["detected_at"],
        expires_at=row["expires_at"],
        consumed_by_dossier=row["consumed_by_dossier"],
    )


def _parse_json_array(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return value


def _row_to_dossier(row: asyncpg.Record) -> ResearchDossier:
    return ResearchDossier(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        topic_category=TopicCategory(row["topic_category"]),
        domains=_parse_json_array(row["domains"]),
        public_safe=row["public_safe"],
        facts=[DossierFact(**f) for f in _parse_json_array(row["facts"])],
        numbers=[DossierNumber(**n) for n in _parse_json_array(row["numbers"])],
        citations=[DossierCitation(**c) for c in _parse_json_array(row["citations"])],
        entities_linked=[
            DossierEntity(**e) for e in _parse_json_array(row["entities_linked"])
        ],
        precedents=[
            DossierPrecedent(**p) for p in _parse_json_array(row["precedents"])
        ],
        confidence_0_1=float(row["confidence_0_1"]),
        freshness_expiry=row["freshness_expiry"],
        source_signals=_parse_json_array(row["source_signals"]) or None,
        language=row["language"],
        summary_short=row["summary_short"],
        summary_medium=row["summary_medium"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
    )


class IntelRepository(BaseRepository):
    """CRUD for trend_signals, research_dossiers, dossier_reuses."""

    # ── Trend Signals ───────────────────────────────────────────────────

    async def append_trend(self, signal: TrendSignalCreate) -> TrendSignal:
        row = await self.fetchrow_safe(
            """
            INSERT INTO trend_signals (
                source, source_url, topic, raw_title, raw_snippet,
                language, urgency_score, bali_zero_relevance,
                decay_half_life_hours, entities_linked
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *;
            """,
            signal.source.value,
            signal.source_url,
            signal.topic,
            signal.raw_title,
            signal.raw_snippet,
            signal.language,
            Decimal(str(signal.urgency_score)),
            (
                Decimal(str(signal.bali_zero_relevance))
                if signal.bali_zero_relevance is not None
                else None
            ),
            signal.decay_half_life_hours,
            json.dumps(signal.entities_linked) if signal.entities_linked else None,
        )
        assert row is not None
        return _row_to_trend(row)

    async def get_trend(self, signal_id: UUID) -> TrendSignal | None:
        row = await self.fetchrow_safe(
            "SELECT * FROM trend_signals WHERE id = $1;",
            signal_id,
        )
        return _row_to_trend(row) if row else None

    async def recent_trends(self, hours: int = 12) -> list[TrendSignal]:
        """Fetch unconsumed trends within lookback window (for War Room Intake)."""
        rows = await self.fetch_safe(
            """
            SELECT * FROM trend_signals
             WHERE detected_at > NOW() - make_interval(hours => $1)
               AND (expires_at IS NULL OR expires_at > NOW())
             ORDER BY urgency_score DESC, detected_at DESC;
            """,
            hours,
        )
        return [_row_to_trend(row) for row in rows]

    async def top_unconsumed_trends(self, limit: int = 20) -> list[TrendSignal]:
        """Top-N active trends for dossier pre-compute batch (cron 04:00)."""
        rows = await self.fetch_safe(
            """
            SELECT *,
                   (urgency_score * COALESCE(bali_zero_relevance, 50) / 100.0) AS score
              FROM trend_signals
             WHERE consumed_by_dossier IS NULL
               AND (expires_at IS NULL OR expires_at > NOW())
             ORDER BY score DESC
             LIMIT $1;
            """,
            limit,
        )
        return [_row_to_trend(row) for row in rows]

    async def mark_trend_consumed(
        self, signal_id: UUID, dossier_id: UUID,
    ) -> None:
        await self.execute_safe(
            """
            UPDATE trend_signals
               SET consumed_by_dossier = $2
             WHERE id = $1;
            """,
            signal_id,
            dossier_id,
        )

    # ── Research Dossiers ────────────────────────────────────────────────

    async def upsert_dossier(
        self, dossier: ResearchDossierCreate,
    ) -> ResearchDossier:
        """Upsert by unique slug. Inserts new or refreshes existing.

        On conflict logs a refresh entry and updates payload fields.
        """

        def _dump_models(models: list[Any]) -> str:
            return json.dumps([m.model_dump(mode="json") for m in models])

        async def _txn(conn: asyncpg.Connection) -> ResearchDossier:
            row = await conn.fetchrow(
                """
                INSERT INTO research_dossiers (
                    slug, title, topic_category, domains, public_safe,
                    facts, numbers, citations, entities_linked, precedents,
                    confidence_0_1, freshness_expiry, source_signals,
                    language, summary_short, summary_medium
                ) VALUES (
                    $1, $2, $3, $4::jsonb, $5,
                    $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb, $10::jsonb,
                    $11, $12, $13::jsonb,
                    $14, $15, $16
                )
                ON CONFLICT (slug) DO UPDATE SET
                    title = EXCLUDED.title,
                    topic_category = EXCLUDED.topic_category,
                    domains = EXCLUDED.domains,
                    public_safe = EXCLUDED.public_safe,
                    facts = EXCLUDED.facts,
                    numbers = EXCLUDED.numbers,
                    citations = EXCLUDED.citations,
                    entities_linked = EXCLUDED.entities_linked,
                    precedents = EXCLUDED.precedents,
                    confidence_0_1 = EXCLUDED.confidence_0_1,
                    freshness_expiry = EXCLUDED.freshness_expiry,
                    source_signals = EXCLUDED.source_signals,
                    language = EXCLUDED.language,
                    summary_short = EXCLUDED.summary_short,
                    summary_medium = EXCLUDED.summary_medium,
                    archived_at = NULL
                RETURNING *, (xmax <> 0) AS was_update;
                """,
                dossier.slug,
                dossier.title,
                dossier.topic_category.value,
                json.dumps(dossier.domains),
                dossier.public_safe,
                _dump_models(dossier.facts),
                _dump_models(dossier.numbers),
                _dump_models(dossier.citations),
                _dump_models(dossier.entities_linked),
                _dump_models(dossier.precedents),
                Decimal(str(dossier.confidence_0_1)),
                dossier.freshness_expiry,
                (
                    json.dumps([str(s) for s in dossier.source_signals])
                    if dossier.source_signals
                    else None
                ),
                dossier.language,
                dossier.summary_short,
                dossier.summary_medium,
            )
            assert row is not None
            if row["was_update"]:
                await conn.execute(
                    """
                    INSERT INTO dossier_refresh_log
                        (dossier_id, reason, new_confidence)
                    VALUES ($1, $2, $3);
                    """,
                    row["id"],
                    RefreshReason.NEW_SOURCE.value,
                    Decimal(str(dossier.confidence_0_1)),
                )
            return _row_to_dossier(row)

        return await self.execute_in_transaction(_txn)

    async def get_dossier(self, dossier_id: UUID) -> ResearchDossier | None:
        row = await self.fetchrow_safe(
            "SELECT * FROM research_dossiers WHERE id = $1;",
            dossier_id,
        )
        return _row_to_dossier(row) if row else None

    async def get_dossier_by_slug(self, slug: str) -> ResearchDossier | None:
        row = await self.fetchrow_safe(
            "SELECT * FROM research_dossiers WHERE slug = $1;",
            slug,
        )
        return _row_to_dossier(row) if row else None

    async def dossiers_for_category(
        self, category: TopicCategory, only_fresh: bool = True,
    ) -> list[ResearchDossier]:
        query = """
            SELECT * FROM research_dossiers
             WHERE topic_category = $1
               AND archived_at IS NULL
        """
        if only_fresh:
            query += " AND freshness_expiry > NOW()"
        query += " ORDER BY confidence_0_1 DESC, freshness_expiry DESC;"
        rows = await self.fetch_safe(query, category.value)
        return [_row_to_dossier(row) for row in rows]

    async def related_fresh_dossiers(
        self,
        reference: ResearchDossier,
        *,
        days: int = 30,
        limit: int = 10,
    ) -> list[ResearchDossier]:
        """Other active dossiers in the same category, excluding self.

        Used by Anomaly Detector (Sprint 16) to pick pairwise-comparison
        candidates for a freshly-inserted dossier.
        """
        rows = await self.fetch_safe(
            """
            SELECT * FROM research_dossiers
             WHERE topic_category = $1
               AND id <> $2
               AND archived_at IS NULL
               AND freshness_expiry > NOW()
               AND created_at > NOW() - make_interval(days => $3)
             ORDER BY confidence_0_1 DESC, created_at DESC
             LIMIT $4;
            """,
            reference.topic_category.value,
            reference.id,
            days,
            limit,
        )
        return [_row_to_dossier(row) for row in rows]

    async def expired_dossiers(self, limit: int = 50) -> list[ResearchDossier]:
        """Dossiers past freshness — candidates for refresh or archive."""
        rows = await self.fetch_safe(
            """
            SELECT * FROM research_dossiers
             WHERE archived_at IS NULL
               AND freshness_expiry < NOW()
             ORDER BY freshness_expiry ASC
             LIMIT $1;
            """,
            limit,
        )
        return [_row_to_dossier(row) for row in rows]

    async def archive_dossier(self, dossier_id: UUID) -> None:
        await self.execute_safe(
            "UPDATE research_dossiers SET archived_at = NOW() WHERE id = $1;",
            dossier_id,
        )

    # ── Dossier Reuse Tracking ──────────────────────────────────────────

    async def record_reuse(
        self,
        dossier_id: UUID,
        consumer: ConsumerType,
        consumer_entity_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        await self.execute_safe(
            """
            INSERT INTO dossier_reuses
                (dossier_id, consumer_type, consumer_entity_id, context_meta)
            VALUES ($1, $2, $3, $4);
            """,
            dossier_id,
            consumer.value,
            consumer_entity_id,
            json.dumps(context) if context else None,
        )

    async def reuse_ratio(self, days: int = 30) -> float:
        """Average reads per compiled dossier in window — target >= 5."""
        row = await self.fetchrow_safe(
            """
            WITH compiled AS (
                SELECT COUNT(*) AS n
                  FROM research_dossiers
                 WHERE created_at > NOW() - make_interval(days => $1)
            ),
            reads AS (
                SELECT COUNT(*) AS n
                  FROM dossier_reuses
                 WHERE used_at > NOW() - make_interval(days => $1)
            )
            SELECT
                CASE WHEN (SELECT n FROM compiled) = 0 THEN 0.0
                     ELSE (SELECT n::float FROM reads) / (SELECT n::float FROM compiled)
                END AS ratio;
            """,
            days,
        )
        return float(row["ratio"]) if row else 0.0

    async def consumer_coverage(self, days: int = 30) -> dict[str, int]:
        """Count reuses per consumer_type in window — for dashboard."""
        rows = await self.fetch_safe(
            """
            SELECT consumer_type, COUNT(*) AS n
              FROM dossier_reuses
             WHERE used_at > NOW() - make_interval(days => $1)
             GROUP BY consumer_type
             ORDER BY n DESC;
            """,
            days,
        )
        return {row["consumer_type"]: row["n"] for row in rows}

    async def dossier_reads(self, dossier_id: UUID) -> list[dict[str, Any]]:
        rows = await self.fetch_safe(
            """
            SELECT consumer_type, consumer_entity_id, used_at, context_meta
              FROM dossier_reuses
             WHERE dossier_id = $1
             ORDER BY used_at DESC;
            """,
            dossier_id,
        )
        return [dict(row) for row in rows]

    # ── Refresh Log ─────────────────────────────────────────────────────

    async def log_refresh(
        self,
        dossier_id: UUID,
        reason: RefreshReason,
        *,
        diff_summary: str | None = None,
        old_confidence: float | None = None,
        new_confidence: float | None = None,
    ) -> None:
        await self.execute_safe(
            """
            INSERT INTO dossier_refresh_log
                (dossier_id, reason, diff_summary, old_confidence, new_confidence)
            VALUES ($1, $2, $3, $4, $5);
            """,
            dossier_id,
            reason.value,
            diff_summary,
            Decimal(str(old_confidence)) if old_confidence is not None else None,
            Decimal(str(new_confidence)) if new_confidence is not None else None,
        )
