-- 156_mata_garuda_tag_intel_finding.sql
--
-- Sprint 5 — wire intel_radar.py → asset_provenance via DB function.
-- Reference: docs/sprint5/intel-radar-wiring.md
-- Rollback:  docs/sprint5/rollback-migration-156.md
--
-- Multi-LLM review: 4 rounds DeepSeek+Gemini hostile review (R1..R4).
-- Brainstorm artifacts: /tmp/sprint5-brainstorm/{00,01,02,03}_*.md
--
-- WHAT THIS MIGRATION DOES:
--   1. Creates mata_garuda schema (idempotent).
--   2. Drops the old 5-arg signature (R4 idempotency fix — needed because
--      CREATE OR REPLACE FUNCTION with a different parameter list creates
--      a NEW overload, causing "function is not unique" ambiguity errors
--      on calls that omit defaults).
--   3. Defines mata_garuda.tag_intel_finding(BIGINT, TEXT, TEXT, TEXT,
--      BOOLEAN, SMALLINT) — central UPSERT helper for intel_finding rows
--      in asset_provenance. Both monorepo callers AND the Pro-local
--      intel_radar.py cron call this function.
--
-- DESIGN DECISIONS (settled across R1..R4 multi-LLM review):
--
-- R1 — NATO Admiralty defaults:
--   * reliability='F' (cannot be judged) for raw OSINT web search.
--     Brave Search filters domains but no per-domain track record.
--   * credibility=5 (cannot be judged) for new sightings;
--     credibility=4 (doubtful) on corroboration (re-sighting same URL).
--   * Optional p_credibility_override allows ground-truth callers to
--     inject grades 1..6. On INSERT, override applies exactly. On
--     UPDATE, LEAST() ensures override never WORSENS an existing grade.
--
-- R1 — Tier-based TTL:
--   L1=90d (core regulatory), L2=30d (adjacent market), L3=7d (lateral macro).
--   TTL is computed from `original_tier` (set on first INSERT, immutable).
--   Re-tag via different tier does NOT shorten TTL (R3 fix).
--
-- R2 — Defensive fallbacks:
--   * source_domain → COALESCE(NULLIF(p_source_domain, ''), 'unknown').
--     Required because asset_provenance.source is NOT NULL but Python
--     urlparse() can yield empty netloc on non-standard URLs.
--   * GRANT EXECUTE TO backend_rag_v2 only (REVOKE FROM PUBLIC).
--
-- R3 — Metadata semantics:
--   * valid_until = GREATEST(existing, new) — TTL never shrinks.
--   * metadata = COALESCE(existing, '{}'::jsonb) || jsonb_build_object(...)
--     — additive merge preserves unknown keys from external producers
--     (R4 fix: COALESCE defends against rare NULL metadata).
--   * first_tagged_at preserved via COALESCE.
--   * corroborating_queries: latest 100 distinct (R4 ordering fix).
--
-- R4 — Race & robustness:
--   * original_tier read INSIDE DO UPDATE clause (no race window).
--   * jsonb_typeof guard on corroborating_queries (defends against
--     external producers writing non-array metadata).
--   * COALESCE on metadata (defends against NULL).
--
-- R4 — Failure semantics (best-effort, NOT atomic):
--   intel_radar.py wraps tag_intel_finding call in try/except. Failure
--   logs WARNING and proceeds — finding INSERT is already committed
--   in a separate statement. Pattern copied from WR2 _tag_provenance_safe.

-- Idempotency: CREATE SCHEMA IF NOT EXISTS + DROP FUNCTION IF EXISTS +
-- CREATE OR REPLACE FUNCTION. Re-running this migration is a no-op.

CREATE SCHEMA IF NOT EXISTS mata_garuda;

-- R4 fix: drop the previously-experimental 5-arg signature if it exists.
-- This is the only signature that could conflict with our new 6-arg
-- definition under default-arg ambiguity. Other variants (e.g., older
-- 7-arg drafts) were never deployed; safe to skip them.
DROP FUNCTION IF EXISTS mata_garuda.tag_intel_finding(BIGINT, TEXT, TEXT, TEXT, BOOLEAN);
DROP FUNCTION IF EXISTS mata_garuda.tag_intel_finding(BIGINT, TEXT, TEXT, TEXT, BOOLEAN, SMALLINT);

