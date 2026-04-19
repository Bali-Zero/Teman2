"""CognitiveRepository — CRUD for the 4 cognitive-layer tables."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.db.base_repository import BaseRepository
from backend.services.cognitive.models import (
    AlertSeverity,
    ComplianceAlert,
    ComplianceAlertCreate,
    CrossDossierThesis,
    CrossDossierThesisCreate,
    ThesisStatus,
    UltraMove,
    UltraMoveCreate,
    UltraMoveDecision,
    WeeklyStrategicBrief,
    WeeklyStrategicBriefCreate,
)

logger = logging.getLogger(__name__)


def _parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _row_to_thesis(row: Any) -> CrossDossierThesis:
    return CrossDossierThesis(
        id=row["id"],
        title=row["title"],
        narrative=row["narrative"],
        source_dossier_ids=[
            UUID(str(x)) for x in (_parse_json(row["source_dossier_ids"]) or [])
        ],
        confidence=float(row["confidence"]),
        implication=row["implication"],
        target_clients_query=row["target_clients_query"],
        generated_at=row["generated_at"],
        valid_until=row["valid_until"],
        status=ThesisStatus(row["status"]),
    )


def _row_to_alert(row: Any) -> ComplianceAlert:
    return ComplianceAlert(
        id=row["id"],
        detected_at=row["detected_at"],
        dossier_a_id=row["dossier_a_id"],
        dossier_b_id=row["dossier_b_id"],
        contradiction_type=row["contradiction_type"],
        severity=AlertSeverity(row["severity"]),
        suggested_action=row["suggested_action"],
        affected_client_query=row["affected_client_query"],
        notified_zero=row["notified_zero"],
        resolved=row["resolved"],
        resolved_at=row["resolved_at"],
    )


def _row_to_brief(row: Any) -> WeeklyStrategicBrief:
    return WeeklyStrategicBrief(
        id=row["id"],
        week_of=row["week_of"],
        top_themes=_parse_json(row["top_themes"]) or [],
        proposed_actions=_parse_json(row["proposed_actions"]) or [],
        kpi_targets=_parse_json(row["kpi_targets"]),
        team_assignments=_parse_json(row["team_assignments"]),
        narrative=row["narrative"],
        generated_at=row["generated_at"],
        zero_approval=row["zero_approval"],
        approved_at=row["approved_at"],
    )


def _row_to_move(row: Any) -> UltraMove:
    return UltraMove(
        id=row["id"],
        proposed_at=row["proposed_at"],
        thesis=row["thesis"],
        narrative=row["narrative"],
        target_query=row["target_query"],
        estimated_cost=row["estimated_cost"],
        estimated_value=row["estimated_value"],
        recommended_tone_register=row["recommended_tone_register"],
        source_inputs=_parse_json(row["source_inputs"]) or {},
        zero_decision=UltraMoveDecision(row["zero_decision"]),
        decided_at=row["decided_at"],
        notes=row["notes"],
    )


class CognitiveRepository(BaseRepository):
    """CRUD for cross_dossier_theses, wr_anomaly_alerts,
    weekly_strategic_briefs, ultra_moves (migration 114).

    Note: ``wr_anomaly_alerts`` was originally named ``compliance_alerts``
    but was renamed 2026-04-20 to avoid collision with the client-centric
    ``compliance_alerts`` table (db/migrations_v2/114) used by the KITAS
    deadline alert engine. Keep these distinct: WR2 tracks contradictions
    *between dossiers*; the other tracks *per-client* compliance deadlines.
    """

    # ── CrossDossierThesis (Sprint 15) ───────────────────────────

    async def insert_thesis(
        self, payload: CrossDossierThesisCreate,
    ) -> CrossDossierThesis:
        row = await self.fetchrow_safe(
            """
            INSERT INTO cross_dossier_theses
                (title, narrative, source_dossier_ids, confidence,
                 implication, target_clients_query, valid_until)
            VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7)
            RETURNING *;
            """,
            payload.title,
            payload.narrative,
            json.dumps([str(x) for x in payload.source_dossier_ids]),
            Decimal(str(payload.confidence)),
            payload.implication,
            payload.target_clients_query,
            payload.valid_until,
        )
        assert row is not None
        return _row_to_thesis(row)

    async def recent_theses(
        self,
        *,
        days: int = 7,
        active_only: bool = True,
    ) -> list[CrossDossierThesis]:
        query = """
            SELECT * FROM cross_dossier_theses
             WHERE generated_at > NOW() - make_interval(days => $1)
        """
        if active_only:
            query += " AND status = 'active'"
        query += " ORDER BY generated_at DESC;"
        rows = await self.fetch_safe(query, days)
        return [_row_to_thesis(row) for row in rows]

    async def thesis_exists_for_sources(
        self,
        source_ids: list[UUID],
        *,
        days: int = 7,
    ) -> bool:
        """Idempotency guard — skip emitting a thesis if the same exact
        source-set was already captured in the lookback window.
        """
        if not source_ids:
            return False
        sorted_ids = sorted(str(x) for x in source_ids)
        row = await self.fetchrow_safe(
            """
            SELECT 1
              FROM cross_dossier_theses
             WHERE generated_at > NOW() - make_interval(days => $1)
               AND (
                   SELECT array_agg(v ORDER BY v)
                     FROM jsonb_array_elements_text(source_dossier_ids) v
               ) = $2::text[]
             LIMIT 1;
            """,
            days,
            sorted_ids,
        )
        return row is not None

    async def archive_thesis(self, thesis_id: UUID) -> None:
        await self.execute_safe(
            """
            UPDATE cross_dossier_theses
               SET status = 'archived'
             WHERE id = $1;
            """,
            thesis_id,
        )

    # ── ComplianceAlert (Sprint 16 — stub for schema symmetry) ──

    async def insert_alert(
        self, payload: ComplianceAlertCreate,
    ) -> ComplianceAlert:
        row = await self.fetchrow_safe(
            """
            INSERT INTO wr_anomaly_alerts
                (dossier_a_id, dossier_b_id, contradiction_type,
                 severity, suggested_action, affected_client_query)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *;
            """,
            payload.dossier_a_id,
            payload.dossier_b_id,
            payload.contradiction_type,
            payload.severity.value,
            payload.suggested_action,
            payload.affected_client_query,
        )
        assert row is not None
        return _row_to_alert(row)

    async def mark_alert_notified(self, alert_id: UUID) -> None:
        await self.execute_safe(
            """
            UPDATE wr_anomaly_alerts
               SET notified_zero = TRUE
             WHERE id = $1;
            """,
            alert_id,
        )

    async def alert_exists_for_pair(
        self,
        dossier_a_id: UUID,
        dossier_b_id: UUID,
        *,
        days: int = 14,
    ) -> bool:
        """Idempotency guard — same ordered pair already flagged recently."""
        pair_a, pair_b = sorted([str(dossier_a_id), str(dossier_b_id)])
        row = await self.fetchrow_safe(
            """
            SELECT 1
              FROM wr_anomaly_alerts
             WHERE detected_at > NOW() - make_interval(days => $1)
               AND (
                    (dossier_a_id::text = $2 AND dossier_b_id::text = $3)
                 OR (dossier_a_id::text = $3 AND dossier_b_id::text = $2)
               )
             LIMIT 1;
            """,
            days,
            pair_a,
            pair_b,
        )
        return row is not None

    async def unresolved_alerts(
        self, *, severity: AlertSeverity | None = None,
    ) -> list[ComplianceAlert]:
        if severity is None:
            rows = await self.fetch_safe(
                """
                SELECT * FROM wr_anomaly_alerts
                 WHERE resolved = FALSE
                 ORDER BY detected_at DESC;
                """,
            )
        else:
            rows = await self.fetch_safe(
                """
                SELECT * FROM wr_anomaly_alerts
                 WHERE resolved = FALSE
                   AND severity = $1
                 ORDER BY detected_at DESC;
                """,
                severity.value,
            )
        return [_row_to_alert(row) for row in rows]

    # ── WeeklyStrategicBrief (Sprint 17 — schema only) ──────────

    async def insert_brief(
        self, payload: WeeklyStrategicBriefCreate,
    ) -> WeeklyStrategicBrief:
        row = await self.fetchrow_safe(
            """
            INSERT INTO weekly_strategic_briefs
                (week_of, top_themes, proposed_actions, kpi_targets,
                 team_assignments, narrative)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6)
            ON CONFLICT (week_of) DO UPDATE SET
                top_themes = EXCLUDED.top_themes,
                proposed_actions = EXCLUDED.proposed_actions,
                kpi_targets = EXCLUDED.kpi_targets,
                team_assignments = EXCLUDED.team_assignments,
                narrative = EXCLUDED.narrative
            RETURNING *;
            """,
            payload.week_of,
            json.dumps(payload.top_themes),
            json.dumps(payload.proposed_actions),
            json.dumps(payload.kpi_targets) if payload.kpi_targets else None,
            json.dumps(payload.team_assignments) if payload.team_assignments else None,
            payload.narrative,
        )
        assert row is not None
        return _row_to_brief(row)

    async def latest_brief(self) -> WeeklyStrategicBrief | None:
        row = await self.fetchrow_safe(
            """
            SELECT * FROM weekly_strategic_briefs
             ORDER BY generated_at DESC
             LIMIT 1;
            """,
        )
        return _row_to_brief(row) if row else None

    async def get_brief(self, brief_id: UUID) -> WeeklyStrategicBrief | None:
        row = await self.fetchrow_safe(
            "SELECT * FROM weekly_strategic_briefs WHERE id = $1;",
            brief_id,
        )
        return _row_to_brief(row) if row else None

    async def update_brief_approval(
        self,
        brief_id: UUID,
        *,
        approved: bool,
    ) -> WeeklyStrategicBrief | None:
        row = await self.fetchrow_safe(
            """
            UPDATE weekly_strategic_briefs
               SET zero_approval = $2,
                   approved_at   = NOW()
             WHERE id = $1
            RETURNING *;
            """,
            brief_id,
            approved,
        )
        return _row_to_brief(row) if row else None

    # ── UltraMove (Sprint 18 — schema only) ─────────────────────

    async def insert_ultra_move(
        self, payload: UltraMoveCreate,
    ) -> UltraMove:
        row = await self.fetchrow_safe(
            """
            INSERT INTO ultra_moves
                (thesis, narrative, target_query, estimated_cost,
                 estimated_value, recommended_tone_register, source_inputs)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING *;
            """,
            payload.thesis,
            payload.narrative,
            payload.target_query,
            payload.estimated_cost,
            payload.estimated_value,
            payload.recommended_tone_register,
            json.dumps(payload.source_inputs),
        )
        assert row is not None
        return _row_to_move(row)

    async def pending_ultra_moves(self) -> list[UltraMove]:
        rows = await self.fetch_safe(
            """
            SELECT * FROM ultra_moves
             WHERE zero_decision = 'pending'
             ORDER BY proposed_at DESC;
            """,
        )
        return [_row_to_move(row) for row in rows]

    async def update_ultra_move_decision(
        self,
        move_id: UUID,
        decision: UltraMoveDecision,
        *,
        notes: str | None = None,
    ) -> UltraMove | None:
        row = await self.fetchrow_safe(
            """
            UPDATE ultra_moves
               SET zero_decision = $2,
                   decided_at = NOW(),
                   notes = COALESCE($3, notes)
             WHERE id = $1
            RETURNING *;
            """,
            move_id,
            decision.value,
            notes,
        )
        return _row_to_move(row) if row else None
