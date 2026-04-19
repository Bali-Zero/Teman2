"""
Migration 112: War Room 2.0 foundation — drafts, posts, metrics, rejections.

Part of War Room 2.0 design (docs/war-room-2.0-design.md), Sprint 1.

Tables:
- war_room_drafts: editorial drafts with lifecycle status
- war_room_posts: published artifacts per platform
- war_room_metrics: engagement/reach/leads time-series
- war_room_leads: UTM-attributed CRM conversions
- war_room_rejections: review rejections + learner input
- war_room_missed_runs: skipped pipeline executions (Pro off, no trend, etc.)
- war_room_costs: LLM + image generation cost tracking per draft

Trigger: notify_war_room_event() fires on war_room_drafts status change and
war_room_posts INSERT, sending pg_notify('war_room_event', json) with payload
{draft_id, status, uri} <= 8 KB (never blob).

Event bus channel registered in event_bus.py PG_CHANNEL_MAP (separate commit).

Reference: /Users/nuzantara/Desktop/nuzantara/docs/war-room-2.0-design.md §7
Author: Claude Opus 4.7
Date: 2026-04-18
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_drafts (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            topic                 TEXT NOT NULL,
            register              TEXT,
            status                TEXT NOT NULL DEFAULT 'briefed',
            brief_json            JSONB,
            research_json         JSONB,
            council_debate_json   JSONB,
            slides_json           JSONB,
            drafts_json           JSONB,
            rejection_reason      TEXT,
            created_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            approved_by           TEXT,
            approved_at           TIMESTAMP WITH TIME ZONE,
            CONSTRAINT war_room_drafts_status_check CHECK (status IN (
                'briefed', 'researched', 'concept', 'drafts',
                'rendered', 'pending_review', 'approved',
                'rejected', 'published', 'missed'
            ))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_drafts_status
        ON war_room_drafts (status, created_at DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_drafts_register
        ON war_room_drafts (register, created_at DESC)
        WHERE register IS NOT NULL;
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_posts (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            draft_id          UUID NOT NULL REFERENCES war_room_drafts(id) ON DELETE CASCADE,
            platform          TEXT NOT NULL,
            post_external_id  TEXT,
            post_url          TEXT,
            register          TEXT,
            published_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            final_text        TEXT,
            CONSTRAINT war_room_posts_platform_check CHECK (platform IN (
                'instagram', 'x', 'linkedin', 'blog', 'newsletter'
            )),
            CONSTRAINT war_room_posts_draft_platform_unique UNIQUE (draft_id, platform)
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_posts_published
        ON war_room_posts (published_at DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_posts_register_platform
        ON war_room_posts (register, platform, published_at DESC)
        WHERE register IS NOT NULL;
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_metrics (
            id            BIGSERIAL PRIMARY KEY,
            post_id       UUID NOT NULL REFERENCES war_room_posts(id) ON DELETE CASCADE,
            metric_name   TEXT NOT NULL,
            value         DOUBLE PRECISION NOT NULL,
            collected_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            source        TEXT NOT NULL,
            CONSTRAINT war_room_metrics_source_check CHECK (source IN (
                'meta_graph', 'playwright_scrape', 'utm_crm', 'partial'
            ))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_metrics_post
        ON war_room_metrics (post_id, metric_name);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_metrics_collected
        ON war_room_metrics (collected_at DESC);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_leads (
            id                BIGSERIAL PRIMARY KEY,
            post_id           UUID NOT NULL REFERENCES war_room_posts(id) ON DELETE CASCADE,
            contact_id        UUID,
            utm_campaign      TEXT,
            utm_medium        TEXT,
            utm_source        TEXT,
            attributed_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            conversion_stage  TEXT,
            revenue_idr       NUMERIC(14, 2),
            CONSTRAINT war_room_leads_stage_check CHECK (
                conversion_stage IS NULL OR conversion_stage IN ('lead', 'qualified', 'client')
            )
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_leads_post
        ON war_room_leads (post_id, attributed_at DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_leads_utm
        ON war_room_leads (utm_campaign, utm_source);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_rejections (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            draft_id        UUID NOT NULL REFERENCES war_room_drafts(id) ON DELETE CASCADE,
            reason          TEXT NOT NULL,
            reason_detail   TEXT,
            rejected_by     TEXT NOT NULL,
            rejected_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT war_room_rejections_reason_check CHECK (reason IN (
                'tone', 'fact', 'visual', 'clickbait', 'sla_expired', 'other'
            )),
            CONSTRAINT war_room_rejections_rejected_by_check CHECK (rejected_by IN (
                'zero', 'validator', 'qa_visual', 'qa_layout', 'system'
            ))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_rejections_reason
        ON war_room_rejections (reason, rejected_at DESC);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_missed_runs (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scheduled_at     TIMESTAMP WITH TIME ZONE NOT NULL,
            skipped_reason   TEXT NOT NULL,
            details_json     JSONB,
            notified_zero    BOOLEAN NOT NULL DEFAULT FALSE,
            created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT war_room_missed_runs_reason_check CHECK (skipped_reason IN (
                'pro_offline', 'no_trend', 'hard_failure', 'quota_exceeded'
            ))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_missed_runs_scheduled
        ON war_room_missed_runs (scheduled_at DESC);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_costs (
            id         BIGSERIAL PRIMARY KEY,
            draft_id   UUID REFERENCES war_room_drafts(id) ON DELETE CASCADE,
            cost_type  TEXT NOT NULL,
            cost_usd   NUMERIC(10, 6) NOT NULL,
            occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            meta_json  JSONB,
            CONSTRAINT war_room_costs_type_check CHECK (cost_type IN (
                'imagen_ultra', 'imagen_fast', 'imagen_other',
                'fireworks_flux', 'deepseek_api', 'claude_cli',
                'gemini_cli', 'ollama_local', 'other'
            ))
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_costs_draft
        ON war_room_costs (draft_id, cost_type);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_room_costs_occurred
        ON war_room_costs (occurred_at DESC);
    """)

    await conn.execute("""
        CREATE OR REPLACE FUNCTION war_room_drafts_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_war_room_drafts_updated_at ON war_room_drafts;
    """)
    await conn.execute("""
        CREATE TRIGGER trg_war_room_drafts_updated_at
        BEFORE UPDATE ON war_room_drafts
        FOR EACH ROW
        EXECUTE FUNCTION war_room_drafts_updated_at();
    """)

    await conn.execute("""
        CREATE OR REPLACE FUNCTION notify_war_room_event()
        RETURNS TRIGGER AS $$
        DECLARE
            payload JSONB;
            event_type TEXT;
        BEGIN
            IF TG_TABLE_NAME = 'war_room_drafts' THEN
                IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM NEW.status THEN
                    RETURN NEW;
                END IF;
                event_type := 'draft_' || NEW.status;
                payload := jsonb_build_object(
                    'draft_id', NEW.id,
                    'status', NEW.status,
                    'event_type', event_type,
                    'occurred_at', NOW()
                );
            ELSIF TG_TABLE_NAME = 'war_room_posts' THEN
                event_type := 'post_published';
                payload := jsonb_build_object(
                    'post_id', NEW.id,
                    'draft_id', NEW.draft_id,
                    'platform', NEW.platform,
                    'event_type', event_type,
                    'occurred_at', NEW.published_at
                );
            ELSE
                RETURN NEW;
            END IF;

            PERFORM pg_notify('war_room_event', payload::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_war_room_drafts_notify ON war_room_drafts;
    """)
    await conn.execute("""
        CREATE TRIGGER trg_war_room_drafts_notify
        AFTER INSERT OR UPDATE ON war_room_drafts
        FOR EACH ROW
        EXECUTE FUNCTION notify_war_room_event();
    """)

    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_war_room_posts_notify ON war_room_posts;
    """)
    await conn.execute("""
        CREATE TRIGGER trg_war_room_posts_notify
        AFTER INSERT ON war_room_posts
        FOR EACH ROW
        EXECUTE FUNCTION notify_war_room_event();
    """)

    logger.info("migration 112: war_room_* tables + triggers created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TRIGGER IF EXISTS trg_war_room_posts_notify ON war_room_posts;")
    await conn.execute("DROP TRIGGER IF EXISTS trg_war_room_drafts_notify ON war_room_drafts;")
    await conn.execute("DROP TRIGGER IF EXISTS trg_war_room_drafts_updated_at ON war_room_drafts;")
    await conn.execute("DROP FUNCTION IF EXISTS notify_war_room_event();")
    await conn.execute("DROP FUNCTION IF EXISTS war_room_drafts_updated_at();")
    await conn.execute("DROP TABLE IF EXISTS war_room_costs;")
    await conn.execute("DROP TABLE IF EXISTS war_room_missed_runs;")
    await conn.execute("DROP TABLE IF EXISTS war_room_rejections;")
    await conn.execute("DROP TABLE IF EXISTS war_room_leads;")
    await conn.execute("DROP TABLE IF EXISTS war_room_metrics;")
    await conn.execute("DROP TABLE IF EXISTS war_room_posts;")
    await conn.execute("DROP TABLE IF EXISTS war_room_drafts;")
    logger.info("migration 112: rolled back")
