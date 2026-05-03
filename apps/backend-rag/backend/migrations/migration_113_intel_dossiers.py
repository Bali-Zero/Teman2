"""
Migration 113: Intel Scraper dossier schema — trend_signals + research_dossiers.

Part of War Room 2.0 Parte II (Intel riposizionato + sistema cognitivo).
Reference: docs/war-room-2.0-design.md §15.4, §21.

Tables:
- trend_signals: raw normalized signals from Intel sources (xAI, RSS, Reddit,
  Google Trends). TTL 48-72h. Feeds dossier pre-compute batch + War Room Intake.
- research_dossiers: structured dossiers per topic (facts, numbers, citations,
  entities_linked, precedents). 30d TTL. Consumed by 10 consumers
  (chatbot, CRM, NLM, Curiosity, Consiglio, War Room, Newsletter,
  Guardian, Team search, Intel pubblica).
- dossier_reuses: tracks which consumer types read each dossier —
  computes dossier_reuse_ratio metric (target >= 5 after 60d).
- dossier_refresh_log: audit of dossier regenerations.

Trigger: notify_intel_event() fires pg_notify('intel_event', json) on
research_dossiers INSERT/UPDATE and trend_signals INSERT.

Author: Claude Opus 4.7
Date: 2026-04-18
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS trend_signals (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source                TEXT NOT NULL,
            source_url            TEXT,
            topic                 TEXT NOT NULL,
            raw_title             TEXT,
            raw_snippet           TEXT,
            language              TEXT,
            urgency_score         NUMERIC(5, 2) NOT NULL,
            bali_zero_relevance   NUMERIC(5, 2),
            decay_half_life_hours INTEGER NOT NULL DEFAULT 48,
            entities_linked       JSONB,
            detected_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            expires_at            TIMESTAMP WITH TIME ZONE,
            consumed_by_dossier   UUID,
            CONSTRAINT trend_signals_source_check CHECK (source IN (
                'xai', 'gtrends', 'reddit', 'rss', 'scraper', 'manual'
            )),
            CONSTRAINT trend_signals_urgency_range CHECK (urgency_score BETWEEN 0 AND 100),
            CONSTRAINT trend_signals_relevance_range CHECK (
                bali_zero_relevance IS NULL OR bali_zero_relevance BETWEEN 0 AND 100
            )
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trend_signals_detected
        ON trend_signals (detected_at DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trend_signals_score
        ON trend_signals ((urgency_score * COALESCE(bali_zero_relevance, 50) / 100.0) DESC)
        WHERE consumed_by_dossier IS NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trend_signals_source
        ON trend_signals (source, detected_at DESC);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS research_dossiers (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug                TEXT UNIQUE NOT NULL,
            title               TEXT NOT NULL,
            topic_category      TEXT NOT NULL,
            domains             JSONB NOT NULL DEFAULT '[]'::jsonb,
            public_safe         BOOLEAN NOT NULL DEFAULT FALSE,

            facts               JSONB NOT NULL DEFAULT '[]'::jsonb,
            numbers             JSONB NOT NULL DEFAULT '[]'::jsonb,
            citations           JSONB NOT NULL DEFAULT '[]'::jsonb,
            entities_linked     JSONB NOT NULL DEFAULT '[]'::jsonb,
            precedents          JSONB NOT NULL DEFAULT '[]'::jsonb,

            confidence_0_1      NUMERIC(4, 3) NOT NULL DEFAULT 0.500,
            freshness_expiry    TIMESTAMP WITH TIME ZONE NOT NULL,

            source_signals      JSONB,
            language            TEXT NOT NULL DEFAULT 'id',
            summary_short       TEXT,
            summary_medium      TEXT,

            created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            archived_at         TIMESTAMP WITH TIME ZONE,

            CONSTRAINT research_dossiers_category_check CHECK (topic_category IN (
                'visa', 'tax', 'kbli', 'property', 'compliance',
                'cultural', 'macro', 'finance', 'crypto', 'other'
            )),
            CONSTRAINT research_dossiers_confidence_range CHECK (
                confidence_0_1 BETWEEN 0 AND 1
            )
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_research_dossiers_category
        ON research_dossiers (topic_category, freshness_expiry DESC)
        WHERE archived_at IS NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_research_dossiers_freshness
        ON research_dossiers (freshness_expiry)
        WHERE archived_at IS NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_research_dossiers_confidence
        ON research_dossiers (confidence_0_1 DESC, freshness_expiry DESC)
        WHERE archived_at IS NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_research_dossiers_domains_gin
        ON research_dossiers USING GIN (domains);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_research_dossiers_entities_gin
        ON research_dossiers USING GIN (entities_linked);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS dossier_reuses (
            id                BIGSERIAL PRIMARY KEY,
            dossier_id        UUID NOT NULL REFERENCES research_dossiers(id) ON DELETE CASCADE,
            consumer_type     TEXT NOT NULL,
            consumer_entity_id TEXT,
            used_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            context_meta      JSONB,
            CONSTRAINT dossier_reuses_consumer_check CHECK (consumer_type IN (
                'chatbot', 'crm', 'nlm', 'curiosity', 'council',
                'warroom', 'newsletter', 'guardian', 'team', 'public',
                'connector', 'anomaly', 'strategos', 'oracle'
            ))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dossier_reuses_dossier
        ON dossier_reuses (dossier_id, consumer_type);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dossier_reuses_used
        ON dossier_reuses (used_at DESC);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS dossier_refresh_log (
            id             BIGSERIAL PRIMARY KEY,
            dossier_id     UUID NOT NULL REFERENCES research_dossiers(id) ON DELETE CASCADE,
            refreshed_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            reason         TEXT NOT NULL,
            diff_summary   TEXT,
            old_confidence NUMERIC(4, 3),
            new_confidence NUMERIC(4, 3),
            CONSTRAINT dossier_refresh_reason_check CHECK (reason IN (
                'expiry', 'new_source', 'manual', 'consumer_request', 'anomaly_trigger'
            ))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dossier_refresh_log_dossier
        ON dossier_refresh_log (dossier_id, refreshed_at DESC);
    """)

    await conn.execute("""
        CREATE OR REPLACE FUNCTION research_dossiers_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_research_dossiers_updated_at ON research_dossiers;
    """)
    await conn.execute("""
        CREATE TRIGGER trg_research_dossiers_updated_at
        BEFORE UPDATE ON research_dossiers
        FOR EACH ROW
        EXECUTE FUNCTION research_dossiers_updated_at();
    """)

    await conn.execute("""
        CREATE OR REPLACE FUNCTION trend_signals_expires_at()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.expires_at IS NULL THEN
                NEW.expires_at = NEW.detected_at + make_interval(hours => NEW.decay_half_life_hours);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_trend_signals_expires_at ON trend_signals;
    """)
    await conn.execute("""
        CREATE TRIGGER trg_trend_signals_expires_at
        BEFORE INSERT ON trend_signals
        FOR EACH ROW
        EXECUTE FUNCTION trend_signals_expires_at();
    """)

    await conn.execute("""
        CREATE OR REPLACE FUNCTION notify_intel_event()
        RETURNS TRIGGER AS $$
        DECLARE
            payload JSONB;
            event_type TEXT;
        BEGIN
            IF TG_TABLE_NAME = 'trend_signals' THEN
                event_type := 'trend_signal_detected';
                payload := jsonb_build_object(
                    'signal_id', NEW.id,
                    'source', NEW.source,
                    'topic', NEW.topic,
                    'urgency_score', NEW.urgency_score,
                    'event_type', event_type,
                    'occurred_at', NEW.detected_at
                );
            ELSIF TG_TABLE_NAME = 'research_dossiers' THEN
                IF TG_OP = 'INSERT' THEN
                    event_type := 'dossier_created';
                ELSE
                    event_type := 'dossier_updated';
                END IF;
                payload := jsonb_build_object(
                    'dossier_id', NEW.id,
                    'slug', NEW.slug,
                    'topic_category', NEW.topic_category,
                    'public_safe', NEW.public_safe,
                    'event_type', event_type,
                    'occurred_at', NEW.updated_at
                );
            ELSE
                RETURN NEW;
            END IF;

            PERFORM pg_notify('intel_event', payload::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_trend_signals_notify ON trend_signals;
    """)
    await conn.execute("""
        CREATE TRIGGER trg_trend_signals_notify
        AFTER INSERT ON trend_signals
        FOR EACH ROW
        EXECUTE FUNCTION notify_intel_event();
    """)

    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_research_dossiers_notify ON research_dossiers;
    """)
    await conn.execute("""
        CREATE TRIGGER trg_research_dossiers_notify
        AFTER INSERT OR UPDATE ON research_dossiers
        FOR EACH ROW
        WHEN (pg_trigger_depth() < 1)
        EXECUTE FUNCTION notify_intel_event();
    """)

    logger.info("migration 113: trend_signals + research_dossiers created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TRIGGER IF EXISTS trg_research_dossiers_notify ON research_dossiers;")
    await conn.execute("DROP TRIGGER IF EXISTS trg_trend_signals_notify ON trend_signals;")
    await conn.execute("DROP TRIGGER IF EXISTS trg_trend_signals_expires_at ON trend_signals;")
    await conn.execute("DROP TRIGGER IF EXISTS trg_research_dossiers_updated_at ON research_dossiers;")
    await conn.execute("DROP FUNCTION IF EXISTS notify_intel_event();")
    await conn.execute("DROP FUNCTION IF EXISTS trend_signals_expires_at();")
    await conn.execute("DROP FUNCTION IF EXISTS research_dossiers_updated_at();")
    await conn.execute("DROP TABLE IF EXISTS dossier_refresh_log;")
    await conn.execute("DROP TABLE IF EXISTS dossier_reuses;")
    await conn.execute("DROP TABLE IF EXISTS research_dossiers;")
    await conn.execute("DROP TABLE IF EXISTS trend_signals;")
    logger.info("migration 113: rolled back")
