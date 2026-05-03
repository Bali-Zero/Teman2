"""
Migration 079: Naga Agentic Research Engine — Core Tables

Creates the 5 foundational tables for the Naga multi-model research system:

1. naga_sessions      — research sessions with LangGraph thread tracking
2. naga_sources       — fetched sources with credibility scoring
3. naga_claims        — atomic verified claims with human review gate
4. naga_claim_evidence — claim<->source join (replaces source_ids UUID[])
5. naga_claim_transitions — claim supersession (many-to-many)

Key design decisions (reviewed by Gemini 2.5 Pro, GPT-5.4, NB-1):
- evidence_map_uri TEXT instead of JSONB to prevent TOAST bloat on 2GB Fly.io PG
- Join tables instead of arrays for referential integrity
- review_status mandatory human review gate on claims
- langgraph_thread_id for LangGraph checkpoint/resume support
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Create all 5 Naga tables with indexes."""

    # -----------------------------------------------------------------------
    # 1. naga_sessions
    # -----------------------------------------------------------------------
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_sessions (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_session_id     UUID REFERENCES naga_sessions(id),
            query                 TEXT NOT NULL,
            tier                  VARCHAR(20) NOT NULL,
            domain                VARCHAR(20),
            mode                  VARCHAR(20) DEFAULT 'oneshot',
            channel               VARCHAR(30),
            ttl_seconds           INT,
            trusted_mode          BOOL DEFAULT FALSE,
            status                VARCHAR(20) DEFAULT 'running',
            -- Metrics
            duration_ms           INT,
            iterations            INT DEFAULT 0,
            search_calls          INT DEFAULT 0,
            sources_found         INT DEFAULT 0,
            claims_extracted      INT DEFAULT 0,
            avg_confidence        FLOAT,
            -- Output
            report_markdown       TEXT,
            report_drive_path     TEXT,
            action_items          JSONB DEFAULT '[]'::jsonb,
            -- State (Pointer State Pattern — no JSONB blob for evidence_map)
            evidence_map_uri      TEXT,
            sub_questions         JSONB,
            url_history           TEXT[],
            langgraph_thread_id   TEXT,
            -- Timestamps
            created_at            TIMESTAMPTZ DEFAULT NOW(),
            completed_at          TIMESTAMPTZ
        );
    """)

    # -----------------------------------------------------------------------
    # 2. naga_sources
    # -----------------------------------------------------------------------
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_sources (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id            UUID NOT NULL REFERENCES naga_sessions(id) ON DELETE CASCADE,
            url                   TEXT NOT NULL,
            title                 TEXT,
            domain                VARCHAR(255),
            source_type           VARCHAR(20),
            credibility_score     FLOAT,
            freshness_date        DATE,
            content_hash          VARCHAR(64),
            content_archived      BOOL DEFAULT FALSE,
            drive_archive_path    TEXT,
            fetched_at            TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(url, session_id)
        );
    """)

    # -----------------------------------------------------------------------
    # 3. naga_claims
    # -----------------------------------------------------------------------
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_claims (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id            UUID NOT NULL REFERENCES naga_sessions(id) ON DELETE CASCADE,
            claim_text            TEXT NOT NULL,
            claim_key             VARCHAR(255),
            domain                VARCHAR(20),
            topic_tags            TEXT[],
            jurisdiction          VARCHAR(50),
            -- Verification
            verification_level    VARCHAR(20),
            confidence            FLOAT,
            cross_ref_count       INT DEFAULT 0,
            -- Human review gate (CRITICAL)
            review_status         VARCHAR(20) DEFAULT 'auto_extracted',
            -- Temporal validity
            valid_as_of           DATE,
            expires_at            DATE,
            resolution_hint       TEXT,
            -- Timestamps
            created_at            TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # -----------------------------------------------------------------------
    # 4. naga_claim_evidence (join table — replaces source_ids UUID[])
    # -----------------------------------------------------------------------
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_claim_evidence (
            id                    SERIAL PRIMARY KEY,
            claim_id              UUID NOT NULL REFERENCES naga_claims(id) ON DELETE CASCADE,
            source_id             UUID NOT NULL REFERENCES naga_sources(id) ON DELETE CASCADE,
            relation              VARCHAR(20) NOT NULL,
            extraction_method     VARCHAR(30),
            source_span_hint      TEXT,
            created_at            TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(claim_id, source_id, relation)
        );
    """)

    # -----------------------------------------------------------------------
    # 5. naga_claim_transitions (many-to-many supersession)
    # -----------------------------------------------------------------------
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_claim_transitions (
            id                    SERIAL PRIMARY KEY,
            from_claim_id         UUID NOT NULL REFERENCES naga_claims(id) ON DELETE CASCADE,
            to_claim_id           UUID NOT NULL REFERENCES naga_claims(id) ON DELETE CASCADE,
            transition_type       VARCHAR(30) NOT NULL,
            reason                TEXT,
            detected_by           VARCHAR(30),
            created_at            TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(from_claim_id, to_claim_id, transition_type)
        );
    """)

    # -----------------------------------------------------------------------
    # Indexes
    # -----------------------------------------------------------------------

    # naga_sessions
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_sessions_parent
        ON naga_sessions (parent_session_id)
        WHERE parent_session_id IS NOT NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_sessions_status
        ON naga_sessions (status);
    """)

    # naga_sources
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_sources_url
        ON naga_sources (url);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_sources_hash
        ON naga_sources (content_hash)
        WHERE content_hash IS NOT NULL;
    """)

    # naga_claims
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_domain
        ON naga_claims (domain);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_topic
        ON naga_claims USING GIN (topic_tags);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_confidence
        ON naga_claims (confidence DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_valid
        ON naga_claims (valid_as_of DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_verification
        ON naga_claims (verification_level);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_review
        ON naga_claims (review_status);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_key
        ON naga_claims (claim_key)
        WHERE claim_key IS NOT NULL;
    """)

    # naga_claim_evidence
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claim_evidence_claim
        ON naga_claim_evidence (claim_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claim_evidence_source
        ON naga_claim_evidence (source_id);
    """)

    # naga_claim_transitions
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claim_transitions_from
        ON naga_claim_transitions (from_claim_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claim_transitions_to
        ON naga_claim_transitions (to_claim_id);
    """)

    logger.info("Migration 079: Naga tables created (5 tables, 15 indexes)")


async def rollback(conn) -> None:
    """Drop all Naga tables in reverse dependency order."""
    await conn.execute("DROP TABLE IF EXISTS naga_claim_transitions CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS naga_claim_evidence CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS naga_claims CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS naga_sources CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS naga_sessions CASCADE;")
    logger.info("Migration 079: Naga tables dropped (5 tables)")
