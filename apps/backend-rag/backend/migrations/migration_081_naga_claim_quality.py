"""
Migration 081: Naga Claims Quality Enhancement

Adds columns for quality scoring, lifecycle management, and dedup support:

1. quality_score    — composite score (freshness × source_reliability × verification)
2. claim_status     — lifecycle: active / expired / duplicate / conflicting / superseded
3. expired_at       — timestamp when claim was marked expired
4. duplicate_of_id  — FK to the canonical claim this duplicates
5. similarity_hash  — trigram-based hash for fast fuzzy dedup lookup

Also populates expires_at for all existing claims (90 days from valid_as_of).
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Add quality enhancement columns to naga_claims."""

    # --- New columns on naga_claims ---
    await conn.execute("""
        ALTER TABLE naga_claims
        ADD COLUMN IF NOT EXISTS quality_score FLOAT,
        ADD COLUMN IF NOT EXISTS claim_status VARCHAR(20) DEFAULT 'active',
        ADD COLUMN IF NOT EXISTS expired_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS duplicate_of_id UUID REFERENCES naga_claims(id),
        ADD COLUMN IF NOT EXISTS similarity_hash VARCHAR(64);
    """)

    # --- Indexes ---
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_quality
        ON naga_claims (quality_score DESC NULLS LAST);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_status
        ON naga_claims (claim_status);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_duplicate_of
        ON naga_claims (duplicate_of_id)
        WHERE duplicate_of_id IS NOT NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_similarity
        ON naga_claims (similarity_hash)
        WHERE similarity_hash IS NOT NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_claims_expires
        ON naga_claims (expires_at)
        WHERE expires_at IS NOT NULL;
    """)

    # --- Backfill: set expires_at for existing claims that lack it ---
    # Visa/immigration domain: 30 days, everything else: 90 days
    updated = await conn.execute("""
        UPDATE naga_claims
        SET expires_at = CASE
            WHEN domain IN ('visa', 'immigration') THEN valid_as_of + INTERVAL '30 days'
            ELSE valid_as_of + INTERVAL '90 days'
        END
        WHERE expires_at IS NULL AND valid_as_of IS NOT NULL;
    """)
    logger.info("Migration 081: backfilled expires_at for existing claims: %s", updated)

    # --- Backfill: set claim_status = 'active' where NULL ---
    await conn.execute("""
        UPDATE naga_claims
        SET claim_status = 'active'
        WHERE claim_status IS NULL;
    """)

    logger.info("Migration 081: Naga claims quality enhancement complete (5 columns, 5 indexes)")


async def rollback(conn) -> None:
    """Remove quality enhancement columns."""
    await conn.execute("DROP INDEX IF EXISTS idx_naga_claims_expires;")
    await conn.execute("DROP INDEX IF EXISTS idx_naga_claims_similarity;")
    await conn.execute("DROP INDEX IF EXISTS idx_naga_claims_duplicate_of;")
    await conn.execute("DROP INDEX IF EXISTS idx_naga_claims_status;")
    await conn.execute("DROP INDEX IF EXISTS idx_naga_claims_quality;")

    await conn.execute("""
        ALTER TABLE naga_claims
        DROP COLUMN IF EXISTS similarity_hash,
        DROP COLUMN IF EXISTS duplicate_of_id,
        DROP COLUMN IF EXISTS expired_at,
        DROP COLUMN IF EXISTS claim_status,
        DROP COLUMN IF EXISTS quality_score;
    """)

    logger.info("Migration 081: Naga claims quality enhancement rolled back")
