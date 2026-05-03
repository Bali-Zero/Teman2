"""
Migration 114: Cognitive layer tables (Sprint 15+).

Sprint 15 adds cross_dossier_theses (Connector L1 output).
Sprint 16 adds wr_anomaly_alerts (Anomaly L2 output).

Note (2026-04-20): originally named ``compliance_alerts``, renamed to
``wr_anomaly_alerts`` to avoid collision with the existing client-centric
``compliance_alerts`` table from db/migrations_v2/114_compliance_alerts.sql
(KITAS/LKPM deadline alerts — different domain, different schema). See
docs/war-room-v2/ACTIVATION_PLAN.md §3 for the full incident.
Sprint 17 adds weekly_strategic_briefs (Strategos L3 output).
Sprint 18 adds ultra_moves (Oracle L4 output).

We create all 4 tables here so later sprints only wire logic — no migration
pollution. Index set is minimal; dashboards can add more as they evolve.

Reference: docs/war-room-2.0-design.md §17, §21.

Trigger: notify_cognitive_event() emits pg_notify('cognitive_event', json)
for each INSERT/UPDATE on any of the four tables. Consumers: dashboard SSE,
Oracle (reads prior Strategos + Connector), Learner (skills/scars on
high-performing theses).

Author: Claude Opus 4.7
Date: 2026-04-18
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    # ── 1. cross_dossier_theses (Connector L1, design §17.1) ────────
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS cross_dossier_theses (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title                 TEXT NOT NULL,
            narrative             TEXT NOT NULL,
            source_dossier_ids    JSONB NOT NULL DEFAULT '[]'::jsonb,
            confidence            NUMERIC(4, 3) NOT NULL,
            implication           TEXT,
            target_clients_query  TEXT,
            generated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            valid_until           TIMESTAMP WITH TIME ZONE,
            status                TEXT NOT NULL DEFAULT 'active',
            CONSTRAINT cross_dossier_theses_confidence_range
                CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT cross_dossier_theses_status_check
                CHECK (status IN ('active', 'superseded', 'archived'))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cross_dossier_theses_generated
        ON cross_dossier_theses (generated_at DESC)
        WHERE status = 'active';
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cross_dossier_theses_sources_gin
        ON cross_dossier_theses USING GIN (source_dossier_ids);
    """)

    # ── 2. wr_anomaly_alerts (Anomaly L2, design §17.2) ─────────────
    # NOTE: was "compliance_alerts" in early draft; renamed to avoid
    # collision with db/migrations_v2/114_compliance_alerts.sql (different
    # domain: KITAS/LKPM client alerts).
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS wr_anomaly_alerts (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            detected_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            dossier_a_id           UUID NOT NULL,
            dossier_b_id           UUID NOT NULL,
            contradiction_type     TEXT NOT NULL,
            severity               TEXT NOT NULL DEFAULT 'medium',
            suggested_action       TEXT,
            affected_client_query  TEXT,
            notified_zero          BOOLEAN NOT NULL DEFAULT FALSE,
            resolved               BOOLEAN NOT NULL DEFAULT FALSE,
            resolved_at            TIMESTAMP WITH TIME ZONE,
            CONSTRAINT wr_anomaly_alerts_severity_check
                CHECK (severity IN ('low', 'medium', 'high', 'critical')),
            CONSTRAINT wr_anomaly_alerts_distinct_sources
                CHECK (dossier_a_id <> dossier_b_id)
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_wr_anomaly_alerts_unresolved
        ON wr_anomaly_alerts (detected_at DESC)
        WHERE resolved = FALSE;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_wr_anomaly_alerts_severity
        ON wr_anomaly_alerts (severity, detected_at DESC)
        WHERE resolved = FALSE;
    """)

    # ── 3. weekly_strategic_briefs (Strategos L3, design §17.3) ─────
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS weekly_strategic_briefs (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            week_of             DATE NOT NULL,
            top_themes          JSONB NOT NULL DEFAULT '[]'::jsonb,
            proposed_actions    JSONB NOT NULL DEFAULT '[]'::jsonb,
            kpi_targets         JSONB,
            team_assignments    JSONB,
            narrative           TEXT,
            generated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            zero_approval       BOOLEAN,
            approved_at         TIMESTAMP WITH TIME ZONE,
            UNIQUE (week_of)
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_weekly_strategic_briefs_generated
        ON weekly_strategic_briefs (generated_at DESC);
    """)

    # ── 4. ultra_moves (Oracle L4, design §17.4) ───────────────────
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ultra_moves (
            id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            proposed_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            thesis                    TEXT NOT NULL,
            narrative                 TEXT NOT NULL,
            target_query              TEXT,
            estimated_cost            TEXT,
            estimated_value           TEXT,
            recommended_tone_register TEXT,
            source_inputs             JSONB NOT NULL DEFAULT '{}'::jsonb,
            zero_decision             TEXT NOT NULL DEFAULT 'pending',
            decided_at                TIMESTAMP WITH TIME ZONE,
            notes                     TEXT,
            CONSTRAINT ultra_moves_decision_check
                CHECK (zero_decision IN ('pending', 'approved', 'rejected', 'deferred'))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ultra_moves_pending
        ON ultra_moves (proposed_at DESC)
        WHERE zero_decision = 'pending';
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ultra_moves_decision
        ON ultra_moves (zero_decision, proposed_at DESC);
    """)

    # ── Notify trigger ─────────────────────────────────────────────
    await conn.execute("""
        CREATE OR REPLACE FUNCTION notify_cognitive_event()
        RETURNS TRIGGER AS $$
        DECLARE
            payload JSONB;
            event_type TEXT;
        BEGIN
            IF TG_TABLE_NAME = 'cross_dossier_theses' THEN
                event_type := 'thesis_' || TG_OP;
                payload := jsonb_build_object(
                    'thesis_id', NEW.id,
                    'table', 'cross_dossier_theses',
                    'event_type', event_type,
                    'occurred_at', NOW()
                );
            ELSIF TG_TABLE_NAME = 'wr_anomaly_alerts' THEN
                event_type := 'alert_' || TG_OP;
                payload := jsonb_build_object(
                    'alert_id', NEW.id,
                    'severity', NEW.severity,
                    'table', 'wr_anomaly_alerts',
                    'event_type', event_type,
                    'occurred_at', NOW()
                );
            ELSIF TG_TABLE_NAME = 'weekly_strategic_briefs' THEN
                event_type := 'brief_' || TG_OP;
                payload := jsonb_build_object(
                    'brief_id', NEW.id,
                    'week_of', NEW.week_of,
                    'table', 'weekly_strategic_briefs',
                    'event_type', event_type,
                    'occurred_at', NOW()
                );
            ELSIF TG_TABLE_NAME = 'ultra_moves' THEN
                event_type := 'ultra_move_' || TG_OP;
                payload := jsonb_build_object(
                    'move_id', NEW.id,
                    'zero_decision', NEW.zero_decision,
                    'table', 'ultra_moves',
                    'event_type', event_type,
                    'occurred_at', NOW()
                );
            ELSE
                RETURN NEW;
            END IF;

            PERFORM pg_notify('cognitive_event', payload::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for table in (
        "cross_dossier_theses",
        "wr_anomaly_alerts",
        "weekly_strategic_briefs",
        "ultra_moves",
    ):
        await conn.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_notify ON {table};"
        )
        await conn.execute(
            f"""
            CREATE TRIGGER trg_{table}_notify
            AFTER INSERT OR UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION notify_cognitive_event();
            """
        )

    logger.info("migration 114: cognitive layer (4 tables + trigger) created")


async def rollback(conn: Any) -> None:
    for table in (
        "ultra_moves",
        "weekly_strategic_briefs",
        "wr_anomaly_alerts",
        "cross_dossier_theses",
    ):
        await conn.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_notify ON {table};"
        )
    await conn.execute("DROP FUNCTION IF EXISTS notify_cognitive_event();")
    await conn.execute("DROP TABLE IF EXISTS ultra_moves;")
    await conn.execute("DROP TABLE IF EXISTS weekly_strategic_briefs;")
    await conn.execute("DROP TABLE IF EXISTS wr_anomaly_alerts;")
    await conn.execute("DROP TABLE IF EXISTS cross_dossier_theses;")
    logger.info("migration 114: rolled back")