CREATE OR REPLACE FUNCTION mata_garuda.tag_intel_finding(
    p_finding_id UUID,
    p_source_domain TEXT,
    p_query TEXT,
    p_tier TEXT,
    p_corroboration BOOLEAN DEFAULT FALSE,
    p_credibility_override SMALLINT DEFAULT NULL
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_now            TIMESTAMPTZ := NOW();
    v_source         TEXT := COALESCE(NULLIF(p_source_domain, ''), 'unknown');
    v_query          TEXT := COALESCE(NULLIF(p_query, ''), 'unknown');
    v_tier           TEXT := COALESCE(NULLIF(p_tier, ''), 'L2');
    v_default_credibility SMALLINT;
    v_credibility    SMALLINT;
    v_provenance_id  BIGINT;
    v_ttl_days       INT;
    v_valid_until    TIMESTAMPTZ;
BEGIN
    -- Validate tier (warn + default rather than RAISE EXCEPTION —
    -- intel_radar's caller is fail-soft, propagating a hard error
    -- would defeat the best-effort tagging contract).
    IF v_tier NOT IN ('L1', 'L2', 'L3') THEN
        RAISE WARNING 'tag_intel_finding: invalid tier %, defaulting to L2', v_tier;
        v_tier := 'L2';
    END IF;

    -- Default credibility logic (R1):
    --   * 5 (cannot judge) for new sighting
    --   * 4 (doubtful) on corroboration
    v_default_credibility := CASE WHEN p_corroboration THEN 4 ELSE 5 END;

    -- Override resolution (R1 + R4):
    --   * On INSERT: override (if valid) applies EXACTLY, even worse than
    --     default — caller asserts ground-truth grade.
    --   * On UPDATE: LEAST() in DO UPDATE prevents regressions.
    -- The INSERT VALUES uses v_credibility directly. The DO UPDATE uses
    -- LEAST(asset_provenance.credibility, EXCLUDED.credibility).
    IF p_credibility_override IS NOT NULL THEN
        IF p_credibility_override BETWEEN 1 AND 6 THEN
            v_credibility := p_credibility_override;
        ELSE
            RAISE WARNING 'tag_intel_finding: invalid credibility_override %, ignoring',
                          p_credibility_override;
            v_credibility := v_default_credibility;
        END IF;
    ELSE
        v_credibility := v_default_credibility;
    END IF;

    -- TTL for INSERT branch is computed from v_tier (= original_tier on
    -- first insert). On UPDATE branch, TTL is recomputed inside the
    -- DO UPDATE clause from the persisted original_tier (R4 race fix).
    v_ttl_days := CASE v_tier
        WHEN 'L1' THEN 90
        WHEN 'L2' THEN 30
        WHEN 'L3' THEN 7
        ELSE 30
    END;

    v_valid_until := v_now + (v_ttl_days || ' days')::INTERVAL;

    INSERT INTO asset_provenance (
        asset_kind, asset_id, source, reliability, credibility,
        owner, invalidation_mode, valid_until,
        invalidation_event_topic, tlp, metadata,
        created_at, updated_at
    ) VALUES (
        'intel_finding',
        p_finding_id::TEXT,
        v_source,
        'F',  -- R1 verdict
        v_credibility,
        'intel_radar',
        'auto',
        v_valid_until,
        -- NULL: invalidation is purely time-driven via TTL sweep on Pro
        -- (com.matagaruda.invalidation-sweep at 04:13 WITA). No event-
        -- driven invalidation channel for intel_finding (verified in
        -- scripts/mata_garuda_invalidation_sweep.py docstring — the
        -- event-driven sweep is deferred to a future cell adapter).
        NULL,
        'amber',  -- internal-team-only intelligence
        jsonb_build_object(
            'original_tier', v_tier,
            'latest_tier', v_tier,
            'first_tagged_at', to_jsonb(v_now),
            'last_tagged_at', to_jsonb(v_now),
            'source_domain', v_source,
            'corroborating_queries', jsonb_build_array(v_query),
            'corroboration_count', 1
        ),
        v_now,  -- explicit (DEFAULT NOW() exists; explicit for symmetry)
        v_now
    )
    ON CONFLICT (asset_kind, asset_id) DO UPDATE SET
        -- TTL never shrinks. Recompute the candidate TTL from the
        -- persisted original_tier (NOT from p_tier — caller might be
        -- corroborating an L1 finding via an L3 query). The GREATEST
        -- vs the existing valid_until is final defense.
        valid_until = GREATEST(
            asset_provenance.valid_until,
            v_now + (
                CASE COALESCE(asset_provenance.metadata->>'original_tier', v_tier)
                    WHEN 'L1' THEN 90
                    WHEN 'L2' THEN 30
                    WHEN 'L3' THEN 7
                    ELSE 30
                END || ' days'
            )::INTERVAL
        ),
        -- Credibility never worsens.
        credibility = LEAST(asset_provenance.credibility, EXCLUDED.credibility),
        -- ADDITIVE metadata merge — `||` preserves unknown keys.
        -- COALESCE defends against the unlikely case of NULL metadata
        -- (mig 154 default is '{}'::jsonb, but a future migration or
        -- direct UPDATE could set NULL).
        metadata = COALESCE(asset_provenance.metadata, '{}'::jsonb) || jsonb_build_object(
            -- original_tier preserved if already set (immutable).
            'original_tier', COALESCE(
                asset_provenance.metadata->>'original_tier',
                v_tier
            ),
            'latest_tier', v_tier,
            'first_tagged_at', COALESCE(
                asset_provenance.metadata->'first_tagged_at',
                to_jsonb(v_now)
            ),
            'last_tagged_at', to_jsonb(v_now),
            'source_domain', v_source,
            -- corroborating_queries: keep latest 100 DISTINCT queries
            -- (FIFO by recency — most recent occurrence wins per query).
            -- jsonb_typeof guard defends against rogue producers that
            -- might have set this field to a non-array.
            'corroborating_queries', (
                SELECT COALESCE(jsonb_agg(q ORDER BY ord DESC), '[]'::jsonb)
                FROM (
                    SELECT q, MAX(ord) AS ord
                    FROM (
                        SELECT q, ord
                        FROM jsonb_array_elements_text(
                            CASE
                                WHEN jsonb_typeof(asset_provenance.metadata->'corroborating_queries') = 'array'
                                    THEN asset_provenance.metadata->'corroborating_queries'
                                ELSE '[]'::jsonb
                            END
                            || jsonb_build_array(v_query)
                        ) WITH ORDINALITY AS arr(q, ord)
                    ) flat
                    GROUP BY q
                    ORDER BY MAX(ord) DESC
                    LIMIT 100
                ) capped
            ),
            'corroboration_count', COALESCE(
                (asset_provenance.metadata->>'corroboration_count')::INT,
                0
            ) + 1
        ),
        updated_at = v_now
    RETURNING id INTO v_provenance_id;

    RETURN v_provenance_id;
END;
$$;

COMMENT ON FUNCTION mata_garuda.tag_intel_finding(UUID, TEXT, TEXT, TEXT, BOOLEAN, SMALLINT) IS
    'Sprint 5 — central UPSERT for intel_finding rows in asset_provenance. '
    'Tier-based TTL computed from immutable original_tier (never shortens). '
    'NATO Admiralty F default reliability for raw OSINT. p_credibility_override '
    'allows ground-truth injection (LEAST() prevents regression on re-tag). '
    'Preserves first_tagged_at, accumulates corroborating_queries (capped 100 '
    'distinct, recency-ordered). Returns provenance_id. Called by '
    '~/scripts/cron-agent-python/intel_radar.py and any future intel producer.';

REVOKE EXECUTE ON FUNCTION mata_garuda.tag_intel_finding(UUID, TEXT, TEXT, TEXT, BOOLEAN, SMALLINT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mata_garuda.tag_intel_finding(UUID, TEXT, TEXT, TEXT, BOOLEAN, SMALLINT) TO backend_rag_v2;

-- === ROLLBACK ===
DROP FUNCTION IF EXISTS mata_garuda.tag_intel_finding(UUID, TEXT, TEXT, TEXT, BOOLEAN, SMALLINT);
-- Schema preserved for idempotent re-runs. Drop manually if no other
-- mata_garuda objects remain (verify with `\dn` in psql).
